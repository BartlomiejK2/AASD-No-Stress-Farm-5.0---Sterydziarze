from agents.effector import Effector

class AirConditionerEffector(Effector):
    def __init__(self):
        super().__init__("air_conditioner")
        self.cooling = False

    def action_impl(self, body):
        if "turn_on" in body:
            self.cooling = body["turn_on"]
            print(f"""[{self.jid}]: 
                  Colling is {'On' if self.cooling == True else 'Off'} 
                  for {self.sleep_time} seconds.""")



        