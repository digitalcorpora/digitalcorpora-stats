PYLINT_FILES=$(shell /bin/ls *.py  | grep -v bottle.py | grep -v app_wsgi.py)

pylint:
	(cd python; pylint $(PYLINT_FILES))

install-dependencies:
	python3 -m pip install --upgrade pip
	if [ -r requirements.txt ]; then pip3 install --user -r requirements.txt ; else echo no requirements.txt ; fi
	find $(HOME) -print

configure-aws:
	sudo yum install -y python3 python3-pip python3-wheel git emacs
	git config --global pager.branch false
	make install-dependencies

coverage:
	(cd python;pytest --debug -v --cov=. --cov-report=xml tests/) || echo pytest failed
