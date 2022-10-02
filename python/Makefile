SHELL=/bin/bash

pylint:
	pylint --rcfile .pylintrc  --verbose  *.py   --fail-under 5

pytest:
	python3 -m pytest .

dump-schema:
	source $$HOME/dbwriter.bash && dbdump --no-data --column-statistics=0 --no-tablespaces --single-transaction=TRUE > schema.sql

dump-db:
	source $$HOME/dbwriter.bash && dbdump -d > database-$$(date -I).backup.sql
