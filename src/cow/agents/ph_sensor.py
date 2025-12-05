from random import uniform

from agents.sensor import Sensor


class PHSensor(Sensor):
    def __init__(self):
        super().__init__()
        self.pH = 6.5

    def collect_data(self):
        self.pH += uniform(-0.1, 0.1)
        return {'pH': self.pH}
