import json
import os
from datetime import datetime, timedelta
import time
from spade.agent import Agent
from spade.behaviour import CyclicBehaviour
from spade.behaviour import OneShotBehaviour
import uuid
from spade.message import Message
from spade.template import Template
from spade.behaviour import PeriodicBehaviour

import json
from datetime import datetime
import asyncio

HISTORY_DEPTH = 1

class CowsAnalyzer(Agent):
    def __init__(self):
        super().__init__(f"cows-analyzer@xmpp_server", os.getenv("PASSWORD"))
        self.data = {
            "cows": {
                "current": {},
                "history": {}
            }
        }
        self.events = asyncio.Queue()

    class AwaitProfilesBehavoiur(CyclicBehaviour):
        async def run(self):
            message = await self.receive(timeout=10)
            if not message:
                return
            
            sender = str(message.sender)

            if not sender.startswith("aggregator-"):
                return

            if message.get_metadata("performative") != "inform":
                return

            message_data = json.loads(message.body)
            await self.agent.save_profile(message_data)

            # print(f"Message {message_data}")
        
    class AnalyzeProfiles(CyclicBehaviour):
        async def on_start(self):
            self.rules = [
                FeverAnalysis(),
                OverheatingAnalysis(),
                StressAnalysis(),
                HungerAnalysis()
            ]
        
        async def run(self):
            event = await self.agent.events.get()
            event_type = event["type"]

            if event_type == "PROFILE_UPDATED":
                await self.handle_profile_update(event)
                return

            elif event_type == "EFFECTOR_REQUEST":
                await self.handle_effector_request(event)
                return


        async def handle_profile_update(self, event):
            cow_name = event["cow_name"]
            history = self.agent.data["cows"]["history"].get(cow_name, [])

            for rule in self.rules:
                result = rule.analyze(cow_name, history)
                if result:
                    await self.agent.events.put(result)

        async def handle_effector_request(self, event):
            cow_name = event["cow_name"]
            effector = event["effector"]
            turn_on = event.get("turn_on")
            reason = event.get("reason", "unknown")

            conversation = EffectorConversation(
                cow_name=cow_name,
                effector=effector,
                turn_on=turn_on,
                reason=reason
            )


            t_agree = Template(sender=conversation.effector_jid)
            t_agree.set_metadata("conversation-id", conversation.conversation_id)
            t_agree.set_metadata("performative", "agree")

            t_refuse = Template(sender=conversation.effector_jid)
            t_refuse.set_metadata("conversation-id", conversation.conversation_id)
            t_refuse.set_metadata("performative", "refuse")

            t_done = Template(sender=conversation.effector_jid)
            t_done.set_metadata("conversation-id", conversation.conversation_id)
            t_done.set_metadata("performative", "done")

            t_failure = Template(sender=conversation.effector_jid)
            t_failure.set_metadata("conversation-id", conversation.conversation_id)
            t_failure.set_metadata("performative", "failure")

            template = t_agree | t_refuse | t_done | t_failure

            self.agent.add_behaviour(conversation, template)


            print(
                f"[Analyzer] EffectorConversation started "
                f"(cow={cow_name}, effector={effector}, reason={reason})"
            )



    async def save_profile(self, message_data):
        for cow_name, sensors in message_data.items():
            profile = {
                "timestamp": datetime.utcnow().isoformat(),
                "sensors": sensors
            }
            self.data["cows"]["current"][cow_name] = profile
            self.data["cows"]["history"].setdefault(cow_name, []).append(profile)
            await self.events.put({
                "type": "PROFILE_UPDATED",
                "cow_name": cow_name
                })

    async def setup(self) -> None:
        template = Template()
        # template.sender = "aggregator-*@xmpp_server"
        template.set_metadata("performative", "inform")

        self.add_behaviour(self.AwaitProfilesBehavoiur(), template)
        self.add_behaviour(self.AnalyzeProfiles())
        # report_behaviour = PeriodicReportBehaviour(period=21600)
        report_behaviour = PeriodicReportBehaviour(period=10)
        self.add_behaviour(report_behaviour)

class EffectorConversation(OneShotBehaviour):

    def __init__(self, cow_name, effector, turn_on, reason):
        super().__init__()

        self.cow_name = cow_name
        self.effector = effector
        self.turn_on = turn_on
        self.reason = reason

        self.conversation_id = str(uuid.uuid4())

        self.effector_jid = f"effector-{effector}-{cow_name}@xmpp_server"
        self.farmer_jid = "farmer@xmpp_server"

    async def run(self):

        await self.send_request()

        reply = await self.receive(timeout=10)

        if not reply:
            await self.inform_farmer("NO_RESPONSE")
            return

        perf = reply.get_metadata("performative")

        if perf == "refuse":
            await self.inform_farmer("REFUSED")
            return

        if perf != "agree":
            await self.inform_farmer("UNEXPECTED_REPLY", perf)
            return

        final = await self.receive(timeout=20)

        if not final:
            await self.inform_farmer("NO_FINAL_RESPONSE")
            return

        final_perf = final.get_metadata("performative")

        if final_perf == "failure":
            await self.inform_farmer("FAILURE", final.body)

        elif final_perf == "done":
            await self.inform_farmer("SUCCESS", final.body)

        else:
            await self.inform_farmer("UNKNOWN_FINAL", final_perf)

    def get_template(self):
        template = Template()
        template.sender = self.effector_jid
        template.set_metadata("conversation-id", self.conversation_id)
        return template

    async def send_request(self):
        msg = Message(to=self.effector_jid)
        msg.set_metadata("performative", "request")
        msg.set_metadata("conversation-id", self.conversation_id)

        msg.body = json.dumps({
            "cow_name": self.cow_name,
            "turn_on": self.turn_on,
            "reason": self.reason,
            "timestamp": datetime.utcnow().isoformat()
        })

        await self.send(msg)

        print(
            f"[Conversation {self.conversation_id}] REQUEST → {self.effector}"
        )


    async def inform_farmer(self, status, details=None):
        msg = Message(to=self.farmer_jid)
        msg.set_metadata("performative", "inform")

        msg.body = json.dumps({
            "cow_name": self.cow_name,
            "effector": self.effector,
            "status": status,
            "reason": self.reason,
            "details": details,
            "conversation_id": self.conversation_id,
            "timestamp": datetime.utcnow().isoformat()
        })

        await self.send(msg)

        print(
            f"[Conversation {self.conversation_id}] INFORM farmer ({status})"
        )


class PeriodicReportBehaviour(PeriodicBehaviour):

    async def run(self):
        report = self.build_report()

        msg = Message(to="farmer@xmpp_server")
        msg.set_metadata("performative", "inform")

        msg.body = json.dumps({
            "type": "PERIODIC_REPORT",
            "timestamp": datetime.utcnow().isoformat(),
            "report": report
        })

        await self.send(msg)

        print("[Report] Periodic report sent to farmer")
        print(f"[Report] {report}")

    def build_report(self):
        report = {}

        now = datetime.utcnow()
        window_start = now - timedelta(hours=6)

        history = self.agent.data["cows"]["history"]

        for cow_name, profiles in history.items():
            recent = [
                p for p in profiles
                if datetime.fromisoformat(p["timestamp"]) >= window_start
            ]

            if not recent:
                continue

            def stats(values):
                return {
                    "last": values[-1],
                    "avg": sum(values) / len(values),
                    "min": min(values),
                    "max": max(values),
                }

            temps = [p["sensors"]["temperature"] for p in recent]
            phs   = [p["sensors"]["pH"] for p in recent]
            acts  = [p["sensors"]["activity"] for p in recent]
            pulses = [p["sensors"]["pulse"] for p in recent]

            report[cow_name] = {
                "temperature": stats(temps),
                "pH": stats(phs),
                "activity": stats(acts),
                "pulse": stats(pulses),
                "samples": len(recent),
                "from": window_start.isoformat(),
                "to": now.isoformat(),
            }

        return report


class AnalysisRule:
    name = "BASE"
    def analyze(self, cow_name, history):
        raise NotImplementedError

class FeverAnalysis(AnalysisRule):
    name = "FEVER"

    def analyze(self, cow_name, history):
        if len(history) < HISTORY_DEPTH:
            return None

        temps = [
            p["sensors"]["temperature"]
            for p in history[-HISTORY_DEPTH:]
        ]

        if all(t > 40.0 for t in temps):
            return {
                "type": "EFFECTOR_REQUEST",
                "cow_name": cow_name,
                "effector": "sprinkler",
                "reason": "fever",
                "turn_on": "True",
                "details": f"Fever. Cow's temperature is {temps[-1]} deg Celsius."
            }

        return None

class OverheatingAnalysis(AnalysisRule):
    name = "OVERHEATING"

    def analyze(self, cow_name, history):
        if len(history) < HISTORY_DEPTH:
            return None

        temps = [
            p["sensors"]["temperature"]
            for p in history[-HISTORY_DEPTH:]
        ]

        if all(t > 39.0 for t in temps):
            return {
                "type": "EFFECTOR_REQUEST",
                "cow_name": cow_name,
                "effector": "fan",
                "reason": "overheating",
                "turn_on": "True",
                "details": f"Overheating. Cow's temperature is {temps[-1]} deg Celsius"
            }

        return None

class StressAnalysis(AnalysisRule):
    name = "STRESS"

    def analyze(self, cow_name, history):
        if len(history) < HISTORY_DEPTH:
            return None

        pulses = [
            p["sensors"]["pulse"]
            for p in history[-HISTORY_DEPTH:]
        ]

        activity = history[-1]["sensors"]["activity"]

        if sum(pulses) / len(pulses) > 90 and activity > 0.2:
            return {
                "type": "EFFECTOR_REQUEST",
                "cow_name": cow_name,
                "effector": "brush",
                "reason": "stress",
                "turn_on": "True",
                "details": f"Stress. Cow's pulse: {pulses[-1]} and activity: {activity} are high."
            }

        return None

class HungerAnalysis(AnalysisRule):
    name = "HUNGER"

    def analyze(self, cow_name, history):
        if len(history) < HISTORY_DEPTH:
            return None

        ph = history[-1]["sensors"]["pH"]
        activity = history[-1]["sensors"]["activity"]

        if ph < 6.0 and activity > 0.2:
            return {
                "type": "EFFECTOR_REQUEST",
                "cow_name": cow_name,
                "effector": "feeder",
                "reason": "hunger",
                "turn_on": "True",
                "details": f"The cow is probably hungry. Cow's ph: {ph} and activity: {activity} are low."
            }

        return None
