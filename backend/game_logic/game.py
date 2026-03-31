from game_logic.config.game_parameters import STACK_INICIAL, INICIAL_BLIND, NUMBER_OF_ROUNDS_TO_RAISE_BLIND
from game_logic.engine.cards_distribution import cards_distribution
from game_logic.players.system_player import SystemPlayer
from game_logic.players.user_player import UserPlayer
import random


class PokerGame:
    def __init__(self):
        self.system = SystemPlayer()
        self.player = UserPlayer()
        self.round_number = 1
        self.blind = INICIAL_BLIND
        self.button = self._set_first_button()

    def _set_first_button(self):
        button = random.choice(['player', 'system'])
        self.big_blind = 'system' if button == 'player' else 'player'
        return button

    def _rotate_button(self):
        if self.button == 'player':
            self.button = 'system'
            self.big_blind = 'player'
        else:
            self.button = 'player'
            self.big_blind = 'system'

    def _maybe_raise_blind(self):
        if self.round_number % NUMBER_OF_ROUNDS_TO_RAISE_BLIND == 0:
            self.blind *= 2
            print(f'\n*** BLIND AUMENTOU PARA {self.blind} ***')

    def _get_actor(self, role: str) -> object:
        return self.player if role == 'player' else self.system

    def _print_separator(self):
        print('\n' + '─' * 50)

    def _print_board(self, flop=None, turn=None, river=None):
        print('\n[ BOARD ]')
        if flop:
            print(f'  Flop  : {flop}')
        if turn:
            print(f'  Turn  : {turn}')
        if river:
            print(f'  River : {river}')

    def _print_stacks(self):
        print(f'  {self.player.name} stack : {self.player.stack}')
        print(f'  {self.system.name} stack : {self.system.stack}')

    def _print_round_info(self):
        self._print_separator()
        print(f'ROUND {self.round_number}')
        print(f'Blind : {self.blind} | Big Blind : {self.blind * 2}')
        print(f'Button: {self.button.upper()} | BB: {self.big_blind.upper()}')
        self._print_stacks()

    def _get_bet_multiplier(self, actor) -> int:
        while True:
            try:
                mult = int(input('Multiplicador do bet (2, 3, 4, 5...): '))
                amount = self.blind * 2 * mult
                if mult < 2:
                    print('Mínimo é 2x.')
                elif amount > actor.stack:
                    print(f'Stack insuficiente. Stack: {actor.stack}')
                else:
                    return mult
            except ValueError:
                print('Digite um número.')

    def _get_raise_multiplier(self, actor) -> int:
        while True:
            try:
                mult = int(input('Multiplicador do raise (2, 3, 4, 5...): '))
                amount = self.blind * 2 * mult
                if mult < 2:
                    print('Mínimo é 2x.')
                elif amount > actor.stack:
                    print(f'Stack insuficiente. Stack: {actor.stack}')
                else:
                    return mult
            except ValueError:
                print('Digite um número.')

    def _get_action(self, actor_name: str, pot: int, to_call: int, can_check: bool, has_bet: bool) -> tuple:
        actor = self._get_actor(actor_name)
        print(f'\n[ {actor.name.upper()} ] stack: {actor.stack} | pot: {pot} | to call: {to_call}')
        print(f'  Suas cartas: {actor.hand}')
        print('Opções:')

        options = []

        if can_check and not has_bet:
            options.append('check')
            options.append('bet (2x, 3x, 4x, 5x...)')
            options.append('all-in')
        elif to_call == 0:
            options.append('check')
            options.append('raise (2x, 3x, 4x, 5x...)')
            options.append('all-in')
        elif to_call >= actor.stack:
            options.append('fold')
            options.append(f'call ({actor.stack}) - ALL-IN')
        else:
            options.append('fold')
            options.append(f'call ({to_call})')
            options.append('raise (2x, 3x, 4x, 5x...)')
            options.append('all-in')

        for i, opt in enumerate(options, start=1):
            print(f'  {i} - {opt}')

        while True:
            choice = input('Ação: ').strip()

            if can_check and not has_bet:
                if choice == '1':
                    return ('check', 0)
                elif choice == '2':
                    mult = self._get_bet_multiplier(actor)
                    return ('bet', self.blind * 2 * mult)
                elif choice == '3':
                    return ('allin', actor.stack)
                else:
                    print('Opção inválida, tente novamente.')

            elif to_call == 0:
                if choice == '1':
                    return ('check', 0)
                elif choice == '2':
                    mult = self._get_raise_multiplier(actor)
                    return ('raise', self.blind * 2 * mult)
                elif choice == '3':
                    return ('allin', actor.stack)
                else:
                    print('Opção inválida, tente novamente.')

            elif to_call >= actor.stack:
                if choice == '1':
                    return ('fold', 0)
                elif choice == '2':
                    return ('call', actor.stack)
                else:
                    print('Opção inválida, tente novamente.')

            else:
                if choice == '1':
                    return ('fold', 0)
                elif choice == '2':
                    return ('call', min(to_call, actor.stack))
                elif choice == '3':
                    mult = self._get_raise_multiplier(actor)
                    return ('raise', self.blind * 2 * mult)
                elif choice == '4':
                    return ('allin', actor.stack)
                else:
                    print('Opção inválida, tente novamente.')

    def _betting_round(self, first_actor: str, pot: int, to_call: int = 0, can_check: bool = False, is_preflop: bool = False, has_bet: bool = False) -> tuple:
        second_actor = 'system' if first_actor == 'player' else 'player'
        actors = [first_actor, second_actor]
        last_raiser = None
        i = 0

        while True:
            current = actors[i % 2]
            actor_obj = self._get_actor(current)

            if actor_obj.stack == 0:
                return pot, None

            action, amount = self._get_action(current, pot, to_call, can_check, has_bet)

            if action == 'fold':
                print(f'\n{actor_obj.name} foldou!')
                winner = second_actor if current == first_actor else first_actor
                return pot, winner

            elif action == 'check':
                print(f'{actor_obj.name} check.')
                if i > 0 and last_raiser is None:
                    return pot, None
                can_check = True

            elif action == 'bet':
                actor_obj.stack -= amount
                pot += amount
                to_call = amount
                has_bet = True
                can_check = False
                last_raiser = current
                print(f'{actor_obj.name} bet {amount}. Pot: {pot}')

            elif action == 'call':
                actual_call = min(amount, actor_obj.stack)
                actor_obj.stack -= actual_call
                pot += actual_call
                to_call = 0
                print(f'{actor_obj.name} call {actual_call}. Pot: {pot}')
                if is_preflop and i == 0 and last_raiser is None:
                    can_check = True
                else:
                    return pot, None

            elif action == 'raise':
                actor_obj.stack -= amount
                pot += amount
                to_call = amount
                has_bet = True
                can_check = False
                last_raiser = current
                print(f'{actor_obj.name} raise {amount}. Pot: {pot}')

            elif action == 'allin':
                actor_obj.stack -= amount
                pot += amount
                to_call = amount
                has_bet = True
                last_raiser = current
                print(f'{actor_obj.name} ALL-IN {amount}! Pot: {pot}')
                other = second_actor if current == first_actor else first_actor
                other_obj = self._get_actor(other)
                if other_obj.stack == 0:
                    return pot, None

            i += 1

    def new_round(self):
        if self.round_number > 1:
            self._rotate_button()
        self._maybe_raise_blind()
        self._print_round_info()

        player_cards, system_cards, flop, turn, river = cards_distribution()
        self.player.receive_cards(player_cards)
        self.system.receive_cards(system_cards)

        print(f'\n[ {self.player.name.upper()} ] Cartas: {self.player.hand}')
        print(f'[ {self.system.name.upper()} ] Cartas: {self.system.hand}')

        print('\n── PRE-FLOP ──')
        small_blind = self.blind
        big_blind = self.blind * 2

        button_obj = self._get_actor(self.button)
        bb_obj = self._get_actor(self.big_blind)

        button_obj.stack -= small_blind
        bb_obj.stack -= big_blind
        pot = small_blind + big_blind

        print(f'{button_obj.name} posta SB {small_blind}. {bb_obj.name} posta BB {big_blind}. Pot: {pot}')

        pot, winner = self._betting_round(
            first_actor=self.button,
            pot=pot,
            to_call=small_blind,
            can_check=False,
            is_preflop=True,
            has_bet=True
        )
        if winner:
            return self._end_round(pot, winner)

        print('\n── FLOP ──')
        self._print_board(flop=flop)
        pot, winner = self._betting_round(first_actor=self.big_blind, pot=pot, can_check=True)
        if winner:
            return self._end_round(pot, winner)

        print('\n── TURN ──')
        self._print_board(flop=flop, turn=turn)
        pot, winner = self._betting_round(first_actor=self.big_blind, pot=pot, can_check=True)
        if winner:
            return self._end_round(pot, winner)

        print('\n── RIVER ──')
        self._print_board(flop=flop, turn=turn, river=river)
        pot, winner = self._betting_round(first_actor=self.big_blind, pot=pot, can_check=True)
        if winner:
            return self._end_round(pot, winner)

        return self._showdown(pot, flop, turn, river)

    def _end_round(self, pot: int, winner: str) -> int:
        winner_obj = self._get_actor(winner)
        winner_obj.stack += pot
        print(f'\n*** {winner_obj.name} ganhou o pot de {pot}! ***')
        self._print_stacks()
        self.player.fold()
        self.system.fold()
        return pot

    def _showdown(self, pot: int, flop, turn, river) -> int:
        print('\n── SHOWDOWN ──')
        self._print_board(flop=flop, turn=turn, river=river)
        print(f'  {self.player.name}: {self.player.hand}')
        print(f'  {self.system.name}: {self.system.hand}')
        print('\n[ Hand evaluator ainda não implementado — escolha o vencedor ]')
        print('  1 - Player vence')
        print('  2 - System vence')
        print('  3 - Empate')

        while True:
            choice = input('Vencedor: ').strip()
            if choice == '1':
                return self._end_round(pot, 'player')
            elif choice == '2':
                return self._end_round(pot, 'system')
            elif choice == '3':
                self.player.stack += pot // 2
                self.system.stack += pot // 2
                print(f'\nEmpate! Pot dividido.')
                self._print_stacks()
                return pot
            else:
                print('Opção inválida.')

    def run(self):
        print('═' * 50)
        print('     TEXAS HOLD\'EM HEADS-UP')
        print('═' * 50)

        while self.player.stack > 0 and self.system.stack > 0:
            self.new_round()
            self.round_number += 1
            input('\nPressione ENTER para próxima rodada...')

        self._print_separator()
        if self.player.stack == 0:
            print(f'\n*** {self.system.name} VENCEU O JOGO! ***')
        else:
            print(f'\n*** {self.player.name} VENCEU O JOGO! ***')


if __name__ == '__main__':
    game = PokerGame()
    game.run()