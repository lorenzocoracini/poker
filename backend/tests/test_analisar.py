import csv
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..', 'experimentos'))
import analisar  # noqa: E402

HEADER = ['Carimbo de data/hora', 'Código Participante',
          'N1. Qual é o seu nível de experiência com poker?', 'N2. Familiaridade',
          'F1. Fácil', 'F2. Correto', 'F3. Ajudou', 'F4. Confiaria', 'F5. Mudaria',
          'F6. De modo geral', 'F7. Qual feedback foi mais útil para você?',
          'J1. Divertida', 'J2. Desafiador', 'J3. Sentido', 'J4. Interface',
          'J5. Aprender', 'J6. Praticar']
ROWS = [
    ['t', 'p01', '1 - Nunca joguei', '1', '5', '4', '4', '3', '4', '4', 'Rodada', '5', '4', '4', '5', '5', '4'],
    ['t', 'P2', '3 - Jogo com frequência', '4', '3', '3', '4', '2', '2', '3', 'Partida', '3', '2', '3', '4', '2', '2'],
    ['t', 'P3', '2 - Conheço as regras', '3', '4', '5', '5', '4', '4', '5', 'Rodada', '4', '5', '5', '5', '4', '5'],
]


def _read(path):
    with open(path, newline='', encoding='utf-8') as f:
        return list(csv.DictReader(f))


def test_column_id_maps_forms_titles():
    assert analisar._column_id('N1. Qual é o seu nível?') == 'N1'
    assert analisar._column_id('J3.  As jogadas do agente') == 'J3'
    assert analisar._column_id('Código Participante') == 'codigo'
    assert analisar._column_id('F10. Outra coisa') == 'F10. Outra coisa'  # not an item id
    assert analisar._column_id('Carimbo de data/hora') == 'Carimbo de data/hora'


def test_questionnaire_reads_forms_export(tmp_path):
    src = tmp_path / 'respostas.csv'
    with open(src, 'w', newline='', encoding='utf-8') as f:
        w = csv.writer(f)
        w.writerow(HEADER)
        w.writerows(ROWS)

    analisar.analyze_questionnaire(str(src), str(tmp_path), first_game={'P1': 1, 'P2': 0, 'P3': 1})

    items = {r['item']: r for r in _read(tmp_path / 'quest_itens.csv')}
    assert set(items) == set(analisar.LIKERT_ITEMS + analisar.GAME_ITEMS)
    assert float(items['J4']['mediana']) == 5.0
    people = {r['codigo']: r for r in _read(tmp_path / 'quest_participantes.csv')}
    assert set(people) == {'P1', 'P2', 'P3'}           # codes normalized
    assert people['P1']['grupo'] == 'iniciante' and people['P2']['grupo'] == 'experiente'
    assert people['P1']['venceu'] == '1'
    tests = {(r['comparacao'], r['variavel']) for r in _read(tmp_path / 'quest_testes.csv')}
    assert ('iniciante x experiente', 'J2') in tests and ('venceu x perdeu', 'J3') in tests
