import random

import pytest

from engine.game.cards_distribution import Card
from engine.fuzzy.hand_strength import calculate_hand_potential
from engine.fuzzy.fuzzy_agent import FuzzyPokerAgent


# calculate_hand_potential (PPot / NPot)

def test_hand_potential_returns_values_in_unit_range():
    random.seed(0)
    hole  = [Card('A', 'hearts'), Card('K', 'hearts')]
    board = [Card('2', 'hearts'), Card('7', 'hearts'), Card('9', 'clubs')]
    ppot, npot = calculate_hand_potential(hole, board, n_simulations=200)
    assert 0.0 <= ppot <= 1.0
    assert 0.0 <= npot <= 1.0


def test_flush_draw_has_higher_ppot_than_weak_no_draw_hand():
    random.seed(1)
    flush_draw_hole  = [Card('A', 'hearts'), Card('K', 'hearts')]
    flush_draw_board = [Card('2', 'hearts'), Card('7', 'hearts'), Card('9', 'clubs')]
    ppot_draw, _ = calculate_hand_potential(flush_draw_hole, flush_draw_board, n_simulations=300)

    random.seed(1)
    weak_hole  = [Card('2', 'clubs'), Card('7', 'diamonds')]
    weak_board = [Card('K', 'spades'), Card('Q', 'clubs'), Card('4', 'hearts')]
    ppot_weak, _ = calculate_hand_potential(weak_hole, weak_board, n_simulations=300)

    assert ppot_draw > ppot_weak


# FuzzyPokerAgent — smoke tests com as 7 variáveis

@pytest.mark.parametrize('value', [0.0, 0.25, 0.5, 0.75, 1.0])
def test_fuzzy_agent_decide_handles_full_input_range(value):
    agent = FuzzyPokerAgent()
    result = agent.decide(value, value, value, value, value, value, value)
    assert result in ('fold', 'call', 'raise')


def test_fuzzy_agent_very_strong_hand_raises():
    agent = FuzzyPokerAgent()
    result = agent.decide(
        hand_strength_val=0.95, pot_odds_val=0.2, position_val=1.0,
        ppot_val=0.0, npot_val=0.0, aggression_val=0.0, commitment_val=0.0,
    )
    assert result == 'raise'


def test_fuzzy_agent_weak_hand_against_aggressive_opponent_folds():
    agent = FuzzyPokerAgent()
    result = agent.decide(
        hand_strength_val=0.15, pot_odds_val=0.5, position_val=0.0,
        ppot_val=0.1, npot_val=0.1, aggression_val=0.9, commitment_val=0.1,
    )
    assert result == 'fold'
