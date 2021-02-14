check:
	pytest --cov=./ --cov-report=xml python
	flake8 python --count --select=E9,F63,F7,F82,W91 --show-source --statistics --exit-zero --max-complexity=10


configure-aws:
	@echo install packages on aws necessary for development. Indempotent 
	sudo yum install -y git emacs python3 python3-pip zsh
	git config --global push.default current
	pip3 install --user -r requirements.txt
	pip3 install --user -r requirements-dev.txt
