PYTHON ?= python3

.PHONY: build run test help

build:
	$(PYTHON) scripts/build_native.py

run:
	PYTHONPATH=src $(PYTHON) -m pulse_tui

test:
	$(PYTHON) tests/test_app.py

help:
	PYTHONPATH=src $(PYTHON) -m pulse_tui --help
