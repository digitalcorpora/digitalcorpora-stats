# Statistics options report and supporting files

The preferred design is one bucket-scoped Storage Lens Advanced configuration,
daily aggregate exports, and DreamHost cron producing static HTML. The report
models roughly $0.04–$0.13/month including a small paid export bucket. The metrics
fee alone is approximately $0.0039/month at the observed 19,266 current objects.
Actual scope, versions, export volume, and billing must be verified before activation.

## Files

- [Statistics options report](DigitalCorpora%20statistics%20system%20options%202026-10-09.docx) is the current deliverable.
- [Storage Lens setup and history](STORAGE_LENS_SETUP.md) explains activation and the limits of historical statistics.
- [Cross-account access CLI](STORAGE_LENS_ACCESS.md) grants Simson's account read-only dashboard access from Digital Corpora.
- `dcstats_budget_report_builder.py` contains the current report prose and cost models.
- `report_layout.py` supplies the shared Word layout and formatting helpers.
- `evidence/` contains the public AWS pricing snapshots used for the calculations.
- `render/` contains the current internal QA PDF and eight rendered page images.
- `archive/` preserves the superseded builder and older render pages. Running the
  archived builder produces its old report inside `archive/`; it is not the current build.

The files were moved from this task's `/private/tmp` locations and its visualization
output directory. Unrelated temporary incident probes and other tasks' files were
left untouched. No credentials or private access logs are included.

## Build and inspect

From the repository root, run:

```sh
make -C doc/statistics-options-2026-10-09 report
make -C doc/statistics-options-2026-10-09 render
```

The builder requires Python with `python-docx`. Rendering also requires the packaged
Codex document renderer and its rendering dependencies. For artifact authoring in
Codex, run `mark-edit` exactly once immediately before the first authoring command,
using the bundled runtimes. Inspect every rendered page before delivering an edited
DOCX. The renderer's PDF and images are QA outputs, not an additional requested deliverable.

`PYTHON` selects the Python executable; `NODE` selects the Node executable used by
`mark-edit`; `DOCX_SKILL_DIR` selects the document skill directory containing the
renderer and marker. These are the only build environment overrides. The Makefile
defaults to local Python and Node and the installed skill path; set the executable
overrides to the bundled workspace runtimes when working in Codex. No AWS profile,
AWS credentials, or network access is needed to build the saved report.

`AWS_PROFILE` selects the authenticated AWS CLI profile and `AWS_REGION` selects
its default Region for the explicit `grant-storage-lens-access` target. It uses
normal AWS credential discovery; do not store credential values in this directory.
`plan-storage-lens-access` prints the policy locally; `check-access` checks Bash
syntax and JSON parsing with `jq`. See the access guide for commands and prerequisites.

All report and rendering outputs are repository-relative. The top-level Makefile and
existing unfinished database work were preserved. Report build targets do not activate
AWS services. Only the explicitly invoked access grant target creates an IAM role.
