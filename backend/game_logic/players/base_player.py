from game_logic.config.game_parameters import STACK_INICIAL

class Player:
    def __init__(self, name: str, stack: int = STACK_INICIAL):
        self.name = name
        self.stack = stack
        self.hand = []

    def receive_cards(self, cards: list):
        self.hand = cards

    def fold(self):
        self.hand = []

    def __repr__(self):
        return f"{self.name} (stack: {self.stack})"