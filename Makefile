pylint:
	(cd python; make pylint)

install-dependencies:
	python3 -m pip install --upgrade pip
	if [ -r requirements.txt ]; then pip3 install --user -r requirements.txt ; else echo no requirements.txt ; fi
	find $(HOME) -print

configure-aws:
	sudo yum install -y python3 python3-pip python3-wheel git emacs
	git config --global pager.branch false
	make install-dependencies

coverage:
	cd python;pytest --debug -v --cov=. --cov-report=xml tests/

pytest:
	cd python; make pytest
