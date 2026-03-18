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
print(cards)
print(cards_ids)



def cards_distribuition():
    cards, cards_ids = cards_generation()

    print(cards)
    print(cards_ids)
    print('-----')

    # players cards
    player_random_card_1_id = random.choice(cards_ids)
    cards_ids.remove(player_random_card_1_id)
    player_card_1 = cards[player_random_card_1_id]

    print(cards_ids)
    print('ID Card 1 Player ->', player_random_card_1_id)
    print('Card 1 Player ->',player_card_1)
    print('-----')


    player_random_card_2_id = random.choice(cards_ids)
    cards_ids.remove(player_random_card_2_id)
    player_card_2 = cards[player_random_card_2_id]

    
    print(cards_ids)
    print('ID Card 2 Player ->',player_random_card_2_id)
    print(' Card 2 Player ->',player_card_2)
    print('-----')

    # system cards
    print(cards_ids)



cards_distribuition()