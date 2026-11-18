PYTHON ?= python3

.PHONY: build run test help

build:
	$(PYTHON) scripts/build_native.py

run:
	PYTHONPATH=src $(PYTHON) -m pulse_tui

test:
	$(PYTHON) tests/test_colors.py
	$(PYTHON) tests/test_character.py
	$(PYTHON) tests/test_styles.py
	$(PYTHON) tests/test_cycle.py
	$(PYTHON) tests/test_cinematic.py
	$(PYTHON) tests/test_scenes.py
	$(PYTHON) tests/test_app.py

help:
	PYTHONPATH=src $(PYTHON) -m pulse_tui --help
