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


class SystemPlayer(Player):
    def __init__(self):
        super().__init__(name='System')
        self.fuzzy_agent     = FuzzyPokerAgent()
        self.last_fuzzy_data = {}

    def decide_action(self, game_state: dict) -> tuple:
        community_cards = game_state['community_cards']
        pot             = game_state['pot']
        to_call         = game_state['to_call']
        can_check       = game_state['can_check']
        has_bet         = game_state['has_bet']
        is_button       = game_state['is_button']
        big_blind       = game_state['big_blind']
        street          = game_state.get('street')

        win_prob     = calculate_win_probability(self.hand, community_cards)
        pot_odds_val = to_call / (pot + to_call) if to_call > 0 else 0.0
        position_val = 1.0 if is_button else 0.0

        if street in ('flop', 'turn'):
            ppot_val, npot_val = calculate_hand_potential(self.hand, community_cards)
        else:
            ppot_val, npot_val = 0.0, 0.0

        aggression_val = self._opponent_aggression(game_state)
        commitment_val = pot / (pot + self.stack) if (pot + self.stack) > 0 else 0.0

        recommendation = self.fuzzy_agent.decide(
            win_prob, pot_odds_val, position_val,
            ppot_val, npot_val, aggression_val, commitment_val,
        )

        self.last_fuzzy_data = {
            'win_prob':            win_prob,
            'pot_odds':            pot_odds_val,
            'position':            position_val,
            'ppot':                ppot_val,
            'npot':                npot_val,
            'opponent_aggression': aggression_val,
            'stack_commitment':    commitment_val,
            'recommendation':      recommendation,
        }

        label = 'IN' if is_button else 'OUT'
        print(
            f'  [FUZZY] win={win_prob:.2f} pot_odds={pot_odds_val:.2f} pos={label} '
            f'ppot={ppot_val:.2f} npot={npot_val:.2f} aggr={aggression_val:.2f} '
            f'commit={commitment_val:.2f} → {recommendation}'
        )

        raise_amount = min(big_blind * 3, self.stack)

        if can_check and not has_bet:
            if recommendation == 'raise':
                return ('bet', raise_amount)
            return ('check', 0)

        if to_call == 0:
            if recommendation == 'raise':
                return ('raise', raise_amount)
            return ('check', 0)

        if to_call >= self.stack:
            if recommendation == 'fold':
                return ('fold', 0)
            return ('call', self.stack)

        if recommendation == 'fold':
            return ('fold', 0)
        if recommendation == 'call':
            return ('call', to_call)
        return ('raise', raise_amount)

    def _opponent_aggression(self, game_state: dict) -> float:
        last_action   = game_state.get('last_player_action')
        this_street   = game_state.get('player_raises_this_street', 0)
        prev_streets  = game_state.get('player_raises_prev_streets', 0)

        last_weight   = _LAST_ACTION_WEIGHT.get(last_action, 0.0)
        street_weight = min(this_street / _AGGRESSION_STREET_CAP, 1.0)
        prev_weight   = min(prev_streets / _AGGRESSION_PREV_CAP, 1.0)

        score = 0.5 * last_weight + 0.3 * street_weight + 0.2 * prev_weight
        return max(0.0, min(1.0, score))
