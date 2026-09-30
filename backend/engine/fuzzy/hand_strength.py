import random
from treys import Card as TreysCard, Evaluator
from engine.game.hands_evaluation import to_treys
from engine.game.cards_distribution import RANKS, SUITS

_SUIT_MAP = {'hearts': 'h', 'diamonds': 'd', 'clubs': 'c', 'spades': 's'}
_RANK_MAP = {'10': 'T'}


def _build_remaining_deck(used_treys: set) -> list:
    remaining = []
    for rank in RANKS:
        for suit in SUITS:
            r = _RANK_MAP.get(rank, rank)
            s = _SUIT_MAP[suit]
            card = TreysCard.new(f'{r}{s}')
            if card not in used_treys:
                remaining.append(card)
    return remaining


def calculate_win_probability(hole_cards: list, community_cards: list, n_simulations: int = 500) -> float:
    evaluator = Evaluator()

    my_treys = [to_treys(c) for c in hole_cards]
    board_treys = [to_treys(c) for c in community_cards]
    used = set(my_treys + board_treys)
    remaining = _build_remaining_deck(used)

    n_community_needed = 5 - len(community_cards)
    wins = 0
    ties = 0

    for _ in range(n_simulations):
        sample = random.sample(remaining, 2 + n_community_needed)
        opp_hand = sample[:2]
        extra_board = sample[2:]
        full_board = board_treys + extra_board

        my_score = evaluator.evaluate(full_board, my_treys)
        opp_score = evaluator.evaluate(full_board, opp_hand)

        if my_score < opp_score:
            wins += 1
        elif my_score == opp_score:
            ties += 1

    return (wins + ties * 0.5) / n_simulations


def calculate_hand_potential(hole_cards: list, community_cards: list, n_simulations: int = 500) -> tuple:
    """Positive/negative potential (Billings 2006): probability of a hand's rank
    improving/worsening relative to a random opponent once the remaining board is dealt.
    Only meaningful on flop/turn (3 or 4 community cards) — callers must gate this.
    """
    evaluator = Evaluator()

    my_treys = [to_treys(c) for c in hole_cards]
    board_treys = [to_treys(c) for c in community_cards]
    used = set(my_treys + board_treys)
    remaining = _build_remaining_deck(used)

    n_community_needed = 5 - len(community_cards)

    ahead_to_ahead = ahead_to_tied = ahead_to_behind = 0
    behind_to_ahead = behind_to_tied = behind_to_behind = 0
    tied_to_ahead = tied_to_tied = tied_to_behind = 0

    for _ in range(n_simulations):
        sample = random.sample(remaining, 2 + n_community_needed)
        opp_hand = sample[:2]
        extra_board = sample[2:]
        full_board = board_treys + extra_board

        my_current = evaluator.evaluate(board_treys, my_treys)
        opp_current = evaluator.evaluate(board_treys, opp_hand)
        my_final = evaluator.evaluate(full_board, my_treys)
        opp_final = evaluator.evaluate(full_board, opp_hand)

        current = 'ahead' if my_current < opp_current else 'behind' if my_current > opp_current else 'tied'
        final   = 'ahead' if my_final   < opp_final   else 'behind' if my_final   > opp_final   else 'tied'

        if current == 'ahead':
            if final == 'ahead':   ahead_to_ahead  += 1
            elif final == 'tied':  ahead_to_tied   += 1
            else:                  ahead_to_behind += 1
        elif current == 'behind':
            if final == 'ahead':   behind_to_ahead  += 1
            elif final == 'tied':  behind_to_tied   += 1
            else:                  behind_to_behind += 1
        else:
            if final == 'ahead':   tied_to_ahead  += 1
            elif final == 'tied':  tied_to_tied   += 1
            else:                  tied_to_behind += 1

    ahead_total  = ahead_to_ahead + ahead_to_tied + ahead_to_behind
    behind_total = behind_to_ahead + behind_to_tied + behind_to_behind
    tied_total   = tied_to_ahead + tied_to_tied + tied_to_behind

    ppot_denom = behind_total + tied_total
    npot_denom = ahead_total + tied_total

    ppot = (behind_to_ahead + tied_to_ahead + 0.5 * behind_to_tied) / ppot_denom if ppot_denom > 0 else 0.0
    npot = (ahead_to_behind + tied_to_behind + 0.5 * ahead_to_tied) / npot_denom if npot_denom > 0 else 0.0

    return ppot, npot
