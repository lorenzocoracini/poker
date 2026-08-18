import sqlite3
import os

DB_PATH = os.path.join(os.path.dirname(__file__), '..', '..', 'poker.db')


def get_connection() -> sqlite3.Connection:
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    conn = get_connection()
    cur = conn.cursor()

    cur.executescript("""
        CREATE TABLE IF NOT EXISTS games (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            started_at  TEXT NOT NULL,
            ended_at    TEXT,
            winner      TEXT,
            total_rounds INTEGER
        );

        CREATE TABLE IF NOT EXISTS rounds (
            id              INTEGER PRIMARY KEY AUTOINCREMENT,
            game_id         INTEGER NOT NULL REFERENCES games(id),
            round_number    INTEGER NOT NULL,
            blind           INTEGER NOT NULL,
            player_cards    TEXT NOT NULL,
            system_cards    TEXT NOT NULL,
            community_cards TEXT NOT NULL,
            winner          TEXT,
            pot             INTEGER
        );

        CREATE TABLE IF NOT EXISTS actions (
            id                   INTEGER PRIMARY KEY AUTOINCREMENT,
            round_id             INTEGER NOT NULL REFERENCES rounds(id),
            street               TEXT NOT NULL,
            actor                TEXT NOT NULL,
            action_type          TEXT NOT NULL,
            amount               INTEGER NOT NULL DEFAULT 0,
            win_prob             REAL,
            pot_odds             REAL,
            position             REAL,
            fuzzy_recommendation TEXT
        );
    """)

    conn.commit()
    conn.close()
