SHELL=/bin/bash

pylint:
	pylint --rcfile .pylintrc  --verbose  *.py

pytest:
	python3 -m pytest .

dump-schema:
	source $$HOME/dbwriter.bash && dbdump -d > schema.sql

dump-db:
	source $$HOME/dbwriter.bash && dbdump -d > database-$$(date -I).backup.sql
