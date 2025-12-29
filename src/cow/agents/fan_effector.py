from agents.effector import Effector

class FanEffector(Effector):
    def __init__(self):
        super().__init__("fan")
        self.fan_on = False

    def action_impl(self, body):
        if "turn_on" in body:
            self.fan_on = body["turn_on"]
            print(f"""[{self.jid}]: 
                  Fan is {'On' if self.fan_on == True else 'Off'} 
                  for {self.sleep_time} seconds.""")