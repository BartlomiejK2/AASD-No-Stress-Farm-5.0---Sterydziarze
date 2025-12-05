import json
import os

from spade.agent import Agent
from spade.message import Message
from spade.behaviour import PeriodicBehaviour


class Sensor(Agent):
    def __init__(self):
        super().__init__(f"{os.getenv("NAME")}-{self.__class__.__name__}@xmpp_server", os.getenv("PASSWORD"))

    class ForwardData(PeriodicBehaviour):
        def __init__(self, data_provider, period=1):
            super().__init__(period)
            self.data_provider = data_provider
            self.aggregator_name = f"aggregator-{os.getenv("NAME")}@xmpp_server"

        async def run(self):
            data = self.data_provider()
            await self.forward_data(data)

        async def forward_data(self, data):
            message = Message(to=self.aggregator_name, body=json.dumps(data))
            message.set_metadata("performative", "inform")

            await self.send(message)

    async def setup(self):
        behaviour = self.ForwardData(data_provider=self.collect_data)
        self.add_behaviour(behaviour)

    def collect_data(self):
        raise NotImplemented
