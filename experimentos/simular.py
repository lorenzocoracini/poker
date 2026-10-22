"""Automatic games between the fuzzy agent and simple baseline opponents.

The baseline takes the seat of the human player in the GameController, so the
agent plays exactly as in the interface (same parameters, 500 Monte Carlo
simulations). Each game is stored in its own SQLite file, apart from the
development and user-study games; `games.participant_code` holds the baseline
name prefixed with 'SIM-'.

Usage (from code/poker):
    python3 experimentos/simular.py --partidas 200 --semente 42
"""
import argparse
import contextlib
import io
import os
import random
import sqlite3
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, '..', 'backend'))

import db.database as database  # noqa: E402
from engine.game.controller import GameController  # noqa: E402

# Safety cap only: blinds double every 10 rounds, so games end long before this.
MAX_ROUNDS = 1000


# ── Baseline opponents ────────────────────────────────────────────────────────
# Each one receives the valid actions [(action, label, default_amount)] and
# returns (action, amount). Bets and raises use the engine's default amount.

def random_opponent(valid, rng):
    action, _, amount = rng.choice(valid)
    return action, amount


def calling_station(valid, rng):
    acts = {a: amt for a, _, amt in valid}
    if 'check' in acts:
        return 'check', 0
    return 'call', acts['call']


def maniac(valid, rng):
    acts = {a: amt for a, _, amt in valid}
    for action in ('bet', 'raise'):
        if action in acts:
            return action, acts[action]
    if 'call' in acts:
        return 'call', acts['call']
    return 'check', 0


OPPONENTS = {
    'aleatorio':      random_opponent,
    'sempre_paga':    calling_station,
    'sempre_aumenta': maniac,
}


# ── Simulation ────────────────────────────────────────────────────────────────

def play_game(opponent_name: str, seed: str) -> dict:
    """Plays one full game until a player runs out of chips."""
    # Seeds the global RNG used by deck shuffling, Monte Carlo and button choice,
    # and a separate one for the opponent, so each game is reproducible alone.
    random.seed(seed)
    rng = random.Random(f'{seed}-oponente')
    policy = OPPONENTS[opponent_name]

    # The agent prints one line per decision; silence it during simulation.
    with contextlib.redirect_stdout(io.StringIO()):
        ctrl  = GameController(participant_code=f'SIM-{opponent_name}')
        state = ctrl.start_new_round()
        while state['status'] != 'GAME_OVER' and ctrl.round_number < MAX_ROUNDS:
            if state['status'] == 'ROUND_OVER':
                state = ctrl.start_new_round()
                continue
            action, amount = policy(state['valid_actions'], rng)
            state = ctrl.apply_player_action(action, amount)
        ctrl.end_game()

    return {
        'game_id': ctrl.recorder.game_id,
        'rounds':  ctrl.round_number,
        'agent_won': state['system_stack'] > 0 and state['player_stack'] == 0,
    }


def check_empty(db_path: str, append: bool):
    """Refuses a database that already has games, unless `append` is set: games of
    two runs with the same seed would be counted twice by the analysis."""
    if append or not os.path.exists(db_path):
        return
    conn = sqlite3.connect(db_path)
    try:
        n = conn.execute('SELECT COUNT(*) FROM games').fetchone()[0]
    except sqlite3.OperationalError:
        n = 0  # file without the games table yet
    finally:
        conn.close()
    if n:
        sys.exit(f'O banco {db_path} já tem {n} partida(s). Apague o arquivo para começar '
                 f'uma simulação nova ou use --acrescentar para somar a ele.')


def main():
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument('--partidas', type=int, default=200,
                        help='games per opponent (default: 200)')
    parser.add_argument('--semente', type=int, default=42,
                        help='base random seed (default: 42)')
    parser.add_argument('--oponentes', nargs='+', choices=list(OPPONENTS),
                        default=list(OPPONENTS), help='opponents to play against')
    parser.add_argument('--db', default=os.path.join(HERE, 'simulacao.db'),
                        help='output SQLite file (default: experimentos/simulacao.db)')
    parser.add_argument('--acrescentar', action='store_true',
                        help='add games to a database that already has some')
    args = parser.parse_args()

    check_empty(args.db, args.acrescentar)
    database.DB_PATH = args.db
    print(f'Banco: {args.db}', file=sys.stderr)

    for name in args.oponentes:
        wins, rounds, start = 0, 0, time.time()
        for i in range(args.partidas):
            result = play_game(name, f'{args.semente}-{name}-{i}')
            wins   += result['agent_won']
            rounds += result['rounds']
            print(f'\r{name}: {i + 1}/{args.partidas}', end='', file=sys.stderr)
        elapsed = time.time() - start
        print(
            f'\r{name}: {args.partidas} partidas, agente venceu {wins} '
            f'({wins / args.partidas:.0%}), {rounds / args.partidas:.1f} rodadas/partida, '
            f'{elapsed / args.partidas:.1f} s/partida',
            file=sys.stderr,
        )


if __name__ == '__main__':
    main()
