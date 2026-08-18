from .base_player import Player
from engine.fuzzy.fuzzy_agent import FuzzyPokerAgent
from engine.fuzzy.hand_strength import calculate_win_probability


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

        win_prob     = calculate_win_probability(self.hand, community_cards)
        pot_odds_val = to_call / (pot + to_call) if to_call > 0 else 0.0
        position_val = 1.0 if is_button else 0.0

        recommendation = self.fuzzy_agent.decide(win_prob, pot_odds_val, position_val)

        self.last_fuzzy_data = {
            'win_prob':       win_prob,
            'pot_odds':       pot_odds_val,
            'position':       position_val,
            'recommendation': recommendation,
        }

        label = 'IN' if is_button else 'OUT'
        print(f'  [FUZZY] win={win_prob:.2f} pot_odds={pot_odds_val:.2f} pos={label} → {recommendation}')

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
