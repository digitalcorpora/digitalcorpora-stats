check:
	pytest --cov=./ --cov-report=xml python
	flake8 python --count --select=E9,F63,F7,F82,W91 --show-source --statistics --exit-zero --max-complexity=10
