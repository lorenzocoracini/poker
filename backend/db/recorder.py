import json
import re
from datetime import datetime, timezone
from db.database import get_connection


def normalize_participant_code(code: str):
    """Canonical study code 'P<n>' (' p01 ' -> 'P1'), so the game and the
    questionnaire match regardless of typing. Returns None if not in that format."""
    match = re.fullmatch(r'[Pp]0*(\d+)', (code or '').strip())
    return f'P{match.group(1)}' if match else None


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

    @property
    def game_id(self):
        return self._game_id

    @property
    def round_id(self):
        return self._round_id

    def start_game(self, participant_code: str = None):
        conn = get_connection()
        cur  = conn.cursor()
        cur.execute(
            "INSERT INTO games (started_at, participant_code) VALUES (?, ?)",
            (_now(), participant_code),
        )
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

    def end_round(self, winner: str, pot: int, community_cards,
                  player_stack: int = None, system_stack: int = None):
        if self._round_id is None:
            return
        conn = get_connection()
        conn.execute(
            """UPDATE rounds SET winner=?, pot=?, community_cards=?,
                                 player_stack_end=?, system_stack_end=?
               WHERE id=?""",
            (winner, pot, _cards_json(community_cards),
             player_stack, system_stack, self._round_id),
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
                win_prob, pot_odds, position,
                ppot, npot, opponent_aggression, stack_commitment,
                fuzzy_recommendation, recommended_action)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (self._round_id, self._street, actor, action_type, amount,
             fd.get('win_prob'), fd.get('pot_odds'), fd.get('position'),
             fd.get('ppot'), fd.get('npot'),
             fd.get('opponent_aggression'), fd.get('stack_commitment'),
             fd.get('recommendation'), fd.get('recommended_action')),
        )
        conn.commit()
        conn.close()

    def record_feedback(self, level: str, prompt: str, response: str, model: str,
                        round_id: int = None):
        """Stores an LLM feedback text with the prompt that produced it, so the
        texts can be checked against the data after the study."""
        if self._game_id is None:
            return
        conn = get_connection()
        conn.execute(
            """INSERT INTO feedbacks
               (game_id, round_id, level, prompt, response, model, created_at)
               VALUES (?, ?, ?, ?, ?, ?, ?)""",
            (self._game_id, round_id, level, prompt, response, model, _now()),
        )
        conn.commit()
        conn.close()
