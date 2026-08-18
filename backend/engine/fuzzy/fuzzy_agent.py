import numpy as np
import skfuzzy as fuzz
from skfuzzy import control as ctrl


class FuzzyPokerAgent:
    def __init__(self):
        self._build_system()

    def _build_system(self):
        # --- Antecedentes ---
        hand_strength = ctrl.Antecedent(np.arange(0, 1.01, 0.01), 'hand_strength')
        pot_odds      = ctrl.Antecedent(np.arange(0, 1.01, 0.01), 'pot_odds')
        position      = ctrl.Antecedent(np.arange(0, 1.01, 0.01), 'position')

        # --- Consequente ---
        action_score  = ctrl.Consequent(np.arange(0, 1.01, 0.01), 'action_score')

        # --- Funções de pertinência: hand_strength ---
        hand_strength['fraca']       = fuzz.trapmf(hand_strength.universe, [0,    0,    0.30, 0.45])
        hand_strength['media']       = fuzz.trimf( hand_strength.universe, [0.35, 0.50, 0.65])
        hand_strength['forte']       = fuzz.trimf( hand_strength.universe, [0.55, 0.70, 0.85])
        hand_strength['muito_forte'] = fuzz.trapmf(hand_strength.universe, [0.75, 0.90, 1.00, 1.00])

        # --- Funções de pertinência: pot_odds ---
        pot_odds['baixo'] = fuzz.trapmf(pot_odds.universe, [0,    0,    0.20, 0.35])
        pot_odds['medio'] = fuzz.trimf( pot_odds.universe, [0.25, 0.40, 0.55])
        pot_odds['alto']  = fuzz.trapmf(pot_odds.universe, [0.45, 0.60, 1.00, 1.00])

        # --- Funções de pertinência: position ---
        position['fora']   = fuzz.trapmf(position.universe, [0,    0,    0.30, 0.50])
        position['dentro'] = fuzz.trapmf(position.universe, [0.50, 0.70, 1.00, 1.00])

        # --- Funções de pertinência: action_score ---
        action_score['fold']  = fuzz.trapmf(action_score.universe, [0,    0,    0.20, 0.35])
        action_score['call']  = fuzz.trimf( action_score.universe, [0.25, 0.50, 0.75])
        action_score['raise'] = fuzz.trapmf(action_score.universe, [0.65, 0.80, 1.00, 1.00])

        # --- Regras fuzzy ---
        rules = [
            # Mão muito forte: sempre raise
            ctrl.Rule(hand_strength['muito_forte'], action_score['raise']),

            # Mão forte com posição: raise; sem posição: call (proteção de pot)
            ctrl.Rule(hand_strength['forte'] & position['dentro'], action_score['raise']),
            ctrl.Rule(hand_strength['forte'] & position['fora'],   action_score['call']),

            # Mão forte mesmo com pot odds altos: ainda vale chamar
            ctrl.Rule(hand_strength['forte'] & pot_odds['alto'], action_score['call']),

            # Mão média: decisão baseada em pot odds e posição
            ctrl.Rule(hand_strength['media'] & pot_odds['baixo'], action_score['call']),
            ctrl.Rule(hand_strength['media'] & pot_odds['medio'], action_score['call']),
            ctrl.Rule(hand_strength['media'] & pot_odds['alto'],  action_score['fold']),
            ctrl.Rule(hand_strength['media'] & position['dentro'], action_score['call']),
            ctrl.Rule(hand_strength['media'] & position['fora'],   action_score['fold']),

            # Mão fraca: fold em qualquer situação
            ctrl.Rule(hand_strength['fraca'] & pot_odds['baixo'], action_score['fold']),
            ctrl.Rule(hand_strength['fraca'] & pot_odds['medio'], action_score['fold']),
            ctrl.Rule(hand_strength['fraca'] & pot_odds['alto'],  action_score['fold']),
            ctrl.Rule(hand_strength['fraca'] & position['fora'],  action_score['fold']),

            # Mão fraca com posição: call ocasional (tentativa de roubo)
            ctrl.Rule(hand_strength['fraca'] & position['dentro'], action_score['call']),
        ]

        system = ctrl.ControlSystem(rules)
        self._sim = ctrl.ControlSystemSimulation(system)

    def decide(self, hand_strength_val: float, pot_odds_val: float, position_val: float) -> str:
        self._sim.input['hand_strength'] = float(np.clip(hand_strength_val, 0.01, 0.99))
        self._sim.input['pot_odds']      = float(np.clip(pot_odds_val,      0.01, 0.99))
        self._sim.input['position']      = float(np.clip(position_val,      0.01, 0.99))

        try:
            self._sim.compute()
            score = self._sim.output['action_score']
        except Exception:
            return 'call'

        if score < 0.35:
            return 'fold'
        elif score < 0.65:
            return 'call'
        else:
            return 'raise'
