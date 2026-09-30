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
| `hand_strength.py` | Calcula `win_prob` (Monte Carlo) e `ppot`/`npot` (potencial da mão), entradas para o agente |

O `SystemPlayer` (`players/system_player.py`) orquestra: calcula as 7 entradas (3
originais + `ppot`, `npot`, `opponent_aggression`, `stack_commitment`), chama o agente
fuzzy e traduz a recomendação para uma ação válida dentro das regras do jogo.

---

## Variáveis de entrada (antecedentes)

Todas definidas no universo **[0, 1]**. As 3 primeiras (`hand_strength`, `pot_odds`,
`position`) compunham o sistema original. As 4 seguintes (`ppot`, `npot`,
`opponent_aggression`, `stack_commitment`) foram adicionadas a partir de um levantamento
de trabalhos correlatos — ver seção [Origem das novas variáveis](#origem-das-novas-variáveis-2024)
mais abaixo.

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

### 4. `ppot` — Potencial positivo (PPot)

Probabilidade de uma mão **atrás ou empatada** terminar **à frente** depois que o board
completar (Billings 2006 — algoritmo clássico de Hand Strength / Hand Potential).
Calculada em `hand_strength.py:calculate_hand_potential()`, reaproveitando a mesma
simulação Monte Carlo de `calculate_win_probability` (mesmo deck restante, mesma
amostragem), mas classificando cada trial em `ahead`/`behind`/`tied` **antes** e
**depois** das cartas futuras:

```
PPot = (behind→ahead + tied→ahead + 0.5·behind→tied) / (behind_total + tied_total)
```

**Só é calculada no flop e no turn.** No pré-flop, `treys.Evaluator` exige ≥5 cartas
(mão+board), o que inviabiliza a classificação "estado atual"; no river não há mais
cartas por vir, então o potencial é 0 por definição — o próprio Billings/paper de
referência nota que hand potential "não é significativo na fase de river". Nessas duas
streets, `SystemPlayer` não chama a simulação: usa `ppot = npot = 0.0` diretamente.

| Termo | Função | Parâmetros |
|-------|--------|------------|
| `baixo` | trapmf | [0, 0, 0.15, 0.30] |
| `medio` | trimf | [0.20, 0.35, 0.50] |
| `alto` | trapmf | [0.40, 0.55, 1.00, 1.00] |

### 5. `npot` — Potencial negativo (NPot)

Complemento de PPot: probabilidade de uma mão **à frente** terminar **atrás** depois do
board completar. Mesma função `calculate_hand_potential()` (retorna a tupla
`(ppot, npot)` em uma única passada de simulação), mesma regra de janela (flop/turn
apenas).

```
NPot = (ahead→behind + tied→behind + 0.5·ahead→tied) / (ahead_total + tied_total)
```

| Termo | Função | Parâmetros |
|-------|--------|------------|
| `baixo` | trapmf | [0, 0, 0.15, 0.30] |
| `medio` | trimf | [0.20, 0.35, 0.50] |
| `alto` | trapmf | [0.40, 0.55, 1.00, 1.00] |

### 6. `opponent_aggression` — Agressividade do oponente

Sinal composto sobre o comportamento recente do oponente (jogador humano), calculado em
`SystemPlayer._opponent_aggression()`:

```
score = 0.5·peso(última_ação) + 0.3·min(raises_nesta_street / 2, 1) + 0.2·min(raises_streets_anteriores / 3, 1)
```

onde `peso(última_ação)` é `1.0` para `raise`/`bet`/`allin`, `0.4` para `call` e `0.0`
para `check`/`fold`/nenhuma ação ainda. `raises_nesta_street` e
`raises_streets_anteriores` vêm de contadores novos no `GameController`
(`_actions_this_street`, `_raises_prev_streets`), populados em `_apply_action` e
consolidados em `_next_street`.

| Termo | Função | Parâmetros |
|-------|--------|------------|
| `passivo` | trapmf | [0, 0, 0.25, 0.40] |
| `moderado` | trimf | [0.30, 0.50, 0.70] |
| `agressivo` | trapmf | [0.60, 0.75, 1.00, 1.00] |

### 7. `stack_commitment` — Comprometimento de stack (proxy de SPR)

Quanto do "total de fichas em jogo" do agente já está no pot nesta rodada — proxy padrão
de Stack-to-Pot Ratio (SPR), calculado sem necessidade de rastrear apostas por street:

```
stack_commitment = pot / (pot + stack_do_agente)
```

Tende a 0 no início da rodada (muito stack disponível em relação ao pot) e a 1 conforme o
agente vai all-in / fica pot-committed.

| Termo | Função | Parâmetros |
|-------|--------|------------|
| `baixo` | trapmf | [0, 0, 0.20, 0.35] |
| `medio` | trimf | [0.25, 0.45, 0.65] |
| `alto` | trapmf | [0.55, 0.70, 1.00, 1.00] |

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

28 regras no total. As 14 primeiras (R1-R14) são o sistema original, organizadas por
força de mão, e **não foram alteradas**. R15-R28 foram adicionadas junto com as 4 novas
variáveis, combinando seletivamente `hand_strength` com uma (ocasionalmente duas) das
novas entradas — evitando o produto cartesiano completo das 7 variáveis, que seria
inviável de escrever/revisar à mão.

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

# --- PPot / NPot: potencial de melhora/piora ---
R15: media AND ppot alto                          → call   # upgrade de fold marginal por potencial de draw
R16: fraca AND ppot alto AND pot_odds baixo        → call   # draw especulativo barato
R17: forte AND npot alto                          → call   # mão forte mas vulnerável: segura, não escala pra raise
R18: media AND npot alto                          → fold   # mão média vulnerável: não vale continuar

# --- Agressividade do oponente (opponent modeling) ---
R19: fraca AND opponent_aggression agressivo                    → fold
R20: media AND opponent_aggression agressivo                    → fold
R21: media AND opponent_aggression agressivo AND pot_odds alto  → fold   # reforço
R22: forte AND opponent_aggression passivo                      → raise  # value bet maior contra passivo
R23: media AND opponent_aggression passivo                       → call   # call down mais solto contra passivo
R24: fraca AND opponent_aggression passivo AND dentro            → raise  # tentativa de roubo (steal)

# --- Comprometimento de stack (SPR) ---
R25: forte AND stack_commitment alto              → raise
R26: media AND stack_commitment alto              → call   # pot committed, mão média não dá pra foldar
R27: fraca AND stack_commitment baixo             → fold   # reforço: sobra stack, sem motivo pra arriscar
R28: stack_commitment alto AND pot_odds baixo      → call
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
    'win_prob':            float,   # probabilidade Monte Carlo
    'pot_odds':            float,   # to_call / (pot + to_call)
    'position':            float,   # 1.0 ou 0.0
    'ppot':                float,   # potencial positivo (0.0 fora de flop/turn)
    'npot':                float,   # potencial negativo (0.0 fora de flop/turn)
    'opponent_aggression': float,   # agressividade do oponente
    'stack_commitment':    float,   # pot / (pot + stack)
    'recommendation':      str,     # 'fold' | 'call' | 'raise'
}
```

Esses dados são persistidos via `GameRecorder` na tabela `actions` (colunas `win_prob`,
`pot_odds`, `position`, `ppot`, `npot`, `opponent_aggression`, `stack_commitment`,
`fuzzy_recommendation`) do SQLite, servindo como dataset para o módulo de aprendizado de
máquina — incluindo a etapa de tuning dos parâmetros das funções de pertinência
mencionada abaixo.

---

## Origem das novas variáveis (2024)

`ppot`, `npot`, `opponent_aggression` e `stack_commitment` foram adicionadas a partir da
análise de features candidatas do paper **Ekmekci, Ö.; Şirin, V. (2013). "Learning
Strategies for Opponent Modeling in Poker". AAAI Workshop on Computer Poker and
Imperfect Information** — que também trata heads-up limit Texas Hold'em e lista 19
features candidatas (Table 1) para modelar o oponente via ML, com um estudo de seleção
de features (backward elimination) por oponente (Table 5). Priorizamos as features mais
selecionadas empiricamente naquele estudo: PPot/NPot (6/8 oponentes), raises em streets
anteriores (8/8 oponentes — a feature mais consistentemente selecionada do paper todo) e
stack comprometido (5/8 oponentes). Detalhes da escolha e do racional de implementação
em `PLANO_EXPANSAO_FUZZY.md` (raiz do projeto).

O paper resolve um problema diferente do nosso (classificação da *próxima ação do
oponente* via NN/SVM/KNN) — não copiamos a metodologia de ML deles, só a definição das
features e a evidência empírica de relevância, adaptando-as para entradas de um sistema
fuzzy.

**Sinalização:** os breakpoints numéricos das funções de pertinência das 4 novas
variáveis (seção acima) são estimativas de engenharia, não derivadas do paper (que não
usa lógica fuzzy) nem de nenhuma outra fonte formal — ponto de partida para a etapa de
calibração automática (ML) dos parâmetros do sistema fuzzy.
