import json
import os
from datetime import datetime, timedelta
import time
from spade.agent import Agent
from spade.behaviour import CyclicBehaviour
from spade.behaviour import OneShotBehaviour

from spade.message import Message
from spade.template import Template
from spade.behaviour import PeriodicBehaviour

import json
from datetime import datetime
import asyncio

HISTORY_DEPTH = 1

class SpatialAnalyzer(Agent):
    def __init__(self):
        super().__init__(f"spacial-analyzer@xmpp_server", os.getenv("PASSWORD"))
        self.data = {
            "room_part": {
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
                TemperatureAnalysis(),
                HumidityAnalysis()
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
            room_part_name = event["room_part_name"]
            history = self.agent.data["room_part"]["history"].get(room_part_name, [])

            for rule in self.rules:
                result = rule.analyze(room_part_name, history)
                if result:
                    await self.agent.events.put(result)

        async def handle_effector_request(self, event):
            room_part_name = event["room_part_name"]
            effector = event["effector"]
            turn_on = event.get("turn_on")
            reason = event.get("reason", "unknown")

            conversation = EffectorConversation(
                room_part_name=room_part_name,
                effector=effector,
                turn_on=turn_on,
                reason=reason
            )

            self.agent.add_behaviour(conversation)

            print(
                f"[Analyzer] EffectorConversation started "
                f"(room_part={room_part_name}, effector={effector}, reason={reason})"
            )



    async def save_profile(self, message_data):
        for room_part_name, sensors in message_data.items():
            profile = {
                "timestamp": datetime.utcnow().isoformat(),
                "sensors": sensors
            }
            self.data["room_part"]["current"][room_part_name] = profile
            self.data["room_part"]["history"].setdefault(room_part_name, []).append(profile)
            await self.events.put({
                "type": "PROFILE_UPDATED",
                "room_part_name": room_part_name
                })

    async def setup(self) -> None:
        self.add_behaviour(self.AwaitProfilesBehavoiur())
        self.add_behaviour(self.AnalyzeProfiles())
        # report_behaviour = PeriodicReportBehaviour(period=21600)
        report_behaviour = PeriodicReportBehaviour(period=10)
        self.add_behaviour(report_behaviour)

class EffectorConversation(OneShotBehaviour):

    def __init__(self, room_part_name, effector, turn_on, reason):
        super().__init__()
        self.room_part_name = room_part_name
        self.effector = effector
        self.turn_on = turn_on
        self.reason = reason

        self.effector_jid = f"effector-{effector}-{room_part_name}@xmpp_server"
        self.farmer_jid = "farmer@xmpp_server"

    async def run(self):
        await self.send_request()

        reply = await self.wait_for_reply(timeout=10)

        if not reply:
            await self.inform_farmer("NO_RESPONSE")
            return

        perf = reply.get_metadata("performative")
        print(f"[Answer] {reply}")
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
        print(f"[Final] {perf}")
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
            "room_part_name": self.room_part_name,
            "turn_on": self.turn_on,
        })

        await self.send(msg)

        print(
            f"[Conversation {self.room_part_name}] REQUEST sent → {self.effector} "
        )

    async def wait_for_reply(self, timeout):
        deadline = time.monotonic() + timeout

        while time.monotonic() < deadline:
            msg = await self.receive(timeout=1)

            if not msg:
                continue

            if str(msg.sender) != self.effector_jid:
                continue

            perf = msg.get_metadata("performative")
            if perf not in ("agree", "refuse", "done", "failure"):
                continue

            return msg

        return None

    

    async def inform_farmer(self, status, details=None):
        msg = Message(to=self.farmer_jid)
        msg.set_metadata("performative", "inform")

        msg.body = json.dumps({
            "room_part_name": self.room_part_name,
            "effector": self.effector,
            "status": status,
            "reason": self.reason,
            "details": details,
            "timestamp": datetime.utcnow().isoformat()
        })

        await self.send(msg)

        print(
            f"[Conversation] INFORM farmer "
            f"(room_part={self.room_part_name}, status={status})"
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

        history = self.agent.data["room_part"]["history"]

        for room_part_name, profiles in history.items():
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
            humidities   = [p["sensors"]["humidity"] for p in recent]


            report[room_part_name] = {
                "temperature": stats(temps),
                "humidity": stats(humidities),
                "samples": len(recent),
                "from": window_start.isoformat(),
                "to": now.isoformat(),
            }

        return report



class AnalysisRule:
    name = "BASE"
    def analyze(self, room_part, history):
        raise NotImplementedError

class TemperatureAnalysis(AnalysisRule):
    name = "TEMPERATURE_HIGH"

    def analyze(self, room_part, history):
        if len(history) < HISTORY_DEPTH:
            return None

        temps = [
            p["sensors"]["temperature"]
            for p in history[-HISTORY_DEPTH:]
        ]

        if all(t > 21.0 for t in temps):
            return {
                "type": "EFFECTOR_REQUEST",
                "room_part_name": room_part,
                "effector": "air_conditioner",
                "reason": "Temperature too high",
                "turn_on": "True",
                "details": f"Temperature too high:  {temps[-1]} deg Celsius"
            }
        return None

class HumidityAnalysis(AnalysisRule):
    name = "HUMIDITY_HIGH"

    def analyze(self, room_part, history):
        if len(history) < HISTORY_DEPTH:
            return None

        temps = [
            p["sensors"]["humidity"]
            for p in history[-HISTORY_DEPTH:]
        ]

        if all(t > 53.0 for t in temps):
            return {
                "type": "EFFECTOR_REQUEST",
                "room_part_name": room_part,
                "effector": "air_conditioner",
                "turn_on": "False",
                "reason": f"Humidity too high: {temps[-1]}"
            }

        return None