from agents.effector import Effector

class FeederEffector(Effector):
    def __init__(self):
        super().__init__("feeder")
        self.feeder_on = False

    def action_impl(self, body):
        if "turn_on" in body:
            self.feeder_on = body["turn_on"]
            print(f"""[{self.jid}]: 
                  Feeder is {'On' if self.feeder_on == True else 'Off'} 
                  for {self.sleep_time} seconds.""")