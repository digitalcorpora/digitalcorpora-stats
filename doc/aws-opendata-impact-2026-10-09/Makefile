# Build a private impact report from explicitly supplied evidence and content.
# INPUT names a private directory of mailbox, tally, and Gmail source records.
# OUTPUT names the private destination for audit records and document artifacts.
# DECISIONS names a private JSON file of reviewed exclusions and address aliases.
# CONTENT names the private report content JSON; no personal data belongs here.
# INPUT_LOG names one retained annual access-log file for read-only counting.
# PYTHON and NODE select runtimes; DOCX_SKILL_DIR selects the packaged renderer.
# Read-only counting never changes source logs or the deployed responder.
PYTHON ?= python3
NODE ?= node
INPUT ?=
OUTPUT ?=
DECISIONS ?=
CONTENT ?=
INPUT_LOG ?=
DOCX_SKILL_DIR ?= /Users/simsong/.codex/plugins/cache/openai-primary-runtime/documents/26.1007.11041/skills/documents
HERE := $(abspath $(dir $(lastword $(MAKEFILE_LIST))))

.PHONY: audit count check report render mark-create
count:
	@test -n "$(INPUT_LOG)"
	bash "$(HERE)/count_access_logs.sh" "$(INPUT_LOG)"
audit:
	@test -n "$(INPUT)" -a -n "$(OUTPUT)"
	"$(PYTHON)" "$(HERE)/request_audit.py" --input "$(INPUT)" --output "$(OUTPUT)" $(if $(DECISIONS),--decisions "$(DECISIONS)")
check:
	"$(PYTHON)" -m unittest discover -s "$(HERE)" -p 'test_*.py'
	bash -n "$(HERE)/count_access_logs.sh"
report:
	"$(PYTHON)" "$(HERE)/build_report.py" --content "$(CONTENT)" --output "$(OUTPUT)"
render:
	"$(PYTHON)" "$(DOCX_SKILL_DIR)/render_docx.py" "$(OUTPUT)/DigitalCorpora impact report for Kyle Cook.docx" --output_dir "$(OUTPUT)/render" --emit_pdf
mark-create:
	"$(NODE)" "$(DOCX_SKILL_DIR)/container_tools/mark_artifact_operation_started.mjs" --operation-kind create --expected-output-count 1 --output-format docx
