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
