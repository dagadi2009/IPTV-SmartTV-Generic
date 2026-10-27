#!/usr/bin/env python3
"""Merge valid XMLTV sources, retaining previous guide when feeds fail."""
import datetime as dt
import os
import pathlib
import urllib.request
import xml.etree.ElementTree as ET

OUT = pathlib.Path('epg/guide.xml')
NOW = dt.datetime.now(dt.timezone.utc)
SOURCES = [
 ('España', 'https://raw.githubusercontent.com/raulfdeztdo/epg/main/guide.xml'),
 ('Reino Unido', 'https://iptv-epg.org/files/epg-gb.xml'),
 ('Canadá', 'https://iptv-epg.org/files/epg-ca.xml'),
]

def parse_time(raw):
    try:
        date = dt.datetime.strptime(raw[:14], '%Y%m%d%H%M%S')
        offset = raw[15:20]
        if len(offset) == 5 and offset[0] in '+-':
            sign = 1 if offset[0] == '+' else -1
            mins = sign * (int(offset[1:3])*60 + int(offset[3:5]))
            date = date.replace(tzinfo=dt.timezone(dt.timedelta(minutes=mins)))
        else:
            date = date.replace(tzinfo=dt.timezone.utc)
        return date.astimezone(dt.timezone.utc)
    except (ValueError, TypeError):
        return None

root = ET.Element('tv', {'generator-info-name':'OmniStream multi-EPG 1.1.6'})
channels = {}
programs = {}
source_count = 0
for country, url in SOURCES:
    try:
        req = urllib.request.Request(url, headers={'User-Agent':'Mozilla/5.0 OmniStream/1.1.6'})
        with urllib.request.urlopen(req, timeout=100) as response:
            body = response.read(65_000_000 + 1)
        if len(body) > 65_000_000:
            raise ValueError('archivo demasiado grande')
        doc = ET.fromstring(body)
        if doc.tag != 'tv':
            raise ValueError('no es XMLTV')
        found = 0
        for ch in doc.findall('channel'):
            cid = ch.get('id')
            if cid and cid not in channels:
                channels[cid] = ch
        for prog in doc.findall('programme'):
            cid = prog.get('channel')
            stop = parse_time(prog.get('stop', ''))
            start = parse_time(prog.get('start', ''))
            if not cid or not start or not stop or stop <= NOW or start > NOW + dt.timedelta(days=3):
                continue
            if not prog.find('title') is None:
                key = (cid, prog.get('start'), prog.get('stop'))
                if key not in programs:
                    programs[key] = prog
                    found += 1
        if found < 10:
            raise ValueError('sin programas vigentes')
        source_count += 1
        print(f'{country}: {found} programas vigentes')
    except Exception as exc:
        print(f'AVISO: {country}: {exc}')

# If no source works, do not overwrite the existing guide.
if not source_count or len(programs) < 10:
    raise SystemExit('No hay fuentes válidas; se conserva el EPG anterior')
used = {key[0] for key in programs}
for cid, ch in channels.items():
    if cid in used:
        root.append(ch)
for key, prog in sorted(programs.items(), key=lambda x:(x[0][0], x[0][1])):
    root.append(prog)
OUT.parent.mkdir(parents=True, exist_ok=True)
tmp = OUT.with_suffix('.xml.tmp')
ET.ElementTree(root).write(tmp, encoding='utf-8', xml_declaration=True)
ET.parse(tmp)
tmp.replace(OUT)
print(f'EPG publicado: {len(used)} canales, {len(programs)} programas, {source_count} fuentes')

