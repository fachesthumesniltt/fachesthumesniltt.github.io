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
import re
import sys
from datetime import datetime

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
    categ   = (detail.get('categ') or '').strip()

    evolution = None
    if point is not None and valinit is not None:
        evolution = round(point - valinit)

    # Fetch individual match history — try MySQL classement DB first, fall back to SPID
    r3 = session.get(f'{BASE_URL}/xml_partie_mysql.php', params={**auth_params, 'licence': licence})
    raw_list = (xmltodict.parse(r3.text).get('liste') or {}).get('partie') or []
    if isinstance(raw_list, dict):
        raw_list = [raw_list]

    use_spid = not raw_list
    if use_spid:
        r3b = session.get(f'{BASE_URL}/xml_partie.php', params={**auth_params, 'numlic': licence})
        raw_list = (xmltodict.parse(r3b.text).get('liste') or {}).get('partie') or []
        if isinstance(raw_list, dict):
            raw_list = [raw_list]

    matches = []
    for g in raw_list:
        date_str = g.get('date', '')
        date_iso = None
        if date_str:
            try:
                date_iso = datetime.strptime(date_str, '%d/%m/%Y').strftime('%Y-%m-%d')
            except ValueError:
                pass
        if use_spid:
            matches.append({
                'date':             date_str,
                'date_iso':         date_iso,
                'opponent':         g.get('nom', ''),
                'opponent_ranking': g.get('classement'),
                'won':              g.get('victoire') == 'V',
                'points':           None,
            })
        else:
            matches.append({
                'date':             date_str,
                'date_iso':         date_iso,
                'opponent':         g.get('advnompre', ''),
                'opponent_ranking': g.get('advclaof'),
                'won':              g.get('vd') == 'V',
                'points':           g.get('pointres'),
            })

    players.append({
        'licence':   licence,
        'nom':       detail.get('nom', ''),
        'prenom':    detail.get('prenom', ''),
        'clast':     detail.get('clast', ''),
        'point':     round(point) if point is not None else None,
        'valinit':   round(valinit) if valinit is not None else None,
        'evolution': evolution,
        'categ':     categ,
        'category':  'senior' if (categ.startswith('S') or categ.startswith('V')) else 'junior',
        'matches':   matches,
        'match_history': [],
    })

# Sort by category group then by points descending
def sort_key(p):
    group = 0 if p['category'] == 'senior' else 1
    pts = -(p['point'] or 0)
    return (group, pts)

players.sort(key=sort_key)

# Build match history from fftt.json (generated before this script)
fftt_path = os.path.join(os.path.dirname(__file__), 'data', 'fftt.json')
if os.path.exists(fftt_path):
    fftt_data = json.load(open(fftt_path))
    # Index players by "NOM Prenom" key for fast lookup
    player_index = {f"{p['nom']} {p['prenom']}": p for p in players}

    for team in fftt_data.get('teams', []):
        for phase in ('phase1', 'phase2'):
            for match in team.get(phase) or []:
                if not match.get('games'):
                    continue
                for game in match['games']:
                    home = game.get('home', '')
                    # Skip doubles (contain " et ")
                    if not home or ' et ' in home:
                        continue
                    player = player_index.get(home)
                    if not player:
                        continue
                    home_won = game.get('home_won', False)

                    # Find or create a history entry for this match
                    match_key = (team['name'], match.get('date_iso', ''), match.get('opponent', ''))
                    history = player['match_history']
                    entry = next((e for e in history if (e['team'], e['date_iso'], e['opponent']) == match_key), None)
                    if entry is None:
                        entry = {
                            'team': team['name'],
                            'division_short': team.get('division_short', ''),
                            'opponent': match.get('opponent', ''),
                            'date': match.get('date', ''),
                            'date_iso': match.get('date_iso', ''),
                            'score_home': match.get('score_home'),
                            'score_away': match.get('score_away'),
                            'phase': phase,
                            'player_wins': 0,
                            'player_played': 0,
                        }
                        history.append(entry)
                    entry['player_played'] += 1
                    if home_won:
                        entry['player_wins'] += 1

    # Sort each player's history by date descending
    for p in players:
        p['match_history'].sort(key=lambda m: m.get('date_iso', ''), reverse=True)

# Generate one content file per player
content_dir = os.path.join(os.path.dirname(__file__), 'content', 'pages', 'joueurs')
os.makedirs(content_dir, exist_ok=True)

for p in players:
    slug = p['licence']
    path = os.path.join(content_dir, f'{slug}.md')
    # Only write if missing to avoid unnecessary rebuilds; overwrite to keep data fresh
    with open(path, 'w', encoding='utf-8') as f:
        f.write(f'---\ntitle: "{p["prenom"]} {p["nom"]}"\nlayout: "joueur"\nlicence: "{p["licence"]}"\n---\n')

json.dump(players, sys.stdout, ensure_ascii=False, indent=2)
