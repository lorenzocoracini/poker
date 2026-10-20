# Sistema de Inferência Fuzzy — Agente de Poker

Documentação completa do módulo fuzzy que decide as jogadas do agente no Texas Hold'em
heads-up. **Este arquivo é a fonte de verdade do sistema fuzzy**: qualquer alteração em
funções de pertinência, regras ou entradas feita em `fuzzy_agent.py`,
`hand_strength.py` ou `system_player.py` deve ser refletida aqui.

Visão geral do projeto (setup, arquitetura, banco, feedback): ver
[`README.md`](../../../README.md) na raiz.

---

## 1. Visão geral

O agente usa um **sistema de inferência Mamdani** (Mamdani & Assilian, 1975)
implementado com `scikit-fuzzy` (`skfuzzy.control`), com **7 entradas**, **1 saída** e
**28 regras**.

```
Estado do jogo
    → Cálculo das 7 features (Monte Carlo, razões de fichas, histórico de ações)
    → Fuzzificação (graus de pertinência)
    → Inferência (ativação das regras: AND = min)
    → Agregação (max) + Defuzzificação (centroide → número em [0, 1])
    → Limiar (número → 'fold' | 'call' | 'raise')
    → Tradução para uma ação legal do motor (check/bet/call/raise/fold)
```

| Arquivo | Responsabilidade |
|---|---|
| `engine/fuzzy/fuzzy_agent.py` | `FuzzyPokerAgent`: antecedentes, consequente, funções de pertinência, regras e `decide()` |
| `engine/fuzzy/hand_strength.py` | `calculate_win_probability()` (força da mão) e `calculate_hand_potential()` (PPot/NPot), ambos por Monte Carlo com `treys` |
| `engine/players/system_player.py` | `compute_decision_features()` (calcula as 7 entradas), `_opponent_aggression()`, `translate_recommendation()` e `SystemPlayer.decide_action()` |

O `ControlSystem` é montado **uma única vez** em `FuzzyPokerAgent.__init__`
(`_build_system()`); cada chamada a `decide()` só seta as entradas e roda `compute()`.

O mesmo `FuzzyPokerAgent` é usado em dois papéis:

1. **Decidir a jogada do sistema** — `SystemPlayer.decide_action()`.
2. **Avaliar a jogada do humano** (somente leitura) — `GameController._evaluate_player_action()`
   calcula as mesmas features da perspectiva do jogador e pergunta ao agente do
   sistema o que ele recomendaria. Isso alimenta a nota de alinhamento e o feedback
   (seção 9).

---

## 2. Variáveis de entrada (antecedentes)

Todas no universo **[0, 1]**, discretizado em passos de 0.01
(`np.arange(0, 1.01, 0.01)`). Antes da inferência, `decide()` faz *clip* de cada
entrada para **[0.01, 0.99]**.

As 3 primeiras (`hand_strength`, `pot_odds`, `position`) formavam o sistema original.
As 4 últimas (`ppot`, `npot`, `opponent_aggression`, `stack_commitment`) foram
adicionadas a partir do levantamento de trabalhos correlatos descrito na seção 8.

| # | Variável | Fonte do valor | Termos |
|---|---|---|---|
| 1 | `hand_strength` | `calculate_win_probability()` | `fraca`, `media`, `forte`, `muito_forte` |
| 2 | `pot_odds` | `to_call / (pot + to_call)` | `baixo`, `medio`, `alto` |
| 3 | `position` | `1.0` se button, `0.0` se big blind | `fora`, `dentro` |
| 4 | `ppot` | `calculate_hand_potential()` (flop/turn) | `baixo`, `medio`, `alto` |
| 5 | `npot` | `calculate_hand_potential()` (flop/turn) | `baixo`, `medio`, `alto` |
| 6 | `opponent_aggression` | `_opponent_aggression()` | `passivo`, `moderado`, `agressivo` |
| 7 | `stack_commitment` | `pot / (pot + stack)` | `baixo`, `medio`, `alto` |

### 2.1 `hand_strength` — Força da mão

Probabilidade estimada de vitória contra uma mão aleatória do oponente.

**Cálculo** (`calculate_win_probability(hole_cards, community_cards, n_simulations=500)`):
monta o deck restante (52 cartas menos as próprias e as do board), e em cada uma das
500 iterações sorteia 2 cartas para o oponente e as cartas comunitárias que faltam;
avalia as duas mãos com `treys.Evaluator` (menor score = melhor mão) e conta vitórias
e empates:

```
hand_strength = (vitórias + 0.5 · empates) / n_simulations
```

Funciona em todas as streets (no pré-flop sorteia as 5 cartas do board).

| Termo | Função | Parâmetros |
|---|---|---|
| `fraca` | trapmf | [0, 0, 0.30, 0.45] |
| `media` | trimf | [0.35, 0.50, 0.65] |
| `forte` | trimf | [0.55, 0.70, 0.85] |
| `muito_forte` | trapmf | [0.75, 0.90, 1.00, 1.00] |

Sobreposições: `fraca`/`media` em [0.35, 0.45], `media`/`forte` em [0.55, 0.65],
`forte`/`muito_forte` em [0.75, 0.85].

### 2.2 `pot_odds` — Odds do pot

Custo relativo de continuar na mão:

```
pot_odds = to_call / (pot + to_call)      (0.0 se to_call == 0)
```

| Termo | Função | Parâmetros |
|---|---|---|
| `baixo` | trapmf | [0, 0, 0.20, 0.35] |
| `medio` | trimf | [0.25, 0.40, 0.55] |
| `alto` | trapmf | [0.45, 0.60, 1.00, 1.00] |

### 2.3 `position` — Posição

Binária: `1.0` se o jogador avaliado é o **button** (in position — age por último do
flop em diante), `0.0` se é o **big blind** (out of position). Após o clip vira
0.99 / 0.01, então na prática ativa só um dos termos com grau 1.

| Termo | Função | Parâmetros |
|---|---|---|
| `fora` | trapmf | [0, 0, 0.30, 0.50] |
| `dentro` | trapmf | [0.50, 0.70, 1.00, 1.00] |

### 2.4 `ppot` — Potencial positivo (PPot)

Probabilidade de uma mão que está **atrás ou empatada agora** terminar **à frente**
quando o board completar — algoritmo de Hand Potential de Billings (2006).

**Cálculo** (`calculate_hand_potential(hole_cards, community_cards, n_simulations=500)`):
em cada iteração sorteia a mão do oponente e as cartas futuras, e classifica o
confronto duas vezes — com o board **atual** e com o board **final** — em
`ahead`/`tied`/`behind`, acumulando as 9 transições possíveis. Retorna `(ppot, npot)`
numa única passada.

```
PPot = (behind→ahead + tied→ahead + 0.5 · behind→tied) / (behind_total + tied_total)
```

**Só é calculado no flop e no turn.** No pré-flop o `treys.Evaluator` exige ≥ 5
cartas (mão + board) para classificar o estado atual; no river não há cartas por vir,
então o potencial é zero por definição. Nessas streets `compute_decision_features()`
nem chama a simulação: usa `ppot = npot = 0.0`.

| Termo | Função | Parâmetros |
|---|---|---|
| `baixo` | trapmf | [0, 0, 0.15, 0.30] |
| `medio` | trimf | [0.20, 0.35, 0.50] |
| `alto` | trapmf | [0.40, 0.55, 1.00, 1.00] |

### 2.5 `npot` — Potencial negativo (NPot)

Complemento do PPot: probabilidade de uma mão **à frente ou empatada agora** terminar
**atrás**. Mesma função, mesma janela (flop/turn).

```
NPot = (ahead→behind + tied→behind + 0.5 · ahead→tied) / (ahead_total + tied_total)
```

| Termo | Função | Parâmetros |
|---|---|---|
| `baixo` | trapmf | [0, 0, 0.15, 0.30] |
| `medio` | trimf | [0.20, 0.35, 0.50] |
| `alto` | trapmf | [0.40, 0.55, 1.00, 1.00] |

> Nota de design: não usamos a combinação `P(win) = HS·(1−NPot) + (1−HS)·PPot`
> (Felix & Reis, 2008) porque `hand_strength` já é um rollout completo até o river.
> PPot/NPot entram como sinais **adicionais** (potencial de melhora/piora), não como
> decomposição da mesma métrica.

### 2.6 `opponent_aggression` — Agressividade do oponente

Sinal composto sobre o comportamento recente do oponente, calculado em
`_opponent_aggression(game_state)` (função module-level em `system_player.py`):

```
score = 0.5 · peso(última_ação)
      + 0.3 · min(raises_nesta_street / 2, 1)
      + 0.2 · min(raises_streets_anteriores / 3, 1)        → clip em [0, 1]
```

| Última ação do oponente | Peso |
|---|---|
| `raise`, `bet`, `allin` | 1.0 |
| `call` | 0.4 |
| `check`, `fold`, nenhuma | 0.0 |

Os contadores vêm do `GameController`:

- `_actions_this_street` — lista `(ator, ação)` da street corrente; zerada em
  `start_new_round()` e `_next_street()`.
- `_raises_prev_streets` — dicionário `{ator: nº de bet/raise/allin}` acumulado nas
  streets já encerradas da rodada; consolidado em `_next_street()` e zerado a cada
  rodada.

Quando o agente decide, "oponente" = humano; quando avalia a jogada do humano,
"oponente" = sistema (os contadores são lidos do outro ator).

Constantes (`_LAST_ACTION_WEIGHT`, `_AGGRESSION_STREET_CAP = 2`,
`_AGGRESSION_PREV_CAP = 3`) ficam no topo de `system_player.py`.

| Termo | Função | Parâmetros |
|---|---|---|
| `passivo` | trapmf | [0, 0, 0.25, 0.40] |
| `moderado` | trimf | [0.30, 0.50, 0.70] |
| `agressivo` | trapmf | [0.60, 0.75, 1.00, 1.00] |

### 2.7 `stack_commitment` — Comprometimento de stack (proxy de SPR)

Fração das fichas "em jogo" do jogador que já está no pot — proxy do *stack-to-pot
ratio* (SPR), sem precisar rastrear apostas por street:

```
stack_commitment = pot / (pot + stack)      (0.0 se pot + stack == 0)
```

Próximo de 0 no início da rodada (muito stack em relação ao pot); tende a 1 quando o
jogador fica *pot committed*. É uma simplificação deliberada das features #7/#8 de
Ekmekci & Şirin (2013), que medem a aposta só da fase atual.

| Termo | Função | Parâmetros |
|---|---|---|
| `baixo` | trapmf | [0, 0, 0.20, 0.35] |
| `medio` | trimf | [0.25, 0.45, 0.65] |
| `alto` | trapmf | [0.55, 0.70, 1.00, 1.00] |

> **Sinalização:** os breakpoints das funções de pertinência das 4 variáveis novas, e
> os pesos/caps de `opponent_aggression`, são **estimativas de engenharia** — não vêm
> de literatura (o paper de referência não usa lógica fuzzy). Uma calibração
> sistemática fica como trabalho futuro (seção 10).

---

## 3. Variável de saída (consequente)

### `action_score`

Universo **[0, 1]**. Não é uma categoria, é um eixo contínuo de agressividade; os
termos nomeiam regiões desse eixo.

| Termo | Função | Parâmetros | Região |
|---|---|---|---|
| `fold` | trapmf | [0, 0, 0.20, 0.35] | baixa agressividade |
| `call` | trimf | [0.25, 0.50, 0.75] | agressividade média |
| `raise` | trapmf | [0.65, 0.80, 1.00, 1.00] | alta agressividade |

> O termo `fold` no consequente não "decide foldar": ele só empurra a massa da
> distribuição para a região baixa do eixo. Quem converte em ação é o limiar da
> seção 5.

---

## 4. Base de regras (28 regras)

Uma única base de regras com um único consequente. R1–R14 são o sistema original
(organizado por força da mão) e **não foram alteradas** na expansão. R15–R28 combinam
`hand_strength` com uma (às vezes duas) das variáveis novas — evitando o produto
cartesiano completo das 7 entradas (4×3×2×3×3×3×3 = 1.944 combinações), inviável de
escrever e revisar à mão.

```text
# ── Mão muito forte ─────────────────────────────────────────────────────
R1:  muito_forte                                      → raise

# ── Mão forte: posição determina agressividade ─────────────────────────
R2:  forte AND position dentro                        → raise
R3:  forte AND position fora                          → call
R4:  forte AND pot_odds alto                          → call    # continua mesmo pagando caro

# ── Mão média: pot odds e posição decidem ──────────────────────────────
R5:  media AND pot_odds baixo                         → call
R6:  media AND pot_odds medio                         → call
R7:  media AND pot_odds alto                          → fold
R8:  media AND position dentro                        → call
R9:  media AND position fora                          → fold

# ── Mão fraca: fold padrão ─────────────────────────────────────────────
R10: fraca AND pot_odds baixo                         → fold
R11: fraca AND pot_odds medio                         → fold
R12: fraca AND pot_odds alto                          → fold
R13: fraca AND position fora                          → fold
R14: fraca AND position dentro                        → call    # especulativo / roubo

# ── PPot / NPot: potencial de melhora/piora ────────────────────────────
R15: media AND ppot alto                              → call    # draw salva mão marginal
R16: fraca AND ppot alto AND pot_odds baixo           → call    # draw barato
R17: forte AND npot alto                              → call    # forte mas vulnerável: não escala
R18: media AND npot alto                              → fold    # média e vulnerável

# ── Agressividade do oponente (opponent modeling) ──────────────────────
R19: fraca AND opp_aggression agressivo               → fold
R20: media AND opp_aggression agressivo               → fold
R21: media AND opp_aggression agressivo AND pot_odds alto → fold  # reforço
R22: forte AND opp_aggression passivo                 → raise   # value bet contra passivo
R23: media AND opp_aggression passivo                 → call    # call down mais solto
R24: fraca AND opp_aggression passivo AND position dentro → raise # steal

# ── Comprometimento de stack (SPR) ─────────────────────────────────────
R25: forte AND stack_commitment alto                  → raise
R26: media AND stack_commitment alto                  → call    # pot committed
R27: fraca AND stack_commitment baixo                 → fold    # sobra stack, sem motivo pra arriscar
R28: stack_commitment alto AND pot_odds baixo         → call
```

Resumo do comportamento:

- **Mão muito forte** → sempre `raise`.
- **Mão forte** → `raise` em posição ou contra oponente passivo ou com stack
  comprometido; `call` fora de posição, com pot odds altos ou com NPot alto.
- **Mão média** → `call` com pot odds baixos/médios, em posição, com draw (PPot alto),
  contra passivo ou pot committed; `fold` com pot odds altos, fora de posição,
  vulnerável (NPot alto) ou contra agressivo.
- **Mão fraca** → `fold` quase sempre; `call` especulativo em posição ou com draw
  barato; `raise` (steal) em posição contra oponente passivo.

---

## 5. Inferência e defuzzificação

Operadores (padrão do `skfuzzy.control`):

| Etapa | Operador |
|---|---|
| AND entre premissas | `min` |
| Implicação (Mamdani) | `min` (corta o termo do consequente na força da regra) |
| Agregação de regras | `max` |
| Defuzzificação | centroide |

1. **Fuzzificação** — cada entrada vira graus de pertinência em todos os seus termos.
   Ex.: `hand_strength = 0.62` → `media = 0.20`, `forte = 0.47` (demais termos = 0).
2. **Ativação** — força de cada regra = `min` dos graus das premissas.
3. **Implicação + agregação** — cada termo do consequente é cortado na força da regra
   que o aponta; as regiões resultantes são unidas por `max`.
4. **Defuzzificação** — centroide da área agregada → `score ∈ [0, 1]`.
5. **Limiar** (em `decide()`):

```python
if   score < 0.35: return 'fold'
elif score < 0.65: return 'call'
else:              return 'raise'
```

Se `compute()` lançar exceção (por exemplo, nenhuma regra ativada), `decide()`
retorna `'call'` como fallback.

### Exemplo resolvido

Entradas: `hand_strength=0.62`, `pot_odds=0.25`, `position=1.0` (button), `ppot=0.10`,
`npot=0.30`, `opponent_aggression=0.40`, `stack_commitment=0.20`.

| Variável | Graus não-nulos |
|---|---|
| hand_strength | media 0.20, forte 0.47 |
| pot_odds | baixo 0.67 |
| position | dentro 1.0 |
| ppot | baixo 1.0 |
| npot | medio 0.67 |
| opponent_aggression | moderado 0.50 |
| stack_commitment | baixo 1.0 |

Regras ativadas: R2 (forte ∧ dentro → raise, 0.47), R5 (media ∧ pot_odds baixo →
call, 0.20), R8 (media ∧ dentro → call, 0.20). Agregado: `raise` cortado em 0.47 e
`call` em 0.20 → centroide **0.713** → `raise`.

Mesma situação **fora de posição** e com oponente **agressivo** (`position=0.0`,
`opponent_aggression=0.90`): ativam R3 (forte ∧ fora → call, 0.47), R5 (call, 0.20),
R9 (media ∧ fora → fold, 0.20) e R20 (media ∧ agressivo → fold, 0.20) → centroide
**0.415** → `call`.

(Valores obtidos rodando `FuzzyPokerAgent().decide(...)` no código atual.)

---

## 6. Tradução para ação do jogo

O agente fala em `fold`/`call`/`raise`; o motor tem `fold`, `check`, `call`, `bet`,
`raise`, `allin`. `translate_recommendation(recommendation, can_check, has_bet,
to_call, stack)` faz a ponte, testando as condições nesta ordem:

| Situação | `fold` | `call` | `raise` |
|---|---|---|---|
| Ninguém apostou na street (`can_check and not has_bet`) | `check` | `check` | `bet` |
| Nada a pagar (`to_call == 0`, ex.: BB após limp) | `check` | `check` | `raise` |
| Pagar exige todo o stack (`to_call >= stack`) | `fold` | `call` | `call` |
| Há valor a pagar | `fold` | `call` | `raise` |

Quando não há nada a pagar, `fold` vira `check` (foldar de graça nunca é melhor).

Tamanhos usados pelo `SystemPlayer`:

- `bet`/`raise`: `min(big_blind × 3, stack)` — tamanho fixo.
- `call`: `min(to_call, stack)`.
- O sistema nunca escolhe `allin` explicitamente; vai all-in quando o raise/call
  consome o stack inteiro.

A mesma função traduz a recomendação feita para o humano (coluna
`recommended_action`), para exibir no feedback a ação concreta que o agente
sugeriria naquele spot.

---

## 7. Dados registrados

A cada decisão, o dicionário de features + recomendação é gravado na tabela `actions`
do SQLite via `GameRecorder.record_action()` — **tanto para o sistema
(`actor='system'`) quanto para o humano (`actor='player'`)**.

```python
{
    'win_prob':            float,  # hand_strength (Monte Carlo)
    'pot_odds':            float,  # to_call / (pot + to_call)
    'position':            float,  # 1.0 (button) ou 0.0 (big blind)
    'ppot':                float,  # 0.0 fora de flop/turn
    'npot':                float,  # 0.0 fora de flop/turn
    'opponent_aggression': float,
    'stack_commitment':    float,  # pot / (pot + stack)
    'recommendation':      str,    # 'fold' | 'call' | 'raise'  → coluna fuzzy_recommendation
    'recommended_action':  str,    # ação traduzida (check/bet/...) → coluna recommended_action
}
```

Para o sistema, esse dicionário fica também em `SystemPlayer.last_fuzzy_data`
e cada decisão imprime no terminal uma linha
`[FUZZY] win=... pot_odds=... pos=IN|OUT ppot=... npot=... aggr=... commit=... → rec (ação)`.

Esses registros (entradas + recomendação + ação real + resultado da rodada) alimentam
a avaliação do jogador (seção 9) e servem de base para uma eventual calibração dos
parâmetros das funções de pertinência e/ou das regras (seção 10).

---

## 8. Origem das variáveis novas

`ppot`, `npot`, `opponent_aggression` e `stack_commitment` foram escolhidas a partir
de **Ekmekci & Şirin (2013)**, que também trata heads-up limit Texas Hold'em e lista
19 features candidatas (Table 1) para prever a próxima ação do oponente via ML
(NN/SVM/KNN), com um estudo de seleção de features por *backward elimination* para
8 oponentes (Table 5). Priorizamos as features mais selecionadas empiricamente:

| Feature(s) no paper | Seleção na Table 5 (de 8) | Variável fuzzy |
|---|---|---|
| #2 PPot | 6/8 | `ppot` |
| #3 NPot | 7/8 | `npot` |
| #6, #9, #10, #14, #15 — última ação e nº de raises (street atual e anteriores) | #14 em **8/8** (a mais consistente do paper) | `opponent_aggression` (composta) |
| #7, #8 — stack comprometido no round (#7 próprio, #8 do adversário) | #8 em 5/8; #7 em 0/8 | `stack_commitment` (adaptada para SPR) |

Descartadas:

- **Hand rank** (#11) — redundante com `hand_strength`, que já é uma estimativa de
  probabilidade de vitória mais informativa.
- **Textura do board** (#16–#19) — menos selecionadas (1–3/8) e mais relevantes em
  jogos multiway.

O paper resolve um problema diferente (classificação da ação do oponente); só
aproveitamos a **definição das features** e a **evidência empírica de relevância**,
adaptando-as como entradas de um sistema fuzzy. Arquitetura escolhida: base de regras
única expandida (descartada a alternativa hierárquica em dois estágios), mantendo as
14 regras originais intactas.

---

## 9. Uso na avaliação do jogador humano

A cada ação do humano, antes de aplicá-la, `GameController._evaluate_player_action()`:

1. Monta um `game_state` da perspectiva do jogador (`is_button = button == 'player'`;
   agressividade calculada sobre as ações do **sistema**).
2. Chama `compute_decision_features(player.hand, player.stack, gs)`.
3. Pede `self.system.fuzzy_agent.decide(...)` e traduz com
   `translate_recommendation(...)`.
4. Grava o resultado junto com a ação real (`actor='player'`).

É estritamente leitura/registro — não altera a jogada de ninguém. O custo é uma
simulação Monte Carlo extra por decisão do humano.

A pontuação (`feedback/session_report.py:score_decision`) projeta as ações numa escala
ordinal `fold (0) < check/call (1) < bet/raise/allin (2)` e compara com a
recomendação **já traduzida para o spot** (`recommended_action`; ex.: `fold` vira
`check` quando não há aposta a pagar): igual = 1.0, adjacente = 0.5, oposta = 0.0.
Registros antigos sem `recommended_action` usam a saída abstrata
(`fuzzy_recommendation`) como fallback.

> **Limitação:** a nota mede alinhamento com a política **deste** agente fuzzy, cujos
> parâmetros ainda não foram calibrados — não é uma medida de jogo ótimo (GTO).

---

## 10. Pontos de calibração (trabalho futuro)

A fase de aprendizado de máquina saiu do escopo do TCC. Parâmetros candidatos a um
ajuste automático futuro:

- Breakpoints das funções de pertinência das 7 entradas e da saída.
- Limiares de defuzzificação (0.35 / 0.65).
- Pesos e caps de `opponent_aggression` (0.5 / 0.3 / 0.2; caps 2 e 3).
- Seleção/peso das regras.
- Tamanho de aposta do sistema (fixo em 3 BB) e nº de simulações Monte Carlo (500).

Ao alterar qualquer um, atualizar este documento.

---

## Referências

- **Mamdani, E. H.; Assilian, S.** (1975). An experiment in linguistic synthesis with
  a fuzzy logic controller. *International Journal of Man-Machine Studies*, 7(1).
- **Zadeh, L. A.** (1965). Fuzzy sets. *Information and Control*, 8(3).
- **Billings, D.** (2006). *Algorithms and Assessment in Computer Poker*. Tese de
  doutorado, University of Alberta — Hand Strength / PPot / NPot.
- **Ekmekci, Ö.; Şirin, V.** (2013). Learning Strategies for Opponent Modeling in
  Poker. *AAAI Workshop on Computer Poker and Imperfect Information* — fonte das
  features novas (lido integralmente).
- **Felix, D.; Reis, L. P.** (2008). An Experimental Approach to Online Opponent
  Modeling in Texas Hold'em Poker. *SBIA 2008* — fórmula combinada HS/PPot/NPot
  (citada, não usada).
- **scikit-fuzzy** — https://scikit-fuzzy.github.io/scikit-fuzzy/

> **Sinalização:** Zadeh, Mamdani & Assilian e os dados bibliográficos de Billings
> (2006) e Felix & Reis (2008) vêm de conhecimento geral (Billings e Felix & Reis
> foram lidos apenas via citação em Ekmekci & Şirin). Confirmar título, veículo e ano
> antes de citar no texto do TCC. O conceito de *pot commitment*/SPR também é de
> conhecimento geral da literatura de estratégia de poker, sem fonte formal lida.
