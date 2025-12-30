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

class SpatialAnalyzer(Agent):
    def __init__(self):
        super().__init__(f"spatial_analyzer@xmpp_server", os.getenv("PASSWORD"))
        self.data = {
            "spatial_parts": {
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
                TemperatureAnalysis(),
                HumidityAnalysis(),
            ]
        
        async def run(self):
            event = await self.agent.events.get()
            event_type = event["type"]

            if event_type == "PROFILE_UPDATED":
                await self.handle_profile_update(event)

            elif event_type == "EFFECTOR_REQUEST":
                await self.handle_effector_request(event)


        async def handle_profile_update(self, event):
            room_part = event["room_part"]
            history = self.agent.data["room_parts"]["history"].get(room_part, [])

            for rule in self.rules:
                result = rule.analyze(room_part, history)
                if result:
                    await self.agent.events.put(result)

        async def handle_effector_request(self, event):
            room_part = event["room_part"]
            effector = event["effector"]
            action_param = event.get("action_param")
            reason = event.get("reason", "unknown")

            conversation = EffectorConversation(
                room_part=room_part,
                effector=effector,
                action=action_param,
                reason=reason
            )

            self.agent.add_behaviour(conversation)

            print(
                f"[Analyzer] EffectorConversation started "
                f"(cow={room_part}, effector={effector}, reason={reason})"
            )



    async def save_profile(self, message_data):
        for room_part, sensors in message_data.items():
            profile = {
                "timestamp": datetime.utcnow().isoformat(),
                "sensors": sensors
            }
            self.data["cows"]["current"][room_part] = profile
            self.data["cows"]["history"].setdefault(room_part, []).append(profile)
            await self.events.put({
                "type": "PROFILE_UPDATED",
                "room_part": room_part
                })

    async def setup(self) -> None:
        self.add_behaviour(self.AwaitProfilesBehavoiur())
        self.add_behaviour(self.AnalyzeProfiles())

class EffectorConversation(OneShotBehaviour):

    def __init__(self, room_part, effector, action, reason):
        super().__init__()
        self.room_part = room_part
        self.effector = effector
        self.action = action
        self.reason = reason

        self.effector_jid = f"effector-{effector}-{room_part}@xmpp_server"
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
            "room_part": self.room_part,
            "action": self.action,
            "reason": self.reason,
            "timestamp": datetime.utcnow().isoformat()
        })

        await self.send(msg)

        print(
            f"[Conversation] REQUEST sent → {self.effector} "
            f"(room part={self.room_part})"
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
            "room_part": self.room_part,
            "effector": self.effector,
            "status": status,
            "reason": self.reason,
            "details": details,
            "timestamp": datetime.utcnow().isoformat()
        })

        await self.send(msg)

        print(
            f"[Conversation] INFORM farmer "
            f"(cow={self.room_part}, status={status})"
        )



class AnalysisRule:
    name = "BASE"
    def analyze(self, room_part, history):
        raise NotImplementedError

class TemperatureAnalysis(AnalysisRule):
    name = "FEVER"

    def analyze(self, room_part, history):
        if len(history) < HISTORY_DEPTH:
            return None

        temps = [
            p["sensors"]["temperature"]
            for p in history[-HISTORY_DEPTH:]
        ]

        if all(t > 39.0 for t in temps):
            return {
                "type": "EFFECTOR_REQUEST",
                "room_part": room_part,
                "effector": "air_conditioner",
                "reason": "Temperature too high"
            }

        return None

class HumidityAnalysis(AnalysisRule):
    name = "FEVER"

    def analyze(self, room_part, history):
        if len(history) < HISTORY_DEPTH:
            return None

        temps = [
            p["sensors"]["humidity"]
            for p in history[-HISTORY_DEPTH:]
        ]

        if all(t > 39.0 for t in temps):
            return {
                "type": "EFFECTOR_REQUEST",
                "room_part": room_part,
                "effector": "fan",
                "reason": "Humidity too high"
            }

        return None