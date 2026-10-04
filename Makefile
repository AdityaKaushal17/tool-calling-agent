.PHONY: seed-prod

ROWS ?= 750

seed-prod:
	python seed.py --rows $(ROWS)