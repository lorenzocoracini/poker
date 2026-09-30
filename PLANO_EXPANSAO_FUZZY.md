# Plano: Expansão do agente fuzzy — 3 → 7 variáveis de entrada

> Status: **implementado.** Todos os itens abaixo (1-9) foram aplicados no código —
> `hand_strength.py`, `controller.py`, `system_player.py`, `fuzzy_agent.py`, schema do
> SQLite, `FUZZY_LOGIC.md`, `DEVELOPMENT.md` e `backend/tests/test_fuzzy.py`. Suíte de
> testes (27 testes) e uma simulação headless de partidas completas foram usadas para
> validar o fluxo ponta a ponta antes de considerar a tarefa concluída. Este documento
> permanece como registro do racional de design (por que essas 4 variáveis, por que essa
> arquitetura de regras) — consulte `FUZZY_LOGIC.md` para a documentação viva/atualizada
> do sistema fuzzy.

## Contexto

Hoje o `FuzzyPokerAgent` (`backend/engine/fuzzy/fuzzy_agent.py`) decide com apenas 3
entradas: `hand_strength`, `pot_odds`, `position`. Antes da etapa final do TCC — treinar
um modelo/otimizador para encontrar os melhores parâmetros das funções de pertinência —
o usuário quer ampliar o espaço de entrada do sistema fuzzy, para que a etapa de ML tenha
mais variáveis relevantes para calibrar.

Como base, o usuário trouxe o paper **Ekmekci, Ö.; Şirin, V. (2013). "Learning Strategies
for Opponent Modeling in Poker". AAAI Workshop on Computer Poker and Imperfect
Information.** (lido integralmente nesta sessão). Esse paper é um ótimo fit de escopo:
também trata **heads-up limit Texas Hold'em** (dois jogadores, exatamente nosso caso) e
lista 19 features candidatas (Table 1) usadas para prever a ação do oponente via ML
(NN/SVM/KNN), com um estudo de seleção de features (backward elimination) por oponente
(Table 5).

Ressalva importante: o paper resolve um problema diferente do nosso (eles fazem
*classificação da próxima ação do oponente*; nós fazemos um *sistema especialista fuzzy*
que decide a própria ação). Por isso não copiamos a metodologia de ML deles — só
aproveitamos a **definição das features** e o dado empírico de quais foram mais
relevantes (Table 5) para priorizar o que vale a pena adicionar ao nosso sistema fuzzy.

## Features escolhidas (confirmadas com o usuário)

| # no paper | Feature do paper | Frequência em Table 5 (de 8 oponentes) | Nossa variável fuzzy |
|---|---|---|---|
| 2 | PPot | 6/8 | `ppot` |
| 3 | NPot | 6/8 | `npot` |
| 6, 9, 10, 14, 15 | última ação + nº de raises (street atual e anteriores) | #14 aparece em **8/8** | `opponent_aggression` (composta) |
| 7, 8 | stack comprometido no round | 5/8 | `stack_commitment` (adaptado para SPR, ver nota abaixo) |

Descartado: **hand rank** (feature #11) — redundante com `hand_strength`, que já é uma
estimativa de win probability mais informativa via Monte Carlo. **Textura do board**
(features #16-19) — foi a feature menos selecionada no estudo (1-3/8) e menos alinhada
com heads-up (mais relevante em jogos multiplayer onde ler o board para "quem pode ter
isso" importa mais).

> Sinalização: os valores numéricos das funções de pertinência (breakpoints
> trapmf/trimf) para as 4 novas variáveis, propostos abaixo, **não vêm do paper** (que
> não usa lógica fuzzy) — são estimativas de engenharia baseadas em heurísticas de poker
> conhecidas, a serem refinadas na etapa de tuning por ML que o usuário já planeja fazer
> em seguida. Isso deve ficar explícito no código/documentação quando implementado.

## Arquitetura: rule base única expandida (decisão do usuário)

Descartada a opção hierárquica (dois estágios). Mantemos um único `ControlSystem` com um
único consequente `action_score`, como hoje — só que com 7 antecedentes e a base de
regras ampliada de 14 para ~27-29 regras. As **14 regras atuais permanecem intactas**
(não removemos nem reescrevemos nenhuma); adicionamos regras novas que combinam
`hand_strength` (tier) com **uma** das 4 novas variáveis (ocasionalmente duas), evitando
o produto cartesiano completo (que seria inviável a mão: 4×3×2×3×3×3×3 combinações).

---

## 1. `backend/engine/fuzzy/hand_strength.py` — PPot / NPot

Nova função `calculate_hand_potential(hole_cards, community_cards, n_simulations=500)`,
implementando o algoritmo clássico de Billings (Billings, D. 2006. *Algorithms and
Assessment in Computer Poker*. PhD Dissertation, University of Alberta — citado no
próprio paper do usuário) — reaproveita `_build_remaining_deck` e o `Evaluator` do
`treys` já usados por `calculate_win_probability`.

Para cada trial da simulação Monte Carlo já existente:
1. Avalia o estado **atual** (mão + board revelado até agora) contra a mão amostrada do
   oponente → classifica em `ahead` / `behind` / `tied`.
2. Avalia o estado **final** (após completar o board, como já é feito hoje) → classifica
   de novo em `ahead` / `behind` / `tied`.
3. Acumula transições: `ahead→behind`, `behind→ahead`, `tied→ahead`, `tied→behind`, etc.

```python
PPot = (behind_to_ahead + tied_to_ahead + 0.5*behind_to_tied) / (behind_total + tied_total)
NPot = (ahead_to_behind + tied_to_behind + 0.5*ahead_to_tied) / (ahead_total + tied_total)
```

**Só é chamada no flop e no turn** (`3 <= len(community_cards) <= 4`) — no pré-flop o
`treys.Evaluator` exige ≥5 cartas (mão+board), e no river não há mais cartas por vir
(potencial = 0 por definição, o próprio paper nota isso: *"hand potential is not
meaningful for the river phase"*). Em `system_player.py`, fora dessa janela,
`ppot = npot = 0.0` sem chamar a simulação (evita custo e é semanticamente correto: sem
cartas futuras, não há potencial).

`calculate_win_probability` (já existente) **não muda** — continua sendo a fonte de
`hand_strength`. Não usamos a fórmula `P(win) = HS×(1−NPot) + (1−HS)×PPot` do paper
(citando Felix & Reis 2008) porque já temos uma estimativa de win probability mais direta
via rollout completo; PPot/NPot entram como sinais **adicionais e distintos** (potencial
de melhora/piora), não como decomposição da mesma métrica.

## 2. `backend/engine/game/controller.py` — rastreamento de ações/raises

Novo estado, inicializado em `__init__`/`start_new_round` e resetado por street:

- `self._last_player_action` — espelha `self._last_system_action` (já existe), mas para
  o jogador humano. Setado em `_apply_action` quando `actor_name == 'player'`.
- `self._actions_this_street: list[tuple[str, str]]` — `(actor_name, action)` de cada
  ação da street corrente. Resetado em `start_new_round` e em `_next_street`.
- `self._raises_prev_streets: dict[str, int]` — contador acumulado de raises
  (`bet`/`raise`/`allin`) por ator, **por round** (não reseta por street). Em
  `_next_street`, antes de limpar `_actions_this_street`, soma as raises da street que
  está terminando dentro desse dicionário.

Em `_apply_system_action`, o dict `gs` passado para `SystemPlayer.decide_action` ganha:
`street`, `last_player_action` (só o tipo, ex. `'raise'`), `player_raises_this_street`,
`player_raises_prev_streets`. `pot` e `to_call` já existem.

`get_state()` ganha `last_player_action` (paridade com `last_system_action`, útil para
depuração/UI — não obrigatório para a lógica fuzzy).

## 3. `backend/engine/players/system_player.py` — features derivadas

```python
_LAST_ACTION_WEIGHT = {'raise': 1.0, 'bet': 1.0, 'allin': 1.0, 'call': 0.4, 'check': 0.0, 'fold': 0.0, None: 0.0}
```

- `opponent_aggression` = combinação ponderada de `last_player_action` (peso 0.5),
  `player_raises_this_street` normalizado (peso 0.3, capado em 2) e
  `player_raises_prev_streets` normalizado (peso 0.2, capado em 3), resultado clipado em
  `[0, 1]`. Constantes de peso ficam como módulo-level em `system_player.py` (não em
  `game_parameters.py`, que é config do *jogo*, não do agente) — comentário no código
  sinalizando que são heurísticas a recalibrar no tuning por ML.
- `stack_commitment` = `pot / (pot + self.stack)` — proxy padrão de SPR (stack-to-pot
  ratio) sem precisar de novo estado no controller (`pot` e `self.stack` já disponíveis).
  Isso é uma simplificação deliberada da feature #7/#8 do paper (que mede aposta *só
  desta fase*): medimos comprometimento em relação ao round inteiro, que é o conceito
  padrão de "pot committed" usado na literatura de estratégia (ex. Miller/Sklansky/Flynt,
  *Professional No-Limit Hold'em* — sinalizando: referência de conhecimento geral, a
  confirmar antes de citar no texto do TCC).
- `ppot`, `npot` = `calculate_hand_potential(...)` se `street in ('flop', 'turn')`, senão
  `(0.0, 0.0)`.
- `self.last_fuzzy_data` ganha as 4 novas chaves (`ppot`, `npot`, `opponent_aggression`,
  `stack_commitment`) — dataset para a Fase 2 de ML já nasce com as novas colunas.
- Log de debug (`print`) passa a incluir as 7 variáveis, não só 3.

## 4. `backend/engine/fuzzy/fuzzy_agent.py` — antecedentes, MFs e regras novas

4 novos `ctrl.Antecedent`, universo `[0, 1]` como os demais:

```python
ppot['baixo']  = trapmf([0, 0, 0.15, 0.30]);  ppot['medio']  = trimf([0.20, 0.35, 0.50]);  ppot['alto']  = trapmf([0.40, 0.55, 1.00, 1.00])
npot['baixo']  = trapmf([0, 0, 0.15, 0.30]);  npot['medio']  = trimf([0.20, 0.35, 0.50]);  npot['alto']  = trapmf([0.40, 0.55, 1.00, 1.00])
opponent_aggression['passivo']   = trapmf([0, 0, 0.25, 0.40])
opponent_aggression['moderado']  = trimf([0.30, 0.50, 0.70])
opponent_aggression['agressivo'] = trapmf([0.60, 0.75, 1.00, 1.00])
stack_commitment['baixo'] = trapmf([0, 0, 0.20, 0.35]); stack_commitment['medio'] = trimf([0.25, 0.45, 0.65]); stack_commitment['alto'] = trapmf([0.55, 0.70, 1.00, 1.00])
```

Regras novas (mantendo as 14 atuais intactas), agrupadas por propósito:

```python
# PPot / NPot — potencial de melhora/piora
R15: media AND ppot['alto']                        → call    # upgrade de fold marginal p/ call por potencial de draw
R16: fraca AND ppot['alto'] AND pot_odds['baixo']   → call    # draw especulativo barato
R17: forte AND npot['alto']                          → call    # mão forte mas vulnerável: segura, não escala pra raise
R18: media AND npot['alto']                          → fold    # mão média vulnerável: não vale continuar

# Agressividade do oponente
R19: fraca AND opponent_aggression['agressivo']              → fold
R20: media AND opponent_aggression['agressivo']               → fold
R21: media AND opponent_aggression['agressivo'] & pot_odds['alto'] → fold   # reforço
R22: forte AND opponent_aggression['passivo']                 → raise   # value bet maior contra passivo
R23: media AND opponent_aggression['passivo']                 → call    # call down mais solto contra passivo
R24: fraca AND opponent_aggression['passivo'] AND position['dentro'] → raise  # tentativa de roubo (steal)

# Comprometimento de stack (SPR)
R25: forte AND stack_commitment['alto']  → raise
R26: media AND stack_commitment['alto']  → call    # pot committed, mão média não dá pra foldar
R27: fraca AND stack_commitment['baixo'] → fold    # reforço: sobra stack, sem motivo pra arriscar
R28: stack_commitment['alto'] AND pot_odds['baixo'] → call
```

(~28 regras totais. Números exatos de breakpoints e a lista final de regras podem ser
ajustados durante a implementação/teste — o objetivo aqui é a estrutura e a cobertura dos
casos, não um valor imutável.)

`decide()` passa a receber 7 parâmetros (`hand_strength_val, pot_odds_val, position_val,
ppot_val, npot_val, aggression_val, commitment_val`), clipando todos em `[0.01, 0.99]`
como hoje, e setando os 7 inputs em `self._sim` antes de `compute()` — necessário porque
com todos os 7 antecedentes participando de alguma regra, o skfuzzy exige todos setados.
Threshold de saída (`<0.35 fold`, `<0.65 call`, senão `raise`) não muda.

## 5-6. `backend/db/database.py` e `backend/db/recorder.py` — persistência

Tabela `actions` ganha 4 colunas: `ppot REAL`, `npot REAL`, `opponent_aggression REAL`,
`stack_commitment REAL`. `GameRecorder.record_action` passa os novos campos de
`fuzzy_data`. Como `CREATE TABLE IF NOT EXISTS` não altera tabelas já criadas, e
`poker.db` é local/gitignored (sem dados de produção a preservar), a orientação é rodar
`rm poker.db` uma vez após a mudança (já documentado em `DEVELOPMENT.md`) em vez de
escrever uma migração `ALTER TABLE`.

## 7-8. Documentação — `FUZZY_LOGIC.md` e `DEVELOPMENT.md`

Atualizar `backend/engine/fuzzy/FUZZY_LOGIC.md` (fonte de verdade do sistema fuzzy) com
as 4 novas variáveis, suas MFs, as novas regras e a citação do paper/Billings 2006.
Atualizar a seção 3 do `DEVELOPMENT.md` (raiz do projeto) para refletir 7 variáveis em
vez de 3, linkando o racional deste plano.

## 9. Testes

Estender `backend/tests/` com:
- Sanidade de `calculate_hand_potential`: um flush draw conhecido (4 cartas do mesmo
  naipe entre mão+flop) deve ter `ppot` sensivelmente mais alto que uma mão sem draw;
  `ppot`/`npot` sempre em `[0, 1]`.
- Smoke test de `FuzzyPokerAgent.decide()` com os 7 parâmetros em uma grade de valores
  (incluindo extremos 0/1) garantindo que sempre retorna `'fold'|'call'|'raise'` sem
  exceção.

---

## Verificação end-to-end

1. `cd backend && pytest` — testes novos e existentes passando.
2. `rm poker.db` (schema mudou).
3. `./run.sh` e jogar algumas rodadas manualmente contra o agente, conferindo no
   terminal que a linha `[FUZZY] ...` imprime as 7 variáveis com valores plausíveis
   (ex. `ppot` só não-zero no flop/turn; `opponent_aggression` sobe após o humano dar
   raise seguido).
4. Inspecionar `poker.db` (`sqlite3 poker.db "select * from actions limit 5;"`) para
   confirmar que as 4 novas colunas estão sendo preenchidas.

## Referências a incluir na escrita (confirmar antes de citar)

- Ekmekci, Ö.; Şirin, V. (2013). *Learning Strategies for Opponent Modeling in Poker*.
  AAAI Workshop on Computer Poker and Imperfect Information — fonte das 19 features
  candidatas e da Table 5 usada para priorização (lido integralmente nesta sessão).
- Billings, D. (2006). *Algorithms and Assessment in Computer Poker*. PhD Dissertation,
  University of Alberta — algoritmo de Hand Strength / PPot / NPot.
- Felix, D.; Reis, L. (2008). *An Experimental Approach to Online Opponent Modeling in
  Texas Hold'em Poker*. SBIA 2008 — mencionado como origem da fórmula
  `P(win)=HS×(1−NPot)+(1−HS)×PPot` (não usada diretamente na implementação, citada só
  como referência de onde vem HS/PPot/NPot combinados).
- Sinalização: a referência a Miller/Sklansky/Flynt para o conceito de "stack
  commitment"/SPR vem de conhecimento geral de treinamento, não de leitura de um paper —
  confirmar título/edição exatos antes de citar no texto.
