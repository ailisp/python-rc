install:
	pipenv sync -d

test:
	pipenv run pytest -s

pack: clean
	pipenv run python setup.py sdist bdist_wheel

upload:
	pipenv run twine upload dist/*

clean:
	rm -rf dist

.PHONY: install test pack upload clean