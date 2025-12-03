import spade
from spade.agent import Agent
from spade.behaviour import CyclicBehaviour, OneShotBehaviour
from spade.message import Message
from spade.template import Template
from numpy import random
import time

class SensorAgent(Agent):
    class InformBehav(CyclicBehaviour):
        async def run(self):
            print("InformBehav running")
            msg = Message(to="aggregator@localhost")     # Instantiate the message
            msg.set_metadata("performative", "inform")  # Set the "inform" FIPA performative
            x = random.normal(size=(1))
            msg.body = str(x[0])                         # Set the message content

            await self.send(msg)
            print(f"Message: {msg.body} sent!")
            time.sleep(1.0)

    async def setup(self):
        print("SensorAgent started")
        b = self.InformBehav()
        self.add_behaviour(b)

class AggregatorAgent(Agent):
    class RecvBehav(CyclicBehaviour):
        async def run(self):

            msg = await self.receive(timeout=10) # wait for a message for 10 seconds
            if msg:
                print("Message received with content: {}".format(msg.body))
                self.data.append(msg.body)
                print(f"Data stored: {self.data}")
            else:
                print("Did not received any message after 10 seconds")

    async def setup(self):
        print("AggregatorAgent started")
        self.data = []
        b = self.RecvBehav()
        template = Template()
        template.set_metadata("performative", "inform")
        self.add_behaviour(b, template)



async def main():
    aggregatoragent = AggregatorAgent("aggregator@localhost", "aggregator_password")
    await aggregatoragent.start(auto_register=True)
    print("Aggregator started")

    sensoragent = SensorAgent("sensor@localhost", "sensor_password")
    await sensoragent.start(auto_register=True)
    print("Sensor started")

    await spade.wait_until_finished(aggregatoragent)
    print("Agents finished")


if __name__ == "__main__":
    spade.run(main())
