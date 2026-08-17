from treys import Card as TreysCard, Evaluator

_SUIT_MAP = {'hearts': 'h', 'diamonds': 'd', 'clubs': 'c', 'spades': 's'}
_RANK_MAP = {'10': 'T'}

def to_treys(card) -> int:
    rank = _RANK_MAP.get(card.rank, card.rank)
    suit = _SUIT_MAP[card.suit]
    return TreysCard.new(f'{rank}{suit}')


def evaluate_showdown(player_hand: list, system_hand: list, community_cards: list) -> str:
    evaluator = Evaluator()
    board = [to_treys(c) for c in community_cards]
    p_score = evaluator.evaluate(board, [to_treys(c) for c in player_hand])
    s_score = evaluator.evaluate(board, [to_treys(c) for c in system_hand])

    if p_score < s_score:
        return 'player'
    elif s_score < p_score:
        return 'system'
    else:
        return 'tie'
