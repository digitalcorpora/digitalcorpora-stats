all:
	py.test
	flake8 python --count --select=E9,F63,F7,F82 --show-source --statistics
	flake8 python
	flake8 python --count --exit-zero --max-complexity=10 --statistics

