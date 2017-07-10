PYTHON=env/bin/python
PIP=env/bin/pip
EI=env/bin/easy_install
NOSE=env/bin/nose2
FLAKE=env/bin/flake8

build:
	virtualenv -p python3 env
	$(PIP) install -U -r requirements.txt
	$(PIP) install -U flake8 nose2

flake:
	$(FLAKE) --exclude=./env ./ --ignore=E501,E731

test:
	$(NOSE) -s $(FLAGS) ./tests/

clean:
	rm -rf `find . -name __pycache__`
	rm -f `find . -type f -name '*.py[co]' `
	rm -f `find . -type f -name '*~' `
	rm -f `find . -type f -name '.*~' `
	rm -f `find . -type f -name '@*' `
	rm -f `find . -type f -name '#*#' `
	rm -f `find . -type f -name '*.orig' `
	rm -f `find . -type f -name '*.rej' `
	rm -f .coverage
	rm -rf coverage
	rm -rf env
	rm -rf build
