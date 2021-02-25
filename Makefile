check:
	pytest --cov=./ --cov-report=xml python
	flake8 python --count --select=E9,F63,F7,F82,W91 --show-source --statistics --exit-zero --max-complexity=10

configure-aws:
	sudo yum install -y python3 python3-pip python3-wheel git emacs
	git config --global pager.branch false
	python3 -m pip install --upgrade pip
	pip3 install --user -r requirements.txt
	pip3 install --user -r requirements-dev.txt

install:
	python3 -m pip install --upgrade pip
	if [ -r requirements.txt ]; then pip3 install --user -r requirements.txt ; fi
	if [ -r requirements-dev.txt ]; then pip3 install --user -r requirements-dev.txt ; fi
