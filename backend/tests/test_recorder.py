import sqlite3

import pytest

import db.database as database
import feedback.llm_client as llm_client
from db.recorder import GameRecorder


@pytest.fixture
def temp_db(tmp_path, monkeypatch):
    db_path = tmp_path / 'test_poker.db'
    monkeypatch.setattr(database, 'DB_PATH', str(db_path))
    database.init_db()
    return database


def _fetch(db_module, sql, params=()):
    conn = db_module.get_connection()
    rows = conn.execute(sql, params).fetchall()
    conn.close()
    return rows


def test_start_game_stores_participant_code(temp_db):
    recorder = GameRecorder()
    recorder.start_game('P01')

    rows = _fetch(temp_db, "SELECT participant_code FROM games WHERE id=?", (recorder.game_id,))
    assert rows[0]['participant_code'] == 'P01'


def test_start_game_without_code_stores_null(temp_db):
    recorder = GameRecorder()
    recorder.start_game()

    rows = _fetch(temp_db, "SELECT participant_code FROM games WHERE id=?", (recorder.game_id,))
    assert rows[0]['participant_code'] is None


def test_record_feedback_stores_round_and_game_levels(temp_db):
    recorder = GameRecorder()
    recorder.start_game('P02')
    recorder.start_round(1, 10, [], [])
    round_id = recorder.round_id

    recorder.record_feedback('round', 'prompt rodada', 'texto rodada', 'modelo-x', round_id)
    recorder.record_feedback('game', 'prompt partida', 'texto partida', 'modelo-x')

    rows = _fetch(temp_db, "SELECT * FROM feedbacks ORDER BY id")
    assert len(rows) == 2
    assert rows[0]['level'] == 'round'
    assert rows[0]['round_id'] == round_id
    assert rows[0]['prompt'] == 'prompt rodada'
    assert rows[0]['response'] == 'texto rodada'
    assert rows[1]['level'] == 'game'
    assert rows[1]['round_id'] is None
    assert all(r['game_id'] == recorder.game_id for r in rows)
    assert all(r['model'] == 'modelo-x' for r in rows)


def test_record_feedback_rejects_unknown_level(temp_db):
    recorder = GameRecorder()
    recorder.start_game()
    with pytest.raises(sqlite3.IntegrityError):
        recorder.record_feedback('session', 'p', 'r', 'm')


def test_init_db_migrates_games_table_without_participant_code(tmp_path, monkeypatch):
    # A DB created before the user study has no `participant_code` column.
    db_path = tmp_path / 'old.db'
    conn = sqlite3.connect(db_path)
    conn.execute("""CREATE TABLE games (
        id INTEGER PRIMARY KEY AUTOINCREMENT, started_at TEXT NOT NULL,
        ended_at TEXT, winner TEXT, total_rounds INTEGER)""")
    conn.commit()
    conn.close()

    monkeypatch.setattr(database, 'DB_PATH', str(db_path))
    database.init_db()

    cols = [r['name'] for r in _fetch(database, "PRAGMA table_info(games)")]
    assert 'participant_code' in cols


def test_generate_functions_return_text_and_prompt(monkeypatch):
    # The API call is replaced: only checks that the prompt sent is returned.
    sent = []
    monkeypatch.setattr(llm_client, '_call_claude',
                        lambda system, user, max_tokens: sent.append(user) or 'resposta')
    summary = {
        'total_decisoes': 1, 'nota_media': 100.0,
        'breakdown_street': {'preflop': {'total_decisoes': 1, 'nota_media': 100.0}},
        'padroes': {
            'foldou_quando_recomendacao_era_raise': 0,
            'deu_raise_quando_recomendacao_era_fold': 0,
            'continuou_mao_fraca_win_prob_abaixo_0_35': 0,
        },
    }

    texto, prompt = llm_client.generate_feedback(summary)

    assert texto == 'resposta'
    assert prompt == sent[0] == llm_client.build_prompt(summary)


def test_end_round_stores_final_stacks(temp_db):
    recorder = GameRecorder()
    recorder.start_game()
    recorder.start_round(1, 10, [], [])
    recorder.end_round('system', 60, [], player_stack=570, system_stack=630)

    rows = _fetch(temp_db, "SELECT player_stack_end, system_stack_end FROM rounds")
    assert (rows[0]['player_stack_end'], rows[0]['system_stack_end']) == (570, 630)


@pytest.mark.parametrize('typed,expected', [
    ('P1', 'P1'), (' p1 ', 'P1'), ('P01', 'P1'), ('p012', 'P12'), ('P10', 'P10'),
    ('', None), ('1', None), ('X1', None), ('P', None), ('P1a', None), (None, None),
])
def test_normalize_participant_code(typed, expected):
    from db.recorder import normalize_participant_code
    assert normalize_participant_code(typed) == expected
