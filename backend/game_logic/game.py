from config.game_parameters import *
from engine.cards_distribuition import cards_distribuition
from players.system_player import SystemPlayer
from players.user_player import UserPlayer



class PokerGame:
    def __init__(self):
        self.system = SystemPlayer()
        self.player = UserPlayer()
        self.round_number = 1


    def new_round(self):
        print('ROUND ->', self.round_number)
        player_cards, system_cards, flop_cards, turn_card, river_card = cards_distribuition()
        return self.player.stack, self.system.stack,player_cards, system_cards, flop_cards, turn_card, river_card



game = PokerGame()
print(game.new_round())
game.round_number += 1
