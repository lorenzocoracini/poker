import pytest

import db.database as database
from feedback.session_report import score_decision, summarize_session


@pytest.mark.parametrize('rec,act,expected', [
    ('fold', 'fold', 1.0),
    ('call', 'call', 1.0),
    ('raise', 'raise', 1.0),
    ('fold', 'call', 0.5),
    ('fold', 'check', 0.5),
    ('call', 'raise', 0.5),
    ('raise', 'call', 0.5),
    ('fold', 'raise', 0.0),
    ('fold', 'allin', 0.0),
    ('raise', 'fold', 0.0),
])
def test_score_decision_known_cases(rec, act, expected):
    assert score_decision(rec, act) == expected


def test_score_decision_unknown_action_returns_zero():
    assert score_decision('fold', 'unknown') == 0.0
    assert score_decision('unknown', 'fold') == 0.0


@pytest.fixture
def temp_db(tmp_path, monkeypatch):
    db_path = tmp_path / 'test_poker.db'
    monkeypatch.setattr(database, 'DB_PATH', str(db_path))
    database.init_db()
    return database


def _insert_game_and_round(db_module):
    conn = db_module.get_connection()
    cur  = conn.cursor()
    cur.execute("INSERT INTO games (started_at) VALUES ('t')")
    game_id = cur.lastrowid
    cur.execute(
        """INSERT INTO rounds
           (game_id, round_number, blind, player_cards, system_cards, community_cards)
           VALUES (?, 1, 10, '[]', '[]', '[]')""",
        (game_id,),
    )
    round_id = cur.lastrowid
    conn.commit()
    conn.close()
    return game_id, round_id


def _insert_action(db_module, round_id, street, action_type, win_prob, recommendation):
    conn = db_module.get_connection()
    conn.execute(
        """INSERT INTO actions
           (round_id, street, actor, action_type, amount,
            win_prob, pot_odds, position, ppot, npot,
            opponent_aggression, stack_commitment, fuzzy_recommendation)
           VALUES (?, ?, 'player', ?, 0, ?, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, ?)""",
        (round_id, street, action_type, win_prob, recommendation),
    )
    conn.commit()
    conn.close()


def test_summarize_session_aggregates_known_actions(temp_db):
    game_id, round_id = _insert_game_and_round(temp_db)

    # (street, action_type, win_prob, recommendation)
    _insert_action(temp_db, round_id, 'preflop', 'call',  0.6, 'call')   # score 1.0
    _insert_action(temp_db, round_id, 'flop',    'fold',  0.2, 'raise')  # score 0.0
    _insert_action(temp_db, round_id, 'turn',    'raise', 0.8, 'raise')  # score 1.0

    summary = summarize_session(game_id)

    assert summary['total_decisoes'] == 3
    assert round(summary['nota_media'], 1) == 66.7
    assert summary['breakdown_street']['preflop']['total_decisoes'] == 1
    assert summary['breakdown_street']['flop']['nota_media'] == 0.0
    assert summary['padroes']['foldou_quando_recomendacao_era_raise'] == 1
    assert summary['padroes']['deu_raise_quando_recomendacao_era_fold'] == 0
    assert summary['padroes']['continuou_mao_fraca_win_prob_abaixo_0_35'] == 0


def test_summarize_session_detects_weak_hand_continuation(temp_db):
    game_id, round_id = _insert_game_and_round(temp_db)
    _insert_action(temp_db, round_id, 'preflop', 'call', 0.2, 'fold')

    summary = summarize_session(game_id)
    assert summary['padroes']['continuou_mao_fraca_win_prob_abaixo_0_35'] == 1


def test_summarize_session_empty_game_returns_zero_total(temp_db):
    game_id, _ = _insert_game_and_round(temp_db)
    summary = summarize_session(game_id)
    assert summary['total_decisoes'] == 0
    assert summary['nota_media'] == 0.0
