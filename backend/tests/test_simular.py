import os
import sys

import pytest

import db.database as database

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..', 'experimentos'))
import simular  # noqa: E402


@pytest.fixture
def temp_db(tmp_path, monkeypatch):
    monkeypatch.setattr(database, 'DB_PATH', str(tmp_path / 'sim.db'))
    return database


@pytest.mark.parametrize('name', list(simular.OPPONENTS))
def test_baselines_return_a_valid_action(name):
    import random
    rng = random.Random(0)
    spots = [
        [('check', 'Check', 0), ('bet', 'Bet', 40), ('allin', 'All-in', 600)],
        [('fold', 'Fold', 0), ('call', 'Call (20)', 20), ('raise', 'Raise', 40)],
        [('fold', 'Fold', 0), ('call', 'Call all-in (15)', 15)],
    ]
    for valid in spots:
        action, _ = simular.OPPONENTS[name](valid, rng)
        assert action in [a for a, _, _ in valid]


def test_play_game_finishes_and_is_reproducible(temp_db):
    first  = [simular.play_game('aleatorio', f'teste-{i}') for i in range(2)]
    second = [simular.play_game('aleatorio', f'teste-{i}') for i in range(2)]

    for a, b in zip(first, second):
        assert (a['rounds'], a['agent_won']) == (b['rounds'], b['agent_won'])

    conn = temp_db.get_connection()
    rows = conn.execute("SELECT participant_code, winner FROM games").fetchall()
    conn.close()
    assert len(rows) == 4
    assert all(r['participant_code'] == 'SIM-aleatorio' for r in rows)
    assert all(r['winner'] in ('player', 'system') for r in rows)


def test_check_empty_refuses_database_with_games(tmp_path, monkeypatch):
    db_path = tmp_path / 'cheio.db'
    monkeypatch.setattr(database, 'DB_PATH', str(db_path))
    database.init_db()
    simular.check_empty(str(db_path), append=False)          # empty: accepted
    simular.play_game('aleatorio', 'teste-0')
    with pytest.raises(SystemExit):
        simular.check_empty(str(db_path), append=False)
    simular.check_empty(str(db_path), append=True)           # explicit append: accepted
    simular.check_empty(str(tmp_path / 'novo.db'), append=False)  # missing file: accepted
