import pytest
from game_logic.engine.cards_distribution import cards_distribution, Deck, Card


def test_card_creation():
    card = Card('A', 'spades')
    assert card.rank == 'A'
    assert card.suit == 'spades'
    assert card.value == 14


def test_card_repr():
    card = Card('K', 'hearts')
    assert repr(card) == 'K of hearts'


def test_card_to_dict():
    card = Card('2', 'clubs')
    assert card.to_dict() == {'rank': '2', 'suit': 'clubs', 'value': 2}


def test_deck_has_52_cards():
    deck = Deck()
    assert len(deck.cards) == 52


def test_deck_no_duplicates():
    deck = Deck()
    reprs = [repr(c) for c in deck.cards]
    assert len(reprs) == len(set(reprs))


def test_deal_removes_cards():
    deck = Deck()
    deck.deal(5)
    assert len(deck.cards) == 47


def test_distribution_correct_sizes():
    player_cards, system_cards, flop_cards, turn_card, river_card = cards_distribution()
    assert len(player_cards) == 2
    assert len(system_cards) == 2
    assert len(flop_cards) == 3
    assert isinstance(turn_card, Card)
    assert isinstance(river_card, Card)


def test_distribution_no_duplicates():
    player_cards, system_cards, flop_cards, turn_card, river_card = cards_distribution()
    all_cards = player_cards + system_cards + flop_cards + [turn_card, river_card]
    reprs = [repr(c) for c in all_cards]
    assert len(reprs) == len(set(reprs))


def test_distribution_all_cards_are_card_instances():
    player_cards, system_cards, flop_cards, turn_card, river_card = cards_distribution()
    all_cards = player_cards + system_cards + flop_cards + [turn_card, river_card]
    for card in all_cards:
        assert isinstance(card, Card)
