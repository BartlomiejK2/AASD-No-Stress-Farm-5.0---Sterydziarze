import json
from copy import copy

class AggregatorTest():
    def __init__(self, sender):
        self.data = {}
        self.send = sender
        self.position_x = 1.0
        self.position_y = 1.5
        self.space_name = "test_aggregator"

    class AggregateData():
        def __init__(self, data_aggregator):
            self.data_aggregator = data_aggregator

        def run(self, message):
            if message:
                data = json.loads(message.body)
                self.data_aggregator(data)
            else:
                print("Did not received any message")

    class ForwardProfile():
        def __init__(self, profile, sender):
            self.profile = profile
            self.send = sender
        def run(self):
            message = FakeMessage(body=json.dumps(self.profile))
            message.set_metadata("performative", "inform")
            self.send(message)

    def test_request(self, message):
        self.AggregateData(data_aggregator=self.aggregate_data).run(message)

    def aggregate_data(self, data):
        for key, value in data.items():
            if key in ['temperature', 'humidity']:
                if key in self.data.keys(): self.data[key] = value
                else: self.data |= {key: value}
                if self.is_profile_ready():
                    self.forward_profile()

    def is_profile_ready(self):
        return all(key in self.data.keys() for key in ('temperature', 'humidity'))

    def forward_profile(self):
        data_to_send = self.data | {
            'position_x': self.position_x,
            'position_y': self.position_y
        }
        self.ForwardProfile(profile={self.space_name: data_to_send}, 
                                        sender=self.send).run()
        self.data = {}


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

def test_aggregator_profile_not_ready():
    mock = Mock()
    aggregator = AggregatorTest(mock)
    message = FakeMessage(body=json.dumps({"temperature": "10"}))
    aggregator.test_request(message)

    assert 0 == mock.call_count
    assert aggregator.is_profile_ready() == False

def test_aggregator_profile_send():
    mock = Mock()
    aggregator = AggregatorTest(mock)
    temperature_message = FakeMessage(body=json.dumps({"temperature": 10.0}))
    humidity_message = FakeMessage(body=json.dumps({"humidity": 15.0}))
    aggregator.test_request(temperature_message)
    aggregator.test_request(humidity_message)

    assert 1 == mock.call_count
    assert aggregator.is_profile_ready() == False

    message = mock.call_args_list[0][0][0]
    data = json.loads(message.body)["test_aggregator"]
    assert data['position_x'] == 1.0
    assert data['position_y'] == 1.5
    assert data["temperature"] == 10.0
    assert data["humidity"] == 15.0
    assert message.get_metadata("performative") == "inform"

def test_aggregator_profile_send_twice():
    mock = Mock()
    aggregator = AggregatorTest(mock)
    temperature_message = FakeMessage(body=json.dumps({"temperature": 10.0}))
    humidity_message = FakeMessage(body=json.dumps({"humidity": 15.0}))
    aggregator.test_request(temperature_message)
    aggregator.test_request(humidity_message)

    assert 1 == mock.call_count
    assert aggregator.is_profile_ready() == False

    message = mock.call_args_list[0][0][0]
    data = json.loads(message.body)["test_aggregator"]
    assert data['position_x'] == 1.0
    assert data['position_y'] == 1.5
    assert data["temperature"] == 10.0
    assert data["humidity"] == 15.0
    assert message.get_metadata("performative") == "inform"

    temperature_message = FakeMessage(body=json.dumps({"temperature": 20.0}))
    temperature_message_new = FakeMessage(body=json.dumps({"temperature": 25.0}))
    humidity_message = FakeMessage(body=json.dumps({"humidity": 7.0}))
    aggregator.test_request(temperature_message)
    aggregator.test_request(temperature_message_new)
    aggregator.test_request(humidity_message)

    assert 2 == mock.call_count
    assert aggregator.is_profile_ready() == False

    message = mock.call_args_list[1][0][0]
    data = json.loads(message.body)["test_aggregator"]
    assert data['position_x'] == 1.0
    assert data['position_y'] == 1.5
    assert data["temperature"] == 25.0
    assert data["humidity"] == 7.0
    assert message.get_metadata("performative") == "inform"

def test_aggregator_false_message():
    mock = Mock()
    aggregator = AggregatorTest(mock)
    message = FakeMessage(body=json.dumps({"aaaa": "10"}))
    aggregator.test_request(message)
    message = FakeMessage(body=json.dumps({"aaaab": "10"}))
    aggregator.test_request(message)
    message = FakeMessage(body=json.dumps({"aaabba": "10"}))
    aggregator.test_request(message)

    assert 0 == mock.call_count
    assert aggregator.is_profile_ready() == False
    assert len(aggregator.data) == 0

def test_aggregator_false_message_two():
    mock = Mock()
    aggregator = AggregatorTest(mock)
    temperature_message = FakeMessage(body=json.dumps({"temperature": 10.0}))
    aggregator.test_request(temperature_message)
    message = FakeMessage(body=json.dumps({"aaaab": "10"}))
    aggregator.test_request(message)
    message = FakeMessage(body=json.dumps({"aaabba": "10"}))
    aggregator.test_request(message)

    assert 0 == mock.call_count
    assert aggregator.is_profile_ready() == False
    assert len(aggregator.data) == 1