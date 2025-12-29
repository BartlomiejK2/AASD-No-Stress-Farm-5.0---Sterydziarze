from agents.effector import Effector

class SprinklerEffector(Effector):
    def __init__(self):
        super().__init__("sprinkler")
        self.sprinkler_on = False

    def action_impl(self, body):
        if "turn_on" in body:
            self.sprinkler_on = body["turn_on"]
            print(f"""[{self.jid}]: 
                  Sprinkler is {'On' if self.sprinkler_on == True else 'Off'} 
                  for {self.sleep_time} seconds.""")