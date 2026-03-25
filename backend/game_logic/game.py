from config.game_parameters import *
from engine.cards_distribuition import cards_distribuition
from players.system_player import SystemPlayer
from players.user_player import UserPlayer
import random


class PokerGame:
    def __init__(self):
        self.system = SystemPlayer()
        self.player = UserPlayer()
        self.round_number = 1
        self.blind = INICIAL_BLIND
        self.button = self.set_first_button()
        self.big_blind = None
        self.round_phase = 'pre-flop'

    def set_first_button(self):
        options = ['system','player']
        self.button = random.choice(options)
        print('BUTTON ->', self.button)
        # BB
        if self.button == 'player':
            self.big_blind =  'system'
        else:
            self.big_blind = 'player'
        return self.button
    
    def change_button(self):
        if self.button == 'player':
            self.button =  'system'
            self.big_blind = 'player'
        else:
            self.button =  'player'
            self.big_blind = 'system'
        print('BUTTON ->', self.button)
    
    def change_round_state(self):
        if self.round_phase == 'pre-flop':
            self.round_phase = 'flop'
        elif self.round_phase == 'flop':
            self.round_phase = 'river'
        elif self.round_phase == 'river':
            self.round_phase = 'turn'

    def info_pre_new_round(self):
        print('ROUND ->', self.round_number)
        print('ROUND PHASE ->', self.round_phase)
        print('BLIND ->', self.blind)
        print('PLAYER STACK ->',self.player.stack)
        print('SYSTEM STACK ->',self.system.stack)


    def new_round(self):
        pote = 0
        if self.round_number > 1:
            self.change_button()
        self.info_pre_new_round()
        player_cards, system_cards, flop_cards, turn_card, river_card = cards_distribuition()

        # PRE FLOP
        print('PLAYER CARDS ->',player_cards)
        if self.button == 'player':
            pote += 5
            self.player.stack -= 5

            pote += 10
            self.system.stack -= 10

        print('POTE -> ', pote)
        print('pl stack ->', self.player.stack)
        print('sys stack ->', self.system.stack)

        





game = PokerGame()
while game.round_number in [1]:
#if game.player.stack != 0 or game.system.stack != 0:
    game.new_round()
    game.round_number += 1
