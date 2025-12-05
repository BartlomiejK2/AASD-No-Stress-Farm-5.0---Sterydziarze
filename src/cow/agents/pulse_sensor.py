from random import uniform

from agents.sensor import Sensor


class PulseSensor(Sensor):
    def __init__(self):
        super().__init__()
        self.pulse = 60

    def collect_data(self):
        self.pulse += uniform(-2, 2)
        return {'pulse': self.pulse}
