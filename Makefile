.PHONY: install setup demo serve test lint evaluate
install:
	python -m pip install -c requirements.lock -e '.[dev,bedrock]'
setup:
	doculens setup
demo:
	doculens demo
serve:
	doculens serve
test:
	pytest -q
lint:
	ruff check doculens tests
evaluate:
	doculens evaluate --output data/evaluation.json
