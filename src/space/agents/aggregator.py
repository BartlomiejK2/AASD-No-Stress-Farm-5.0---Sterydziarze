import json
import os
from copy import copy

from spade.agent import Agent
from spade.behaviour import CyclicBehaviour, OneShotBehaviour
from spade.message import Message


class Aggregator(Agent):
    def __init__(self):
        self.space_name = os.getenv("NAME")
        self.position_x = os.getenv("POSITION_X")
        self.position_y = os.getenv("POSITION_Y")

        super().__init__(f"aggregator-{self.space_name}@xmpp_server", os.getenv("PASSWORD"))
        self.data = {}

    class AggregateData(CyclicBehaviour):
        def __init__(self, data_aggregator):
            super().__init__()
            self.data_aggregator = data_aggregator

        async def run(self):
            message = await self.receive(timeout=15)

            if message:
                data = json.loads(message.body)
                self.data_aggregator(data)
            else:
                print("Did not received any message")

    class ForwardProfile(OneShotBehaviour):
        def __init__(self, profile):
            super().__init__()
            self.profile = profile

        async def run(self):
            message = Message(to="spacial-analyzer@xmpp_server", body=json.dumps(self.profile))
            message.set_metadata("performative", "inform")
            await self.send(message)

    async def setup(self):
        behaviour = self.AggregateData(data_aggregator=self.aggregate_data)
        self.add_behaviour(behaviour)

    def aggregate_data(self, data):
        for key, value in data.items():
            if key in ['temperature', 'humidity']:
                self.data |= {key: value}
                if self.is_profile_ready():
                    self.forward_profile()

    def is_profile_ready(self):
        return all(key in self.data.keys() for key in ('temperature', 'humidity'))

    def forward_profile(self):
        data_to_send = self.data | {
            'position_x': self.position_x,
            'position_y': self.position_y
        }
        behaviour = self.ForwardProfile(profile={self.space_name: data_to_send})
        self.add_behaviour(behaviour)
        self.data.clear()
