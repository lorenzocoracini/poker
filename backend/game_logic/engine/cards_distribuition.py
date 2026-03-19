import random

cards_options = ['2','3','4','5','6','7','8','9','10','j','q','k','a']
suits_options = ['hearts','diamonds','clubs','spades']

def cards_generation():
    cards = {}
    cards_ids = []
    id_count = 1
    for c in cards_options:
        for s in suits_options:
            card = {}
            card['card'] = c
            card['suit'] = s
            cards[id_count] = card
            cards_ids.append(id_count)
            id_count += 1

    return cards, cards_ids

cards, cards_ids = cards_generation()



def cards_distribuition():
    cards, cards_ids = cards_generation()

    # players cards
    player_random_card_1_id = random.choice(cards_ids)
    cards_ids.remove(player_random_card_1_id)
    player_card_1 = cards[player_random_card_1_id]


    player_random_card_2_id = random.choice(cards_ids)
    cards_ids.remove(player_random_card_2_id)
    player_card_2 = cards[player_random_card_2_id]


    player_cards = [player_card_1, player_card_2]
    
   
    # system cards

    system_random_card_1_id = random.choice(cards_ids)
    cards_ids.remove(system_random_card_1_id)
    system_card_1 = cards[system_random_card_1_id]

    system_random_card_2_id = random.choice(cards_ids)
    cards_ids.remove(system_random_card_2_id)
    system_card_2 = cards[system_random_card_2_id]


    system_cards = [system_card_1, system_card_2]

    # Board cards
    board_card_1_id = random.choice(cards_ids)
    cards_ids.remove(board_card_1_id)
    board_card_1 = cards[board_card_1_id]

    board_card_2_id = random.choice(cards_ids)
    cards_ids.remove(board_card_2_id)
    board_card_2 = cards[board_card_2_id]

    board_card_3_id = random.choice(cards_ids)
    cards_ids.remove(board_card_3_id)
    board_card_3 = cards[board_card_3_id]

    flop_cards = [board_card_1, board_card_2, board_card_3]

    board_card_4_id = random.choice(cards_ids)
    cards_ids.remove(board_card_4_id)
    board_card_4 = cards[board_card_4_id]

    turn_card = board_card_4

    board_card_5_id = random.choice(cards_ids)
    cards_ids.remove(board_card_5_id)
    board_card_5 = cards[board_card_5_id]

    river_card = board_card_5

    return player_cards, system_cards, flop_cards, turn_card, river_card


player_cards, system_cards, flop_cards, turn_card, river_card = cards_distribuition()

print(' -- Player Card --')
print(player_cards)

print(' -- System Card --')
print(system_cards)

print(' -- Board Cards --')
print('Flop ->', flop_cards)
print('Turn >', turn_card)
print('River ->', river_card)