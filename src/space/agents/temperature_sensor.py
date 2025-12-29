from random import uniform

from agents.sensor import Sensor


class TemperatureSensor(Sensor):
    def __init__(self):
        super().__init__()
        self.temperature = 20

    def collect_data(self):
        self.temperature += uniform(-0.3, 0.3)
        return {'temperature': self.temperature}
