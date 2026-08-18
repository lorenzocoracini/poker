# Sistema de Inferência Fuzzy — Agente de Poker

Documentação do módulo fuzzy que controla as decisões do agente inteligente no jogo Texas Hold'em Heads-Up.

---

## Visão geral

O agente usa um **sistema de inferência Mamdani** implementado com a biblioteca `scikit-fuzzy`. O fluxo de decisão segue quatro etapas:

```
Entradas numéricas
    → Fuzzificação (graus de pertinência)
    → Inferência (ativação das regras)
    → Agregação + Defuzzificação (centroide → número)
    → Limiar (número → string: fold / call / raise)
    → Mapeamento para ação válida no jogo
```

A implementação está dividida em dois arquivos:

| Arquivo | Responsabilidade |
|---------|-----------------|
| `fuzzy_agent.py` | Define variáveis, funções de pertinência e regras; expõe `decide()` |
| `hand_strength.py` | Calcula `win_prob` via simulação Monte Carlo (entrada para o agente) |

O `SystemPlayer` (`players/system_player.py`) orquestra: calcula as entradas, chama o agente fuzzy e traduz a recomendação para uma ação válida dentro das regras do jogo.

---

## Variáveis de entrada (antecedentes)

Todas definidas no universo **[0, 1]**.

### 1. `hand_strength` — Força da mão

Representa a probabilidade de vitória estimada via simulação Monte Carlo sobre o deck restante (500 iterações por decisão). Calculada em `hand_strength.py`.

| Termo linguístico | Função | Parâmetros |
|-------------------|--------|------------|
| `fraca` | trapmf | [0, 0, 0.30, 0.45] |
| `media` | trimf | [0.35, 0.50, 0.65] |
| `forte` | trimf | [0.55, 0.70, 0.85] |
| `muito_forte` | trapmf | [0.75, 0.90, 1.00, 1.00] |

```
0    0.30  0.45  0.55  0.65  0.75  0.90  1.0
|____|      |      |      |      |      |
fraca↘    media↗ ↘   forte↗  ↘   muito_forte→
```

**Como é calculado:** `calculate_win_probability()` amostra aleatoriamente 2 cartas para o oponente e as cartas comunitárias faltantes, avalia ambas as mãos com `treys.Evaluator` e conta vitórias e empates. O resultado é `(wins + ties * 0.5) / n_simulations`.

### 2. `pot_odds` — Odds do pot

Mede o custo relativo de continuar na mão em relação ao pot atual:

```
pot_odds = to_call / (pot + to_call)
```

Se não há nada a pagar (`to_call == 0`), `pot_odds = 0.0`.

| Termo | Função | Parâmetros |
|-------|--------|------------|
| `baixo` | trapmf | [0, 0, 0.20, 0.35] |
| `medio` | trimf | [0.25, 0.40, 0.55] |
| `alto` | trapmf | [0.45, 0.60, 1.00, 1.00] |

### 3. `position` — Posição

Variável binária que indica se o agente está **in position** (é o button, age por último).

| Valor | Significado |
|-------|-------------|
| `1.0` | `dentro` — button (age por último; vantagem informacional) |
| `0.0` | `fora` — big blind (age primeiro no flop em diante) |

| Termo | Função | Parâmetros |
|-------|--------|------------|
| `fora` | trapmf | [0, 0, 0.30, 0.50] |
| `dentro` | trapmf | [0.50, 0.70, 1.00, 1.00] |

---

## Variável de saída (consequente)

### `action_score` — Pontuação de ação

Universo **[0, 1]**. Não é uma categoria — é uma região contínua. Os termos nomeiam zonas do espaço de saída:

| Termo | Função | Parâmetros | Zona |
|-------|--------|------------|------|
| `fold` | trapmf | [0, 0, 0.20, 0.35] | baixa agressividade |
| `call` | trimf | [0.25, 0.50, 0.75] | agressividade média |
| `raise` | trapmf | [0.65, 0.80, 1.00, 1.00] | alta agressividade |

> **Importante:** a palavra `'fold'` no consequente não toma a decisão de foldar. Ela nomeia a **região [0, 0.35]** do universo de saída. As regras empurram o score para essa região; o centroide calcula um número; o limiar (`score < 0.35`) é o que converte em ação.

---

## Regras fuzzy

14 regras no total, organizadas por força de mão.

```python
# Mão muito forte: sempre raise
R1:  muito_forte                        → raise

# Mão forte: posição determina agressividade
R2:  forte AND dentro                   → raise
R3:  forte AND fora                     → call
R4:  forte AND pot_odds alto            → call   # proteção mesmo sem posição

# Mão média: pot odds e posição decidem
R5:  media AND pot_odds baixo           → call
R6:  media AND pot_odds medio           → call
R7:  media AND pot_odds alto            → fold
R8:  media AND dentro                   → call
R9:  media AND fora                     → fold

# Mão fraca: fold padrão
R10: fraca AND pot_odds baixo           → fold
R11: fraca AND pot_odds medio           → fold
R12: fraca AND pot_odds alto            → fold
R13: fraca AND fora                     → fold

# Mão fraca com posição: call especulativo (tentativa de roubo)
R14: fraca AND dentro                   → call
```

---

## Inferência e defuzzificação

1. **Fuzzificação:** cada valor de entrada é convertido em graus de pertinência para todos os termos da variável (ex: `win_prob = 0.62` → `forte = 0.40`, `muito_forte = 0.13`).

2. **Ativação das regras:** cada regra dispara com intensidade igual ao `min` dos graus de pertinência das premissas (operador AND fuzzy).

3. **Agregação:** as regiões do consequente (`fold`, `call`, `raise`) são cortadas na intensidade de cada regra e somadas (`max` por região).

4. **Defuzzificação (centroide):** a área agregada é resumida em um único número — o centro de massa da distribuição resultante.

5. **Limiar (thresholding):** o número é convertido em string:

```python
if   score < 0.35:  return 'fold'
elif score < 0.65:  return 'call'
else:               return 'raise'
```

---

## Mapeamento para ação do jogo

A recomendação (`'fold'` / `'call'` / `'raise'`) não é aplicada diretamente — o `SystemPlayer` adapta ao estado legal do jogo:

| Estado do jogo | `fold` | `call` | `raise` |
|----------------|--------|--------|---------|
| Pode check (sem bet) | `check` | `check` | `bet bb×3` |
| Nada a pagar | `check` | `check` | `raise bb×3` |
| All-in do oponente | `fold` | `call (all-in)` | `call (all-in)` |
| Há valor a pagar | `fold` | `call to_call` | `raise bb×3` |

O sistema nunca faz bet/raise maior que sua stack (`min(bb*3, self.stack)`).

---

## Dados salvos para ML

A cada decisão, o `SystemPlayer` armazena `last_fuzzy_data`:

```python
{
    'win_prob':       float,   # probabilidade Monte Carlo
    'pot_odds':       float,   # to_call / (pot + to_call)
    'position':       float,   # 1.0 ou 0.0
    'recommendation': str,     # 'fold' | 'call' | 'raise'
}
```

Esses dados são persistidos via `GameRecorder` na tabela `actions` (coluna `fuzzy_recommendation`) do SQLite, servindo como dataset para o módulo de aprendizado de máquina.
