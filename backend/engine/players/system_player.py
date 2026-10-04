from .base_player import Player
from engine.fuzzy.fuzzy_agent import FuzzyPokerAgent
from engine.fuzzy.hand_strength import calculate_win_probability, calculate_hand_potential

# Heurísticas de composição do sinal de agressividade do oponente — engenharia própria,
# a recalibrar na etapa de tuning por ML (ver PLANO_EXPANSAO_FUZZY.md).
_LAST_ACTION_WEIGHT = {
    'raise': 1.0, 'bet': 1.0, 'allin': 1.0,
    'call':  0.4,
    'check': 0.0, 'fold': 0.0, None: 0.0,
}
_AGGRESSION_STREET_CAP = 2
_AGGRESSION_PREV_CAP   = 3


def _opponent_aggression(game_state: dict) -> float:
    last_action  = game_state.get('last_player_action')
    this_street  = game_state.get('player_raises_this_street', 0)
    prev_streets = game_state.get('player_raises_prev_streets', 0)

    last_weight   = _LAST_ACTION_WEIGHT.get(last_action, 0.0)
    street_weight = min(this_street / _AGGRESSION_STREET_CAP, 1.0)
    prev_weight   = min(prev_streets / _AGGRESSION_PREV_CAP, 1.0)

    score = 0.5 * last_weight + 0.3 * street_weight + 0.2 * prev_weight
    return max(0.0, min(1.0, score))


def compute_decision_features(hand: list, stack: int, game_state: dict) -> dict:
    """Features used by the fuzzy agent, reusable for any hand (system or human)."""
    community_cards = game_state['community_cards']
    pot             = game_state['pot']
    to_call         = game_state['to_call']
    is_button       = game_state['is_button']
    street          = game_state.get('street')

    win_prob     = calculate_win_probability(hand, community_cards)
    pot_odds_val = to_call / (pot + to_call) if to_call > 0 else 0.0
    position_val = 1.0 if is_button else 0.0

    if street in ('flop', 'turn'):
        ppot_val, npot_val = calculate_hand_potential(hand, community_cards)
    else:
        ppot_val, npot_val = 0.0, 0.0

    aggression_val = _opponent_aggression(game_state)
    commitment_val = pot / (pot + stack) if (pot + stack) > 0 else 0.0

    return {
        'win_prob':            win_prob,
        'pot_odds':            pot_odds_val,
        'position':            position_val,
        'ppot':                ppot_val,
        'npot':                npot_val,
        'opponent_aggression': aggression_val,
        'stack_commitment':    commitment_val,
    }


def translate_recommendation(recommendation: str, can_check: bool, has_bet: bool,
                              to_call: int, stack: int) -> str:
    """Maps the fuzzy agent's abstract fold/call/raise output onto the action
    label actually available in this spot (ex: 'raise' -> 'bet' when nothing
    has been wagered yet). Used both to pick the system's real action and to
    label what a human *should* have done, for display/scoring purposes."""
    if can_check and not has_bet:
        return 'bet' if recommendation == 'raise' else 'check'
    if to_call == 0:
        return 'raise' if recommendation == 'raise' else 'check'
    if to_call >= stack:
        return 'fold' if recommendation == 'fold' else 'call'
    return recommendation


class SystemPlayer(Player):
    def __init__(self):
        super().__init__(name='System')
        self.fuzzy_agent     = FuzzyPokerAgent()
        self.last_fuzzy_data = {}

    def decide_action(self, game_state: dict) -> tuple:
        to_call   = game_state['to_call']
        can_check = game_state['can_check']
        has_bet   = game_state['has_bet']
        is_button = game_state['is_button']
        big_blind = game_state['big_blind']

        features = compute_decision_features(self.hand, self.stack, game_state)

        recommendation = self.fuzzy_agent.decide(
            features['win_prob'], features['pot_odds'], features['position'],
            features['ppot'], features['npot'],
            features['opponent_aggression'], features['stack_commitment'],
        )
        action = translate_recommendation(recommendation, can_check, has_bet, to_call, self.stack)

        self.last_fuzzy_data = {
            **features, 'recommendation': recommendation, 'recommended_action': action,
        }

        label = 'IN' if is_button else 'OUT'
        print(
            f"  [FUZZY] win={features['win_prob']:.2f} pot_odds={features['pot_odds']:.2f} pos={label} "
            f"ppot={features['ppot']:.2f} npot={features['npot']:.2f} aggr={features['opponent_aggression']:.2f} "
            f"commit={features['stack_commitment']:.2f} → {recommendation} ({action})"
        )

        raise_amount = min(big_blind * 3, self.stack)
        call_amount  = min(to_call, self.stack)

        if action == 'check': return ('check', 0)
        if action == 'bet':   return ('bet', raise_amount)
        if action == 'raise': return ('raise', raise_amount)
        if action == 'fold':  return ('fold', 0)
        return ('call', call_amount)
