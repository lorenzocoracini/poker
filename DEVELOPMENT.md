# Guia de Desenvolvimento — Poker Heads-Up

Documento de referência para desenvolvimento do projeto (Fase 1 do TCC: sistema
especialista fuzzy). Complementa o [README.md](README.md) e o
[FUZZY_LOGIC.md](backend/engine/fuzzy/FUZZY_LOGIC.md).

---

## 1. Como rodar o projeto

### Requisitos

- Python 3.12 (testado com 3.12.3)
- Não há ambiente virtual versionado no repositório (`venv/` está no `.gitignore`)

### Setup inicial

```bash
cd /home/lorenzocoracini/Documents/tcc/code/poker
python3 -m venv venv
source venv/bin/activate
pip install -r backend/requirements.txt
```

Dependências principais (`backend/requirements.txt`): `treys` (avaliação de mãos),
`scikit-fuzzy` + `numpy` + `scipy` + `networkx` (motor fuzzy), `streamlit`
(interface), `pytest` + `pytest-asyncio` (testes), `anthropic` + `python-dotenv`
(feedback pós-jogo — ver seção 6).

### Rodar a aplicação (frontend Streamlit)

```bash
./run.sh
```

Isso equivale a `cd frontend && python3 -m streamlit run app.py`. A interface abre
no navegador (por padrão `http://localhost:8501`).

O `frontend/app.py` insere `backend/` no `sys.path` manualmente (não há
instalação como pacote), por isso os imports internos são feitos como
`engine.game.controller`, `db.database`, etc. — sempre relativos à raiz `backend/`.

### Rodar os testes

```bash
cd backend
pytest
```

(`conftest.py` vazio em `backend/` — o pytest usa `backend/` como rootdir, o que
garante que `engine.*` e `db.*` sejam importáveis sem instalação do pacote.)

### Banco de dados

SQLite em `poker.db` (raiz do projeto, ignorado pelo git). Criado/atualizado
automaticamente por `db/database.py:init_db()` a cada início de partida
(`GameController.__init__`). Para resetar o histórico, basta apagar o arquivo:

```bash
rm poker.db
```

Tabelas: `games`, `rounds`, `actions` (esta última guarda `win_prob`, `pot_odds`,
`position` e `fuzzy_recommendation` — dataset já preparado para a Fase 2 de ML).

---

## 2. Estrutura real do código

> Nota: esta estrutura reflete o estado atual do código-fonte após o refactor em
> `backend/`. Difere do layout descrito no `CLAUDE.md` da raiz do TCC
> (`agente/`, `poker_engine/`, `fuzzy/`, `ml/`), que descreve a organização
> pretendida em nível de repositório, não a estrutura interna do app.

```
code/poker/
├── README.md
├── run.sh                          ← atalho para o Streamlit
├── poker.db                        ← SQLite (gerado em runtime, gitignored)
├── backend/
│   ├── requirements.txt
│   ├── conftest.py                 ← vazio, define rootdir do pytest
│   ├── db/
│   │   ├── database.py             ← conexão + schema SQLite
│   │   └── recorder.py             ← GameRecorder: grava games/rounds/actions
│   ├── engine/
│   │   ├── config/
│   │   │   └── game_parameters.py  ← constantes do jogo (stacks, blinds)
│   │   ├── game/
│   │   │   ├── controller.py       ← GameController: máquina de estados pura
│   │   │   ├── cards_distribution.py
│   │   │   └── hands_evaluation.py
│   │   ├── players/
│   │   │   ├── base_player.py
│   │   │   ├── user_player.py      ← jogador humano
│   │   │   └── system_player.py    ← agente: orquestra fuzzy → ação de jogo
│   │   └── fuzzy/
│   │       ├── fuzzy_agent.py      ← FuzzyPokerAgent (sistema Mamdani, 7 entradas)
│   │       ├── hand_strength.py    ← win_prob, ppot/npot via Monte Carlo (treys)
│   │       └── FUZZY_LOGIC.md      ← documentação detalhada do sistema fuzzy
│   └── tests/
│       ├── test_cards_distribution.py
│       ├── test_players.py
│       └── test_fuzzy.py
└── frontend/
    └── app.py                      ← UI Streamlit, consome GameController
```

**Fluxo de uma rodada:** `GameController.start_new_round()` distribui cartas,
posta blinds e avança a ação (`_advance_until_player`) chamando
`SystemPlayer.decide_action()` sempre que for a vez do agente, até a vez do
jogador humano ou fim da rodada (`_go_to_showdown` / `_end_round`).

`GameController` é **stateless em relação a I/O** (comentário no próprio código:
"Pure state-machine controller — no I/O") — só manipula estado e retorna dicts
via `get_state()`; toda renderização é responsabilidade do `frontend/app.py`.

---

## 3. Como funciona o agente fuzzy

Resumo prático — para o detalhamento completo (funções de pertinência, tabelas
de regras, defuzzificação passo a passo) ver
[`backend/engine/fuzzy/FUZZY_LOGIC.md`](backend/engine/fuzzy/FUZZY_LOGIC.md),
que é a fonte de verdade e deve ser mantido em sincronia com `fuzzy_agent.py`.

### Arquitetura

- **Tipo de sistema:** inferência fuzzy Mamdani, implementado com `scikit-fuzzy`
  (`skfuzzy.control`).
- **Onde vive:** `backend/engine/fuzzy/fuzzy_agent.py` (`FuzzyPokerAgent`).
- **Quem chama:** `SystemPlayer.decide_action()` (`backend/engine/players/system_player.py`)
  calcula as 7 entradas, chama `fuzzy_agent.decide(...)` e traduz a
  recomendação (`fold`/`call`/`raise`) para uma ação válida do motor de jogo
  (`check`, `bet`, `call`, `raise`, `fold`, `allin`), respeitando stack e
  estado da rodada.
- O sistema fuzzy é reconstruído (`_build_system()`) uma única vez, no
  `__init__` do `FuzzyPokerAgent` — não é recriado a cada decisão.
- As 4 últimas entradas (`ppot`, `npot`, `opponent_aggression`, `stack_commitment`)
  foram adicionadas a partir de um levantamento de trabalhos correlatos
  (Ekmekci & Şirin, 2013) — ver `PLANO_EXPANSAO_FUZZY.md` e a seção "Origem das
  novas variáveis" em `FUZZY_LOGIC.md` para o racional completo.

### Entradas (antecedentes) — universo [0, 1]

| Variável | Como é calculada | Termos linguísticos |
|---|---|---|
| `hand_strength` | `calculate_win_probability()` em `hand_strength.py`: simulação Monte Carlo (500 iterações padrão) com `treys.Evaluator`, amostrando cartas do oponente e board restante do deck | `fraca`, `media`, `forte`, `muito_forte` |
| `pot_odds` | `to_call / (pot + to_call)`, ou `0.0` se não há nada a pagar | `baixo`, `medio`, `alto` |
| `position` | binária: `1.0` se o agente é o button (in position), `0.0` se é big blind (out of position) | `fora`, `dentro` |
| `ppot` | `calculate_hand_potential()`: Monte Carlo classificando ahead/behind/tied antes e depois do board completar (Billings 2006). Só calculada no flop/turn; `0.0` no pré-flop/river | `baixo`, `medio`, `alto` |
| `npot` | Idem `ppot` (mesma função, retorna a tupla), mas medindo o risco de uma mão à frente terminar atrás | `baixo`, `medio`, `alto` |
| `opponent_aggression` | `_opponent_aggression()` (função module-level em `system_player.py`): combinação ponderada de última ação do humano + nº de raises nesta street + nº de raises em streets anteriores (rastreados no `GameController`) | `passivo`, `moderado`, `agressivo` |
| `stack_commitment` | `pot / (pot + stack_do_agente)` — proxy de SPR (stack-to-pot ratio) | `baixo`, `medio`, `alto` |

### Funções de pertinência (parâmetros exatos)

```python
hand_strength['fraca']       = trapmf([0,    0,    0.30, 0.45])
hand_strength['media']       = trimf( [0.35, 0.50, 0.65])
hand_strength['forte']       = trimf( [0.55, 0.70, 0.85])
hand_strength['muito_forte'] = trapmf([0.75, 0.90, 1.00, 1.00])

pot_odds['baixo'] = trapmf([0,    0,    0.20, 0.35])
pot_odds['medio'] = trimf( [0.25, 0.40, 0.55])
pot_odds['alto']  = trapmf([0.45, 0.60, 1.00, 1.00])

position['fora']   = trapmf([0,    0,    0.30, 0.50])
position['dentro'] = trapmf([0.50, 0.70, 1.00, 1.00])

ppot['baixo'] = trapmf([0,    0,    0.15, 0.30]); ppot['medio'] = trimf([0.20, 0.35, 0.50]); ppot['alto'] = trapmf([0.40, 0.55, 1.00, 1.00])
npot['baixo'] = trapmf([0,    0,    0.15, 0.30]); npot['medio'] = trimf([0.20, 0.35, 0.50]); npot['alto'] = trapmf([0.40, 0.55, 1.00, 1.00])

opponent_aggression['passivo']   = trapmf([0,    0,    0.25, 0.40])
opponent_aggression['moderado']  = trimf( [0.30, 0.50, 0.70])
opponent_aggression['agressivo'] = trapmf([0.60, 0.75, 1.00, 1.00])

stack_commitment['baixo'] = trapmf([0,    0,    0.20, 0.35])
stack_commitment['medio'] = trimf( [0.25, 0.45, 0.65])
stack_commitment['alto']  = trapmf([0.55, 0.70, 1.00, 1.00])
```

> Sinalização: os breakpoints das 4 novas variáveis são estimativas de engenharia, não
> derivadas de literatura — ponto de partida para a etapa de calibração por ML.

### Saída (consequente) — `action_score`, universo [0, 1]

```python
action_score['fold']  = trapmf([0,    0,    0.20, 0.35])
action_score['call']  = trimf( [0.25, 0.50, 0.75])
action_score['raise'] = trapmf([0.65, 0.80, 1.00, 1.00])
```

Defuzzificação por **centroide** (padrão do `scikit-fuzzy`), seguida de limiar
fixo em `decide()`:

```python
if   score < 0.35: return 'fold'
elif score < 0.65: return 'call'
else:              return 'raise'
```

### Regras (visão geral — 28 regras)

As 14 regras originais (R1-R14) não foram alteradas:

- Mão `muito_forte` → sempre `raise`.
- Mão `forte`: `raise` se `dentro` (in position), `call` se `fora`; também
  `call` se `pot_odds` alto (protege o pot mesmo sem posição).
- Mão `media`: `call` com `pot_odds` baixo/médio ou `dentro`; `fold` com
  `pot_odds` alto ou `fora`.
- Mão `fraca`: `fold` em quase todos os casos; `call` especulativo (tentativa
  de roubo) se estiver `dentro`.

14 regras novas (R15-R28) combinam `hand_strength` com uma das 4 novas variáveis
(evitando o produto cartesiano completo das 7 entradas):

- `ppot`/`npot`: draws com potencial alto sobem de `fold`/`call` para `call`; mãos
  vulneráveis (`npot` alto) recuam de `raise` para `call` ou de `call` para `fold`.
- `opponent_aggression`: contra oponente `agressivo`, mãos fracas/médias tendem a
  `fold`; contra `passivo`, joga-se mais solto (`call`/`raise`, inclusive tentativas de
  roubo com mão fraca em posição).
- `stack_commitment`: com `stack_commitment` alto (pot committed), mãos médias que
  fossem `fold` passam a `call`, e mãos fortes reforçam `raise`.

Tabela completa das 28 regras: ver `FUZZY_LOGIC.md`.

### Pontos de extensão para a Fase 2 (ML)

- Toda decisão do agente fica registrada em `SystemPlayer.last_fuzzy_data` e
  persistida via `GameRecorder.record_action()` na tabela `actions`
  (colunas `win_prob`, `pot_odds`, `position`, `ppot`, `npot`,
  `opponent_aggression`, `stack_commitment`, `fuzzy_recommendation`). Desde a
  seção 6, essas mesmas colunas também são preenchidas para `actor='player'`,
  usando a avaliação de referência do próprio agente fuzzy do sistema
  (`GameController._evaluate_player_action()`).
- Esse dataset é o ponto de partida natural para treinar/ajustar o componente
  de aprendizado de máquina mencionado no `CLAUDE.md` da raiz (Fase 2).
- Alterações nas funções de pertinência ou nas regras devem ser feitas em
  `fuzzy_agent.py` **e** refletidas em `FUZZY_LOGIC.md` — evitar duplicar essa
  documentação neste arquivo.

---

## 4. Parâmetros de jogo (não-fuzzy)

Definidos em `backend/engine/config/game_parameters.py`:

| Constante | Valor | Significado |
|---|---|---|
| `STACK_INICIAL` | 600 | Fichas iniciais de cada jogador |
| `INICIAL_BLIND` | 10 | Small blind inicial |
| `INICIAL_BIG_BLIND` | 20 | Big blind inicial |
| `NUMBER_OF_ROUNDS_TO_RAISE_BLIND` | 10 | A cada N rodadas, o blind dobra (`GameController.start_new_round`) |

O tamanho de bet/raise do agente é fixo em `big_blind × 3`, limitado à stack
disponível (`SystemPlayer.decide_action`, `raise_amount = min(big_blind * 3, self.stack)`).

---

## 5. Referências bibliográficas (a confirmar/expandir na escrita)

- **Lógica fuzzy / Mamdani:** Zadeh, L. A. (1965). *Fuzzy sets*. Information and
  Control. / Mamdani, E. H.; Assilian, S. (1975). *An experiment in linguistic
  synthesis with a fuzzy logic controller*.
- **scikit-fuzzy:** biblioteca open-source usada na implementação
  (`https://scikit-fuzzy.github.io/scikit-fuzzy/`).
- **Avaliação de mãos (treys) e simulação Monte Carlo para poker:** justificar
  na escrita com literatura de estimação de equity em Texas Hold'em
  (ex.: Billings et al., pesquisas do grupo de poker da University of Alberta).
- **Hand Strength / PPot / NPot:** Billings, D. (2006). *Algorithms and Assessment in
  Computer Poker*. PhD Dissertation, University of Alberta — algoritmo implementado em
  `calculate_hand_potential()` (lido via citação dentro do paper abaixo).
- **Features de opponent modeling (`opponent_aggression`, `stack_commitment`,
  PPot/NPot):** Ekmekci, Ö.; Şirin, V. (2013). *Learning Strategies for Opponent
  Modeling in Poker*. AAAI Workshop on Computer Poker and Imperfect Information — paper
  trazido e lido integralmente pelo usuário durante o desenvolvimento; fonte das 19
  features candidatas e do racional de priorização em `PLANO_EXPANSAO_FUZZY.md`.

> Sinalização: as sugestões de Zadeh/Mamdani/scikit-fuzzy/Billings-geral acima vêm do
> conhecimento geral de treinamento do Claude, não de leitura direta desses textos —
> confirmar título/ano exatos e adequação ao referencial teórico do TCC antes de citar
> na escrita. O paper Ekmekci & Şirin (2013) e a citação de Billings 2006 dentro dele
> **foram lidos integralmente** nesta sessão (ver `PLANO_EXPANSAO_FUZZY.md`).

---

## 6. Feedback pós-jogo (API do Claude)

Ao final de uma partida (`status == 'GAME_OVER'`), a interface oferece o botão
"📝 Gerar feedback da partida", que compara as decisões do jogador humano com o
que o próprio agente fuzzy do sistema teria recomendado, e usa a API do Claude
para transformar essa comparação num texto de feedback em português.

### Como funciona

A cada ação do jogador humano, `GameController._evaluate_player_action()`
monta o `game_state` da perspectiva do jogador (espelhando o que já é feito
para o sistema em `_apply_system_action`) e chama
`compute_decision_features()` + `self.system.fuzzy_agent.decide(...)` — a
mesma infraestrutura usada para decidir a jogada do próprio sistema, só que em
modo somente leitura: o resultado é gravado na tabela `actions` (colunas
`win_prob`, `ppot`, `npot`, `opponent_aggression`, `stack_commitment`,
`fuzzy_recommendation`), mas não influencia a jogada de ninguém.

Ao clicar no botão de feedback (`backend/feedback/`):

1. `session_report.summarize_session(game_id)` busca todas as linhas
   `actor='player'` da partida e calcula, pra cada uma,
   `score_decision(recomendado, real)` — escala ordinal `fold < call/check <
   bet/raise/allin`, onde acerto exato = 1.0, ação adjacente = 0.5, oposta =
   0.0. Agrega numa nota média (0-100%), um breakdown por street e alguns
   padrões objetivos (ex.: quantas vezes foldou quando a recomendação era
   raise).
2. `llm_client.generate_feedback(summary)` manda essas estatísticas (só os
   números, sem inventar detalhes de mãos) pro modelo `claude-haiku-4-5-20251001`
   via `anthropic.Anthropic()`, pedindo um texto curto em português.

### Configuração

```bash
cp .env.example .env
```

Preencher `ANTHROPIC_API_KEY` no `.env` (não versionado — já no `.gitignore`).
Sem a chave, ou em caso de falha de rede, o botão mostra um aviso (`st.warning`)
em vez de quebrar a interface.

### Limitação importante

A nota de alinhamento mede o quanto o jogador jogou de acordo com a **política
do próprio agente fuzzy implementado neste projeto** — não é uma medida de
jogo "ótimo" externo (GTO) nem vem de uma fonte validada fora do TCC. As
funções de pertinência e regras do `FuzzyPokerAgent` têm breakpoints de
engenharia própria (ver seção 3) ainda não calibrados por ML — a nota reflete
esse estágio do agente, não uma referência absoluta de habilidade em poker.
