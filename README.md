[![codecov](https://codecov.io/gh/digitalcorpora/digitalcorpora-stats/branch/master/graph/badge.svg?token=rEVoZlToSm)](https://codecov.io/gh/digitalcorpora/digitalcorpora-stats)
This repo computes hash codes for the digitalcorpora collection stored in the s3://digitalcopora/ s3 bucket. It also downloads the bucket statistics and updates the SQL database. Becuase it has write access to the MySQL database, it runs under a different user than the https://github.com/digitalcorpora/app repo.

You can even run it in a specially-created VM.

# Getting going on a new VM
```
sudo yum install git emacs && git clone --recursive git@github.com:digitalcorpora/digitalcorpora-stats.git

cd digitalcorpora-stats
make install-dependencies
make check
```

# Stats for the Digital Corpora website

## AWS SSO authentication

The project `.envrc` uses AWS CLI v2 SSO authentication. Install AWS CLI v2 and
direnv, enable the shell's direnv hook, then run `direnv allow` in this directory.
Run `make aws-sso-login` (or `aws sso login --profile digitalcorpora`) when your
cached SSO session expires. No 1Password access keys are loaded.

The project-local `etc/aws-digitalcorpora-config` contains two profiles:

- `digitalcorpora`: SSO as `DigitalCorporaAccess` in Simson's account `376778049323`.
- `digitalcorpora-storage-lens`: assumes `DigitalCorporaStorageLensReadOnly` in
  Digital Corpora account `809276937361` using that SSO session.

Run `make aws-env-check` for syntax/profile checks, `make aws-identity` to verify
SSO, `make aws-storage-lens-identity` to verify role assumption, and
`make aws-storage-lens-list` to list the Oregon dashboard configurations.
These read-only profiles cannot create the access role. Run the grant script only
with separate Digital Corpora administrator credentials, as described in the
[Storage Lens access guide](doc/statistics-options-2026-10-09/STORAGE_LENS_ACCESS.md).

| Variable | Purpose |
| --- | --- |
| `AWS_PROFILE` | Defaults to `digitalcorpora`, the SSO source profile. Select `digitalcorpora-storage-lens` explicitly for Storage Lens. |
| `AWS_CONFIG_FILE` | Absolute path to `etc/aws-digitalcorpora-config`. Other profiles in `~/.aws/config` require explicitly selecting that file. |
| `AWS_REGION`, `AWS_DEFAULT_REGION` | Default service Region `us-west-2`; the SSO session authenticates in `us-east-1`. |
| `OP_BYPASS_AWS` | Set to `1` so the existing shell wrapper bypasses 1Password. |
| `AWS_ACCESS_KEY_ID`, `AWS_SECRET_ACCESS_KEY`, `AWS_SESSION_TOKEN`, `AWS_SECURITY_TOKEN`, `AWS_DEFAULT_PROFILE` | Unset to prevent inherited credentials from overriding SSO. |

AWS manages cached login credentials outside the repository. Direnv restores the
previous shell environment when you leave this directory. See the
[AWS CLI SSO guide](https://docs.aws.amazon.com/cli/latest/userguide/cli-configure-sso.html).

The implemented ingestion, aggregation, and proposed event-driven replacement
are documented in [Theory of Operation](doc/THEORY_OF_OPERATION.md). The older
[design note](doc/Design.md) is a roadmap and includes paths not implemented in
the current service. The approved DynamoDB target data/report contract is in
[DynamoDB Statistics Design](doc/DYNAMODB_STATS_DESIGN.md).

## Functionality:
- Parsed the logfiles for digitalcorpora.org
- Downloads and parses the S3 download logs
- Scans the corpora at s3://digitalcorpora/corpora/ and checks for:
  - New files that need to be hashed. They are hashed with a multi-threaded hasher.
  - Files that no longer exist. They are GCed from the database if they were never downloaded, and they are marked no longer present if they were downloaded.

## Migration status

The static Storage Lens website migration is on hold as of October 13, 2026.
See [the checkpoint](doc/statistics-options-2026-10-09/ON_HOLD_2026-10-13.md)
for verified exports, credential limitations, the account-wide monitoring cost
issue, and the remaining implementation/deployment work. AWS Advanced metrics
remain enabled; pausing this task does not stop their charges.

## Design

The October 2026 budget comparison, report builders, pricing evidence, and render
outputs are in [Statistics options](doc/statistics-options-2026-10-09/README.md).
[Storage Lens setup and history](doc/statistics-options-2026-10-09/STORAGE_LENS_SETUP.md)
describes the proposed native aggregates and DreamHost publication path. Its report
build overrides are `PYTHON`, `NODE`, and `DOCX_SKILL_DIR` (runtime and renderer paths;
no credentials). The dashboard and exports were enabled on October 9; the static
reader/rendering implementation is still pending.
The [cross-account access CLI](doc/statistics-options-2026-10-09/STORAGE_LENS_ACCESS.md)
creates a read-only viewing role when explicitly run. `AWS_PROFILE` selects its AWS
CLI credentials and `AWS_REGION` selects its default Region; no credentials are saved.

- Run as a daemon/system service so whenever a new log is created, it is automatically parsed, using something like a watch folder.
- Reads database credentials from home directory.
- Options will be set using a config file
- On initial run, user will specify config file using -c option followed by the path to the config file

## Flow
- Program is run and set as a system service, using config file
- logfile name syntax and logfile syntax are specified in config file
- Data is parsed and stored in MySQL database
- MySQL database is read and output in html file under stats.digitalcorpora.org/reports
- bad logs will be sorted out, and an error log will be produced containing relevant information

## Deployment
- `$HOME/digitalcorpora-stats-dev` - Development directory
- `$HOME/digitalcorpora-stats` - Deployment directory

# Tools
## weblog
weblog is a python module that offers:

- Uniform parsing of Apache and S3 logs
- Ability to dedup logs, sort logs, and filter by year.
