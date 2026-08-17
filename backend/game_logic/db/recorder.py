import json
from datetime import datetime, timezone
from game_logic.db.database import get_connection


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _cards_json(cards) -> str:
    return json.dumps([c.to_dict() for c in cards])


class GameRecorder:
    """Records game sessions, rounds and actions to SQLite."""

    def __init__(self):
        self._game_id  = None
        self._round_id = None
        self._street   = None

    def start_game(self):
        conn = get_connection()
        cur  = conn.cursor()
        cur.execute("INSERT INTO games (started_at) VALUES (?)", (_now(),))
        self._game_id = cur.lastrowid
        conn.commit()
        conn.close()

    def end_game(self, winner: str, total_rounds: int):
        if self._game_id is None:
            return
        conn = get_connection()
        conn.execute(
            "UPDATE games SET ended_at=?, winner=?, total_rounds=? WHERE id=?",
            (_now(), winner, total_rounds, self._game_id),
        )
        conn.commit()
        conn.close()

    def start_round(self, round_number: int, blind: int,
                    player_cards, system_cards):
        if self._game_id is None:
            return
        conn = get_connection()
        cur  = conn.cursor()
        cur.execute(
            """INSERT INTO rounds
               (game_id, round_number, blind, player_cards, system_cards, community_cards)
               VALUES (?, ?, ?, ?, ?, ?)""",
            (self._game_id, round_number, blind,
             _cards_json(player_cards), _cards_json(system_cards), '[]'),
        )
        self._round_id = cur.lastrowid
        conn.commit()
        conn.close()

    def end_round(self, winner: str, pot: int, community_cards):
        if self._round_id is None:
            return
        conn = get_connection()
        conn.execute(
            "UPDATE rounds SET winner=?, pot=?, community_cards=? WHERE id=?",
            (winner, pot, _cards_json(community_cards), self._round_id),
        )
        conn.commit()
        conn.close()

    def set_street(self, street: str):
        self._street = street

    def record_action(self, actor: str, action_type: str, amount: int,
                      fuzzy_data: dict = None):
        if self._round_id is None:
            return
        fd = fuzzy_data or {}
        conn = get_connection()
        conn.execute(
            """INSERT INTO actions
               (round_id, street, actor, action_type, amount,
                win_prob, pot_odds, position, fuzzy_recommendation)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (self._round_id, self._street, actor, action_type, amount,
             fd.get('win_prob'), fd.get('pot_odds'),
             fd.get('position'), fd.get('recommendation')),
        )
        conn.commit()
        conn.close()
