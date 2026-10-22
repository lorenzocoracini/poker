import contextlib
import io
import random

import pytest

import db.database as database
from engine.game.cards_distribution import cards_distribution
from engine.game.controller import GameController
from engine.players.system_player import translate_recommendation


@pytest.fixture
def ctrl(tmp_path, monkeypatch):
    """Controller placed on the flop with 600 chips each, empty pot, player first."""
    monkeypatch.setattr(database, 'DB_PATH', str(tmp_path / 'bet.db'))
    with contextlib.redirect_stdout(io.StringIO()):
        c = GameController()
    c.player.stack = c.system.stack = 600
    c.pot, c.street, c.to_call = 0, 'flop', 0
    c.can_check, c.has_bet, c.last_raiser = True, False, None
    c._actors, c._actor_idx, c._is_preflop = ['player', 'system'], 0, False
    player_cards, system_cards, flop, turn, river = cards_distribution()
    c.player.receive_cards(player_cards)
    c.system.receive_cards(system_cards)
    c.flop = c._full_flop = flop
    c._full_turn, c._full_river = turn, river
    c.recorder._round_id = None  # nothing is recorded
    return c


def paid(c):
    return 600 - c.player.stack, 600 - c.system.stack


def test_raise_matches_the_bet_before_adding(ctrl):
    ctrl._apply_action('player', 'bet', 200)
    ctrl._apply_action('system', 'raise', 60)
    assert paid(ctrl) == (200, 260)
    assert ctrl.to_call == 60
    ctrl._apply_action('player', 'call', 0)
    assert paid(ctrl) == (260, 260)


def test_small_raise_over_small_bet(ctrl):
    ctrl._apply_action('player', 'bet', 40)
    ctrl._apply_action('system', 'raise', 60)
    ctrl._apply_action('player', 'call', 0)
    assert paid(ctrl) == (100, 100)
    assert ctrl.pot == 200


def test_all_in_over_a_bet_owes_only_the_difference(ctrl):
    ctrl._actors = ['system', 'player']
    ctrl._apply_action('system', 'bet', 60)
    ctrl._apply_action('player', 'allin', 0)
    assert paid(ctrl) == (600, 60)
    assert ctrl.player.stack == 0
    assert ctrl.to_call == 540


def test_all_in_bigger_than_opponent_stack_keeps_the_excess(ctrl):
    ctrl.system.stack = 300
    ctrl._apply_action('player', 'allin', 0)
    assert ctrl.player.stack == 300   # only 300 can be contested
    assert ctrl.to_call == 300


def test_calling_all_in_for_less_returns_the_uncalled_part(ctrl):
    # Player has 200 in the pot; the system, with 100 left, calls all-in.
    ctrl.player.stack, ctrl.system.stack, ctrl.pot, ctrl.to_call = 400, 600, 200, 200
    ctrl.system.stack = 100
    ctrl._apply_action('system', 'call', 0)
    # 100 uncalled chips go back to the player; the contested pot is 100 + 100.
    assert ctrl.pot == 200
    assert ctrl.showdown
    assert (ctrl.player.stack, ctrl.system.stack) in {(700, 0), (500, 200), (600, 100)}


def test_raise_against_all_in_opponent_becomes_call(ctrl):
    ctrl._apply_action('player', 'allin', 0)
    ctrl._apply_action('system', 'raise', 60)   # nothing left to raise against
    assert ctrl.pot == 1200                     # system called 600, no extra chips
    assert ctrl.showdown
    assert ctrl.player.stack + ctrl.system.stack == 1200


def test_no_raise_options_against_all_in_opponent(ctrl):
    ctrl._actors = ['system', 'player']
    ctrl.system.stack = 100
    ctrl._apply_action('system', 'allin', 0)
    assert ctrl.system.stack == 0
    acts = [a for a, _, _ in ctrl.get_valid_actions()]
    assert acts == ['fold', 'call']


def test_translate_recommendation_never_raises_against_all_in():
    assert translate_recommendation('raise', False, True, 100, 500, opponent_all_in=True) == 'call'
    assert translate_recommendation('raise', False, True, 100, 500) == 'raise'


@pytest.mark.parametrize('seed', range(8))
def test_random_games_keep_contributions_consistent(tmp_path, monkeypatch, seed):
    """Whenever the player must act, what is owed equals the difference between
    what each side has put in this round, and chips are never created or lost."""
    monkeypatch.setattr(database, 'DB_PATH', str(tmp_path / f'r{seed}.db'))
    random.seed(seed)
    rng = random.Random(seed)
    with contextlib.redirect_stdout(io.StringIO()):
        c = GameController()
        while True:
            start = (c.player.stack, c.system.stack)
            state = c.start_new_round()
            while state['status'] == 'WAITING_PLAYER':
                put_p = start[0] - c.player.stack
                put_s = start[1] - c.system.stack
                assert c.player.stack + c.system.stack + c.pot == 1200
                assert c.pot == put_p + put_s
                assert c.to_call == max(0, put_s - put_p)
                action, _, amount = rng.choice(state['valid_actions'])
                if action in ('bet', 'raise'):
                    amount = rng.choice([c.blind * 2, c.blind * 6, 10_000])
                state = c.apply_player_action(action, amount)
            assert c.player.stack + c.system.stack == 1200
            if state['status'] == 'GAME_OVER' or c.round_number > 300:
                break


def test_translate_recommendation_never_raises_without_chips():
    # Big blind that used its last chips, nothing to call: check, not raise.
    assert translate_recommendation('raise', False, True, 0, 0) == 'check'
    assert translate_recommendation('raise', False, True, 0, 100) == 'raise'


def test_short_big_blind_returns_uncontested_small_blind(tmp_path, monkeypatch):
    # Big blind with 10 chips at blinds 20/40: only 10 of the small blind is contested.
    monkeypatch.setattr(database, 'DB_PATH', str(tmp_path / 'blind.db'))
    with contextlib.redirect_stdout(io.StringIO()):
        c = GameController()
        c.round_number, c.blind = 11, 20       # next round keeps blinds at 20/40
        c.button = 'player'                    # start_new_round rotates: system becomes dealer
        c.big_blind_pos = 'system'
        c.player.stack, c.system.stack = 10, 1190
        c.start_new_round()
    assert c.button == 'system'
    assert c.pot <= 20 or c.showdown
    assert c.player.stack + c.system.stack + (0 if c.showdown else c.pot) == 1200
    if c.showdown:
        assert (c.player.stack, c.system.stack) in {(20, 1180), (0, 1200), (10, 1190)}
