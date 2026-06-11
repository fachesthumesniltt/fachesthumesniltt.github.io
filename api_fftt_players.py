#!/usr/bin/env -S uv run
# /// script
# requires-python = ">=3.8"
# dependencies = ["requests", "xmltodict"]
# ///

import hashlib
import hmac
import time
import requests
import xmltodict
import json
import os
import sys

password = os.environ['FFTT_PASSWD']
key = hashlib.md5(password.encode())

fftt_id = "SW790"
serie = "DHVZWO23BF3DPHT"
tm = time.strftime("%Y%m%d%H%M%S000", time.localtime())
tmc = hmac.new(key.hexdigest().encode(), tm.encode(), hashlib.sha1).hexdigest()
auth_params = {'tm': tm, 'tmc': tmc, 'serie': serie, 'id': fftt_id}

BASE_URL = 'http://www.fftt.com/mobile/pxml'

session = requests.Session()
proxy = os.environ.get('http_proxy') or os.environ.get('HTTP_PROXY')
if proxy:
    session.proxies.update({'http': proxy, 'https': proxy})

session.get(f'{BASE_URL}/xml_initialisation.php', params=auth_params)

# Fetch all club players
r = session.get(f'{BASE_URL}/xml_liste_joueur.php', params={**auth_params, 'club': '07590074'})
raw = xmltodict.parse(r.text)['liste']['joueur']
club_players = raw if isinstance(raw, list) else [raw]

players = []
for p in club_players:
    licence = p.get('licence', '')
    if not licence:
        continue

    r2 = session.get(f'{BASE_URL}/xml_joueur.php', params={**auth_params, 'licence': licence})
    parsed = xmltodict.parse(r2.text).get('liste') or {}
    detail = parsed.get('joueur')
    if not detail:
        continue
    if isinstance(detail, list):
        detail = detail[0]

    def to_float(v):
        try:
            return float(v)
        except (TypeError, ValueError):
            return None

    point   = to_float(detail.get('point'))
    valinit = to_float(detail.get('valinit'))
    valcla  = to_float(detail.get('valcla'))
    categ   = (detail.get('categ') or '').strip()

    evolution = None
    if point is not None and valinit is not None:
        evolution = round(point - valinit)

    players.append({
        'nom':       detail.get('nom', ''),
        'prenom':    detail.get('prenom', ''),
        'clast':     detail.get('clast', ''),
        'point':     round(point) if point is not None else None,
        'valinit':   round(valinit) if valinit is not None else None,
        'evolution': evolution,
        'categ':     categ,
        'category':  'senior' if (categ.startswith('S') or categ.startswith('V')) else 'junior',
    })

# Sort by category group then by points descending
def sort_key(p):
    group = 0 if p['category'] == 'senior' else 1
    pts = -(p['point'] or 0)
    return (group, pts)

players.sort(key=sort_key)

json.dump(players, sys.stdout, ensure_ascii=False, indent=2)
