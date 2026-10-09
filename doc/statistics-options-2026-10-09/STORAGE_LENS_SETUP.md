# Enabling Storage Lens and accessing history

Storage Lens Advanced can supply the daily aggregate input for DreamHost cron without
retaining our own download-event database. Enabling it is an AWS configuration change;
it does not require moving download URLs or changing the public corpus access policy.
The following is a setup plan, not an activated service.

## Account and permissions

For Simson account `376778049323` to view dashboards in Digital Corpora account
`809276937361`, use the [cross-account access CLI](STORAGE_LENS_ACCESS.md). It grants
read-only viewing of free and enabled Advanced metrics; it does not enable paid metrics.

Create the configuration in the account that owns `digitalcorpora`, using an IAM user
or role with Storage Lens permissions. A separate Lambda account cannot monitor this
bucket solely because the bucket is public. Organization dashboards are an alternative
only with the relevant organization access. The operator needs configuration list,
get, and put permissions; dashboard access is separate. DreamHost needs only read
access to the aggregate export prefix, with listing permission if its reader lists
objects. [AWS permissions](https://docs.aws.amazon.com/AmazonS3/latest/userguide/storage_lens_iam_permissions.html)

Renew the expired AWS login before implementation and first inspect existing Storage
Lens configurations. Reuse a suitable bucket-scoped configuration if one exists.
Avoid enabling a second overlapping paid configuration without a reason, or upgrading
the account-wide default dashboard if it would monitor unrelated buckets. The billing
account for the configuration and the owner of its export bucket must be identified.

## Configuration

1. Open S3 Storage Lens **Dashboards** and create or edit one enabled configuration
   with home Region `us-west-2`. Scope it to `digitalcorpora` only.
2. Select **Advanced tier**, with **Activity**, **Detailed status code**, and
   **Performance** metrics. These supply GET and byte totals, status patterns,
   read-size distributions, and daily unique-object accesses.
3. Use `/` as the delimiter. Enable prefix aggregation for console views if useful,
   and the **Expanded prefixes metrics report** for all corpus directories. Ordinary
   dashboard/default-export prefixes are filtered by storage threshold and depth;
   expanded exports include prefixes up to depth 50. The eventual public report must
   select disjoint corpus categories rather than sum overlapping parent/child prefixes.
4. Choose ordinary S3 **CSV** exports for a simple DreamHost reader, or Parquet if
   there is a reason to add a Parquet reader. Use both the default report for bucket
   totals and expanded-prefix report for directory detail. Select a private general
   purpose export bucket in `us-west-2`, and use SSE-S3 encryption. Leave S3 Tables
   and CloudWatch publishing disabled in the initial design.
5. Grant the Storage Lens service permission to write to the export prefix, scoped
   by the configuration's source account and ARN. Add the DreamHost reader's
   read-only permission. Apply a short export retention policy after confirming that
   the reader has durably saved daily summaries. Confirm the policy with a real export.
6. Allow up to 48 hours for the configuration to appear accurately. Verify the first
   complete default and expanded exports, measured sizes, dates, and fields before
   configuring the reporting cron. A successful configuration API call is not proof
   of successful export delivery.

The console/CLI support these settings. A configuration can be submitted through
`aws s3control put-storage-lens-configuration`; the account ID, configuration ID,
export bucket, and policy must be resolved before producing a deployable command.
[AWS configuration guide](https://docs.aws.amazon.com/AmazonS3/latest/userguide/storage_lens_creating_dashboard.html),
[AWS destination bucket policy](https://docs.aws.amazon.com/AmazonS3/latest/userguide/example-bucket-policies.html#example-bucket-policies-use-case-10)

The configuration is bucket-scoped, so the approximately $0.0039 metrics estimate
includes the bucket's current public object count, not just one reporting prefix.
Hidden versions and other objects can raise monitored count. Export storage, requests,
and any paid transfer are separate. The report models $0.04–$0.13/month under its
explicit small-export assumptions; a $0.20 planning allowance leaves ample room below
the accepted $1 average budget. Verify the first bill and export volume.

## DreamHost publication

The new cron reads the latest complete manifests and aggregate files, validates their
report date, selects `corpora/` categories, replaces each day's summary transactionally,
and renders static HTML atomically. Publish files accessed/day, GETs/day, GB/day,
status and read-size patterns, and the date and quality of the data. A new configuration
may have only a short history, so missing dates must remain missing rather than become
zero. The reader/rendering code still needs implementation; neither the old importer
nor a new cron was activated while preparing this report.

## Can it go back in time

**Storage Lens has historical retention, but it should not be treated as a promised
backfill of previously uncollected download statistics.** AWS documents 15 months of
metric retention. Free-tier queries expose 14 days, while Advanced exposes up to
15 months. An existing dashboard may already contain historical storage measurements;
its activity history depends on what was enabled and collected. The setup and retention
documentation does not promise retrospective generation of newly enabled activity,
performance, or expanded-prefix metrics.
[AWS retention and metrics selection](https://docs.aws.amazon.com/AmazonS3/latest/userguide/storage_lens_basics_metrics_recommendations.html)

The practical check is to inspect the existing dashboard's September dates for GET,
downloaded-byte, and unique-access fields after confirming its current configuration.
If those measurements exist, preserve them. If they do not, plan new reporting from
the first available native day; retained old S3 access logs can support a separate
bounded historical aggregation. Storage Lens has no documented interface for uploading
our old logs to populate its past daily metrics. Daily exports are not a documented
bulk re-export/backfill mechanism for the preceding 15 months.

For the September surge, do not promise a native reconstruction without inspecting
the account's actual history. Existing database totals have known replay inflation
and must retain that quality note. Static summaries saved on DreamHost can be retained
longer than Storage Lens's console history while each database stays below 3 GB.
