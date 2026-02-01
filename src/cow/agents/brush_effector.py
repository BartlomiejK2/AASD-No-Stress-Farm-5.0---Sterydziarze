from agents.effector import Effector

class BrushEffector(Effector):
    def __init__(self):
        super().__init__("brush")

    def action_impl(self, body):
        if "turn_on" in body:
            self.value = {"turned_on": body["turn_on"]}
            print(f"""[{self.jid}]: 
                  Brush is {'On' if body["turn_on"] == "True" else 'Off'} 
                  for {self.sleep_time} seconds.""")



