#!/usr/bin/env python3
# Reconcile solution-request evidence without counting mail copies as people.
# Read responder mbox archives, both historical tally formats, and Gmail exports.
# Decode MIME and HTML, extracting the first request form in quoted messages.
# Preserve each record and its provenance for private human adjudication.
# Normalize email spelling; merge different addresses only through an alias map.
# Exclusions and confirmed requests are supplied explicitly, never inferred from domains.
# Write private evidence and aggregate counts; publish no mailbox contents automatically.
from __future__ import annotations

import argparse
import csv
import email.policy
import email.utils
import json
import mailbox
import os
import re
from collections import Counter
from datetime import date as Date
from html.parser import HTMLParser
from pathlib import Path

from pydantic import BaseModel, ConfigDict, Field

NAME, EMAIL, INSTITUTION, TITLE = 'name', 'email', 'institution', 'title'
UNDERGRADUATES, GRADUATES, DOMESTIC = 'undergraduates', 'graduates', 'domestic'
BODY, SOURCE, SOURCE_ID, DATE = 'body', 'source', 'source_id', 'date'
FORM_KEYS = (NAME, EMAIL, INSTITUTION, TITLE, UNDERGRADUATES, GRADUATES, DOMESTIC)
HEADER_FROM, HEADER_TO, HEADER_DATE, HEADER_SUBJECT = 'from', 'to', 'date', 'subject'
ADDRESS = re.compile(r"[\w.!#$%&'*+/=?^`{|}~-]+@[\w.-]+\.[a-zA-Z]{2,}")
FIELDS = re.compile(r'^[>\s\ufeff]*(name|email|e-mail|email address|institution|title|undergraduates|gradautes|graduates|domestic)\s*:\s*(.*)$', re.I | re.M)
DATE_LINE = re.compile(r'^20\d\d-\d\d-\d\d$')


class Headers(BaseModel):
    model_config = ConfigDict(populate_by_name=True, extra='ignore')
    sender: str = Field(default='', alias=HEADER_FROM)
    recipient: str = Field(default='', alias=HEADER_TO)
    date: str = ''
    subject: str = ''


class GmailMessage(BaseModel):
    model_config = ConfigDict(extra='ignore')
    id: str
    headers: Headers
    plain: str = ''
    html: str = ''


class Evidence(BaseModel):
    source: str
    source_id: str
    date: Date | None = None
    email: str
    name: str = ''
    institution: str = ''
    title: str = ''
    undergraduates: str = ''
    graduates: str = ''
    domestic: str = ''
    body: str = ''
    form: bool = False


class Decisions(BaseModel):
    aliases: dict[str, str] = Field(default_factory=dict)
    excluded: dict[str, str] = Field(default_factory=dict)
    confirmed_manual: list[str] = Field(default_factory=list)


class YearCounts(BaseModel):
    year: int
    active_requesters: int
    first_observed_requesters: int


class Summary(BaseModel):
    records: int
    candidate_identities: int
    excluded_identities: int
    confirmed_requesters: int
    unresolved_identities: int
    annual: list[YearCounts]
    by_source: dict[str, int]


class HTMLText(HTMLParser):
    def __init__(self):
        super().__init__()
        self.parts: list[str] = []
        self.hidden = 0

    def handle_starttag(self, tag, attrs):
        if tag in ('script', 'style'): self.hidden += 1
        if tag in ('br', 'p', 'div', 'tr', 'li'): self.parts.append('\n')

    def handle_endtag(self, tag):
        if tag in ('script', 'style'): self.hidden = max(0, self.hidden - 1)
        if tag in ('p', 'div', 'tr', 'li'): self.parts.append('\n')

    def handle_data(self, data):
        if not self.hidden: self.parts.append(data)


def html_text(text: str) -> str:
    parser = HTMLText()
    parser.feed(text)
    return ''.join(parser.parts)


def normalize_email(value: str) -> str:
    found = ADDRESS.search(value)
    if not found: return ''
    address = found.group().lower().rstrip('.')
    local, domain = address.rsplit('@', 1)
    if domain in ('gmail.com', 'googlemail.com'):
        local = local.split('+', 1)[0].replace('.', '')
        domain = 'gmail.com'
    return f'{local}@{domain}'


def message_date(value: str) -> Date | None:
    try: return email.utils.parsedate_to_datetime(value).date()
    except (ValueError, TypeError, OverflowError): return None


def form_fields(text: str) -> dict[str, str]:
    values: dict[str, str] = {}
    for match in FIELDS.finditer(text):
        key, value = match.groups()
        key = key.lower()
        if key in ('e-mail', 'email address'): key = EMAIL
        if key == 'gradautes': key = GRADUATES
        if key == NAME and values.get(EMAIL): break
        if key not in values: values[key] = value.strip()
    return values


def evidence_from_text(text: str, headers: Headers, source: str, source_id: str) -> Evidence | None:
    values = form_fields(text)
    address = normalize_email(values.get(EMAIL, ''))
    is_form = bool(address and values.get(NAME))
    if not is_form:
        if source == 'archive': return None
        addresses = email.utils.getaddresses([headers.sender, headers.recipient])
        addresses = [(name, normalize_email(address)) for name, address in addresses]
        addresses = [(name, address) for name, address in addresses if address and not is_owner(address)]
        if len(addresses) != 1: return None
        values[NAME], address = addresses[0]
    return Evidence(source=source, source_id=source_id, date=message_date(headers.date), email=address,
                    body=text, form=is_form, **{key: values.get(key, '') for key in FORM_KEYS if key != EMAIL})


def is_owner(address: str) -> bool:
    return address.split('@')[0] in ('simsong', 'slgarfin', 'slgmail', 'corpora-admin', 'admin', 'm57_mail') or address.startswith('mailer-daemon@')


def read_mbox(path: Path) -> list[Evidence]:
    records = []
    box = mailbox.mbox(path, create=False)
    try:
        for index, original in enumerate(box):
            message = email.message_from_bytes(original.as_bytes(), policy=email.policy.default)
            part = message.get_body(preferencelist=('plain', 'html'))
            if not part: continue
            text = part.get_content()
            if part.get_content_type() == 'text/html': text = html_text(text)
            headers = Headers(sender=str(message.get('From', '')), recipient=str(message.get('To', '')),
                              date=str(message.get('Date', '')), subject=str(message.get('Subject', '')))
            record = evidence_from_text(text, headers, 'archive', f'{path.name}:{index + 1}')
            if record: records.append(record)
    finally: box.close()
    return records


def read_tally(path: Path) -> list[Evidence]:
    lines = path.read_text(encoding='utf-8', errors='replace').splitlines()[1:]
    rows = []
    if lines and '\t' in lines[0]: rows = list(csv.reader(lines, delimiter='\t'))
    else:
        current: list[str] = []
        for line in lines:
            if DATE_LINE.fullmatch(line):
                if current: rows.append(current)
                current = [line]
            elif current: current.append(html_text(line))
        if current: rows.append(current)
    records = []
    for index, row in enumerate(rows):
        if len(row) < 3: continue
        address = normalize_email(row[2])
        if not address: continue
        try: when = Date.fromisoformat(row[0])
        except ValueError: continue
        row += [''] * max(0, 6 - len(row))
        records.append(Evidence(source=path.name, source_id=f'{path.name}:{index + 1}', date=when,
                                name=row[1].strip(), email=address, domestic=row[3],
                                undergraduates=row[4], graduates=row[5], form=True))
    return records


def read_gmail(path: Path) -> list[Evidence]:
    records = []
    for raw in json.loads(path.read_text()):
        message = GmailMessage.model_validate(raw)
        text = message.plain or html_text(message.html)
        record = evidence_from_text(text, message.headers, path.stem, message.id)
        if record: records.append(record)
    return records


def summarize(records: list[Evidence], decisions: Decisions) -> Summary:
    identities: dict[str, list[Evidence]] = {}
    for record in records:
        address = decisions.aliases.get(record.email, record.email)
        identities.setdefault(address, []).append(record)
    confirmed = {address: items for address, items in identities.items()
                 if address not in decisions.excluded and (any(item.form for item in items) or address in decisions.confirmed_manual)}
    active, first = Counter(), Counter()
    for items in confirmed.values():
        years = {item.date.year for item in items if item.date}
        active.update(years)
        if years: first[min(years)] += 1
    excluded = len(set(identities) & set(decisions.excluded))
    return Summary(records=len(records), candidate_identities=len(identities), excluded_identities=excluded,
                   confirmed_requesters=len(confirmed), unresolved_identities=len(identities)-len(confirmed)-excluded,
                   annual=[YearCounts(year=year, active_requesters=active[year], first_observed_requesters=first[year]) for year in sorted(active)],
                   by_source=dict(Counter(record.source for record in records)))


def main():
    os.umask(0o077)
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--input', type=Path, required=True)
    parser.add_argument('--decisions', type=Path)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    records = read_mbox(args.input / 'archive.mbox')
    for name in ('tally-all.csv', 'tally.csv', 't2.csv'): records += read_tally(args.input / name)
    for path in sorted(args.input.glob('gmail-*.json')):
        if path.name != 'gmail-manual-search.json': records += read_gmail(path)
    decisions = Decisions.model_validate_json(args.decisions.read_text()) if args.decisions else Decisions()
    args.output.mkdir(parents=True, exist_ok=True)
    args.output.chmod(0o700)
    (args.output / 'records.json').write_text(json.dumps([record.model_dump(mode='json') for record in records], indent=2))
    (args.output / 'records.json').chmod(0o600)
    summary = summarize(records, decisions)
    (args.output / 'summary.json').write_text(summary.model_dump_json(indent=2))
    (args.output / 'summary.json').chmod(0o600)
    print(summary.model_dump_json(indent=2))


if __name__ == '__main__': main()
