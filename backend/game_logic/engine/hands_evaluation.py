# To do

class HandsEvaluation:
    def __init__(self, player_hand: dict, system_hand: dict):
        self.player_hand = player_hand
        self.system_hand = system_hand

    
    def evaluate(self):
        if self.player_hand > self.system_hand:
            return self.player_hand
        return self.system_hand