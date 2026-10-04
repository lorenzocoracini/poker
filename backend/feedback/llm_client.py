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


def generate_feedback(summary: dict) -> str:
    client  = anthropic.Anthropic()
    message = client.messages.create(
        model='claude-haiku-4-5-20251001',
        max_tokens=600,
        system=SYSTEM_PROMPT,
        messages=[{'role': 'user', 'content': build_prompt(summary)}],
    )
    return message.content[0].text
