import asyncio
import spade
from agents.aggregator import Aggregator
from agents.temperature_sensor import TemperatureSensor
from agents.humidity_sensor import HumiditySensor
from agents.air_conditioner_effector import AirConditionerEffector


async def main():
    # --- inicjalizacja agentów ---
    aggregator_agent = Aggregator()
    temperature_sensor = TemperatureSensor()
    humidity_sensor = HumiditySensor()
    air_conditioner = AirConditionerEffector()

    # --- retry połączenia z XMPP (jeden wspólny punkt) ---
    while True:
        try:
            await aggregator_agent.start(auto_register=True)
            await temperature_sensor.start(auto_register=True)
            await humidity_sensor.start(auto_register=True)
            await air_conditioner.start(auto_register=True)
            print("All agents started")
            break
        except Exception as e:
            print("XMPP not ready, retrying in 5s:", e)
            await asyncio.sleep(5)

    # --- SYGNAŁ HEALTHCHECK ---
    # Ten plik oznacza: WSZYSCY agenci są połączeni i działają
    with open("/tmp/agent_ready", "w") as f:
        f.write("ready")

    # --- utrzymanie życia systemu ---
    await spade.wait_until_finished(aggregator_agent)
    print("Agents finished")


if __name__ == "__main__":
    spade.run(main())
