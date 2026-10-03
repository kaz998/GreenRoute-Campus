.PHONY: install run test compile clean

install:
	./install_linux.sh

run:
	./run.sh

test:
	.venv/bin/python -m pytest -q

compile:
	.venv/bin/python -m py_compile app/__init__.py app/config.py app/db.py app/services/*.py app/ml/*.py seed.py setup_ai.py

clean:
	rm -rf .pytest_cache __pycache__ app/**/__pycache__ tests/**/__pycache__
