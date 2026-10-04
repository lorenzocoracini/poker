# generate_feedback is NOT tested here — it would call the real Anthropic API
# (costs money, needs network and a real API key, which this environment does
# not have). Only build_prompt (pure string formatting) is covered.
from feedback.llm_client import build_prompt


def test_build_prompt_contains_key_numbers():
    summary = {
        'total_decisoes': 5,
        'nota_media': 80.0,
        'breakdown_street': {
            'preflop': {'total_decisoes': 5, 'nota_media': 80.0},
        },
        'padroes': {
            'foldou_quando_recomendacao_era_raise': 1,
            'deu_raise_quando_recomendacao_era_fold': 0,
            'continuou_mao_fraca_win_prob_abaixo_0_35': 2,
        },
    }

    prompt = build_prompt(summary)

    assert '5' in prompt
    assert '80.0%' in prompt
    assert 'preflop' in prompt
    assert '1' in prompt
    assert '2' in prompt


def test_build_prompt_returns_string_with_multiple_streets():
    summary = {
        'total_decisoes': 10,
        'nota_media': 55.5,
        'breakdown_street': {
            'preflop': {'total_decisoes': 4, 'nota_media': 50.0},
            'flop':    {'total_decisoes': 6, 'nota_media': 60.0},
        },
        'padroes': {
            'foldou_quando_recomendacao_era_raise': 0,
            'deu_raise_quando_recomendacao_era_fold': 1,
            'continuou_mao_fraca_win_prob_abaixo_0_35': 0,
        },
    }

    prompt = build_prompt(summary)

    assert isinstance(prompt, str)
    assert 'flop' in prompt
    assert '55.5%' in prompt
