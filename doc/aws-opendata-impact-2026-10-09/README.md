# DigitalCorpora sponsorship impact report tools

These read-only tools support a report for Kyle Cook dated October 9, 2026. They do not change the responder, ingest logs, send mail, or publish evidence. Private mailbox exports, address adjudications, credentials, report content, and generated documents must remain outside this public repository.

`count_access_logs.sh ACCESS_LOG...` streams retained S3 logs for the same bucket, accepts successful object GET/copy-part GET requests (HTTP 200/206), and deduplicates AWS request IDs globally before counting requests and bytes by event year. Filenames reflect ingestion year and cannot establish event year. It reports all objects, `corpora/` datasets, `downloads/` tools, other objects, and the M57-Patents prefix. A range request counts as one request, not a completed image download or a person. The existing stats configuration object is excluded. Dash byte counts mean zero recorded bytes. Malformed successful lines are reported on stderr and must be investigated before using the result. Retained logs may be incomplete, so these are observed counts. Sort uses up to 64 MB of memory per process and private temporary files. GNU sort uses one worker thread. For large sources, `--extract` produces sorted, deduplicated intermediate records; `--merge` combines only those sorted intermediates and deduplicates across them. Intermediates contain request identifiers and must remain private.

`request_audit.py` reconciles the responder mbox, old tab-separated tallies, new six-line tallies, and normalized Gmail JSON. It retains source IDs and bodies for private review. Complete forms are candidate requests, not proof of delivery or genuine identities. Review spam, unrelated form submissions, and ambiguous correspondence through a private decisions JSON containing `aliases`, `excluded` (address-to-reason), and `confirmed_manual` (addresses). Different addresses are merged only by explicit decisions; Gmail dots and plus tags normalize automatically. Annual figures show evidence years and earliest observed evidence, which may be follow-up dates or quoted requests. They do not establish first-ever request dates. Counts estimate people through email identities; shared addresses and undiscovered aliases remain limitations.

Input files are `archive.mbox`, `tally-all.csv`, `tally.csv`, `t2.csv`, and selected `gmail-*.json` arrays (excluding `gmail-manual-search.json`). Each Gmail item has `id`, `headers` (`from`, `to`, `date`, `subject`), `plain`, and `html`; provide decoded MIME bodies. Historical messages without a complete form are extracted only from Gmail and require manual confirmation. No archive completeness is assumed.

Run through the supplied Makefile:

```sh
make -C doc/aws-opendata-impact-2026-10-09 check PYTHON=/path/to/python
make -C doc/aws-opendata-impact-2026-10-09 count INPUT_LOG=/private/s3logs.2025.log
make -C doc/aws-opendata-impact-2026-10-09 audit INPUT=/private/evidence OUTPUT=/private/audit DECISIONS=/private/decisions.json PYTHON=/path/to/python
make -C doc/aws-opendata-impact-2026-10-09 mark-create NODE=/path/to/node
make -C doc/aws-opendata-impact-2026-10-09 report CONTENT=/private/content.json OUTPUT=/private/report PYTHON=/path/to/python
make -C doc/aws-opendata-impact-2026-10-09 render OUTPUT=/private/report PYTHON=/path/to/python
```

Python dependencies are Pydantic 2 and python-docx. The Codex bundled renderer supplies document visual QA. `PYTHON` and `NODE` choose executable runtimes; `INPUT` is the private evidence directory; `INPUT_LOG` is a retained annual access log; `OUTPUT` is the private artifact directory; `DECISIONS` is reviewed private identity adjudication; `CONTENT` is the reviewed report JSON; `DOCX_SKILL_DIR` is the Documents skill installation containing its renderer and operation marker. No variable contains credentials. Report JSON fields are defined by the Pydantic models in `build_report.py`. Render and inspect every page before handoff.
