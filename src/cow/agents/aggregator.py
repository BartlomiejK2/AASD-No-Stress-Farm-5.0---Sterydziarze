import json
import os
from copy import copy

from spade.agent import Agent
from spade.behaviour import CyclicBehaviour, OneShotBehaviour
from spade.message import Message


class Aggregator(Agent):
    def __init__(self):
        self.cow_name = os.getenv("NAME")
        super().__init__(f"aggregator-{self.cow_name}@xmpp_server", os.getenv("PASSWORD"))
        self.data = {}

    class AggregateData(CyclicBehaviour):
        def __init__(self, data_aggregator):
            super().__init__()
            self.data_aggregator = data_aggregator

        async def run(self):
            message = await self.receive(timeout=3)

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
            message = Message(to="cows-analyzer@xmpp_server", body=json.dumps(self.profile))
            message.set_metadata("performative", "inform")
            await self.send(message)

    async def setup(self):
        behaviour = self.AggregateData(data_aggregator=self.aggregate_data)
        self.add_behaviour(behaviour)

    def aggregate_data(self, data):
        for key, value in data.items():
            if key in ['temperature', 'pH', 'activity', 'pulse']:
                self.data |= {key: value}
                if self.is_profile_ready():
                    self.forward_profile()

    def is_profile_ready(self):
        return all(key in self.data.keys() for key in ('temperature', 'pH', 'activity', 'pulse'))

    def forward_profile(self):
        behaviour = self.ForwardProfile(profile={self.cow_name: copy(self.data)})
        self.add_behaviour(behaviour)
        self.data.clear()
