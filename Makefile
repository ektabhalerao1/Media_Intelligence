PYTHON ?= python3
VENV_DIR ?= .venv

.PHONY: help venv install run clean

help:
	@echo "Targets:"
	@echo "  make venv    - Create virtual environment"
	@echo "  make install - Install dependencies into virtual environment"
	@echo "  make run     - Run Streamlit app (app.py)"
	@echo "  make clean   - Remove virtual environment and cache files"

venv:
	$(PYTHON) -m venv $(VENV_DIR)

install:
	$(VENV_DIR)/bin/pip install --upgrade pip
	$(VENV_DIR)/bin/pip install -r requirements.txt

run:
	$(VENV_DIR)/bin/streamlit run app.py

clean:
	rm -rf $(VENV_DIR) __pycache__ reader/__pycache__ .streamlit
