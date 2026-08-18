import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'backend'))

import streamlit as st
from game_logic.controller import GameController

st.set_page_config(page_title='Poker Agent', page_icon='🃏', layout='wide')

SUIT_SYMBOLS = {'hearts': '♥', 'diamonds': '♦', 'clubs': '♣', 'spades': '♠'}
SUIT_COLORS  = {'hearts': '#cc2200', 'diamonds': '#cc2200', 'clubs': '#111', 'spades': '#111'}
TOTAL_CHIPS  = 1200  # 2 × STACK_INICIAL


# ── Card helpers ──────────────────────────────────────────────────────────────

def card_html(card) -> str:
    sym   = SUIT_SYMBOLS[card.suit]
    color = SUIT_COLORS[card.suit]
    return (
        f'<span style="display:inline-block;border:1px solid #bbb;border-radius:6px;'
        f'padding:5px 13px;margin:3px;font-size:22px;font-weight:bold;'
        f'background:#fff;color:{color};box-shadow:1px 2px 4px #0002;">'
        f'{card.rank}{sym}</span>'
    )


def back_html() -> str:
    return (
        '<span style="display:inline-block;border:1px solid #446;border-radius:6px;'
        'padding:5px 13px;margin:3px;font-size:22px;font-weight:bold;'
        'background:#1a3a6a;color:#1a3a6a;box-shadow:1px 2px 4px #0002;">XX</span>'
    )


def render_hand(cards, hidden=False) -> str:
    if not cards:
        return '<span style="color:#aaa;font-style:italic;font-size:18px;">—</span>'
    if hidden:
        return ''.join(back_html() for _ in cards)
    return ''.join(card_html(c) for c in cards)


# ── Session state init ────────────────────────────────────────────────────────

if 'ctrl' not in st.session_state:
    st.session_state.ctrl       = None
    st.session_state.game_ended = False

ctrl  = st.session_state.ctrl
state = ctrl.get_state() if ctrl else None


# ── Sidebar ───────────────────────────────────────────────────────────────────

with st.sidebar:
    st.title('🃏 Poker Agent')
    st.caption('Texas Hold\'em Heads-Up — TCC Lorenzo Coracini')
    st.divider()

    if ctrl and state:
        c1, c2 = st.columns(2)
        c1.metric('Round', state['round_number'])
        c2.metric('Pot',   state['pot'])
        st.write(f"**Blinds:** {state['blind']} / {state['blind'] * 2}  *(SB / BB)*")
        st.divider()

        st.write(f"**Street:** {(state['street'] or '—').upper()}")
        st.write(f"**Button:** {'Você' if state['button'] == 'player' else 'Sistema'}")
        st.divider()

        total = state['player_stack'] + state['system_stack']
        safe  = total if total > 0 else 1

        st.write('**Fichas**')
        st.write(f'👤 Você: **{state["player_stack"]}**')
        st.progress(state['player_stack'] / safe)
        st.write(f'🤖 Sistema: **{state["system_stack"]}**')
        st.progress(state['system_stack'] / safe)
        st.divider()

        # Fuzzy insight (valor para o TCC)
        fuzzy = getattr(ctrl.system, 'last_fuzzy_data', {})
        if fuzzy:
            st.write('**Última decisão fuzzy**')
            st.write(f"Win prob: `{fuzzy.get('win_prob', 0):.1%}`")
            st.write(f"Pot odds: `{fuzzy.get('pot_odds', 0):.1%}`")
            rec = fuzzy.get('recommendation', '—')
            color = {'fold': '🔴', 'call': '🟡', 'raise': '🟢'}.get(rec, '⚪')
            st.write(f"Recomendação: {color} **{rec}**")
            st.divider()

        st.write('**Log**')
        log_text = '\n'.join(reversed(state['log']))
        st.text_area('', value=log_text, height=260,
                     disabled=True, label_visibility='collapsed')


# ── Main ──────────────────────────────────────────────────────────────────────

st.markdown('## Texas Hold\'em Heads-Up')

# ── Tela inicial ──────────────────────────────────────────────────────────────

if ctrl is None:
    st.info('Bem-vindo ao Poker Agent! Clique para iniciar.')
    if st.button('🎴 Nova Partida', type='primary', use_container_width=True):
        c = GameController()
        c.start_new_round()
        st.session_state.ctrl       = c
        st.session_state.game_ended = False
        st.rerun()
    st.stop()

status = state['status']

# ── Board ─────────────────────────────────────────────────────────────────────

st.markdown('#### Board')
board = state['community_cards']
board_html = render_hand(board) if board else \
    '<span style="color:#aaa;font-style:italic;font-size:16px;">Sem cartas comunitárias ainda</span>'
st.markdown(board_html, unsafe_allow_html=True)

st.divider()

# ── Mãos ─────────────────────────────────────────────────────────────────────

col_p, col_s = st.columns(2)

reveal_system = state['showdown'] or status in ('ROUND_OVER', 'GAME_OVER')

with col_p:
    st.markdown('#### 👤 Sua mão')
    st.markdown(render_hand(state['player_hand']), unsafe_allow_html=True)
    if reveal_system and state.get('player_hand_desc'):
        st.caption(state['player_hand_desc'])

ACTION_LABELS = {
    'fold':  '🔴 foldou',
    'check': '⚪ check',
    'call':  '🟡 call {}',
    'bet':   '🟠 bet {}',
    'raise': '🟢 raise {}',
    'allin': '🔥 ALL-IN {}',
}

with col_s:
    st.markdown('#### 🤖 Sistema')
    st.markdown(render_hand(state['system_hand'], hidden=not reveal_system),
                unsafe_allow_html=True)
    if reveal_system and state.get('system_hand_desc'):
        st.caption(state['system_hand_desc'])
    last = state.get('last_system_action')
    if last and not reveal_system:
        action, amount = last
        template = ACTION_LABELS.get(action, action)
        label = template.format(amount) if '{}' in template else template
        st.caption(f'Última ação: **{label}**')

st.divider()

# ── Área de ação ──────────────────────────────────────────────────────────────

if status == 'WAITING_PLAYER':
    st.markdown('#### Sua vez')
    valid  = state['valid_actions']  # [(action, label, default_amount)]
    acts   = [a for a, _, _ in valid]
    bb     = state['blind'] * 2

    needs_amount = any(a in acts for a in ('bet', 'raise'))

    if needs_amount:
        max_amt     = state['player_stack']
        safe_min    = bb
        safe_max    = max(bb, max_amt)
        safe_val    = max(safe_min, min(bb, safe_max))
        input_key   = f'raise_{state["round_number"]}_{state["street"]}'
        st.number_input(
            f'Valor do bet / raise  (BB = {bb}, pot = {state["pot"]})',
            min_value=safe_min,
            max_value=safe_max,
            value=safe_val,
            step=bb,
            key=input_key,
        )

    btn_cols = st.columns(len(valid))
    for col, (action, label, default_amount) in zip(btn_cols, valid):
        with col:
            btn_type = 'primary' if action in ('call', 'check') else 'secondary'
            if st.button(label, type=btn_type, use_container_width=True):
                amt = (
                    int(st.session_state.get(input_key, bb))
                    if action in ('bet', 'raise') else default_amount
                )
                ctrl.apply_player_action(action, amt)
                st.rerun()

elif status == 'ROUND_OVER':
    winner = state['round_winner']
    pot    = state['pot']

    if winner == 'player':
        st.success(f'Você ganhou o pot de **{pot}**! 🎉')
    elif winner == 'system':
        st.error(f'Sistema ganhou o pot de **{pot}**.')
    else:
        st.info('Empate! Pot dividido.')

    st.caption(f'Encerramento: {"Showdown" if state["showdown"] else "Fold"}')

    # Descrições das mãos só no showdown (no fold o sistema não revela)
    if state['showdown']:
        p_desc = state.get('player_hand_desc', '')
        s_desc = state.get('system_hand_desc', '')
        if p_desc:
            st.caption(f'Sua mão: **{p_desc}**  |  Sistema: **{s_desc}**')

    st.divider()
    if st.button('▶ Próxima Rodada', type='primary', use_container_width=True):
        ctrl.start_new_round()
        st.rerun()

elif status == 'GAME_OVER':
    if not st.session_state.game_ended:
        ctrl.end_game()
        st.session_state.game_ended = True

    if state['player_stack'] == 0:
        st.error('🤖 Sistema venceu o jogo! Você ficou sem fichas.')
    else:
        st.success('🏆 Você venceu o jogo! Sistema ficou sem fichas.')

    if st.button('🎴 Novo Jogo', type='primary', use_container_width=True):
        c = GameController()
        c.start_new_round()
        st.session_state.ctrl       = c
        st.session_state.game_ended = False
        st.rerun()
