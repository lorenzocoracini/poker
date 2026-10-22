# Poker Heads-Up — Agente Fuzzy com Feedback via LLM

Implementação do TCC *"Um agente inteligente baseado em lógica fuzzy para jogar e
avaliar decisões no poker heads-up"* (Lorenzo Coracini — Sistemas de Informação, UFSC).

Jogo de **Texas Hold'em heads-up** (humano vs. agente) com interface Streamlit. O
agente decide com um **sistema de inferência fuzzy Mamdani** de 7 entradas; cada
decisão — do agente e do humano — é registrada em SQLite. O mesmo sistema fuzzy avalia
as jogadas do humano e, ao fim de cada rodada e da partida, um LLM gera feedback em
linguagem natural comparando essas jogadas com o que o agente recomendaria.

| Documento | Conteúdo |
|---|---|
| `README.md` (este) | Setup, arquitetura, motor de jogo, banco, feedback, testes |
| [`backend/engine/fuzzy/FUZZY_LOGIC.md`](backend/engine/fuzzy/FUZZY_LOGIC.md) | Sistema fuzzy completo: variáveis, funções de pertinência, 27 regras, inferência, exemplo resolvido, referências |

---

## 1. Status do projeto

| Fase | Status |
|---|---|
| Motor de jogo heads-up (blinds, streets, showdown, all-in) | ✅ |
| Agente fuzzy — 3 entradas originais | ✅ |
| Agente fuzzy — expansão para 7 entradas (PPot, NPot, agressividade, comprometimento) | ✅ |
| Persistência de todas as decisões em SQLite | ✅ |
| Avaliação das jogadas do humano pelo agente + feedback por rodada e por partida (API do Claude) | ✅ |

---

## 2. Como rodar

### Requisitos

- Python 3.12 (testado com 3.12.3)
- Chave da API da Anthropic (opcional — só para o texto de feedback)

### Setup

```bash
cd code/poker
python3 -m venv venv
source venv/bin/activate
pip install -r backend/requirements.txt
cp .env.example .env        # e preencher ANTHROPIC_API_KEY
```

Dependências (`backend/requirements.txt`):

| Pacote | Uso |
|---|---|
| `treys` | Avaliação de mãos (showdown e Monte Carlo) |
| `scikit-fuzzy`, `numpy`, `scipy`, `networkx` | Motor de inferência fuzzy |
| `streamlit` | Interface |
| `anthropic`, `python-dotenv` | Geração do texto de feedback |
| `pytest`, `pytest-asyncio` | Testes |

### Aplicação

```bash
./run.sh            # = cd frontend && python3 -m streamlit run app.py
```

Abre em `http://localhost:8501`. O terminal mostra uma linha `[FUZZY] ...` por decisão
do agente, com as 7 entradas e a recomendação.

### Testes

```bash
cd backend
pytest
```

### Banco de dados

`poker.db` na raiz do projeto (gitignored), criado/atualizado por
`db/database.py:init_db()` a cada `GameController()`. Para zerar o histórico:
`rm poker.db`.

---

## 3. Estrutura do código

```
code/poker/
├── README.md                       ← este arquivo
├── run.sh                          ← sobe o Streamlit
├── .env.example                    ← template de ANTHROPIC_API_KEY
├── poker.db                        ← SQLite (gerado em runtime, gitignored)
├── frontend/
│   ├── app.py                      ← UI Streamlit; só consome GameController
│   └── .streamlit/config.toml      ← file watcher em modo poll (WSL)
└── backend/
    ├── requirements.txt
    ├── conftest.py                 ← vazio; fixa backend/ como rootdir do pytest
    ├── engine/
    │   ├── config/game_parameters.py   ← stacks e blinds
    │   ├── game/
    │   │   ├── controller.py           ← GameController: máquina de estados do jogo
    │   │   ├── cards_distribution.py   ← baralho e distribuição
    │   │   └── hands_evaluation.py     ← showdown e descrição da mão (treys)
    │   ├── players/
    │   │   ├── base_player.py          ← Player (nome, stack, mão)
    │   │   ├── user_player.py          ← humano
    │   │   └── system_player.py        ← agente + cálculo das features fuzzy
    │   └── fuzzy/
    │       ├── fuzzy_agent.py          ← FuzzyPokerAgent (Mamdani, 7 entradas, 27 regras)
    │       ├── hand_strength.py        ← win prob e PPot/NPot por Monte Carlo
    │       └── FUZZY_LOGIC.md          ← documentação do sistema fuzzy
    ├── db/
    │   ├── database.py                 ← conexão e schema
    │   └── recorder.py                 ← GameRecorder: grava games/rounds/actions
    ├── feedback/
    │   ├── session_report.py           ← pontuação e agregação das jogadas do humano
    │   └── llm_client.py               ← prompts e chamada à API do Claude
    └── tests/
```

Não há instalação como pacote: `frontend/app.py` insere `backend/` no `sys.path`, e
todos os imports são relativos a `backend/` (`engine.game.controller`,
`db.database`, `feedback.session_report`...).

> A organização interna difere do layout `agente/`, `poker_engine/`, `fuzzy/`, `ml/`
> descrito no `CLAUDE.md` da raiz do TCC, que é a organização pretendida em nível de
> repositório.

---

## 4. Arquitetura

```
┌──────────────────┐   apply_player_action()   ┌──────────────────────────┐
│  frontend/app.py │ ────────────────────────▶ │      GameController      │
│   (Streamlit)    │ ◀──────────────────────── │  máquina de estados pura │
└──────────────────┘        get_state()        └──────────────────────────┘
         │                                       │          │          │
         │ feedback                 decide_action │  avalia  │          │ record_action
         ▼                                       ▼  humano  ▼          ▼
┌──────────────────┐                  ┌──────────────────────────┐  ┌──────────────┐
│    feedback/     │ ◀── SELECT ───── │  SystemPlayer            │  │ GameRecorder │
│ session_report   │                  │  compute_decision_       │  │   (SQLite)   │
│ llm_client ──▶ API do Claude        │  features → FuzzyPoker-  │  └──────────────┘
└──────────────────┘                  │  Agent.decide → translate│
                                      └──────────────────────────┘
```

- **`GameController`** não faz I/O de interface: só altera estado e devolve um dict em
  `get_state()`. Toda renderização é do `app.py`.
- **`SystemPlayer`** calcula as 7 features (`compute_decision_features`), consulta o
  `FuzzyPokerAgent` e traduz `fold`/`call`/`raise` em ação legal
  (`translate_recommendation`). Detalhes em `FUZZY_LOGIC.md`.
- **`GameRecorder`** grava cada ação com as features e a recomendação.
- **`feedback/`** lê o banco e produz nota de alinhamento + texto.

---

## 5. Motor de jogo

### Parâmetros (`engine/config/game_parameters.py`)

| Constante | Valor | Significado |
|---|---|---|
| `STACK_INICIAL` | 600 | Fichas iniciais de cada jogador |
| `INICIAL_BLIND` | 10 | Small blind inicial (big blind = 2×) |
| `INICIAL_BIG_BLIND` | 20 | Big blind inicial |
| `NUMBER_OF_ROUNDS_TO_RAISE_BLIND` | 10 | O blind dobra a cada 10 rodadas |

### Fluxo de uma rodada

1. `start_new_round()` — rota o button (a partir da 2ª rodada; o button inicial é
   sorteado), dobra o blind se for o caso, distribui as cartas (board completo já é
   sorteado e revelado aos poucos), posta blinds e zera os contadores de
   agressividade.
2. **Pré-flop**: o button (que é o small blind no heads-up) age primeiro.
   **Flop/turn/river**: o big blind age primeiro.
3. `_advance_until_player()` aplica as ações do sistema em loop até ser a vez do
   humano (`WAITING_PLAYER`) ou a rodada acabar.
4. `apply_player_action(action, amount)` avalia a jogada do humano com o agente
   (`_evaluate_player_action`, só leitura), aplica a ação e volta ao passo 3.
5. A street encerra com `call`, ou com dois `check`s; `_next_street()` revela as
   cartas, consolida os raises da street e reinicia a ordem de ação.
6. A rodada termina por **fold** (`_end_round`) ou **showdown** (`_go_to_showdown`,
   empate divide o pot). Se alguém fica com stack 0, `status = 'GAME_OVER'`; senão
   `ROUND_OVER`.

Estados (`status`): `INIT` → `WAITING_PLAYER` ⇄ (ações do sistema) → `ROUND_OVER` →
… → `GAME_OVER`.

### Regras específicas

- **Limp pré-flop**: se o button apenas paga o big blind, o big blind ainda tem a
  opção de check ou raise.
- **All-in sem side pot**: o excedente que o oponente não consegue cobrir é devolvido
  imediatamente a quem foi all-in. Se alguém está all-in, o board é completado e vai
  direto ao showdown.
- **Ações do humano** (`get_valid_actions`): check/bet/all-in quando ninguém apostou;
  fold/call/raise/all-in quando há aposta; fold/call all-in quando pagar exige o
  stack inteiro. Valor de bet/raise escolhido na UI (mínimo 1 BB, passo 1 BB).
- **Ações do sistema**: bet/raise fixos em `min(3 × BB, stack)`.

---

## 6. Banco de dados

SQLite, schema em `db/database.py`.

```
games   (id, started_at, ended_at, winner, total_rounds)
  └── rounds  (id, game_id, round_number, blind, player_cards, system_cards,
  │            community_cards, winner, pot)                  ← cartas em JSON
  │     └── actions (id, round_id, street, actor, action_type, amount,
  │                  win_prob, pot_odds, position, ppot, npot,
  │                  opponent_aggression, stack_commitment,
  │                  fuzzy_recommendation, recommended_action)
```

- `actor` ∈ {`player`, `system`}; `action_type` ∈ {`fold`, `check`, `call`, `bet`,
  `raise`, `allin`}.
- As colunas de features e recomendação são preenchidas **para os dois atores**: para
  o sistema é a decisão que ele tomou; para o humano é a recomendação que o agente
  teria dado na mesma situação.
- `fuzzy_recommendation` é a saída abstrata (`fold`/`call`/`raise`);
  `recommended_action` é a ação concreta traduzida (ex.: `raise` → `bet`).
- `init_db()` faz uma migração leve (`ALTER TABLE ... ADD COLUMN recommended_action`)
  para bancos antigos. Para mudanças de schema maiores, apagar `poker.db`.

Consulta útil:

```bash
sqlite3 poker.db "SELECT street, actor, action_type, win_prob, fuzzy_recommendation FROM actions ORDER BY id DESC LIMIT 10;"
```

---

## 7. Feedback ao jogador

Compara cada decisão do humano com a recomendação do agente fuzzy do sistema na
mesma situação.

### Pontuação (`feedback/session_report.py`)

`score_decision(recomendado, real)` projeta as ações numa escala ordinal
`fold (0) < check/call (1) < bet/raise/allin (2)`. O `recomendado` é a recomendação
já traduzida para o spot (`recommended_action`; ex.: `fold` vira `check` quando não há
aposta a pagar), com fallback para `fuzzy_recommendation` em registros antigos:

| Diferença | Score | Exemplo |
|---|---|---|
| igual | 1.0 | recomendação `call`, jogou `check` |
| adjacente | 0.5 | recomendação `fold`, jogou `call` |
| oposta | 0.0 | recomendação `fold`, jogou `raise` |

A **nota de alinhamento** é a média dos scores × 100%.

### Feedback por rodada (tela `ROUND_OVER`)

Botão **"📊 Ver feedback da rodada"** → `summarize_round(round_id)`:

- Nota de alinhamento da rodada.
- Tabela com cada decisão: street, nº da decisão na street, `win_prob`, `pot_odds`,
  `ppot`, `npot`, agressividade do oponente, `stack_commitment`, ação recomendada
  (`recommended_action`), ação real e alinhamento.
- Comentário curto (1–3 frases) do Claude sobre a decisão mais relevante
  (`generate_round_feedback`, `max_tokens=250`). Só chama a API se houver decisões.

### Feedback da partida (tela `GAME_OVER`)

Botão **"📝 Gerar feedback da partida"** → `summarize_session(game_id)`:

- Nota média geral e por street.
- Padrões objetivos: vezes que foldou quando a recomendação era raise; vezes que deu
  bet/raise/all-in quando era fold; vezes que continuou na mão com `win_prob < 0.35`.
- Texto de 3–5 parágrafos do Claude com pontos fortes e de melhoria
  (`generate_feedback`, `max_tokens=600`).

### LLM (`feedback/llm_client.py`)

- Modelo: `claude-haiku-4-5-20251001`, chamado em um único ponto (`_call_claude`),
  o que facilita trocar de provider.
- Os prompts enviam **apenas as estatísticas** e instruem explicitamente a não
  inventar cartas ou situações ausentes dos dados. Resposta em português.
- A chave vem de `ANTHROPIC_API_KEY` (`.env` carregado por `python-dotenv`). Sem
  chave ou sem rede, a UI mostra um `st.warning` em vez de quebrar.
- Resultados guardados em `st.session_state` para não regerar a cada rerun.

> **Limitação:** a nota mede aderência à política do próprio agente fuzzy, cujos
> parâmetros ainda são estimativas de engenharia — não é uma medida de jogo ótimo
> (GTO) nem uma referência externa de habilidade.

---

## 8. Interface (`frontend/app.py`)

- **Sidebar**: rodada, pot, blinds, street, button e stacks com barra de progresso.
  Não mostra dados da decisão fuzzy do agente, para não revelar a força da mão dele.
- **Área principal**: board, mão do jogador, mão do sistema (oculta até o fim da
  rodada), última ação do sistema e botões de ação válidos.
- **Fim de rodada / partida**: resultado, descrição das mãos no showdown, botões de
  feedback e de próxima rodada / novo jogo.

---

## 9. Testes (`backend/tests/`)

| Arquivo | Cobre |
|---|---|
| `test_cards_distribution.py` | `Card`, baralho de 52 cartas e distribuição sem repetição |
| `test_players.py` | `Player`, `UserPlayer` e `SystemPlayer` (stack, mão, fold) |
| `test_fuzzy.py` | PPot/NPot em [0, 1] e flush draw > mão sem draw; `decide()` em toda a faixa de entradas; mão muito forte → raise; mão fraca vs. agressivo → fold |
| `test_system_player.py` | `compute_decision_features` (chaves, pot odds zero) e `SystemPlayer.decide_action` |
| `test_session_report.py` | `score_decision` e `summarize_session` contra SQLite temporário |
| `test_llm_client.py` | Montagem dos prompts (a API real **não** é chamada nos testes) |

---

## 10. Trabalhos futuros

A fase de aprendizado de máquina prevista originalmente saiu do escopo do TCC. O
registro na tabela `actions` (7 features + recomendação + ação real, para os dois
jogadores, ligado ao resultado em `rounds`) fica como base para trabalhos futuros:

- Calibrar automaticamente os breakpoints das funções de pertinência, limiares de
  defuzzificação e pesos de `opponent_aggression` (lista completa na seção 10 do
  `FUZZY_LOGIC.md`).
- Modelar o oponente humano a partir do histórico de ações.

---

## Referências

Ver a seção de referências do [`FUZZY_LOGIC.md`](backend/engine/fuzzy/FUZZY_LOGIC.md)
(Mamdani & Assilian 1975; Zadeh 1965; Billings 2006; Ekmekci & Şirin 2013;
Felix & Reis 2008; scikit-fuzzy).
