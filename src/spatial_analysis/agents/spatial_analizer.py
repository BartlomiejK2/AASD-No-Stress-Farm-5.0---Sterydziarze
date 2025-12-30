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

class SpatialAnalyzer(Agent):
    def __init__(self):
        super().__init__(f"spacial-analyzer@xmpp_server", os.getenv("PASSWORD"))
        self.data = {
            "room_parts": {
                "current": {},
                "history": {}
            }
        }
        self.events = asyncio.Queue()
        self.profile_queue = asyncio.Queue()     # wiadomości od agregatorów
        self.effector_queue = asyncio.Queue() 
        self.conversations = {} 

    class MessageRouterBehaviour(CyclicBehaviour):
        async def run(self):
            msg = await self.receive(timeout=10)
            if not msg:
                return

            sender = str(msg.sender)
            perf = msg.get_metadata("performative")

            if sender.startswith("aggregator-") and perf == "inform":
                await self.agent.profile_queue.put(msg)
                return

            if perf in ("agree", "refuse", "done", "failure"):
                await self.agent.effector_queue.put(msg)
                return

            print("[Router] Ignored message:", msg)

    class ProfileConsumerBehaviour(CyclicBehaviour):
        async def run(self):
            msg = await self.agent.profile_queue.get()

            data = json.loads(msg.body)
            await self.agent.save_profile(data)


    async def save_profile(self, message_data):
        for room_part_name, sensors in message_data.items():
            profile = {
                "timestamp": datetime.utcnow().isoformat(),
                "sensors": sensors
            }
            self.data["room_parts"]["current"][room_part_name] = profile
            self.data["room_parts"]["history"].setdefault(room_part_name, []).append(profile)
            await self.events.put({
                "type": "PROFILE_UPDATED",
                "room_part_name": room_part_name
                })    
    
    class AnalyzeProfilesBehaviour(CyclicBehaviour):
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
            history = self.agent.data["room_parts"]["history"].get(room_part_name, [])

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


            template = Template()
            template.sender = conversation.effector_jid
            template.set_metadata("conversation-id", conversation.conversation_id)

            self.agent.add_behaviour(conversation, template)


            print(
                f"[Analyzer] EffectorConversation started "
                f"(room_part={room_part_name}, effector={effector}, reason={reason})"
            )

    class EffectorResponseHandler(CyclicBehaviour):
        async def run(self):
            msg = await self.agent.effector_queue.get()

            perf = msg.get_metadata("performative")
            cid = msg.get_metadata("conversation-id")

            if not cid:
                print("[EffectorHandler] No conversation-id, ignored")
                return

            conversation = self.agent.conversations.get(cid)
            if not conversation:
                print(f"[EffectorHandler] Unknown conversation {cid}")
                return

            print(
                f"[EffectorHandler] {perf.upper()} "
                f"(room_part={conversation['room_part_name']}, "
                f"effector={conversation['effector']})"
            )

            if perf == "agree":
                return

            if perf == "refuse":
                await self.inform_farmer(conversation, "REFUSED")
                self.finish(cid)
                return

            if perf == "done":
                await self.inform_farmer(conversation, "SUCCESS", msg.body)
                self.finish(cid)
                return

            if perf == "failure":
                await self.inform_farmer(conversation, "FAILURE", msg.body)
                self.finish(cid)
                return


        async def inform_farmer(self, conversation, status, details=None):
            msg = Message(to="farmer@xmpp_server")
            msg.set_metadata("performative", "inform")

            msg.body = json.dumps({
                "room_part_name": conversation["room_part_name"],
                "effector": conversation["effector"],
                "status": status,
                "reason": conversation["reason"],
                "details": details,
                "timestamp": datetime.utcnow().isoformat()
            })

            await self.send(msg)

            print(
                f"[Farmer] room_part={conversation['room_part_name']} "
                f"effector={conversation['effector']} "
                f"status={status}"
            )

    async def setup(self) -> None:
        self.add_behaviour(self.MessageRouterBehaviour())
        self.add_behaviour(self.ProfileConsumerBehaviour())
        self.add_behaviour(self.AnalyzeProfilesBehaviour())
        self.add_behaviour(self.EffectorResponseHandler())
        self.add_behaviour(PeriodicReportBehaviour(period=15))


class EffectorConversation(OneShotBehaviour):

    def __init__(self, room_part_name, effector, turn_on, reason):
        super().__init__()

        self.room_part_name = room_part_name
        self.effector = effector
        self.turn_on = turn_on
        self.reason = reason

        self.conversation_id = str(uuid.uuid4())

        self.effector_jid = f"effector-{effector}-{room_part_name}@xmpp_server"
        self.farmer_jid = "farmer@xmpp_server"

    async def run(self):
        self.agent.conversations[self.conversation_id] = {
            "room_part_name": self.room_part_name,
            "effector": self.effector,
            "turn_on": self.turn_on,
            "reason": self.reason,
            "started_at": datetime.utcnow().isoformat()
        }
        await self.send_request()



    async def send_request(self):
        msg = Message(to=self.effector_jid)
        msg.set_metadata("performative", "request")
        msg.set_metadata("conversation-id", self.conversation_id)

        msg.body = json.dumps({
            "room_part_name": self.room_part_name,
            "turn_on": self.turn_on,
            "reason": self.reason,
            "timestamp": datetime.utcnow().isoformat()
        })

        await self.send(msg)

        print(
            f"[Conversation {self.conversation_id}] REQUEST → {self.effector}"
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

        history = self.agent.data["room_parts"]["history"]

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