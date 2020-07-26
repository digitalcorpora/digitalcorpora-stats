check:
	pytest --cov=./ --cov-report=xml python
	flake8 python --count --select=E9,F63,F7,F82,W91,W293,W391 --show-source --statistics
	flake8 python
	flake8 python --count --exit-zero --max-complexity=10 --statistics

