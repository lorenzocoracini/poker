import sqlite3
import os

# POKER_DB lets each experiment use its own file (e.g. estudo.db, simulacao.db)
# without mixing with the development games in the default poker.db.
DB_PATH = os.environ.get(
    'POKER_DB', os.path.join(os.path.dirname(__file__), '..', '..', 'poker.db')
)


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
            total_rounds INTEGER,
            participant_code TEXT
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
            pot             INTEGER,
            player_stack_end INTEGER,
            system_stack_end INTEGER
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
            ppot                 REAL,
            npot                 REAL,
            opponent_aggression  REAL,
            stack_commitment     REAL,
            fuzzy_recommendation TEXT,
            recommended_action   TEXT
        );

        CREATE TABLE IF NOT EXISTS feedbacks (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            game_id     INTEGER NOT NULL REFERENCES games(id),
            round_id    INTEGER REFERENCES rounds(id),
            level       TEXT NOT NULL CHECK (level IN ('round', 'game')),
            prompt      TEXT NOT NULL,
            response    TEXT NOT NULL,
            model       TEXT NOT NULL,
            created_at  TEXT NOT NULL
        );
    """)

    # Lightweight migration for DBs created before `recommended_action` existed.
    # Same for `participant_code` and the end-of-round stacks, added for the experiments.
    for table, column, kind in (('actions', 'recommended_action', 'TEXT'),
                                ('games',   'participant_code',   'TEXT'),
                                ('rounds',  'player_stack_end',   'INTEGER'),
                                ('rounds',  'system_stack_end',   'INTEGER')):
        try:
            cur.execute(f"ALTER TABLE {table} ADD COLUMN {column} {kind}")
        except sqlite3.OperationalError:
            pass  # column already exists

    conn.commit()
    conn.close()
