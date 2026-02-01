from agents.effector import Effector

class AirConditionerEffector(Effector):
    def __init__(self):
        super().__init__("air_conditioner")

    def action_impl(self, body):
        if "turn_on" in body:
            self.value = {"turned_on": body["turn_on"]}
            print(f"""[{self.jid}]: 
                  Colling is {'On' if body["turn_on"] == "True" else 'Off'} 
                  for {self.sleep_time} seconds.""")



        