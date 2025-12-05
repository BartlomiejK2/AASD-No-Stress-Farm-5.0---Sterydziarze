import json
import os

from spade.agent import Agent
from spade.behaviour import CyclicBehaviour


class CowsAnalyzer(Agent):
    def __init__(self):
        super().__init__(f"analyzer@xmpp_server", os.getenv("PASSWORD"))
        self.data = {}

    class CollectProfilesData(CyclicBehaviour):
        def __init__(self, data_collector):
            super().__init__()
            self.data_collector = data_collector

        async def run(self):
            message = await self.receive(timeout=10)

            if message:
                data = json.loads(message.body)
                self.data_collector(data)
            else:
                print("Did not received any message")

    async def setup(self) -> None:
        behaviour = self.CollectProfilesData(data_collector=self.collect_data)
        self.add_behaviour(behaviour)

    def collect_data(self, data):
        self.data |= data
        self.analyse_data()

    def analyse_data(self):
        print(f"analyse data: {self.data}")
