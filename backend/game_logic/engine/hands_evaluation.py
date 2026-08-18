from treys import Card as TreysCard, Evaluator

_SUIT_MAP = {'hearts': 'h', 'diamonds': 'd', 'clubs': 'c', 'spades': 's'}
_RANK_MAP = {'10': 'T'}

def to_treys(card) -> int:
    rank = _RANK_MAP.get(card.rank, card.rank)
    suit = _SUIT_MAP[card.suit]
    return TreysCard.new(f'{rank}{suit}')


_HAND_RANK_PT = {
    'High Card':       'Carta alta',
    'Pair':            'Um par',
    'Two Pair':        'Dois pares',
    'Three of a Kind': 'Trinca',
    'Straight':        'Sequência',
    'Flush':           'Flush',
    'Full House':      'Full House',
    'Four of a Kind':  'Quadra',
    'Straight Flush':  'Straight Flush',
    'Royal Flush':     'Royal Flush',
}


def hand_description(hand: list, community_cards: list) -> str:
    evaluator = Evaluator()
    board  = [to_treys(c) for c in community_cards]
    score  = evaluator.evaluate(board, [to_treys(c) for c in hand])
    rank   = evaluator.class_to_string(evaluator.get_rank_class(score))
    return _HAND_RANK_PT.get(rank, rank)


def evaluate_showdown(player_hand: list, system_hand: list, community_cards: list) -> tuple:
    """Returns (winner, player_desc, system_desc).
    winner: 'player' | 'system' | 'tie'
    """
    evaluator = Evaluator()
    board   = [to_treys(c) for c in community_cards]
    p_score = evaluator.evaluate(board, [to_treys(c) for c in player_hand])
    s_score = evaluator.evaluate(board, [to_treys(c) for c in system_hand])
    p_desc  = _HAND_RANK_PT.get(evaluator.class_to_string(evaluator.get_rank_class(p_score)), '')
    s_desc  = _HAND_RANK_PT.get(evaluator.class_to_string(evaluator.get_rank_class(s_score)), '')

    if p_score < s_score:
        winner = 'player'
    elif s_score < p_score:
        winner = 'system'
    else:
        winner = 'tie'

    return winner, p_desc, s_desc
