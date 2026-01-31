import json
import os
from random import uniform
from time import sleep

from spade.agent import Agent
from spade.behaviour import CyclicBehaviour, OneShotBehaviour
from spade.message import Message

from copy import deepcopy


class EffectorTest:
    def __init__(self, sender, succes_rate):
        self.free = True
        self.value = None
        self.send = sender
        self.succes_rate = succes_rate

    class GetRequest():
        def __init__(self, callback):
            self.callback = callback

        def run(self, message):
            if message:
                if message.get_metadata("performative") != "request":
                    return
                self.callback(deepcopy(message))
                
    class RefuseRequest():
        def __init__(self, message, sender):
            self.message = message
            self.send = sender

        def run(self):
            reply = self.message.make_reply()
            reply.set_metadata("performative", "refuse")
            self.send(reply)

    class AcceptRequest():
        def __init__(self, message, sender):
            self.message = message
            self.send = sender

        def run(self):
            reply = self.message.make_reply()
            reply.set_metadata("performative", "agree")
            self.send(reply)

    class FailureInform():
        def __init__(self, message, sender):
            self.message = message
            self.send = sender
            
        def run(self):
            reply = self.message.make_reply()
            reply.set_metadata("performative", "failure")
            self.send(reply)

    class SuccessDataInform():
        def __init__(self, data, message, sender):
            self.message = message
            self.send = sender
            self.data = data
        def run(self):
            reply = self.message.make_reply()
            reply.set_metadata("performative", "done")
            reply.body = json.dumps(self.data)
            self.send(reply)

    class ActionRunner():
        def __init__(self, message, take_action):
            self.message = message
            self.take_action = take_action

        def run(self):
           self.take_action(json.loads(self.message.body))

    def refuse(self, message):
        self.RefuseRequest(message, self.send).run()

    def accept(self, message):
        self.AcceptRequest(message, self.send).run()
        
    def fail(self, message):
        self.FailureInform(message, self.send).run()
    
    def done(self, message):
        self.SuccessDataInform(self.value, message, self.send).run()

    def run_action(self, message, take_action):
        if uniform(0.0, 1.0) < self.succes_rate:
            self.ActionRunner(message, take_action).run()
            return True
        else:
            return False

    def callback(self, message):
        if not self.free:
            self.refuse(message)
        else:
            self.free = False
            self.accept(message)
            if self.run_action(message, self.action):
                self.done(message)
            else:
                self.fail(message)

    def action(self, body):
        self.action_impl(body)
        self.free = True

    def action_impl(self, body):
        self.value = {"turned_on": body["turn_on"]}

    def test_request(self, message):
        self.GetRequest(callback=self.callback).run(message)


class FakeMessage:
    def __init__(self, body = None, sender="tester@localhost", to = "effector@localhost"):
        self.sender = sender
        self.metadata = {}
        self.to = to
        self.body = body
    def get_metadata(self, key):
        return self.metadata.get(key)

    def set_metadata(self, key, value):
        self.metadata[key] = value

    def make_reply(self):
        return FakeMessage(sender="effector@localhost", to="tester@localhost")


from unittest.mock import Mock

def test_effector_refuse():
    mock = Mock()
    effector = EffectorTest(mock, 1.0)

    effector.free = False

    request = FakeMessage(body=json.dumps({"turn_on": "True"}))
    request.set_metadata("performative", "request")

    effector.test_request(request)

    mock.assert_called_once()
    message = mock.call_args[0][0]
    assert message.get_metadata("performative") == "refuse"
    assert message.sender == "effector@localhost"
    assert message.to == "tester@localhost"


def test_effector_accept():
    mock = Mock()
    effector = EffectorTest(mock, 1.0)

    effector.free = True

    request = FakeMessage(body=json.dumps({"turn_on": "True"}))
    request.set_metadata("performative", "request")
    effector.test_request(request)

    assert 2 == mock.call_count
    for args in mock.call_args_list:
        print(args[0][0])

    agree_message = mock.call_args_list[0][0][0]
    assert agree_message.get_metadata("performative") == "agree"
    assert agree_message.sender == "effector@localhost"
    assert agree_message.to == "tester@localhost"

    done_message = mock.call_args_list[1][0][0]
    assert done_message.get_metadata("performative") == "done"
    assert done_message.sender == "effector@localhost"
    assert done_message.to == "tester@localhost"
    assert json.loads(done_message.body)["turned_on"] == "True"

def test_effector_failure():
    mock = Mock()
    effector = EffectorTest(mock, 0.0)

    effector.free = True

    request = FakeMessage(body=json.dumps({"turn_on": "True"}))
    request.set_metadata("performative", "request")
    effector.test_request(request)

    assert 2 == mock.call_count
    for args in mock.call_args_list:
        print(args[0][0])

    agree_message = mock.call_args_list[0][0][0]
    assert agree_message.get_metadata("performative") == "agree"
    assert agree_message.sender == "effector@localhost"
    assert agree_message.to == "tester@localhost"

    fail_message = mock.call_args_list[1][0][0]
    assert fail_message.get_metadata("performative") == "failure"
    assert fail_message.sender == "effector@localhost"
    assert fail_message.to == "tester@localhost"
