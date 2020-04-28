install:
	pipenv sync -d

test:
	pipenv run pytest -s

pack:
	pipenv run python setup.py sdist bdist_wheel

upload:
	pipenv run twine upload dist/*

release: clean pack upload

clean:
	rm -rf dist

.PHONY: install test pack upload clean