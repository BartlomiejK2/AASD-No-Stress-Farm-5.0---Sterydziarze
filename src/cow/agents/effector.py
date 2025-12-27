import json
import os
from copy import copy
from random import uniform
from time import sleep

from spade.agent import Agent
from spade.behaviour import CyclicBehaviour, OneShotBehaviour
from spade.message import Message


class Effector(Agent):
    def __init__(self, type: str, success_rate: float, sleep_time: float):
        self.cow_name = os.getenv("NAME")
        self.succes_rate = success_rate
        self.sleep_time = sleep_time
        self.free = True
        self.value = None
        super().__init__(f"effector-{type}-{self.cow_name}@xmpp_server", os.getenv("PASSWORD"))

    class GetRequest(CyclicBehaviour):
        def __init__(self, callback):
            super().__init__()
            self.callback = callback

        async def run(self):
            message = await self.receive(timeout=3)

            if message:
                self.callback(message)
            else:
                print("Did not received any request")

    class RefuseRequest(OneShotBehaviour):
        def __init__(self, message):
            super().__init__()
            self.message = message

        async def run(self):
            message = Message(to = message.sender, body="")
            message.set_metadata("performative", "refuse")
            await self.send(message)

    class AcceptRequest(OneShotBehaviour):
        def __init__(self, message):
            super().__init__()
            self.message = message

        async def run(self):
            message = Message(to = message.sender, body="")
            message.set_metadata("performative", "agree")
            await self.send(message)
    
    class FailureInform(OneShotBehaviour):
        def __init__(self, message):
            super().__init__()
            self.message = message

        async def run(self):
            message = Message(to = message.sender, body="")
            message.set_metadata("performative", "failure")
            await self.send(message)

    class SuccessDataInform(OneShotBehaviour):
        def __init__(self, message, data):
            super().__init__()
            self.message = message
            self.data = data

        async def run(self):
            message = Message(to = message.sender, body = json.dumps(self.data))
            message.set_metadata("performative", "done")
            await self.send(message)

    class ActionRunner(OneShotBehaviour):
        def __init__(self, message, take_action, sleep_time):
            super().__init__()
            self.message = message
            self.take_action = take_action
            self.sleep_time = sleep_time

        async def run(self):
           self.take_action(self.message.body)
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
                self.fail()
        self.free = True

    def action(self):
        if uniform(0.0, 1.0) > self.succes_rate:
            self.action_impl()
            return True
        else:
            return False
        
    async def setup(self):
        behaviour = self.GetRequest(data_aggregator = self.callback)
        self.add_behaviour(behaviour)

    def action_impl(self):
        raise NotImplemented
    