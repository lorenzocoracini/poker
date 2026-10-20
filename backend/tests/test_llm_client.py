# generate_feedback is NOT tested here — it would call the real Anthropic API
# (costs money, needs network and a real API key, which this environment does
# not have). Only build_prompt (pure string formatting) is covered.
from feedback.llm_client import build_prompt, build_round_prompt


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
    assert 'pré-flop' in prompt
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


def test_build_round_prompt_uses_portuguese_labels():
    summary = {
        'total_decisoes': 1,
        'nota_media': 50.0,
        'decisoes': [{
            'street': 'flop', 'win_prob': 0.26, 'pot_odds': 0.0, 'ppot': 0.26,
            'npot': 0.35, 'opponent_aggression': 0.0, 'stack_commitment': 0.06,
            'recommended_action': 'check', 'fuzzy_recommendation': 'fold',
            'action_type': 'bet', 'score': 0.5,
        }],
    }

    prompt = build_round_prompt(summary)

    assert 'chance de vitória 26%' in prompt
    assert 'risco de piorar 35%' in prompt
    assert 'win_prob' not in prompt
    assert 'ppot' not in prompt
