import random
from game_logic.config.game_parameters import INICIAL_BLIND, NUMBER_OF_ROUNDS_TO_RAISE_BLIND
from game_logic.engine.cards_distribution import cards_distribution
from game_logic.engine.hands_evaluation import evaluate_showdown
from game_logic.players.system_player import SystemPlayer
from game_logic.players.user_player import UserPlayer
from game_logic.db.database import init_db
from game_logic.db.recorder import GameRecorder


class GameController:
    """Pure state-machine controller — no I/O. Driven by Streamlit or CLI."""

    def __init__(self):
        init_db()
        self.system   = SystemPlayer()
        self.player   = UserPlayer()
        self.recorder = GameRecorder()

        self.round_number   = 0
        self.blind          = INICIAL_BLIND
        self.button         = random.choice(['player', 'system'])
        self.big_blind_pos  = 'system' if self.button == 'player' else 'player'

        # Community cards revealed progressively
        self.flop  = []
        self.turn  = None
        self.river = None
        self._full_flop  = []
        self._full_turn  = None
        self._full_river = None

        # Betting state
        self.street      = None
        self.pot         = 0
        self.to_call     = 0
        self.can_check   = False
        self.has_bet     = False
        self.last_raiser = None
        self._actors     = []
        self._actor_idx  = 0
        self._is_preflop = False

        # Status: INIT | WAITING_PLAYER | ROUND_OVER | GAME_OVER
        self.status              = 'INIT'
        self.round_winner        = None
        self.showdown            = False
        self.log                 = []
        self._last_player_hand   = []
        self._last_system_hand   = []
        self._last_system_action = None

        self.recorder.start_game()

    # ── Helpers ───────────────────────────────────────────────────────────────

    def _actor(self, name: str):
        return self.player if name == 'player' else self.system

    def _other(self, name: str) -> str:
        return 'system' if name == 'player' else 'player'

    def _current_actor_name(self) -> str:
        return self._actors[self._actor_idx % 2]

    def _community_cards(self) -> list:
        cards = list(self.flop)
        if self.turn:
            cards.append(self.turn)
        if self.river:
            cards.append(self.river)
        return cards

    def _rotate_button(self):
        if self.button == 'player':
            self.button        = 'system'
            self.big_blind_pos = 'player'
        else:
            self.button        = 'player'
            self.big_blind_pos = 'system'

    # ── Round lifecycle ───────────────────────────────────────────────────────

    def start_new_round(self) -> dict:
        if self.round_number > 0:
            self._rotate_button()
        self.round_number += 1

        if self.round_number > 1 and (self.round_number - 1) % NUMBER_OF_ROUNDS_TO_RAISE_BLIND == 0:
            self.blind *= 2
            self.log.append(f'*** Blind aumentou para {self.blind} ***')

        player_cards, system_cards, flop, turn, river = cards_distribution()
        self.player.receive_cards(player_cards)
        self.system.receive_cards(system_cards)
        self._full_flop  = flop
        self._full_turn  = turn
        self._full_river = river
        self.flop  = []
        self.turn  = None
        self.river = None

        sb     = self.blind
        bb     = self.blind * 2
        btn    = self._actor(self.button)
        bb_obj = self._actor(self.big_blind_pos)
        btn.stack    -= sb
        bb_obj.stack -= bb
        self.pot = sb + bb

        self.log.append(f'── Round {self.round_number} | Blind {self.blind} ──')
        self.log.append(f'{btn.name} SB {sb}  {bb_obj.name} BB {bb}  Pot: {self.pot}')

        self.recorder.start_round(self.round_number, self.blind,
                                  player_cards, system_cards)
        self.recorder.set_street('preflop')

        self.street      = 'preflop'
        self._is_preflop = True
        self._actors     = [self.button, self.big_blind_pos]
        self._actor_idx  = 0
        self.to_call     = sb
        self.can_check   = False
        self.has_bet     = True
        self.last_raiser = None
        self.round_winner      = None
        self.showdown          = False
        self.status            = None  # reset so _advance_until_player doesn't return immediately
        self._last_player_hand = []
        self._last_system_hand = []

        return self._advance_until_player()

    # ── Advance engine ────────────────────────────────────────────────────────

    def _advance_until_player(self) -> dict:
        """Run forward applying system actions until player must act or round ends."""
        while True:
            if self.status in ('ROUND_OVER', 'GAME_OVER'):
                return self.get_state()
            if self._current_actor_name() == 'player':
                self.status = 'WAITING_PLAYER'
                return self.get_state()
            self._apply_system_action()

    def _apply_system_action(self):
        gs = {
            'community_cards': self._community_cards(),
            'pot':       self.pot,
            'to_call':   self.to_call,
            'can_check': self.can_check,
            'has_bet':   self.has_bet,
            'is_button': self.button == 'system',
            'big_blind': self.blind * 2,
        }
        action, amount = self.system.decide_action(gs)
        self._apply_action('system', action, amount, self.system.last_fuzzy_data)

    def apply_player_action(self, action: str, amount: int = 0) -> dict:
        if self.status != 'WAITING_PLAYER':
            return self.get_state()
        self._apply_action('player', action, amount)
        return self._advance_until_player()

    # ── Action logic ──────────────────────────────────────────────────────────

    def _apply_action(self, actor_name: str, action: str, amount: int,
                      fuzzy: dict = None):
        actor = self._actor(actor_name)
        other = self._other(actor_name)
        self.recorder.record_action(actor_name, action, amount, fuzzy)

        if actor_name == 'system':
            self._last_system_action = (action, amount)

        if action == 'fold':
            self.log.append(f'{actor.name} foldou.')
            self.round_winner = other
            self._end_round()

        elif action == 'check':
            self.log.append(f'{actor.name} check.')
            if self._actor_idx > 0 and self.last_raiser is None:
                self._next_street()
            else:
                self.can_check  = True
                self._actor_idx += 1

        elif action in ('bet', 'raise'):
            amt = min(amount, actor.stack)
            actor.stack     -= amt
            self.pot        += amt
            self.to_call     = amt
            self.has_bet     = True
            self.can_check   = False
            self.last_raiser = actor_name
            self.log.append(f'{actor.name} {action} {amt}. Pot: {self.pot}')
            self._actor_idx += 1

        elif action == 'call':
            amt = min(self.to_call, actor.stack)
            actor.stack -= amt
            self.pot    += amt
            self.to_call = 0
            self.log.append(f'{actor.name} call {amt}. Pot: {self.pot}')
            # Preflop limp: give BB option to check or raise
            if self._is_preflop and self._actor_idx == 0 and self.last_raiser is None:
                self.can_check  = True
                self._actor_idx += 1
            else:
                self._next_street()

        elif action == 'allin':
            all_in_amt = actor.stack
            other_obj  = self._actor(other)
            # Em heads-up não há side pot: o excesso que o oponente não pode pagar
            # volta imediatamente para quem foi all-in
            effective  = min(all_in_amt, other_obj.stack)
            excess     = all_in_amt - effective

            actor.stack  = excess   # devolve o que não pode ser contestado
            self.pot    += effective
            self.to_call = effective
            self.has_bet = True
            self.last_raiser = actor_name

            if excess > 0:
                self.log.append(f'{actor.name} ALL-IN {effective} (devolvidos {excess}). Pot: {self.pot}')
            else:
                self.log.append(f'{actor.name} ALL-IN {effective}! Pot: {self.pot}')

            self._actor_idx += 1
            if other_obj.stack == 0:
                self._go_to_showdown()

    # ── Street and round transitions ──────────────────────────────────────────

    def _next_street(self):
        order = ['preflop', 'flop', 'turn', 'river']
        idx   = order.index(self.street)

        if idx == len(order) - 1:
            self._go_to_showdown()
            return

        self.street      = order[idx + 1]
        self._is_preflop = False

        if self.street == 'flop':
            self.flop = self._full_flop
        elif self.street == 'turn':
            self.turn = self._full_turn
        elif self.street == 'river':
            self.river = self._full_river

        self.log.append(f'── {self.street.upper()} ──')
        self.to_call     = 0
        self.can_check   = True
        self.has_bet     = False
        self.last_raiser = None
        self._actors     = [self.big_blind_pos, self.button]
        self._actor_idx  = 0
        self.recorder.set_street(self.street)

        # Se alguém está all-in não há mais betting — corre o board e vai ao showdown
        if self.player.stack == 0 or self.system.stack == 0:
            self._go_to_showdown()

    def _go_to_showdown(self):
        self.flop  = self._full_flop
        self.turn  = self._full_turn
        self.river = self._full_river
        self.showdown = True

        community = self._community_cards()
        result = evaluate_showdown(self.player.hand, self.system.hand, community)

        if result == 'tie':
            self.player.stack += self.pot // 2
            self.system.stack += self.pot // 2
            self.round_winner  = 'tie'
            self.log.append('Empate! Pot dividido.')
        else:
            self._actor(result).stack += self.pot
            self.round_winner = result
            self.log.append(f'{self._actor(result).name} ganhou {self.pot} no showdown!')

        self._last_player_hand = list(self.player.hand)
        self._last_system_hand = list(self.system.hand)
        self.recorder.end_round(self.round_winner, self.pot, community)
        self.player.fold()
        self.system.fold()
        self.status = (
            'ROUND_OVER' if self.player.stack > 0 and self.system.stack > 0
            else 'GAME_OVER'
        )

    def _end_round(self):
        self._actor(self.round_winner).stack += self.pot
        self.log.append(f'{self._actor(self.round_winner).name} ganhou {self.pot}!')
        self._last_player_hand = list(self.player.hand)
        self._last_system_hand = list(self.system.hand)
        self.recorder.end_round(self.round_winner, self.pot, self._community_cards())
        self.player.fold()
        self.system.fold()
        self.status = (
            'ROUND_OVER' if self.player.stack > 0 and self.system.stack > 0
            else 'GAME_OVER'
        )

    # ── Public API ────────────────────────────────────────────────────────────

    def get_valid_actions(self) -> list:
        """Returns list of (action, label, default_amount) for player."""
        actor = self.player
        bb    = self.blind * 2
        acts  = []

        if self.can_check and not self.has_bet:
            acts.append(('check', 'Check', 0))
            if actor.stack > 0:
                acts.append(('bet',   'Bet',                     bb * 2))
                acts.append(('allin', f'All-in ({actor.stack})', actor.stack))
        elif self.to_call == 0:
            acts.append(('check', 'Check', 0))
            if actor.stack > 0:
                acts.append(('raise', 'Raise',                   bb * 2))
                acts.append(('allin', f'All-in ({actor.stack})', actor.stack))
        elif self.to_call >= actor.stack:
            acts.append(('fold', 'Fold',                              0))
            acts.append(('call', f'Call all-in ({actor.stack})', actor.stack))
        else:
            acts.append(('fold',  'Fold',                   0))
            acts.append(('call',  f'Call ({self.to_call})', self.to_call))
            if actor.stack > 0:
                acts.append(('raise', 'Raise',                   bb * 2))
                acts.append(('allin', f'All-in ({actor.stack})', actor.stack))

        return acts

    def get_state(self) -> dict:
        round_ended = self.status in ('ROUND_OVER', 'GAME_OVER')
        return {
            'status':          self.status,
            'round_number':    self.round_number,
            'blind':           self.blind,
            'button':          self.button,
            'street':          self.street,
            'pot':             self.pot,
            'to_call':         self.to_call,
            'player_hand':     self._last_player_hand if round_ended else self.player.hand,
            'player_stack':    self.player.stack,
            'system_stack':    self.system.stack,
            'system_hand':     self._last_system_hand if round_ended else self.system.hand,
            'community_cards': self._community_cards(),
            'flop':            self.flop,
            'turn':            self.turn,
            'river':           self.river,
            'log':             list(self.log[-30:]),
            'round_winner':    self.round_winner,
            'showdown':        self.showdown,
            'valid_actions':        self.get_valid_actions() if self.status == 'WAITING_PLAYER' else [],
            'last_system_action':   self._last_system_action,
        }

    def end_game(self):
        if self.player.stack == 0:
            winner = 'system'
        elif self.system.stack == 0:
            winner = 'player'
        else:
            winner = None
        self.recorder.end_game(winner, self.round_number)
