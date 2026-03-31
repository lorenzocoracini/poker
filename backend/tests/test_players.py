import pytest
from game_logic.players.base_player import Player
from game_logic.players.system_player import SystemPlayer
from game_logic.players.user_player import UserPlayer
from game_logic.engine.cards_distribution import Card
from game_logic.config.game_parameters import STACK_INICIAL


#  Base Player 

def test_player_initial_stack():
    player = Player(name='Test')
    assert player.stack == STACK_INICIAL

def test_player_initial_hand_is_empty():
    player = Player(name='Test')
    assert player.hand == []

def test_player_receive_cards():
    player = Player(name='Test')
    cards = [Card('A', 'spades'), Card('K', 'hearts')]
    player.receive_cards(cards)
    assert len(player.hand) == 2

def test_player_fold_clears_hand():
    player = Player(name='Test')
    cards = [Card('A', 'spades'), Card('K', 'hearts')]
    player.receive_cards(cards)
    player.fold()
    assert player.hand == []

def test_player_repr():
    player = Player(name='Test')
    assert repr(player) == f'Test (stack: {STACK_INICIAL})'


# System Player 

def test_system_player_name():
    system = SystemPlayer()
    assert system.name == 'System'

def test_system_player_is_player():
    system = SystemPlayer()
    assert isinstance(system, Player)


# User Player

def test_user_player_name():
    user = UserPlayer()
    assert user.name == 'Player'

def test_user_player_is_player():
    user = UserPlayer()
    assert isinstance(user, Player)