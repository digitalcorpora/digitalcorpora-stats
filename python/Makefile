SHELL=/bin/bash

pylint:
	python3 -m pylint --rcfile .pylintrc  --verbose  *.py   --fail-under 5

pytest:
	python3 -m pytest .

dump-schema:
	source $$HOME/dbwriter.bash && dbdump --no-data --no-tablespaces --single-transaction=TRUE > schema.sql

dump-db:
	source $$HOME/dbwriter.bash && dbdump -d > database-$$(date -I).backup.sql
