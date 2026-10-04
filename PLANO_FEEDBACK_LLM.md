# Plano: Avaliação da jogada do humano + feedback via API do Claude

> Status: **proposta em revisão** — nada foi implementado ainda. Este documento existe
> para leitura/aprovação com calma; a implementação só começa quando for pedida
> explicitamente.

## Contexto

Depois de discutir alternativas mais leves que o self-play/otimização de parâmetros
fuzzy (ficou descartado por enquanto — ver histórico da conversa), a ideia escolhida é:
a cada decisão do **jogador humano**, comparar a ação real tomada com o que o próprio
agente fuzzy do sistema (o oponente que ele está enfrentando) teria recomendado naquela
mesma situação, registrar isso, e ao final da partida gerar (a) uma nota objetiva de
alinhamento e (b) um texto de feedback em português escrito pela API do Claude a partir
dessas estatísticas.

Achado importante: a tabela `actions` do SQLite **já tem** todas as colunas necessárias
(`win_prob`, `pot_odds`, `position`, `ppot`, `npot`, `opponent_aggression`,
`stack_commitment`, `fuzzy_recommendation`) — hoje só ficam preenchidas pras ações do
`system`. Não é preciso nenhuma migração de schema; só preencher essas colunas também
pras ações do `actor='player'`.

Decisões confirmadas com o usuário:
- API key via `python-dotenv` (dependência nova, pequena) lendo um `.env` na raiz
  (já gitignored).
- Modelo: `claude-haiku-4-5-20251001` (rápido/barato, roda 1x por partida).
- Código novo em `backend/feedback/` (pacote único: query+pontuação e client da LLM).
- UI mostra nota numérica (% de alinhamento) **e** o texto da LLM.

---

## 1. `backend/engine/players/system_player.py` — extrair cálculo de features

Hoje `decide_action()` calcula win_prob/pot_odds/position/ppot/npot/aggression/commitment
inline (linhas 22-58) e já guarda tudo em `self.last_fuzzy_data`. Preciso rodar esse
mesmo cálculo para a mão do **jogador humano**, que não é um `SystemPlayer`.

- Extrair para funções **module-level** (não métodos — não dependem de `self`):
  `compute_decision_features(hand, stack, game_state) -> dict` (retorna win_prob,
  pot_odds, position, ppot, npot, opponent_aggression, stack_commitment) e
  `_opponent_aggression(game_state) -> float` (já existe como método; vira função).
- `SystemPlayer.decide_action()` passa a chamar `compute_decision_features(self.hand,
  self.stack, game_state)` e montar `self.last_fuzzy_data` a partir do resultado — mesmo
  comportamento de hoje, só reorganizado. Testado pelos testes já existentes
  (`test_fuzzy.py`), que não devem mudar de resultado.

## 2. `backend/engine/game/controller.py` — avaliar a ação do humano

- Nova função privada `_evaluate_player_action(self) -> dict`: monta o mesmo tipo de
  `game_state` que `_apply_system_action` já monta hoje (linhas 161-178), mas da
  perspectiva do `'player'` (oponente = `'system'`): `is_button = self.button ==
  'player'`, `last_player_action` = última ação do **sistema**
  (`self._last_system_action`), `player_raises_this_street`/`player_raises_prev_streets`
  contados sobre o ator `'system'` em vez de `'player'`. Chama
  `compute_decision_features(self.player.hand, self.player.stack, gs)` e pede a
  recomendação de referência ao **próprio fuzzy agent do sistema**:
  `self.system.fuzzy_agent.decide(features['win_prob'], ..., features['stack_commitment'])`.
  Retorna `{**features, 'recommendation': recomendacao}` — mesmo formato de
  `last_fuzzy_data`, então `self.recorder.record_action(...)` grava nas mesmas colunas
  sem mudança nenhuma no `recorder.py`/`database.py`.
- `apply_player_action()` (linha 182) passa a chamar `_evaluate_player_action()` antes
  de `_apply_action`, e repassar o resultado como o parâmetro `fuzzy=`:
  ```python
  def apply_player_action(self, action, amount=0):
      if self.status != 'WAITING_PLAYER':
          return self.get_state()
      evaluation = self._evaluate_player_action()
      self._apply_action('player', action, amount, evaluation)
      return self._advance_until_player()
  ```
- **Importante:** essa avaliação é só leitura/registro — não influencia `_apply_action`
  nem a jogada do sistema. A única mudança observável no jogo é mais uma simulação
  Monte Carlo (~500 iterações) a cada decisão do humano, pelo mesmo motivo que já existe
  pro sistema (custo aceitável, já discutido antes).

## 3. `backend/db/recorder.py` — expor `game_id`

`GameRecorder` já guarda `self._game_id` internamente. Adicionar:
```python
@property
def game_id(self):
    return self._game_id
```
Necessário pro frontend buscar o relatório da partida certa ao final do jogo.

## 4. `backend/feedback/` (novo pacote)

### `session_report.py`

- `ACTION_ORDINAL = {'fold': 0, 'check': 1, 'call': 1, 'bet': 2, 'raise': 2, 'allin': 2}`
  — mapeia as 6 ações do motor pro espaço fold<call<raise usado pelo fuzzy.
- `score_decision(recommended: str, actual: str) -> float`: `1 - abs(ord(rec) -
  ord(actual)) / 2` → match exato = 1.0, adjacente = 0.5, oposto = 0.0.
- `fetch_player_actions(game_id: int) -> list[dict]`: query em
  `backend/db/database.py:get_connection()` — `SELECT a.street, a.action_type, a.amount,
  a.win_prob, a.pot_odds, a.ppot, a.npot, a.opponent_aggression, a.stack_commitment,
  a.fuzzy_recommendation FROM actions a JOIN rounds r ON a.round_id = r.id WHERE
  r.game_id = ? AND a.actor = 'player'`.
- `summarize_session(game_id: int) -> dict`: roda `fetch_player_actions`, calcula pra
  cada linha `score_decision(fuzzy_recommendation, action_type)`, agrega: `total_decisoes`,
  `nota_media` (0-100%), contagem por street, e alguns padrões simples e objetivos
  (ex: quantas vezes foldou quando a recomendação era raise; quantas vezes deu raise
  quando a recomendação era fold — "superagressividade"; mão fraca categorizada por
  `win_prob < 0.35` continuando a mão mesmo assim). Mantém a lista de agregações curta e
  literal — nada de inferência extra além de contar o que já está nos dados.

### `llm_client.py`

- `from dotenv import load_dotenv; load_dotenv()` no topo do módulo (carrega `.env` da
  raiz do projeto se existir; não falha se não existir).
- `build_prompt(summary: dict) -> str`: formata os números de `summarize_session` em um
  prompt curto e literal (lista as estatísticas, não floreia), pedindo à LLM um texto em
  português, 3-5 parágrafos curtos, tom construtivo, citando 1-2 pontos fortes e 1-2
  pontos de melhoria **baseados só nos números fornecidos** — instrução explícita no
  prompt pra não inventar detalhes de mãos específicas que não estão nos dados.
- `generate_feedback(summary: dict) -> str`: `anthropic.Anthropic()` (lê
  `ANTHROPIC_API_KEY` do ambiente/`.env` automaticamente) →
  `client.messages.create(model='claude-haiku-4-5-20251001', max_tokens=600,
  system=<instrução de tom/formato>, messages=[{'role': 'user', 'content':
  build_prompt(summary)}])` → retorna `message.content[0].text`. Erros (key ausente,
  falha de rede) propagam como exceção clara — tratados na UI, não aqui.

## 5. Dependências — `backend/requirements.txt`

Adicionar `anthropic` e `python-dotenv` (ambas confirmadas com o usuário).

## 6. `.env.example` (novo, raiz do projeto)

```
ANTHROPIC_API_KEY=
```
Só o template — sem chave real. `.env` real continua fora do git (já no `.gitignore`).

## 7. `frontend/app.py` — UI no `GAME_OVER`

No bloco `elif status == 'GAME_OVER':` (linha 229-244), depois da mensagem de
vitória/derrota: botão **"📝 Gerar feedback da partida"**. Ao clicar: pega
`ctrl.recorder.game_id`, chama `session_report.summarize_session(game_id)`, mostra a
nota (`st.metric` ou similar) e, com um spinner, chama `llm_client.generate_feedback(...)`
e exibe o texto via `st.markdown`. Resultado guardado em `st.session_state` pra não
regerar a cada rerun da página. `try/except` ao redor da chamada à API — se faltar
`ANTHROPIC_API_KEY` ou a chamada falhar, mostra `st.warning` com mensagem amigável em vez
de quebrar a tela.

## 8. Testes (`backend/tests/`)

- `test_system_player.py` (ou ampliar `test_fuzzy.py`): `compute_decision_features`
  isolada retorna as 7 chaves esperadas; `SystemPlayer.decide_action` continua
  funcionando (regressão, reusa os testes já existentes).
- Novo `test_session_report.py`: `score_decision` com casos conhecidos (match exato,
  adjacente, oposto); `summarize_session` contra um banco SQLite temporário (criado via
  `db.database.init_db()` apontando pra um arquivo `.db` em `tmp_path` do pytest, ou
  inserindo linhas diretamente) com 2-3 ações fake, conferindo a nota agregada.
- `llm_client.generate_feedback` **não** é testado contra a API real (custo/rede) — só
  `build_prompt()` é testado (contém as estatísticas certas na string). Documentar isso
  explicitamente no teste.

## 9. Documentação

- `DEVELOPMENT.md`: nova seção curta "Feedback pós-jogo (API do Claude)" — como
  configurar `.env`, o que é a nota de alinhamento, limitação já conhecida (mede
  alinhamento com a política do próprio agente fuzzy, não um "ótimo" externo/GTO).
- `.env.example` já documenta a variável esperada.

---

## Verificação end-to-end

1. `cd backend && pytest` — suíte completa (existente + novos testes) passando.
2. Copiar `.env.example` → `.env`, preencher `ANTHROPIC_API_KEY` real.
3. `./run.sh`, jogar uma partida curta até `GAME_OVER` (ou forçar stacks baixos editando
   `STACK_INICIAL` temporariamente pra não precisar jogar muitas mãos), clicar "Gerar
   feedback da partida" e conferir: nota numérica plausível + texto da LLM em português,
   coerente com as jogadas feitas.
4. Conferir no SQLite (`sqlite3`/script Python) que linhas `actor='player'` da tabela
   `actions` agora têm `win_prob`/`ppot`/`npot`/etc. e `fuzzy_recommendation`
   preenchidos (hoje ficam `NULL`).
5. Testar o caminho de erro: rodar sem `ANTHROPIC_API_KEY` setada e confirmar que a UI
   mostra aviso amigável em vez de stack trace.
