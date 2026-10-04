from db.database import get_connection

# Maps the engine's 6 action types onto the fold < call < raise space used by
# the fuzzy agent's recommendation.
ACTION_ORDINAL = {
    'fold': 0,
    'check': 1, 'call': 1,
    'bet': 2, 'raise': 2, 'allin': 2,
}


def score_decision(recommended: str, actual: str) -> float:
    """1.0 on exact match, 0.5 on adjacent, 0.0 on opposite."""
    rec_ord = ACTION_ORDINAL.get(recommended)
    act_ord = ACTION_ORDINAL.get(actual)
    if rec_ord is None or act_ord is None:
        return 0.0
    return 1 - abs(rec_ord - act_ord) / 2


def fetch_player_actions(game_id: int) -> list:
    conn = get_connection()
    rows = conn.execute(
        """SELECT a.street, a.action_type, a.amount,
                  a.win_prob, a.pot_odds, a.ppot, a.npot,
                  a.opponent_aggression, a.stack_commitment,
                  a.fuzzy_recommendation, a.recommended_action
           FROM actions a JOIN rounds r ON a.round_id = r.id
           WHERE r.game_id = ? AND a.actor = 'player'""",
        (game_id,),
    ).fetchall()
    conn.close()
    return [dict(row) for row in rows]


def fetch_round_actions(round_id: int) -> list:
    conn = get_connection()
    rows = conn.execute(
        """SELECT street, action_type, amount,
                  win_prob, pot_odds, ppot, npot,
                  opponent_aggression, stack_commitment,
                  fuzzy_recommendation, recommended_action
           FROM actions
           WHERE round_id = ? AND actor = 'player'
           ORDER BY id""",
        (round_id,),
    ).fetchall()
    conn.close()
    return [dict(row) for row in rows]


def summarize_round(round_id: int) -> dict:
    actions = fetch_round_actions(round_id)

    scored = [
        {**a, 'score': score_decision(a['fuzzy_recommendation'], a['action_type'])}
        for a in actions if a['fuzzy_recommendation'] is not None
    ]

    total      = len(scored)
    nota_media = (sum(s['score'] for s in scored) / total * 100) if total else 0.0

    return {
        'total_decisoes': total,
        'nota_media':     nota_media,
        'decisoes':       scored,
    }


def summarize_session(game_id: int) -> dict:
    actions = fetch_player_actions(game_id)

    scored = [
        {**a, 'score': score_decision(a['fuzzy_recommendation'], a['action_type'])}
        for a in actions if a['fuzzy_recommendation'] is not None
    ]

    total      = len(scored)
    nota_media = (sum(s['score'] for s in scored) / total * 100) if total else 0.0

    por_street = {}
    for s in scored:
        street = s['street']
        por_street.setdefault(street, {'total': 0, 'soma_score': 0.0})
        por_street[street]['total']      += 1
        por_street[street]['soma_score'] += s['score']
    breakdown_street = {
        street: {
            'total_decisoes': d['total'],
            'nota_media':      (d['soma_score'] / d['total'] * 100) if d['total'] else 0.0,
        }
        for street, d in por_street.items()
    }

    foldou_quando_raise = sum(
        1 for s in scored
        if s['fuzzy_recommendation'] == 'raise' and s['action_type'] == 'fold'
    )
    raise_quando_fold = sum(
        1 for s in scored
        if s['fuzzy_recommendation'] == 'fold' and s['action_type'] in ('bet', 'raise', 'allin')
    )
    continuou_com_mao_fraca = sum(
        1 for s in scored
        if s['win_prob'] is not None and s['win_prob'] < 0.35
        and s['action_type'] in ('call', 'bet', 'raise', 'allin')
    )

    return {
        'total_decisoes':    total,
        'nota_media':        nota_media,
        'breakdown_street':  breakdown_street,
        'padroes': {
            'foldou_quando_recomendacao_era_raise':     foldou_quando_raise,
            'deu_raise_quando_recomendacao_era_fold':   raise_quando_fold,
            'continuou_mao_fraca_win_prob_abaixo_0_35': continuou_com_mao_fraca,
        },
    }
