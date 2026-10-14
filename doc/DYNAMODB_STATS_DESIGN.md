# DynamoDB Statistics Design

Status: proposed in [issue #69](https://github.com/digitalcorpora/digitalcorpora-stats/issues/69). This is the approved target direction, not an implemented service.

## Decisions

* The current S3 server-access-log delivery delay (usually a few hours) is acceptable.
* Raw S3 access-log objects are not retained after durable ingestion completes.
* Keep a summary of each IP address and object for a rolling year: first/last
  download time, total bytes, and accepted-download count. No per-request
  history is retained.
* Keep full browser user-agent strings only as global summaries for 180 days;
  this is a configuration value, not a permanent event archive.
* A SAM stack owns the report-artifact bucket. Its versioned JSON output is
  public only through the selected report distribution/origin; DynamoDB is not
  public.
* AWS Budgets must warn at $5 actual monthly spend, warn again at $10, and
  require a hard operational review at $25. The $25 threshold does not
  automatically disable ingestion.

## Data flow and freshness

S3 server access logs are the input. The log bucket sends an object-created
notification to SQS; the ingestion Lambda conditionally records each accepted
source line, updates aggregates, and marks the log object complete. It deletes
the S3 log object only after completion is durable. A successful ingestion
conditionally queues a report projection if no report has been computed in the
previous five minutes. The projector writes static JSON artifacts asynchronously.

The report freshness objective is **five minutes after the access-log object is
delivered**. It is not five minutes after the original download: S3 server
access logs are best-effort and normally arrive within a few hours.

## SAM processing and rollups

All production compute and report artifacts run in a SAM application. The
DynamoDB table is deliberately external to the SAM stack: its lifecycle must
not be tied to a stack replacement or deletion. The stack receives the table
name as a parameter and is granted only the item actions needed by each Lambda.

| Trigger | Records in | Records out | Frequency |
| --- | --- | --- | --- |
| `access-log-ingestor` Lambda, from SQS | One or more S3 log-object notifications; each object contains S3 access-log lines | Log state, short-lived receipt items, hour/object, day/object, day/prefix, IP/object, and user-agent summaries; at most one projection-queue message per five minutes | Event-driven; normally seconds after S3 delivers a log object. |
| `report-projector` Lambda, from SQS | One projection request plus current hour/day/object and day/prefix aggregate items | Eight immutable static JSON artifacts and a new `current.json` manifest | On demand after ingestion, rate-limited to no more than once every five minutes. |
| `daily-rollup-repair` Lambda | Previous seven days of mutable day/object and day/prefix aggregates | Corrected day totals and report artifacts; a reconciliation metric | EventBridge schedule daily at 01:00 UTC, plus an operator-invoked backfill mode. |
| `yearly-materializer` Lambda | All day aggregates for one completed UTC calendar year | `YEAR#<year>` aggregate items and a versioned yearly JSON artifact | EventBridge schedule on 2 January at 03:00 UTC; operator-invoked for backfill/rebuild. |

The canonical statistics are the hour and day aggregate items written by the
ingestor. The daily repair job does not increment a second total; it re-reads
the canonical day shards and **replaces** derived day/report values. It therefore
corrects late S3 log delivery without double-counting. The yearly materializer
also rebuilds from canonical day items and replaces its completed-year output,
so rerunning it is idempotent. It is intentionally delayed until after the
calendar year, then remains rebuildable if very late logs are discovered.

```text
S3 access-log object
  -> SQS notification
  -> access-log-ingestor
  -> receipt + hour/day/IP/user-agent DynamoDB summaries
  -> conditional five-minute projection claim -> projection SQS queue
  -> report-projector -> static JSON artifacts

day aggregates for completed year
  -> (2 January or manual rebuild) yearly-materializer
  -> yearly DynamoDB aggregate + static JSON artifact
```

## DynamoDB table contract

Use one on-demand, Standard-class table in `us-west-2`, encrypted with the
AWS-managed DynamoDB KMS key (`alias/aws/dynamodb`). All keys below are logical
encodings; values are strings unless noted. `shard(key)` is a stable hexadecimal
value in `00`–`0f`. No public IAM principal receives table access.

The reviewable physical table request is
[`DYNAMODB_TABLE_SCHEMA.json`](DYNAMODB_TABLE_SCHEMA.json). The table-creation
program supplies the real table name; the JSON template deliberately contains
no account-specific identifier.

| Item | PK | SK | Required attributes | Retention/access |
| --- | --- | --- | --- | --- |
| Object metadata | `OBJ#<s3-key>` | `META` | bytes, mtime, ETag, SHA-256, SHA3-256, present | Durable; event-driven inventory authority. |
| Log object state | `LOG#<bucket>#<key>#<version-or-etag>` | `META` | received_at, state, completed_at, source ETag/version, parser counts | TTL 35 days after completion; prevents replay and supports reconciliation. |
| Source-record receipt | `REC#<log-object-identity>` | `LINE#<zero-padded-line-number>#<sha256(raw-line)>` | accepted_at, object key, expiration | TTL 35 days. Contains no full log line, IP, or user agent. Conditioned creation provides exactly-once aggregate changes during retry without conflating identical lines. |
| Hour/object aggregate | `HOUR#<UTC-hour>#<shard(s3-key)>` | `OBJ#<s3-key>` | accepted count, bytes total, first_seen, last_seen, partial count | Retain 32 days; serves rolling 24-hour reports. |
| Day/object aggregate | `DAY#<UTC-date>#<shard(s3-key)>` | `OBJ#<s3-key>` | accepted count, bytes total, first_seen, last_seen, partial count | Retain 400 days; serves 7/30-day reports and yearly rollups. |
| Day/prefix aggregate | `DAY#<UTC-date>#PFX#<64-char-prefix>` | `TOTAL` | accepted count, bytes total, first_seen, last_seen | Retain 400 days; serves the 7/30/90-day SAFEDOCS reports. |
| IP/object yearly summary | `IP#<normalized-IP>` | `OBJ#<s3-key>` | first_seen, last_seen, bytes_total, accepted count, expires_at | TTL is last_seen + 366 days. Restricted operational data. |
| User-agent summary | `UA#<sha256(user-agent)>` | `META` | full user-agent, first_seen, last_seen, accepted count, expires_at | TTL is last_seen + 180 days. Restricted operational data. |
| Projector state | `SYSTEM#REPORTS` | `STATE` | projection_version, projected_at, lock expiry | Durable singleton; conditional updates prevent concurrent projections. |
| Year/object aggregate | `YEAR#<UTC-year>#<shard(s3-key)>` | `OBJ#<s3-key>` | accepted count, bytes total, first_seen, last_seen | Durable derived rollup, rebuilt from daily aggregates. |

An empty or absent user-agent is represented as `UA#NONE`; it does not create a
new anonymous string. IP values must be normalized with Python's `ipaddress`
module before they form a key. The IP and user-agent item families are protected
by separate IAM actions/conditions from aggregate-only report access.

The table has one global secondary index, `present-mtime-index`, used only for
the “last 50 uploads” report. Present object metadata items set
`gsi1pk=PRESENT#1` and `gsi1sk=<zero-padded-UTC-epoch>#<s3-key>`; absent objects
omit both attributes. The projector queries that index backwards with `Limit=50`.

`SYSTEM#REPORTS/STATE` contains `last_projected_at`, `lease_until`, and a
monotonic projection version. After a log object commits, the ingestor executes
a conditional update that succeeds only when no lease is active and
`last_projected_at` is at least five minutes old. The winning ingestor sends one
message to the projection queue; all other ingestors do nothing. The projector
holds a short lease, publishes a complete new version, and only then updates
`last_projected_at`. A failed projection expires its lease and is retried by
SQS; ingestion never waits for report generation.

### Idempotent write sequence

For each accepted 200/206 source line, the Lambda calculates its line number and
raw-line SHA-256 within the immutable log-object identity. It uses a DynamoDB
transaction to:

1. conditionally create its source-record receipt;
2. increment the hour/object, day/object, and day/prefix aggregates;
3. update the IP/object and user-agent summaries, preserving `first_seen` and
   extending `last_seen`/TTL.

The transaction is attempted only if the receipt does not exist. A duplicate
delivery or partial retry therefore changes no aggregate. The final handler
transaction marks the log object `complete` only after all eligible lines have
been processed. Expired receipts are acceptable because S3 event duplicates are
expected promptly; the 35-day window is also checked by reconciliation before
source deletion. The five-minute projection claim is attempted once per
completed **log object**, never once per source download line.

The implementation must batch source records only within DynamoDB transaction
limits and use SQS partial-batch failures. It must not acknowledge a source
message until its durable state is complete.

## Report mapping and artifacts

The projector reads DynamoDB `Query` results only; it performs no table scan and
does not call Athena. It writes immutable payloads such as
`reports/v/<timestamp>/downloads-24h.json` then atomically updates a small
`reports/current.json` manifest in the SAM-owned artifact bucket. The existing
web page fetches that manifest/artifact and browser JavaScript renders it.

| Current report | Source | Artifact |
| --- | --- | --- |
| Last 50 corpora uploads | object metadata ordered by a `present/mtime` index | `uploads-latest.json` |
| SAFEDOCS/UNSAFEDOCS, 7/30/90 days | day/prefix aggregates over the stated UTC days | `safedocs-7d.json`, `safedocs-30d.json`, `safedocs-90d.json` |
| Downloads, 7 days | day/object aggregates over seven UTC days | `downloads-7d.json` |
| Downloads, rolling 24 hours | hour/object aggregates over the previous 24 UTC hours | `downloads-24h.json` |
| Failed/incomplete downloads, 24 hours | hour/object `partial_count` and bytes versus current object size | `incomplete-downloads-24h.json` |
| Downloads per day, 30 days | day/object aggregate rollup by UTC date | `downloads-per-day-30d.json` |

Artifacts include `generated_at`, `window_start`, `window_end`, schema version,
and sorted display rows. Reports are served as stale-but-consistent JSON until a
complete newer manifest is published; a failed projection cannot replace the
last known-good report.

### Publication to digitalcorpora.org

The browser does not receive an S3 bucket name or AWS credentials. It fetches a
same-origin configuration file, for example
`https://digitalcorpora.org/reports/stats/stats-config.json`, whose only
location-bearing field is a relative HTTPS manifest URL:

```json
{
  "schema_version": 1,
  "manifest_url": "/reports/stats/current.json"
}
```

The SAM-owned artifact bucket is the source of published aggregate JSON. Only
its non-sensitive `reports/` prefix is readable by the PHP cache proxy; raw
logs, receipt items, IP summaries, and user-agent summaries are never published.
The PHP endpoint maintains a local report cache as follows:

1. Read the locally cached manifest and artifact.
2. If the cache is at most five minutes old, serve it immediately.
3. Otherwise, take a local file lock, fetch the current manifest and artifact
   from S3, verify the manifest checksum, write a temporary cache file, and
   atomically rename it into place before serving it.
4. If refresh fails, serve the last known-good cache with an explicit stale
   response indicator rather than failing the report page.

The browser only fetches same-origin URLs from `digitalcorpora.org`, so it sees
a complete old or complete new JSON version and receives neither an S3 bucket
name nor AWS credentials.

`rsync` is a separate code-deployment mechanism: GitHub CI/CD or the developer
laptop publishes the JavaScript report client, PHP cache endpoint, and report
page source to a dedicated site directory. It does **not** transport generated
statistics. The deployment must not rsync against the site root or delete
unrelated site content.

## Retention, deletion, and recovery

Raw log objects are deleted only after their `LOG` item is complete. Their
per-record receipts outlive deletion for 35 days; IP/object summaries retain
the required year of operational history, and user-agent summaries retain 180
rolling days. DynamoDB TTL deletion is asynchronous, so application reads
filter `expires_at > now` and a scheduled cleanup metric detects delayed expiry.

A scheduled reconciliation lists newly delivered log objects, checks their log
state, and re-enqueues anything missing or incomplete. It must not recreate a
source object that was deliberately deleted after completion.

## Cost controls

The data contract avoids permanent raw-event storage. An accepted record
normally makes one receipt write, three aggregate writes, one IP/object write,
and one user-agent write; the final implementation must measure transaction
request units rather than assume a fixed price. The
budget alerts at $5, $10, and $25, consumed-capacity metrics, SQS backlog/DLQ
alarms, and a per-query Athena workgroup limit are required before production
traffic.

Create an account-level AWS Budgets monthly cost budget with actual and,
after enough history exists, forecast notifications at each $5, $10, and $25
absolute-dollar threshold. Send notifications directly to the owner email and
an SNS topic; do not add a Lambda merely to relay them. Configure a weekly AWS
Budgets Report to the same recipients and, if service-level detail is needed,
a weekly AWS Cost Management dashboard PDF covering DynamoDB, Lambda, SQS, S3,
Athena, and data transfer. Budget data is delayed billing data, so the $25 gate
is a mandatory human review rather than a real-time circuit breaker.

Athena is for restricted investigations only. If it is later needed, it queries
an explicitly retained export, not a public report request and not a dependency
of log ingestion.

## Remaining approval gate

Before infrastructure work begins, review and approve: the 35-day receipt
window, 180-day user-agent retention, 400-day aggregate retention, the exact
IP access policy, and the report-artifact bucket/distribution name.

## AWS account boundary

Use a new AWS Organizations management/billing account with no workload
resources, and create `digitalcorpora-stats` as a separate workload member
account. The management account, not the existing DigitalCorpora S3 account,
holds the payment method and pays the consolidated bill. The workload account
owns the SAM stack, DynamoDB table, report bucket, budgets, and cost reports.

The existing S3-owning account remains the source of the data and access-log
buckets. Cross-account bucket and SQS policies must allow only the workload
roles to receive notifications and read the required objects. This separation
is a security and cost-allocation boundary; it does not make DynamoDB, Lambda,
or SQS free, and consolidated free-tier usage is shared across an organization.

Do not move or serve the corpus from the workload account: that could forfeit
the existing S3-hosting arrangement whose value is far larger than this
statistics workload. The workload account reads only small access-log objects
and serves small report JSON artifacts. Event-driven full-object hashing stays
behind issue #73 until a staging measurement proves that object size, Lambda
duration, S3 request cost, and cross-account access are acceptable.
