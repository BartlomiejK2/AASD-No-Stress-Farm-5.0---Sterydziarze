from random import uniform

from agents.sensor import Sensor


class PedometerSensor(Sensor):
    def __init__(self):
        super().__init__()
        self.activity = 1

    def collect_data(self):
        self.activity *= uniform(0.8, 1.2)
        return {'activity': self.activity}
