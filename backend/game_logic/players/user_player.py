from .base_player import Player


class UserPlayer(Player):
    def __init__(self):
        super().__init__()
        self.name = 'Player'


