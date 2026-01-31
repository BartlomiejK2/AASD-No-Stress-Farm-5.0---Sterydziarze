import json
import os
from random import uniform
from time import sleep

from spade.agent import Agent
from spade.behaviour import CyclicBehaviour, OneShotBehaviour
from spade.message import Message

from copy import deepcopy


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
                self.callback(deepcopy(message))
            else:
                print(f"[{self.jid}]: Did not received any request")

    class RefuseRequest(OneShotBehaviour):
        def __init__(self, message, jid):
            super().__init__()
            self.message = message
            self.jid = jid

        async def run(self):
            reply = self.message.make_reply()
            reply.set_metadata("performative", "refuse")
            print(f"[{self.jid}] refuse {reply}")
            await self.send(reply)


    class AcceptRequest(OneShotBehaviour):
        def __init__(self, message, jid):
            super().__init__()
            self.message = message
            self.jid = jid

        async def run(self):
            reply = self.message.make_reply()
            reply.set_metadata("performative", "agree")
            print(f"[{self.jid}]: accept {reply}")
            print(f"[{self.jid}]: accept from {self.message.sender}")
            await self.send(reply)

    
    class FailureInform(OneShotBehaviour):
        def __init__(self, message, jid):
            super().__init__()
            self.message = message
            self.jid = jid

        async def run(self):
            reply = self.message.make_reply()
            reply.set_metadata("performative", "failure")
            print(f"[{self.jid}]: failure {reply}")
            await self.send(reply)


    class SuccessDataInform(OneShotBehaviour):
        def __init__(self, message, data, jid):
            super().__init__()
            self.message = message
            self.data = data
            self.jid = jid

        async def run(self):
            reply = self.message.make_reply()
            reply.set_metadata("performative", "done")
            reply.body = json.dumps(self.data)
            print(f"[{self.jid}]: success {reply}")
            await self.send(reply)


    class ActionRunner(OneShotBehaviour):
        def __init__(self, message, take_action, sleep_time):
            super().__init__()
            self.message = message
            self.take_action = take_action
            self.sleep_time = sleep_time

        async def run(self):
           sleep(self.sleep_time)
           self.take_action(json.loads(self.message.body))

    def refuse(self, message):
        behaviour = self.RefuseRequest(message, self.jid)
        self.add_behaviour(behaviour)

    def accept(self, message):
        behaviour = self.AcceptRequest(message, self.jid)
        self.add_behaviour(behaviour)

    def fail(self, message):
        behaviour = self.FailureInform(message, self.jid)
        self.add_behaviour(behaviour)
    
    def done(self, message):
        behaviour = self.SuccessDataInform(message, self.value, self.jid)
        self.add_behaviour(behaviour)

    def run_action(self, message, take_action, sleep_time):
        if uniform(0.0, 1.0) < self.succes_rate:
            behaviour = self.ActionRunner(message, take_action, sleep_time)
            self.add_behaviour(behaviour)
            return True
        else:
            return False

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

    def action(self, body):
        self.action_impl(body)
        self.free = True
 
    async def setup(self):
        behaviour = self.GetRequest(callback = self.callback, jid = self.jid)
        self.add_behaviour(behaviour)

    def action_impl(self, body):
        raise NotImplemented
    