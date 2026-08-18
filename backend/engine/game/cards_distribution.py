import random

RANKS = ['2', '3', '4', '5', '6', '7', '8', '9', '10', 'J', 'Q', 'K', 'A']
SUITS = ['hearts', 'diamonds', 'clubs', 'spades']

RANK_VALUES = {r: i for i, r in enumerate(RANKS, start=2)}  # '2'->2, 'A'->14


class Card:
    def __init__(self, rank: str, suit: str):
        self.rank = rank
        self.suit = suit
        self.value = RANK_VALUES[rank]

    def __repr__(self):
        return f"{self.rank} of {self.suit}"

    def to_dict(self):
        return {'rank': self.rank, 'suit': self.suit, 'value': self.value}


class Deck:
    def __init__(self):
        self.cards = [Card(rank, suit) for suit in SUITS for rank in RANKS]
        random.shuffle(self.cards)

    def deal(self, n: int = 1) -> list[Card]:
        dealt = []
        for i in range(n):
            card = self.cards.pop()
            dealt.append(card)
        return dealt


def cards_distribution() -> tuple:
    deck = Deck()

    player_cards = deck.deal(2)
    system_cards = deck.deal(2)
    flop_cards   = deck.deal(3)
    turn_card    = deck.deal(1)[0]
    river_card   = deck.deal(1)[0]

    return player_cards, system_cards, flop_cards, turn_card, river_card