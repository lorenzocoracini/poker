from engine.game.cards_distribution import Card
from engine.players.system_player import SystemPlayer, compute_decision_features


def _game_state(**overrides):
    gs = {
        'community_cards': [],
        'pot': 10,
        'to_call': 5,
        'can_check': False,
        'has_bet': True,
        'is_button': True,
        'big_blind': 10,
        'street': 'preflop',
        'last_player_action': None,
        'player_raises_this_street': 0,
        'player_raises_prev_streets': 0,
    }
    gs.update(overrides)
    return gs


def test_compute_decision_features_returns_expected_keys():
    hand = [Card('A', 'hearts'), Card('K', 'hearts')]
    features = compute_decision_features(hand, 100, _game_state())
    assert set(features) == {
        'win_prob', 'pot_odds', 'position', 'ppot', 'npot',
        'opponent_aggression', 'stack_commitment',
    }
    assert 0.0 <= features['win_prob'] <= 1.0
    assert features['position'] == 1.0  # is_button=True


def test_compute_decision_features_zero_to_call_has_zero_pot_odds():
    hand = [Card('2', 'clubs'), Card('7', 'diamonds')]
    features = compute_decision_features(hand, 100, _game_state(to_call=0))
    assert features['pot_odds'] == 0.0


def test_system_player_decide_action_fills_last_fuzzy_data():
    system = SystemPlayer()
    system.receive_cards([Card('A', 'hearts'), Card('A', 'spades')])
    action, amount = system.decide_action(_game_state())
    assert action in ('fold', 'call', 'raise', 'bet', 'allin', 'check')
    assert set(system.last_fuzzy_data) == {
        'win_prob', 'pot_odds', 'position', 'ppot', 'npot',
        'opponent_aggression', 'stack_commitment', 'recommendation',
        'recommended_action',
    }
    assert system.last_fuzzy_data['recommendation'] in ('fold', 'call', 'raise')


def test_system_player_very_strong_hand_tends_to_raise_preflop():
    system = SystemPlayer()
    system.receive_cards([Card('A', 'hearts'), Card('A', 'spades')])
    # Can check, no bet yet, in position — pocket aces should recommend raise.
    action, amount = system.decide_action(_game_state(
        can_check=True, has_bet=False, to_call=0,
    ))
    assert system.last_fuzzy_data['recommendation'] == 'raise'
    assert action == 'bet'
