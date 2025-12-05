from random import uniform

from agents.sensor import Sensor


class TemperatureSensor(Sensor):
    def __init__(self):
        super().__init__()
        self.temperature = 40

    def collect_data(self):
        self.temperature += uniform(-0.5, 0.5)
        return {'temperature': self.temperature}
