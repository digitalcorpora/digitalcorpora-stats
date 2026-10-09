# This utility revises the requested statistics report for the clarified budget.
# It imports the adjacent Word layout and builds the report with costed options.
# The report distinguishes literal zero cost from recurring fees below one dollar.
# It uses the user's free S3 and DreamHost arrangements as the cost baseline.
# AWS free tiers are conditional on available allowances and bounded workloads.
# The saved document is rendered separately and inspected before delivery.
from pathlib import Path
from docx.shared import Pt
from report_layout import OUT, RT, OxmlElement, doc, p, page, qn, sub, table
doc.add_paragraph('DigitalCorpora statistics options within a one dollar budget', 'Title')
p('Prepared for Simson Garfinkel by Codex  •  Revised 9 October 2026')
p('The operating target is $0 in a typical month, no more than $1/month on average, and $2 in exceptional months. Keep free S3 delivery and use DreamHost cron to render static HTML. DreamHost databases are free while each stays below 3 GB; multiple databases are available. Storage Lens Advanced and its exports are paid. A separate AWS account can supply unused Lambda free-tier allowances, subject to its billing configuration.')
p('Recommendation: use Storage Lens Advanced with daily exports, and let DreamHost cron read them and render static HTML. The user explicitly accepted the approximately $0.0039/month metrics fee and allows up to $1/month. Including a small paid export bucket, the modeled total is about $0.04/month with unused export-transfer allowances, or $0.13 at conservative transfer retail rates. This avoids our processing individual download events and barely changes when request traffic surges. Optional bounded temporary log samples can add automation heuristics; native S3 metrics alone leave bot status unknown.')
sub('Proposals compared')
table(['Option', 'What we learn', 'Monthly spend', 'Budget fit'], [
 ['1  DreamHost aggregates', 'Observed files, bytes, range responses, bot heuristics', '$0 incremental', 'Strict zero if existing host copes'],
 ['2  Storage Lens and cron', 'Broad prefix activity, GB, unique files accessed, read sizes', 'About $0.04–$0.13', 'Best native option within tolerance'],
 ['3  Capped Lambda samples', 'Sampled file and automation patterns; totals need 1 or 2', '$0 with free tier', 'Conditional on explicit processing caps'],
 ['4  Optional DynamoDB', 'Aggregate state and summaries; no new download evidence', '$0 provisioned free tier', 'Optional; DreamHost already suffices'],
 ['5  One CloudWatch filter', 'Bucket GETs and bytes; no distinct files or bots', '$0–$1.80 metrics only', 'Conditional; avoid as foundation'],
], [1.85,2.7,1.3,1.25])
p('The $0 estimates mean incremental cash spending under the arrangements supplied by the user, not free labor or unlimited processing capacity. We should tolerate delayed or sampled statistics during overload rather than automatically buy capacity. No service should be invoked once per corpus download.')
p('CloudFront, WAF Bot Control, CloudTrail data events, Kinesis, and routine Athena queries are excluded from the recommended design. Their useful features do not justify their recurring or traffic-dependent fees at this budget. Detailed rejected-option prices appear on page 6.')

page('Native AWS statistics for a few cents')
sub('Option 2 uses Storage Lens and DreamHost cron')
p('Enable one bucket-scoped Storage Lens Advanced configuration and ordinary S3 CSV or Parquet exports. A new DreamHost cron job reads the daily aggregate export, replaces that day’s summary in a small database, and renders static HTML. AWS captures the activity internally; our system receives aggregate records rather than individual access events. Do not enable CloudWatch publishing, S3 Tables, or a paid dashboard. [1–4]')
p('We could publish requests and GB/day by disjoint corpus prefixes, unique objects accessed/day, HTTP 200 versus 206 counts, read-size distributions, and error trends. Expanded prefix exports can cover small and deep directories; validate the chosen export fields in a pilot. These report broad activity without maintaining a database row for every request. They provide neither reliable human identification nor guaranteed completed-download counts. [2,3]')
table(['Component', 'Conservative quantity', 'Retail monthly cost'], [
 ['Storage Lens Advanced', '19,266 monitored objects; one configuration', '$0.0038532'],
 ['Paid export storage', 'At most 1 GiB retained in S3 Standard', '$0.023'],
 ['Paid export PUTs', 'At most 1,000 requests', '$0.005'],
 ['Export reads', '100 GETs; allow about 1,000 LISTs', 'About $0.0051'],
 ['DreamHost database and static HTML', 'Existing services; each database below 3 GB', '$0 incremental'],
 ['Export transfer to DreamHost', 'At most 1 GiB transferred monthly', '$0–$0.09'],
 ['Total of these assumptions', 'Oregon retail; transfer allowance varies', 'About $0.04–$0.13'],
], [2.05,3.55,1.5])
p('A practical initial estimate is $0.04–$0.13/month, with a $0.20 operating allowance for this option. The lower figure assumes the export account has unused recurring free internet transfer; the upper figure allows about $0.09 for 1 GiB exported to DreamHost. Corpus download bandwidth remains free, independently of this new export bucket. These are quantities to verify, not a guaranteed invoice ceiling. Export volume, pagination, hidden object versions, extra configurations, and taxes can change the bill. The sponsored corpus’s download bandwidth stays $0. Ordinary S3 export storage and requests are conservatively priced as paid, as the user specified. [1]')
p('Storage Lens charges by monitored objects rather than access events. At 80M, 800M, or 8B requests/month, the modeled metrics charge remains about $0.004 if inventory is unchanged. At $0.20/million objects-month, one million objects costs $0.20 and five million costs $1 before export costs. Count versions and all objects in scope, rather than just the current public listing. [1]')
p('Literal zero: Storage Lens free metrics and S3’s free daily storage metrics describe stored bytes and object counts. They do not supply the requested download activity, downloaded bytes, or human/bot split. Because Advanced and exports are paid here, this option cannot honestly be described as a $0 service. [2,4]')
p('Use the export’s date and freshness explicitly. Replace revised daily values instead of adding repeated exports. Never add nested prefix totals together, and never sum daily unique counts to claim distinct files across an entire month.')

page('A strict zero cost system on DreamHost')
sub('Option 1 streams logs into daily summaries')
p('Build a new bounded worker that reads temporary S3 access logs, groups records by event day and file, and writes daily aggregates. DreamHost cron renders those summaries into static HTML. Retain counts and bytes, HTTP status counters, and coarse automation classes. Do not retain permanent request rows, IP histories, or full user-agent strings in the reporting database. S3 reads and download bandwidth are free under the user’s arrangement. [5,6]')
p('This can report all observed file keys, corpus totals, GB/day, range-response counts, unique observed files/day, and declared-bot or likely-automation patterns. It still reads every delivered event when operating in complete mode. AWS access logging is best effort and can deliver duplicates, so these are observed statistics rather than an exact accounting of every client download. [5,6]')
sub('Store much less than the present system')
p('Use one aggregate row per day and file, with fixed columns for requests, response bytes, status counts, and coarse automation counts. A small corpus-summary table supplies public charts. A processed-input ledger and bounded temporary duplicate checks support replay recovery. Reprocessing replaces a day’s result; it must not add the same counters a second time. Duplicate request IDs can occur across separate delivered log objects, so a processed-object ledger alone does not prove source deduplication.')
p('At the observed 19,266 files, a 31-day partition has at most about 597,000 day/file rows. At an assumed 1 KiB total per row including indexes, that is about 0.61 decimal GB. Real table and index sizes must be measured. Keep monthly partitions in separate DreamHost databases and rotate well before 3 GB. Broad category summaries are much smaller. Multiple databases are useful for aggregate retention, not a reason to perpetuate the request-event database.')
sub('Cost and behavior during a surge')
table(['Monthly source requests', 'Assumed raw logs', 'Incremental cash cost', 'Operational consequence'], [
 ['80M', '80 GB', '$0', 'Full aggregation if host throughput permits'],
 ['800M', '800 GB', '$0', 'May require more processing time or delayed days'],
 ['8B', '8 TB', '$0', 'Full timely processing is not established; sampling may be necessary'],
], [1.6,1.15,1.45,2.9])
p('The raw-size model is 1,000 uncompressed bytes per request. It is a sizing assumption, not measured current traffic. Free services do not establish sufficient CPU, scratch space, or bandwidth throughput. Benchmark a bounded job before promising a daily deadline. Maintain short, approved raw retention, and expose provisional, incomplete, or sampled coverage if the worker falls behind.')
p('This is a $0 alternative for full observed file and byte detail. Its tradeoff is continued temporary log processing and custom recovery logic. With the few-cents Storage Lens fee accepted, keep this as an optional source of extra detail rather than the required foundation.')

page('Lambda within an unused free tier')
sub('Option 3 handles aggregates or a bounded log sample')
p('A separate analysis account can run a small scheduled Lambda that reads Storage Lens exports, or reads a selected sample of temporary logs and writes compact summaries for DreamHost to fetch. Use ordinary regional Lambda, a private invocation path, and the existing host for static publication. Keep outputs on DreamHost or in an explicitly costed small S3 export bucket. There is no need for API Gateway, a public Lambda endpoint, provisioned concurrency, or a NAT gateway.')
p('AWS lists 1M Lambda requests and 400,000 GB-seconds per month at no charge. A daily publisher at 0.5 GB for 60 seconds, 31 times per month, uses 930 GB-seconds and 31 requests. EventBridge Scheduler’s 14M free monthly invocations easily cover the schedule, or DreamHost cron can invoke it directly. Free allowances must actually be available; accounts in the same consolidated-billing organization share free-tier treatment. Do not rely on introductory credits to make ongoing costs zero. [7–9]')
sub('Why processing every log is not free at surge scale')
table(['Source requests per month', 'Invocations at 1,000 records each', 'Compute at 1 GB and 2 seconds', 'Lambda after unused free tier'], [
 ['80M', '80,000', '160,000 GB-seconds', '$0'],
 ['800M', '800,000', '1,600,000 GB-seconds', 'About $20'],
 ['8B', '8,000,000', '16,000,000 GB-seconds', 'About $261.40'],
], [1.5,1.9,2.0,1.7])
p('These are hypothetical batch density and runtime, excluding retries, queue operations, state writes, and other services. Larger batches or faster parsing can lower them, but those savings require measurement. Putting an S3 ObjectCreated trigger on every delivered log can exceed the budget before a worker notices the surge. S3 notifications do not emit a GET event for each downloaded file. [7,10]')
sub('An explicit processing envelope makes zero plausible')
p('For sampled analysis, set a fixed schedule of at most 120 private invocations/month, 1 GB memory, 120-second timeout, and no automatic retries or catch-up invocations. That bounds worker compute to 14,400 GB-seconds/month. Adding the daily publisher above yields 15,330 GB-seconds: $0 with unused allowances, or about $0.26 at retail before ancillary services. Sample input sizes must fit a run; truncated or oversized inputs are recorded as incomplete rather than silently extrapolated.')
p('Use scheduled polling instead of an unbounded event source or continuously polled queue. Cap input bytes, listing pages, and output size as well as execution count. This sacrifices complete observation during a surge while preserving the cash budget. Reserved concurrency alone limits parallelism, not monthly execution volume. Scheduling and IAM must prevent additional callers or a replay loop from defeating the envelope.')
p('For scale illustration, a 1 percent log-object sample at 800M requests averages 8,000 selected objects and 16,000 GB-seconds under the earlier batch model; at 8B it is 80,000 objects and 160,000 GB-seconds. A fixed envelope is safer than a percentage alone. Hash sampling of whole log objects is clustered sampling, so uncertainty must account for clustering and missing coverage.')

page('Databases and monitoring within the budget')
sub('Option 4 adds DynamoDB only if it simplifies processing')
p('DreamHost already provides the persistent database and publication layer at $0 under the user’s limits. Prefer that for daily summaries. Lambda can return a small aggregate to the host or stage a bounded export; it need not connect directly to a public MySQL server. DynamoDB is optional for a tiny processing ledger or keyed daily results, not a requirement for statistics.')
p('DynamoDB’s published recurring free allowance includes 25 provisioned write capacity units, 25 provisioned read capacity units, and 25 GB storage in the Standard table class. A small table at 1 WCU and 1 RCU can fit. Use provisioned capacity with a fixed ceiling, no global tables, and no paid backup or point-in-time recovery features unless separately budgeted. Table and index capacity share the allowance; account and payer scope must be verified. On-demand request charges are not erased by the provisioned-capacity allowance. [11]')
p('A capped aggregate workload can therefore cost $0, while throttling postpones writes rather than increasing provisioned capacity. Prefer immutable daily snapshots and replacement of corrected results. Item-size rounding, transactions, indexes, and hot keys affect throughput; a free tier is not a guarantee that 25 writes/second means 25 complete multi-item transactions/second. DreamHost’s multiple small aggregate databases remain the simpler default.')
sub('Option 5 is a conditional bucket metric fallback')
p('S3 request metrics can provide bucket GET counts and bytes without request logs. CloudWatch advertises 10 eligible custom or detailed metrics in its free tier. One S3 filter can emit up to 16 different metrics, and choosing two dashboard widgets does not restrict which metrics are billed. With 10 unused eligible allowances and 7–16 active series, metric storage could be $0–$1.80/month at $0.30 per excess metric-month. Without those allowances, 7–16 series cost $2.10–$4.80. Confirm actual S3 billing treatment and emitted series before using this option. [4,12]')
p('A single filter does not answer which files or collections were downloaded, unique files/day, or human versus bot. Multiple prefix filters could quickly exceed $1/month. Avoid them in the base design. GetMetricData calls are separately charged; a small cron can use GetMetricStatistics within available API allowances. Use the Sum statistic for requests and bytes, not Average. [12,13]')
sub('Budget monitoring is free but not a spending stop')
p('AWS Budgets monitoring and notifications are free. Configure zero-spend and $0.50/$1/$2 alerts during any later implementation; avoid daily emailed Budget Reports, which cost $0.01 per delivery. Billing updates lag usage, so alerts cannot enforce a hard $2 ceiling. Enforce the workload limits described on page 4 and bound paid export storage, transfer, and request counts. [14,15]')
p('Do not ingest S3 request logs into CloudWatch Logs. Keep only brief operational diagnostics with bounded retention. Avoid accidental fixed fees such as customer-managed KMS keys, NAT gateways, public APIs, paid dashboards, and extra monitoring features. Exact $0 depends on the selected services and verified unused allowances, not merely on a new account’s name.')

page('Bot visibility and options excluded by cost')
sub('What the proposed reports can say about people and bots')
p('Native S3 aggregate metrics expose requests, bytes, status counts, and access patterns. They do not expose user agents, bot identities, or proof of human intent. Large numbers of small range responses can indicate automation, but researchers and legitimate download tools also use ranges. This supports an automation-pattern indicator, not a claim that an AI company downloaded the corpus.')
p('Temporary S3 logs can identify declared crawlers, command-line clients, and likely automation patterns. Report named or declared bots, likely automation, browser-like, and unknown as separate classes. A Python client can belong to a human researcher, while a bot can spoof a browser. Avoid a falsely precise binary human/bot percentage. For a sample, publish the sampling method and coverage; broad popularity estimates can be useful while rare files disappear.')
p('On a 1 percent independent request sample, a file with 100 requests/day has about a 36.6 percent chance of being unseen. This example is not the uncertainty model for whole-log-object sampling, which can be much more clustered. Do not multiply sampled unique files by 100 to estimate total unique files. Do not multiply the fraction of bot requests by total bytes to claim bot GB; byte totals need classification for those responses.')
sub('Why higher level paid events do not fit')
table(['Service or design', 'Useful information', 'Cost boundary'], [
 ['CloudTrail five minute aggregates', 'API, resource, identity access trends; no response bytes', '$104 / $1,040 / $10,400 at 80M / 800M / 8B atomic events'],
 ['Athena scanning full temporary logs', 'File totals and automation heuristics', 'Four passes at 1 KB/event: $1.46 / $14.55 / $145.52 scans alone'],
 ['CloudFront with Common Bot Control', 'Popular objects and stronger bot labels for routed traffic', 'Prior modeled plans start around $200/month at incident volumes'],
 ['Kinesis provisioned sample stream', 'Continuous sampled processing', 'One shard is about $10.80/month before other charges'],
 ['DynamoDB on-demand write per request', 'A row or counter update per observed request', '$50 / $500 / $5,000 for one small write per request'],
], [2.15,2.4,2.55])
p('CloudTrail aggregation is a genuine higher-level event mechanism, but its $0.30/million aggregation surcharge is additional to $1/million atomic data-event capture. Athena has no equivalent recurring free scan allowance assumed here. Tiny queries over aggregate exports may cost cents, but DreamHost cron can read those exports directly. CloudFront delivery would add expense to existing free S3 bandwidth; even inexpensive plans cannot make the incident workload a $0 service. [16–20]')
p('The compatible higher-level input is the daily Storage Lens export. Under literal $0, the compatible approach is local aggregation of temporary S3 logs or a deliberately capped sample; there is no established native free S3 event that supplies every downloaded file, human classification, and GB/day together.')

page('Recommended choices and verification')
sub('Choose the reporting input and keep DreamHost publication')
p('Choose Option 2: one bucket-scoped Storage Lens Advanced configuration, ordinary S3 aggregate exports, and DreamHost cron producing static HTML. The user accepted the metrics fee and up to $1/month; the modeled all-in total is about $0.04/month with unused export-transfer allowances, or $0.13 at conservative transfer retail rates, with a $0.20 initial operating allowance. Keep an average below $1 and treat $2 as an exceptional-month ceiling, not the normal allowance. Use Option 1 only if full observed file detail or broader automation heuristics justify temporary log processing.')
p('Use Option 3 only if a free-tier Lambda simplifies aggregate collection or offloads a bounded sample. Keep DreamHost as the database and publisher. Add Option 4 only when a tiny DynamoDB ledger materially simplifies recovery. A new AWS account is an available hosting choice, not a reason to replace a free database or create a public API.')
table(['Public statistic', 'Meaning and limitation'], [
 ['Files accessed per day', 'Unique observed keys or native unique-object accesses; not complete copies'],
 ['Download requests per day', 'GET count, with successful 200 and 206 separated when available'],
 ['GB delivered per day', 'Observed response bytes / 1,000,000,000; define source and coverage'],
 ['Automation class', 'Declared bot, likely automation, browser-like, unknown; no proof of humanity'],
 ['Quality and freshness', 'Final, provisional, sampled, incomplete; last successful input date'],
], [2.15,4.95])
sub('Evidence and remaining measurements')
p('The anonymous public listing on 9 October found 19,266 current objects and 18.84 decimal TB in us-west-2. Hidden versions and extra monitored scope remain unmeasured. Earlier incident records reported 26.26M raw rows on 21 September, repeated HTTP 206 ZIP probes, and one source associated with 3.36M rows and 2.82 TB. Replay also duplicated rows. The 80M/800M/8B monthly cases are planning scenarios, not deduplicated current usage or evidence identifying an AI company.')
p('The checkout inspected for the original report was slg-dev at 7c249f9c62e6c7e529ef9b94b0fba638a687a6ef, with existing unfinished work. No repository files or infrastructure were changed. Private usage was unavailable because AWS logins were expired and the SSH server key differed from the trusted record. This revision uses the user’s explicit S3, DreamHost, paid Storage Lens, and Lambda-account clarifications.')
p('Before implementation, validate one native export and its actual paid bytes and requests, or benchmark a bounded log batch on DreamHost. Confirm account permissions, free-tier eligibility and billing scope, cross-account export reads, actual table/index sizes, and host throughput. Check retry interruption, duplicate source records, late logs, and day replacement through the real processing path. Static pages should display the source date and coverage so a stalled job cannot masquerade as fresh statistics.')
p('A new reporting cron is part of a future implementation, not permission to restart the old failing importer. Keep old history with its replay-quality note. Retention changes, deleting the old database, or switching public reporting require a separately reviewed implementation. Labor and maintenance are outside the monthly service estimates.')

sources = [
 ('S3 pricing and Storage Lens object charge','https://aws.amazon.com/s3/pricing/?loc=4&nc=sn'),
 ('Storage Lens metric glossary and free versus advanced tiers','https://docs.aws.amazon.com/AmazonS3/latest/userguide/storage_lens_metrics_glossary.html'),
 ('Storage Lens performance and expanded prefix exports','https://aws.amazon.com/blogs/aws/amazon-s3-storage-lens-adds-performance-metrics-support-for-billions-of-prefixes-and-export-to-s3-tables/'),
 ('S3 CloudWatch monitoring and free storage metrics','https://docs.aws.amazon.com/AmazonS3/latest/userguide/cloudwatch-monitoring.html'),
 ('S3 access logging and best effort delivery','https://docs.aws.amazon.com/AmazonS3/latest/userguide/ServerLogs.html'),
 ('S3 log fields','https://docs.aws.amazon.com/AmazonS3/latest/userguide/LogFormat.html'),
 ('Lambda pricing and monthly free allowances','https://aws.amazon.com/lambda/pricing/'),
 ('EventBridge Scheduler pricing','https://aws.amazon.com/eventbridge/pricing/'),
 ('Free tier scope under consolidated billing','https://docs.aws.amazon.com/us_en/awsaccountbilling/latest/aboutv2/useconsolidatedbilling-effective.html'),
 ('S3 notification event types','https://docs.aws.amazon.com/AmazonS3/latest/userguide/notification-how-to-event-types-and-destinations.html'),
 ('DynamoDB recurring provisioned capacity allowances','https://aws.amazon.com/dynamodb/pricing/'),
 ('CloudWatch free tier and charged API exceptions','https://aws.amazon.com/cloudwatch/pricing/'),
 ('S3 metrics definitions and dimensions','https://docs.aws.amazon.com/AmazonS3/latest/userguide/metrics-dimensions.html'),
 ('AWS Budgets monitoring and reports pricing','https://aws.amazon.com/aws-cost-management/aws-budgets/pricing/'),
 ('AWS Budgets update lag','https://docs.aws.amazon.com/cost-management/latest/userguide/budgets-managing-costs.html'),
 ('CloudTrail aggregation requires atomic data events','https://docs.aws.amazon.com/awscloudtrail/latest/userguide/aggregating-data-events.html'),
 ('CloudTrail atomic capture and aggregation prices','https://aws.amazon.com/cloudtrail/pricing/'),
 ('Athena scan pricing','https://aws.amazon.com/athena/pricing/'),
 ('CloudFront plan prices and unsupported features','https://docs.aws.amazon.com/AmazonCloudFront/latest/DeveloperGuide/flat-rate-pricing-plan.html'),
 ('Kinesis stream pricing','https://aws.amazon.com/kinesis/data-streams/pricing/'),
]
def link(para,label,url):
    rel=para.part.relate_to(url,RT.HYPERLINK,is_external=True)
    hl=OxmlElement('w:hyperlink'); hl.set(qn('r:id'),rel)
    r=OxmlElement('w:r'); pr=OxmlElement('w:rPr')
    color=OxmlElement('w:color'); color.set(qn('w:val'),'174B77'); pr.append(color)
    r.append(pr); t=OxmlElement('w:t'); t.text=label; r.append(t); hl.append(r); para._p.append(hl)
page('Sources and calculation notes')
p('Prices checked against official AWS documentation on 9 October 2026. S3 Oregon retail rates were also verified in the official offer feed dated 28 September. Estimates exclude labor, taxes, support subscriptions, and services already free under the user’s arrangements. Free-tier estimates require unused recurring allowances, not promotional credits.')
for i,(name,url) in enumerate(sources,1):
    para=p(f'[{i}] '); para.paragraph_format.space_after=Pt(5); link(para,name,url)
sub('Reproducible cost arithmetic')
p('Native metrics: 19,266 ÷ 1,000,000 × $0.20 = $0.0038532/month. Example paid exports: 1 GiB × $0.023 + 1,000 PUTs × $0.005/1,000 + 100 GETs × $0.0004/1,000 + 1,000 LISTs × $0.005/1,000. Total including Lens is about $0.037 before export transfer. Allow up to about $0.09 more for 1 GiB transferred to DreamHost if the recurring 100 GB internet-transfer allowance is unavailable. Corpus delivery remains free.')
p('Full-log Lambda: L = N/1,000 invocations; compute = 2L GB-seconds. Cost with unused allowances = max(0, 2L − 400,000) × $0.0000166667 + max(0, L − 1,000,000) × $0.20/1,000,000. This yields $0/$20/$261.40 for 80M/800M/8B requests.')
doc.core_properties.title='DigitalCorpora statistics options within a one dollar budget'
doc.core_properties.subject='Zero typical monthly cost and options below one dollar'
doc.core_properties.author='Codex'
path=OUT/'DigitalCorpora statistics system options 2026-10-09.docx'
for root in [doc._element,doc.styles._element]:
    for border in root.xpath('.//w:pBdr'): border.getparent().remove(border)
doc.save(path)
print(path)
