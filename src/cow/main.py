import spade
from agents.aggregator import Aggregator
from agents.temperature_sensor import TemperatureSensor
from agents.pedometer_sensor import PedometerSensor
from agents.ph_sensor import PHSensor
from agents.pulse_sensor import PulseSensor


async def main():
    aggregator_agent = Aggregator()
    await aggregator_agent.start(auto_register=True)
    print("Aggregator started")

    temperature_sensor = TemperatureSensor()
    await temperature_sensor.start(auto_register=True)

    pedometer_sensor = PedometerSensor()
    await pedometer_sensor.start(auto_register=True)

    ph_sensor = PHSensor()
    await ph_sensor.start(auto_register=True)

    pulse_sensor = PulseSensor()
    await pulse_sensor.start(auto_register=True)

    with open("/tmp/agent_ready", "w") as f:
        f.write("ready")

    await spade.wait_until_finished(aggregator_agent)
    print("Agents finished")


if __name__ == "__main__":
    spade.run(main())
