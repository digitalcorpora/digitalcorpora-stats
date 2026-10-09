#!/usr/bin/env bash
# Count successful object requests across retained S3 access-log files.
# The report needs request counts rather than coarsened database row counts.
# Extract AWS request identifiers, byte counts, dates, and collection scopes.
# Sort by identifier to remove duplicated log delivery and ingestion replays.
# Stream input and use bounded sort memory; temporary records remain private.
# Read the source without changing it and remove temporary data on exit.
# Group by event year, since ingestion-year filenames can contain delayed events.
set -euo pipefail
umask 077
mode=report
if [[ ${1:-} == --extract ]]; then mode=extract; shift; fi
if [[ ${1:-} == --merge ]]; then mode=merge; shift; fi
if [[ $# == 0 ]]; then echo "usage: $0 [--extract|--merge] INPUT..." >&2; exit 2; fi
work=$(mktemp -d)
trap 'rm -rf "$work"' EXIT
sort_args=(-S 64M -T "$work" -s -u -k1,1)
if sort --version >/dev/null 2>&1; then sort_args+=(--parallel=1); fi
extract() {
LC_ALL=C awk -F '"' '
  { split($1,p," "); split($3,r," ") }
  p[8] ~ /^(REST[.]GET[.]OBJECT|REST[.]COPY[.]PART_GET|WEBSITE[.]GET[.]OBJECT)$/ && r[1] ~ /^(200|206)$/ {
    if (p[9] == "stats/digitalcorpora_configuration1.csv") next
    split(p[3],d,"/")
    year=substr(d[3],1,4)
    if (p[7] !~ /^[[:alnum:]]+$/ || year !~ /^[0-9][0-9][0-9][0-9]$/ || (r[3] != "-" && r[3] !~ /^[0-9]+$/)) { bad++; next }
    if (r[3] == "-") r[3] = 0
    scope = p[9] ~ /^corpora\// ? "corpora" : (p[9] ~ /^downloads\// ? "tools" : "other")
    m57 = p[9] ~ /^corpora\/scenarios\/2009-m57-patents\// ? 1 : 0
    print p[7],year,r[3],scope,m57
    raw++
  }
  END { print "accepted_lines\t" raw+0 "\nmalformed_successful_lines\t" bad+0 > "/dev/stderr" }
' "$@"
}
if [[ $mode == merge ]]; then
  LC_ALL=C sort -m "${sort_args[@]}" "$@" > "$work/records"
else
  extract "$@" | LC_ALL=C sort "${sort_args[@]}" > "$work/records"
fi
if [[ $mode == extract ]]; then cat "$work/records"; exit; fi
awk '
  { years[$2]=1; n[$2,"all"]++; b[$2,"all"]+=$3; n[$2,$4]++; b[$2,$4]+=$3; if ($5==1) {n[$2,"m57"]++; b[$2,"m57"]+=$3} }
  END {
    split("all corpora tools other m57",scopes," ")
    for (year in years) for (i=1;i<=5;i++) printf "%s\t%s\t%d\t%.0f\n",year,scopes[i],n[year,scopes[i]],b[year,scopes[i]]
  }
' "$work/records" | LC_ALL=C sort -k1,1n -k2,2 > "$work/annual"
printf 'year\tscope\trequests\tbytes\n'
cat "$work/annual"
