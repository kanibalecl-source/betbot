install:
	python -m pip install -U pip && pip install -r requirements.txt
run:
	uvicorn app.main:app --host 0.0.0.0 --port 8080 --reload
test:
	pytest -q
lint:
	ruff check app tests
clean:
	python scripts/cleanup_repo.py
