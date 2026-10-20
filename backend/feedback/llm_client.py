from dotenv import load_dotenv
load_dotenv()

import anthropic

# Same Portuguese labels shown in the interface table, so the generated text
# does not echo internal variable names (win_prob, ppot...) back to the player.
STREET_PT = {'preflop': 'pré-flop', 'flop': 'flop', 'turn': 'turn', 'river': 'river'}

TERMS_INSTRUCTION = (
    "Use os mesmos termos em português dos dados (ex.: chance de vitória, chance de "
    "melhorar, risco de piorar, fichas comprometidas); não use nomes de variáveis "
    "nem termos em inglês como win probability."
)

SYSTEM_PROMPT = (
    "Você é um assistente que escreve feedback construtivo sobre uma partida de "
    "poker Texas Hold'em heads-up. Use apenas os números fornecidos — não invente "
    "mãos, cartas ou situações específicas que não estão nos dados. Responda em "
    "português do Brasil, em 3 a 5 parágrafos curtos, tom direto e construtivo, "
    "citando 1 a 2 pontos fortes e 1 a 2 pontos de melhoria baseados só nesses números. "
    + TERMS_INSTRUCTION
)


def build_prompt(summary: dict) -> str:
    lines = [
        f"Total de decisões avaliadas: {summary['total_decisoes']}",
        f"Nota média de alinhamento: {summary['nota_media']:.1f}%",
        "Nota média por etapa:",
    ]
    for street, data in summary['breakdown_street'].items():
        lines.append(
            f"  - {STREET_PT.get(street, street)}: {data['total_decisoes']} decisões, "
            f"nota média {data['nota_media']:.1f}%"
        )
    padroes = summary['padroes']
    lines.append(
        f"Vezes que foldou quando a recomendação era raise: "
        f"{padroes['foldou_quando_recomendacao_era_raise']}"
    )
    lines.append(
        f"Vezes que deu raise quando a recomendação era fold: "
        f"{padroes['deu_raise_quando_recomendacao_era_fold']}"
    )
    lines.append(
        f"Vezes que continuou na mão com chance de vitória abaixo de 35%: "
        f"{padroes['continuou_mao_fraca_win_prob_abaixo_0_35']}"
    )
    lines.append(
        "\nEscreva um feedback em português com base só nesses números, sem "
        "inventar detalhes de mãos específicas."
    )
    return '\n'.join(lines)


ROUND_SYSTEM_PROMPT = (
    "Você é um assistente que comenta rapidamente UMA rodada de poker Texas Hold'em "
    "heads-up. Use apenas os números fornecidos — não invente cartas ou situações que "
    "não estão nos dados. Responda em português do Brasil, em 1 a 3 frases curtas e "
    "diretas, destacando a decisão mais relevante da rodada. "
    + TERMS_INSTRUCTION
)


def build_round_prompt(summary: dict) -> str:
    lines = [
        f"Decisões do jogador nesta rodada: {summary['total_decisoes']}",
        f"Nota média de alinhamento: {summary['nota_media']:.1f}%",
    ]
    for d in summary['decisoes']:
        recomendado = d.get('recommended_action') or d['fuzzy_recommendation']
        lines.append(
            f"  - {STREET_PT.get(d['street'], d['street'])}: "
            f"chance de vitória {d['win_prob']:.0%}, pot odds {d['pot_odds']:.0%}, "
            f"chance de melhorar {d['ppot']:.0%}, risco de piorar {d['npot']:.0%}, "
            f"agressividade do agente {d['opponent_aggression']:.0%}, "
            f"fichas comprometidas {d['stack_commitment']:.0%} "
            f"→ recomendação do agente: {recomendado} | jogada do jogador: {d['action_type']} "
            f"(pontuação {d['score']:.1f})"
        )
    lines.append("\nComente brevemente a decisão mais importante dessa rodada.")
    return '\n'.join(lines)


# Ponto único de chamada ao provider de LLM — manter aqui facilita trocar/adicionar
# outro provider (ex: modelo gratuito) sem mexer nos prompts/chamadores.
def _call_claude(system_prompt: str, user_prompt: str, max_tokens: int) -> str:
    client  = anthropic.Anthropic()
    message = client.messages.create(
        model='claude-haiku-4-5-20251001',
        max_tokens=max_tokens,
        system=system_prompt,
        messages=[{'role': 'user', 'content': user_prompt}],
    )
    return message.content[0].text


def generate_feedback(summary: dict) -> str:
    return _call_claude(SYSTEM_PROMPT, build_prompt(summary), max_tokens=600)


def generate_round_feedback(summary: dict) -> str:
    return _call_claude(ROUND_SYSTEM_PROMPT, build_round_prompt(summary), max_tokens=250)
