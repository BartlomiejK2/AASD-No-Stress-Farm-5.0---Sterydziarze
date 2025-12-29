import json
import os
from datetime import datetime

from spade.agent import Agent
from spade.behaviour import CyclicBehaviour
from spade.behaviour import OneShotBehaviour

from spade.message import Message
from spade.template import Template

import json
from datetime import datetime
import asyncio

HISTORY_DEPTH = 3

class CowsAnalyzer(Agent):
    def __init__(self):
        super().__init__(f"analyzer@xmpp_server", os.getenv("PASSWORD"))
        self.data = {
            "cows": {
                "current": {},
                "history": {}
            },
            "anomalies": {},
        }
        self.events = asyncio.Queue()

    class AwaitProfilesBehavoiur(CyclicBehaviour):
        async def run(self):
            message = await self.receive(timeout=10)
            if not message:
                return
            
            message_data = json.loads(message.body)
            await self.agent.save_profile(message_data)

            print(f"Message {message_data}")
        
    class AnalyzeProfiles(CyclicBehaviour):
        async def on_start(self):
            self.rules = [
                FeverAnalysis(),
                StressAnalysis(),
                HungerAnalysis()
            ]
        
        async def run(self):
            event = await self.agent.events.get()
            event_type = event["type"]

            if event_type == "PROFILE_UPDATED":
                await self.handle_profile_update(event)

            elif event_type == "EFFECTOR_REQUEST":
                await self.handle_effector_request(event)

            elif event_type == "EFFECTOR_DONE":
                await self.handle_effector_done(event)


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
            action_param = event.get("action_param")
            reason = event.get("reason", "unknown")

            conversation = EffectorConversation(
                cow_name=cow_name,
                effector=effector,
                action=action_param,
                reason=reason
            )

            self.agent.add_behaviour(conversation)

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
        self.add_behaviour(self.AwaitProfilesBehavoiur())
        self.add_behaviour(self.AnalyzeProfiles())

class EffectorConversation(OneShotBehaviour):

    def __init__(self, cow_name, effector, action, reason):
        super().__init__()
        self.cow_name = cow_name
        self.effector = effector
        self.action = action
        self.reason = reason

        self.effector_jid = f"effector-{effector}-{cow_name}@xmpp_server"
        self.farmer_jid = "farmer@xmpp_server"

    async def run(self):
        await self.send_request()

        reply = await self.wait_for_reply(timeout=10)

        if not reply:
            await self.inform_farmer("NO_RESPONSE")
            return

        perf = reply.get_metadata("performative")

        if perf == "refuse":
            await self.inform_farmer("REFUSED")
            return

        if perf != "agree":
            await self.inform_farmer("UNEXPECTED_REPLY", reply.body)
            return

        final = await self.wait_for_reply(timeout=20)

        if not final:
            await self.inform_farmer("NO_FINAL_RESPONSE")
            return

        final_perf = final.get_metadata("performative")

        if final_perf == "failure":
            await self.inform_farmer("FAILURE", final.body)

        elif final_perf in ("inform-done", "inform-result", "done"):
            await self.inform_farmer("SUCCESS", final.body)

        else:
            await self.inform_farmer("UNKNOWN_FINAL", final.body)


    async def send_request(self):
        msg = Message(to=self.effector_jid)
        msg.set_metadata("performative", "request")

        msg.body = json.dumps({
            "cow_name": self.cow_name,
            "action": self.action,
            "reason": self.reason,
            "timestamp": datetime.utcnow().isoformat()
        })

        await self.send(msg)

        print(
            f"[Conversation] REQUEST sent → {self.effector} "
            f"(cow={self.cow_name})"
        )


    async def wait_for_reply(self, timeout):
        msg = await self.receive(timeout=timeout)

        if not msg:
            return None

        if str(msg.sender) != self.effector_jid:
            return None

        return msg
    

    async def inform_farmer(self, status, details=None):
        msg = Message(to=self.farmer_jid)
        msg.set_metadata("performative", "inform")

        msg.body = json.dumps({
            "cow_name": self.cow_name,
            "effector": self.effector,
            "status": status,
            "reason": self.reason,
            "details": details,
            "timestamp": datetime.utcnow().isoformat()
        })

        await self.send(msg)

        print(
            f"[Conversation] INFORM farmer "
            f"(cow={self.cow_name}, status={status})"
        )



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

        if all(t > 39.0 for t in temps):
            return {
                "type": "EFFECTOR_REQUEST",
                "cow_name": cow_name,
                "effector": "sprinkler",
                "reason": "fever"
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

        if sum(pulses) / len(pulses) > 90 and activity > 200:
            return {
                "type": "EFFECTOR_REQUEST",
                "cow_name": cow_name,
                "effector": "brush",
                "reason": "stress"
            }

        return None

class HungerAnalysis(AnalysisRule):
    name = "HUNGER"

    def analyze(self, cow_name, history):
        if len(history) < HISTORY_DEPTH:
            return None

        ph = history[-1]["sensors"]["pH"]
        activity = history[-1]["sensors"]["activity"]

        if ph < 6.0 and activity < 200:
            return {
                "type": "EFFECTOR_REQUEST",
                "cow_name": cow_name,
                "effector": "feeder",
                "reason": "hunger"
            }

        return None
