"""Builds the CSV tables used by Chapter 5 from the experiment databases.

Inputs (each one is optional; missing inputs are skipped):
  --simulacao  SQLite file written by simular.py
  --estudo     SQLite file of the user study (games with a participant code)
  --respostas  questionnaire CSV exported from Google Forms, with the header
               renamed to: codigo,N1,N2,F1,F2,F3,F4,F5,F6,F7[,F8]
  --auditoria  CSV for the manual check of the LLM texts (created/updated here,
               the column `classificacao` is filled by hand with 'fiel' or 'erro')

Outputs: CSV files in --saida (default: escrita/dados), read in LaTeX with
pgfplotstable. Only sqlite3, numpy and scipy are used.

Usage (from code/poker):
    python3 experimentos/analisar.py --simulacao experimentos/simulacao.db \\
        --estudo experimentos/estudo.db --respostas experimentos/respostas.csv
"""
import argparse
import csv
import os
import sqlite3
import sys

import numpy as np
from scipy import stats

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, '..', 'backend'))

import db.database as database  # noqa: E402
from engine.config.game_parameters import STACK_INICIAL  # noqa: E402
from feedback.session_report import summarize_session  # noqa: E402
from db.recorder import normalize_participant_code  # noqa: E402

DEFAULT_OUT = os.path.join(HERE, '..', '..', '..', 'escrita', 'dados')
STREETS = ['preflop', 'flop', 'turn', 'river']
ACTIONS = ['fold', 'check', 'call', 'bet', 'raise', 'allin']
LIKERT_ITEMS = ['F1', 'F2', 'F3', 'F4', 'F5', 'F6']
INDEX_ITEMS = ['F1', 'F2', 'F3', 'F4', 'F5']  # F6 is the overall item, kept apart


# ── Helpers ───────────────────────────────────────────────────────────────────

def connect(path: str) -> sqlite3.Connection:
    conn = sqlite3.connect(path)
    conn.row_factory = sqlite3.Row
    return conn


def write_csv(out_dir: str, name: str, header: list, rows: list):
    path = os.path.join(out_dir, name)
    with open(path, 'w', newline='', encoding='utf-8') as f:
        w = csv.writer(f)
        w.writerow(header)
        for row in rows:
            w.writerow([f'{v:.4f}' if isinstance(v, float) else v for v in row])
    print(f'  {name}: {len(rows)} linhas')


def wilson_ci(successes: int, n: int) -> tuple:
    """95% Wilson interval for a proportion (Wilson, 1927)."""
    ci = stats.binomtest(successes, n).proportion_ci(confidence_level=0.95, method='wilson')
    return ci.low, ci.high


def mean_ci(values) -> tuple:
    """Mean, standard deviation and 95% t interval of the mean."""
    a = np.asarray(values, dtype=float)
    mean, sd = a.mean(), a.std(ddof=1) if len(a) > 1 else 0.0
    if len(a) < 2:
        return mean, sd, mean, mean
    half = stats.t.ppf(0.975, len(a) - 1) * sd / np.sqrt(len(a))
    return mean, sd, mean - half, mean + half


def cronbach_alpha(matrix) -> float:
    """Cronbach (1951): k/(k-1) * (1 - sum of item variances / variance of total)."""
    m = np.asarray(matrix, dtype=float)
    k = m.shape[1]
    item_var  = m.var(axis=0, ddof=1).sum()
    total_var = m.sum(axis=1).var(ddof=1)
    return float('nan') if total_var == 0 else k / (k - 1) * (1 - item_var / total_var)


def action_frequency(conn, game_filter: str, params: tuple) -> list:
    """Agent action counts per street, as (street, n, % of each action)."""
    rows = conn.execute(
        f"""SELECT a.street, a.action_type, COUNT(*) AS n
            FROM actions a JOIN rounds r ON a.round_id = r.id
            JOIN games g ON r.game_id = g.id
            WHERE a.actor = 'system' AND {game_filter}
            GROUP BY a.street, a.action_type""",
        params,
    ).fetchall()
    counts = {s: dict.fromkeys(ACTIONS, 0) for s in STREETS}
    for r in rows:
        counts[r['street']][r['action_type']] = r['n']
    out = []
    for s in STREETS + ['total']:
        c = counts[s] if s != 'total' else {
            a: sum(counts[st][a] for st in STREETS) for a in ACTIONS}
        n = sum(c.values())
        out.append([s, n] + [c[a] / n * 100 if n else 0.0 for a in ACTIONS])
    return out


# ── Simulation ────────────────────────────────────────────────────────────────

def analyze_simulation(path: str, out: str):
    print(f'Simulação: {path}')
    conn = connect(path)
    opponents = [r[0] for r in conn.execute(
        "SELECT DISTINCT participant_code FROM games WHERE participant_code LIKE 'SIM-%' "
        "ORDER BY participant_code")]

    wins_rows, bb_rows, action_rows = [], [], []
    for code in opponents:
        name = code[len('SIM-'):]
        games = conn.execute(
            "SELECT id, winner, total_rounds FROM games "
            "WHERE participant_code = ? AND winner IS NOT NULL", (code,)).fetchall()
        n    = len(games)
        wins = sum(g['winner'] == 'system' for g in games)
        low, high = wilson_ci(wins, n)
        wins_rows.append([name, n, wins, wins / n * 100, low * 100, high * 100,
                          float(np.mean([g['total_rounds'] for g in games]))])

        # Agent result per round in big blinds: change of the agent's stack
        # divided by the big blind of that round.
        bb_per_round = []
        for g in games:
            prev = STACK_INICIAL
            for r in conn.execute(
                    "SELECT blind, system_stack_end FROM rounds "
                    "WHERE game_id = ? ORDER BY round_number", (g['id'],)):
                if r['system_stack_end'] is None:
                    break
                bb_per_round.append((r['system_stack_end'] - prev) / (2 * r['blind']))
                prev = r['system_stack_end']
        mean, sd, low, high = mean_ci(bb_per_round)
        bb_rows.append([name, len(bb_per_round), mean, sd, low, high])

        for row in action_frequency(conn, "g.participant_code = ? AND g.winner IS NOT NULL",
                                    (code,)):
            action_rows.append([name] + row)
    conn.close()

    write_csv(out, 'sim_vitorias.csv',
              ['oponente', 'partidas', 'vitorias', 'taxa', 'ic_inf', 'ic_sup', 'rodadas_media'],
              wins_rows)
    write_csv(out, 'sim_bb_por_rodada.csv',
              ['oponente', 'rodadas', 'bb_media', 'bb_desvio', 'ic_inf', 'ic_sup'], bb_rows)
    write_csv(out, 'sim_acoes.csv', ['oponente', 'etapa', 'n'] + ACTIONS, action_rows)


# ── User study ────────────────────────────────────────────────────────────────

STUDY_FILTER = "g.participant_code IS NOT NULL AND g.participant_code NOT LIKE 'SIM-%'"


def analyze_study(path: str, out: str) -> dict:
    """Writes the per-game tables and returns {code: result of the first game}."""
    print(f'Estudo: {path}')
    database.DB_PATH = path  # summarize_session reads through db.database
    conn = connect(path)
    games = conn.execute(
        f"""SELECT g.id, g.participant_code AS code, g.winner, g.total_rounds
            FROM games g WHERE {STUDY_FILTER} ORDER BY g.participant_code, g.id""").fetchall()

    game_rows, street_rows, pattern_rows = [], [], []
    first_game, order = {}, {}
    unfinished = 0
    for g in games:
        if g['winner'] is None:
            unfinished += 1
            continue
        code = normalize_participant_code(g['code']) or g['code']
        order[code] = order.get(code, 0) + 1
        s = summarize_session(g['id'])
        last = conn.execute(
            "SELECT player_stack_end FROM rounds WHERE game_id = ? "
            "ORDER BY round_number DESC LIMIT 1", (g['id'],)).fetchone()
        fb = dict(conn.execute(
            "SELECT level, COUNT(*) FROM feedbacks WHERE game_id = ? GROUP BY level",
            (g['id'],)).fetchall())
        won = int(g['winner'] == 'player')
        game_rows.append([code, order[code], g['id'], won, g['total_rounds'],
                          last['player_stack_end'] if last else '', s['total_decisoes'],
                          s['nota_media'], fb.get('round', 0), fb.get('game', 0)])
        for street in STREETS:
            d = s['breakdown_street'].get(street)
            if d:
                street_rows.append([code, order[code], street,
                                    d['total_decisoes'], d['nota_media']])
        p = s['padroes']
        pattern_rows.append([code, order[code],
                             p['foldou_quando_recomendacao_era_raise'],
                             p['deu_raise_quando_recomendacao_era_fold'],
                             p['continuou_mao_fraca_win_prob_abaixo_0_35']])
        first_game.setdefault(code, won)

    action_rows = [['humanos'] + r for r in
                   action_frequency(conn, f"{STUDY_FILTER} AND g.winner IS NOT NULL", ())]
    conn.close()
    if unfinished:
        print(f'  aviso: {unfinished} partida(s) sem fim ignorada(s)')

    write_csv(out, 'estudo_partidas.csv',
              ['codigo', 'partida', 'game_id', 'venceu', 'rodadas', 'fichas_finais',
               'decisoes', 'nota_media', 'feedbacks_rodada', 'feedbacks_partida'], game_rows)
    write_csv(out, 'estudo_nota_etapa.csv',
              ['codigo', 'partida', 'etapa', 'decisoes', 'nota_media'], street_rows)
    write_csv(out, 'estudo_padroes.csv',
              ['codigo', 'partida', 'foldou_rec_raise', 'raise_rec_fold', 'continuou_fraca'],
              pattern_rows)
    write_csv(out, 'estudo_acoes_agente.csv', ['oponente', 'etapa', 'n'] + ACTIONS, action_rows)
    return first_game


# ── Questionnaire ─────────────────────────────────────────────────────────────

def _level(value: str):
    """Accepts '3' or '3 - Jogo com frequência' (Forms exports the option text)."""
    value = value.strip()
    return int(value[0]) if value[:1].isdigit() else None


def _compare(label: str, variable: str, a: list, b: list) -> list:
    """Mann-Whitney U (Mann & Whitney, 1947), two-sided; exploratory with small n."""
    if len(a) < 2 or len(b) < 2:
        return [label, variable, len(a), len(b), '', '', '', '']
    u, p = stats.mannwhitneyu(a, b, alternative='two-sided')
    return [label, variable, len(a), len(b), float(np.median(a)), float(np.median(b)),
            float(u), float(p)]


def analyze_questionnaire(path: str, out: str, first_game: dict):
    print(f'Respostas: {path}')
    with open(path, newline='', encoding='utf-8') as f:
        answers = list(csv.DictReader(f))
    for a in answers:
        a['codigo'] = normalize_participant_code(a['codigo']) or a['codigo'].strip()
        a['N1'] = _level(a['N1'])
        a['N2'] = _level(a['N2'])
        for item in LIKERT_ITEMS:
            a[item] = _level(a[item])

    # Per item: distribution for the stacked bars, median, mode and % agreement (4 or 5).
    item_rows = []
    for item in LIKERT_ITEMS:
        values = [a[item] for a in answers if a[item] is not None]
        counts = [values.count(v) for v in range(1, 6)]
        n = len(values)
        item_rows.append([item, n, float(np.median(values)), counts.index(max(counts)) + 1,
                          sum(counts[3:]) / n * 100] + [c / n * 100 for c in counts])
    write_csv(out, 'quest_itens.csv',
              ['item', 'n', 'mediana', 'moda', 'pct_concorda',
               'p1', 'p2', 'p3', 'p4', 'p5'], item_rows)

    complete = [a for a in answers if all(a[i] is not None for i in INDEX_ITEMS)]
    alpha = cronbach_alpha([[a[i] for i in INDEX_ITEMS] for a in complete]) \
        if len(complete) > 2 else float('nan')
    write_csv(out, 'quest_alfa.csv', ['itens', 'n', 'alfa'],
              [['F1-F5', len(complete), alpha]])

    # Per participant: experience level, group, result of the first game and index.
    part_rows = []
    for a in complete:
        group = 'iniciante' if a['N1'] in (1, 2) else 'experiente'
        won = first_game.get(a['codigo'], '')
        part_rows.append([a['codigo'], a['N1'], a['N2'], group, won,
                          float(np.mean([a[i] for i in INDEX_ITEMS])), a['F6']])
    write_csv(out, 'quest_participantes.csv',
              ['codigo', 'nivel', 'familiaridade', 'grupo', 'venceu', 'indice', 'F6'],
              part_rows)

    tests = []
    for var, col in (('indice', 5), ('F6', 6)):
        tests.append(_compare('iniciante x experiente', var,
                              [r[col] for r in part_rows if r[3] == 'iniciante'],
                              [r[col] for r in part_rows if r[3] == 'experiente']))
        tests.append(_compare('venceu x perdeu', var,
                              [r[col] for r in part_rows if r[4] == 1],
                              [r[col] for r in part_rows if r[4] == 0]))
    write_csv(out, 'quest_testes.csv',
              ['comparacao', 'variavel', 'n1', 'n2', 'mediana1', 'mediana2', 'U', 'p'], tests)

    # Experience group x result of the first game, with Fisher's exact test.
    table = [[sum(1 for r in part_rows if r[3] == g and r[4] == w) for w in (1, 0)]
             for g in ('iniciante', 'experiente')]
    p = stats.fisher_exact(table)[1] if all(sum(row) for row in table) else float('nan')
    write_csv(out, 'quest_nivel_vitoria.csv', ['grupo', 'venceu', 'perdeu', 'pct_vitoria', 'p_fisher'],
              [[g, row[0], row[1], row[0] / sum(row) * 100 if sum(row) else 0.0, p]
               for g, row in zip(('iniciante', 'experiente'), table)])

    f7 = {}
    for a in answers:
        if a.get('F7', '').strip():
            f7[a['F7'].strip()] = f7.get(a['F7'].strip(), 0) + 1
    total = sum(f7.values())
    write_csv(out, 'quest_f7.csv', ['opcao', 'n', 'pct'],
              [[k, v, v / total * 100] for k, v in sorted(f7.items())])


# ── LLM text check ────────────────────────────────────────────────────────────

AUDIT_HEADER = ['feedback_id', 'codigo', 'nivel', 'round_id', 'prompt', 'resposta',
                'classificacao', 'observacao']


def update_audit(study_db: str, audit_path: str, out: str):
    """Appends new feedback texts to the audit sheet, keeping the classifications
    already filled in, and summarizes them."""
    print(f'Auditoria: {audit_path}')
    existing = {}
    if os.path.exists(audit_path):
        with open(audit_path, newline='', encoding='utf-8') as f:
            existing = {row['feedback_id']: row for row in csv.DictReader(f)}

    conn = connect(study_db)
    rows = conn.execute(
        f"""SELECT f.id, g.participant_code AS code, f.level, f.round_id, f.prompt, f.response
            FROM feedbacks f JOIN games g ON f.game_id = g.id
            WHERE {STUDY_FILTER} ORDER BY f.id""").fetchall()
    conn.close()
    for r in rows:
        existing.setdefault(str(r['id']), {
            'feedback_id': r['id'], 'codigo': normalize_participant_code(r['code']) or r['code'],
            'nivel': r['level'],
            'round_id': r['round_id'] or '', 'prompt': r['prompt'], 'resposta': r['response'],
            'classificacao': '', 'observacao': ''})
    with open(audit_path, 'w', newline='', encoding='utf-8') as f:
        w = csv.DictWriter(f, fieldnames=AUDIT_HEADER)
        w.writeheader()
        w.writerows(existing.values())

    summary = []
    for level in ('round', 'game', 'total'):
        sel = [r for r in existing.values() if level == 'total' or r['nivel'] == level]
        label = [r['classificacao'].strip().lower() for r in sel]
        summary.append([level, len(sel), label.count('fiel'), label.count('erro'),
                        sum(1 for c in label if c not in ('fiel', 'erro'))])
    write_csv(out, 'fidelidade.csv',
              ['nivel', 'total', 'fiel', 'erro', 'nao_classificado'], summary)


def main():
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument('--simulacao', default=os.path.join(HERE, 'simulacao.db'))
    parser.add_argument('--estudo', default=os.path.join(HERE, 'estudo.db'))
    parser.add_argument('--respostas', default=os.path.join(HERE, 'respostas.csv'))
    parser.add_argument('--auditoria', default=os.path.join(HERE, 'auditoria_feedbacks.csv'))
    parser.add_argument('--saida', default=DEFAULT_OUT)
    args = parser.parse_args()

    os.makedirs(args.saida, exist_ok=True)
    first_game = {}
    if os.path.exists(args.simulacao):
        analyze_simulation(args.simulacao, args.saida)
    if os.path.exists(args.estudo):
        first_game = analyze_study(args.estudo, args.saida)
        update_audit(args.estudo, args.auditoria, args.saida)
    if os.path.exists(args.respostas):
        analyze_questionnaire(args.respostas, args.saida, first_game)


if __name__ == '__main__':
    main()
