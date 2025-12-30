import json
import os
from random import uniform
from time import sleep

from spade.agent import Agent
from spade.behaviour import CyclicBehaviour, OneShotBehaviour
from spade.message import Message


class Effector(Agent):
    def __init__(self, type: str):
        self.cow_name = os.getenv("NAME")
        self.succes_rate = float(os.getenv("SUCCES_RATE"))
        self.sleep_time = float(os.getenv("SLEEP_TIME"))
        self.free = True
        self.value = None
        super().__init__(f"effector-{type}-{self.cow_name}@xmpp_server", os.getenv("PASSWORD"))

    class GetRequest(CyclicBehaviour):
        def __init__(self, callback, jid):
            super().__init__()
            self.callback = callback
            self.jid = jid

        async def run(self):
            message = await self.receive(timeout=10)

            if message:
                if message.get_metadata("performative") != "request":
                    return
                print(f"[{self.jid}]: Received request from {message.sender}")
                self.callback(message)
            else:
                print(f"[{self.jid}]: Did not received any request")

    class RefuseRequest(OneShotBehaviour):
        def __init__(self, message):
            super().__init__()
            self.message = message

        async def run(self):
            reply = Message(to=self.message.sender)
            reply.set_metadata("performative", "refuse")
            reply.set_metadata(
                "conversation-id",
                self.message.get_metadata("conversation-id")
            )
            await self.send(reply)


    class AcceptRequest(OneShotBehaviour):
        def __init__(self, message):
            super().__init__()
            self.message = message

        async def run(self):
            reply = Message(to=self.message.sender)
            reply.set_metadata("performative", "agree")
            reply.set_metadata(
                "conversation-id",
                self.message.get_metadata("conversation-id")
            )
            await self.send(reply)

    
    class FailureInform(OneShotBehaviour):
        def __init__(self, message):
            super().__init__()
            self.message = message

        async def run(self):
            reply = Message(to=self.message.sender)
            reply.set_metadata("performative", "failure")
            reply.set_metadata(
                "conversation-id",
                self.message.get_metadata("conversation-id")
            )
            await self.send(reply)


    class SuccessDataInform(OneShotBehaviour):
        def __init__(self, message, data):
            super().__init__()
            self.message = message
            self.data = data

        async def run(self):
            reply = Message(
                to=self.message.sender,
                body=json.dumps(self.data)
            )
            reply.set_metadata("performative", "done")
            reply.set_metadata(
                "conversation-id",
                self.message.get_metadata("conversation-id")
            )
            await self.send(reply)


    class ActionRunner(OneShotBehaviour):
        def __init__(self, message, take_action, sleep_time):
            super().__init__()
            self.message = message
            self.take_action = take_action
            self.sleep_time = sleep_time

        async def run(self):
           self.take_action(json.loads(self.message.body))
           sleep(self.sleep_time)

    def refuse(self, message):
        behaviour = self.RefuseRequest(message)
        self.add_behaviour(behaviour)

    def accept(self, message):
        behaviour = self.AcceptRequest(message)
        self.add_behaviour(behaviour)

    def fail(self, message):
        behaviour = self.FailureInform(message)
        self.add_behaviour(behaviour)
    
    def done(self, message):
        behaviour = self.SuccessDataInform(message, self.value)
        self.add_behaviour(behaviour)

    def run_action(self, message, take_action, sleep_time):
        behaviour = self.ActionRunner(message, take_action, sleep_time)
        self.add_behaviour(behaviour)

    def callback(self, message):
        if not self.free:
            self.refuse(message)
        else:
            self.free = False
            self.accept(message)
            if self.run_action(message, self.action, self.sleep_time):
                self.done(message)
            else:
                self.fail(message)
        self.free = True

    def action(self, body):
        if uniform(0.0, 1.0) > self.succes_rate:
            self.action_impl(body)
            return True
        else:
            return False
        
    async def setup(self):
        behaviour = self.GetRequest(callback = self.callback, jid = self.jid)
        self.add_behaviour(behaviour)

    def action_impl(self, body):
        raise NotImplemented
    