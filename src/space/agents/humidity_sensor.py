from random import uniform

from agents.sensor import Sensor


class HumiditySensor(Sensor):
    def __init__(self):
        super().__init__()
        self.humidity = 50

    def collect_data(self):
        self.humidity += uniform(-2, 2)
        return {'humidity': self.humidity}
