SHELL=bash
PYTHON_DIR=python

pylint:
	cd $(PYTHON_DIR); make pylint

summarize:
	source $$HOME/dbwriter.bash; python3 python/dclogtool.py --env --prod --download_summarize

dreamhost-download-s3logs:
	source $$HOME/dbwriter.bash; .venv/bin/python python/dclogtool.py --s3_logs_download_ingest_and_save --env --prod --loglevel INFO -j10 --ignore_keys ignore.txt

dreamhost-summarize:
	source $$HOME/dbwriter.bash; .venv/bin/python python/dclogtool.py --download_summarize --stable_only --max_summarize_days 1 --env --prod --loglevel INFO

dreamhost-optimize:
	source $$HOME/dbwriter.bash; .venv/bin/python python/dclogtool.py --optimize_downloads --env --prod --loglevel INFO

dreamhost-hourly:
	$(MAKE) dreamhost-download-s3logs
	$(MAKE) dreamhost-summarize

backup-sql:
	source $$HOME/dbwriter.bash; dbdump | gzip -9 > $$HOME/dcstats-dump.$$(date -I).gz

check:
	make pytest

install-dependencies:
	python3 -m pip install --user --upgrade pip
	if [ -r requirements.txt ]; then pip3 install --user -r requirements.txt ; else echo no requirements.txt ; fi

configure-aws:
	sudo yum install -y python3 python3-pip python3-wheel git emacs
	git config --global pager.branch false
	make install-dependencies

coverage:
	cd $(PYTHON_DIR); python3 -m pytest --debug -v --cov=. --cov-report=xml tests; cp coverage.xml ..

pytest:
	cd $(PYTHON_DIR); make pytest
