# Build the statistics report and render page images for visual inspection.
# PYTHON selects a runtime with python-docx; NODE selects the artifact runtime.
# DOCX_SKILL_DIR locates the packaged renderer and artifact marker.
# These overridable environment variables contain paths, never credentials.
# Report builds and checks do not change AWS or the production reporting system.
# AWS_PROFILE/AWS_REGION select AWS CLI context only for the explicit grant target.
PYTHON ?= python3
NODE ?= node
DOCX_SKILL_DIR ?= /Users/simsong/.codex/plugins/cache/openai-primary-runtime/documents/26.1007.11041/skills/documents
REPORT_DIR := $(abspath $(dir $(lastword $(MAKEFILE_LIST))))
REPORT := $(REPORT_DIR)/DigitalCorpora statistics system options 2026-10-09.docx

.PHONY: report render mark-edit grant-storage-lens-access plan-storage-lens-access check-access
report:
	"$(PYTHON)" "$(REPORT_DIR)/dcstats_budget_report_builder.py"

render: report
	"$(PYTHON)" "$(DOCX_SKILL_DIR)/render_docx.py" "$(REPORT)" --output_dir "$(REPORT_DIR)/render" --emit_pdf

mark-edit:
	"$(NODE)" "$(DOCX_SKILL_DIR)/container_tools/mark_artifact_operation_started.mjs" --operation-kind edit --expected-output-count 1 --output-format docx

grant-storage-lens-access:
	bash "$(REPORT_DIR)/grant-storage-lens-access.sh"

plan-storage-lens-access:
	bash "$(REPORT_DIR)/grant-storage-lens-access.sh" --plan

check-access:
	bash -n "$(REPORT_DIR)/grant-storage-lens-access.sh"
	bash "$(REPORT_DIR)/grant-storage-lens-access.sh" --plan | jq -e . >/dev/null
