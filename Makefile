PYTHON_DIR=python

pylint:
	(cd $(PYTHON_DIR); make pylint)

summarize:
	(source $$HOME/dbwriter.bash; python3 python/dclogtool.py --env --prod --download_summarize --year 2025)

dreamhost-download-s3logs:
	(source $$HOME/dbwriter.bash; python3 python/dclogtool.py --s3_logs_download_ingest_and_save --env --prod  --loglevel WARNING -j10 --ignore_keys ignore.txt)

dynamodb-create-tables:
	@test -n "$$DYNAMODB_STATS_TABLE" || (echo "DYNAMODB_STATS_TABLE is required"; exit 2)
	python3 python/dynamodb_stats_schema.py --wait

dynamodb-schema-test:
	(cd $(PYTHON_DIR); python3 -m pytest tests/dynamodb_stats_schema_test.py)

backup-sql:
	(source $$HOME/dbwriter.bash; dbdump | gzip -9 > $$HOME/dcstats-dump.$$(date -I).gz)

check:
	make pytest

install-dependencies:
	if [ "$$(python3 -c 'import sys; print(int(sys.prefix == sys.base_prefix))')" = 1 ]; then python3 -m pip install --user --upgrade pip; else python3 -m pip install --upgrade pip; fi
	if [ -r requirements.txt ]; then if [ "$$(python3 -c 'import sys; print(int(sys.prefix == sys.base_prefix))')" = 1 ]; then pip3 install --user -r requirements.txt; else pip3 install -r requirements.txt; fi; else echo no requirements.txt; fi

configure-aws:
	sudo yum install -y python3 python3-pip python3-wheel git emacs
	git config --global pager.branch false
	make install-dependencies

coverage:
	(cd $(PYTHON_DIR); python3 -m pytest --debug -v --cov=. --cov-report=xml tests; cp coverage.xml ..)

pytest:
	(cd $(PYTHON_DIR); make pytest)

# .envrc selects AWS_PROFILE/AWS_CONFIG_FILE and AWS_REGION/AWS_DEFAULT_REGION.
# OP_BYPASS_AWS bypasses the user's 1Password shell wrapper for SSO.
# Inherited AWS key/token variables are cleared; credentials use the SSO cache.
.PHONY: aws-env-check aws-sso-login aws-identity aws-storage-lens-identity aws-storage-lens-list
aws-env-check:
	bash -n .envrc
	AWS_CONFIG_FILE="$(CURDIR)/etc/aws-digitalcorpora-config" aws configure list-profiles | rg -x digitalcorpora
	AWS_CONFIG_FILE="$(CURDIR)/etc/aws-digitalcorpora-config" aws configure list-profiles | rg -x digitalcorpora-storage-lens

aws-sso-login:
	direnv exec "$(CURDIR)" aws sso login --profile digitalcorpora

aws-identity:
	direnv exec "$(CURDIR)" aws sts get-caller-identity --profile digitalcorpora --query '{Account:Account,Arn:Arn}' --output json --no-cli-pager

aws-storage-lens-identity:
	direnv exec "$(CURDIR)" aws sts get-caller-identity --profile digitalcorpora-storage-lens --query '{Account:Account,Arn:Arn}' --output json --no-cli-pager

aws-storage-lens-list:
	direnv exec "$(CURDIR)" aws s3control list-storage-lens-configurations --account-id 809276937361 --region us-west-2 --profile digitalcorpora-storage-lens --no-cli-pager
