from dotenv import load_dotenv
load_dotenv()

import anthropic

SYSTEM_PROMPT = (
    "Você é um assistente que escreve feedback construtivo sobre uma partida de "
    "poker Texas Hold'em heads-up. Use apenas os números fornecidos — não invente "
    "mãos, cartas ou situações específicas que não estão nos dados. Responda em "
    "português do Brasil, em 3 a 5 parágrafos curtos, tom direto e construtivo, "
    "citando 1 a 2 pontos fortes e 1 a 2 pontos de melhoria baseados só nesses números."
)


def build_prompt(summary: dict) -> str:
    lines = [
        f"Total de decisões avaliadas: {summary['total_decisoes']}",
        f"Nota média de alinhamento: {summary['nota_media']:.1f}%",
        "Nota média por street:",
    ]
    for street, data in summary['breakdown_street'].items():
        lines.append(
            f"  - {street}: {data['total_decisoes']} decisões, "
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
        f"Vezes que continuou na mão com probabilidade de vitória abaixo de 35%: "
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
    "diretas, destacando a decisão mais relevante da rodada."
)


def build_round_prompt(summary: dict) -> str:
    lines = [
        f"Decisões do jogador nesta rodada: {summary['total_decisoes']}",
        f"Nota média de alinhamento: {summary['nota_media']:.1f}%",
    ]
    for d in summary['decisoes']:
        lines.append(
            f"  - {d['street']}: win_prob={d['win_prob']:.2f} pot_odds={d['pot_odds']:.2f} "
            f"ppot={d['ppot']:.2f} npot={d['npot']:.2f} "
            f"agressividade_oponente={d['opponent_aggression']:.2f} "
            f"stack_commitment={d['stack_commitment']:.2f} "
            f"→ recomendado={d['fuzzy_recommendation']} | ação real={d['action_type']} "
            f"(score={d['score']:.1f})"
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
