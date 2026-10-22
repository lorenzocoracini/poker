# Usage (from code/poker):
#   make jogar                    play against the agent (development DB, poker.db)
#   make estudo                   user-study session: asks the participant code, uses experimentos/estudo.db
#   make simular PARTIDAS=200     run the simulation, then the analysis
#   make analisar                 rebuild the CSVs in escrita/dados

PARTIDAS ?= 200
SEMENTE  ?= 42
EXP      := $(CURDIR)/experimentos

.PHONY: jogar estudo simular analisar

jogar:
	./run.sh

estudo:
	POKER_ESTUDO=1 POKER_DB=$(EXP)/estudo.db ./run.sh

simular:
	python3 experimentos/simular.py --partidas $(PARTIDAS) --semente $(SEMENTE) --db $(EXP)/simulacao.db
	$(MAKE) analisar

analisar:
	python3 experimentos/analisar.py
