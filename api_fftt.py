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
import re
import os
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

r = session.get(f'{BASE_URL}/xml_equipe.php',
                params={**auth_params, 'numclu': '07590074', 'type': 'm'})
raw_equipes = xmltodict.parse(r.text)['liste']['equipe']
equipes = raw_equipes if isinstance(raw_equipes, list) else [raw_equipes]

LIEN_RE = re.compile(
    r'renc_id=(\d+)&is_retour=(\d+)&phase=(\d+)&res_1=(\d+)&res_2=(\d+)'
    r'&equip_1=([\w\-\+\%]+)&equip_2=([\w\-\+\%]+)'
    r'&equip_id1=(\d+)&equip_id2=(\d+)&clubnum_1=(\d+)&clubnum_2=(\d+)'
)


def strip_club_code(name):
    return re.sub(r'\s*\(.*?\)', '', name or '').strip()


def compute_stats(matches):
    w, d, l, played = 0, 0, 0, 0
    for m in matches:
        if m['score_home'] is None:
            continue
        played += 1
        if m['score_home'] > m['score_away']:
            w += 1
        elif m['score_home'] < m['score_away']:
            l += 1
        else:
            d += 1
    return {'w': w, 'd': d, 'l': l, 'played': played, 'total': len(matches)}


CLUB_NUM = '07590074'

def fetch_match_details(lien, fach_is_equa):
    """Returns {players: [{name, wins}], games: [{home, away, home_won}]} or None."""
    z = LIEN_RE.match(lien)
    if not z:
        return None
    renc_id, is_retour, phase, res_1, res_2, equip_1, equip_2, equip_id1, equip_id2, clubnum_1, clubnum_2 = z.groups()
    params = {
        **auth_params,
        'renc_id': renc_id, 'is_retour': is_retour, 'phase': phase,
        'res_1': res_1, 'res_2': res_2, 'equip_1': equip_1, 'equip_2': equip_2,
        'equip_id1': equip_id1, 'equip_id2': equip_id2,
        'clubnum_1': clubnum_1, 'clubnum_2': clubnum_2,
    }
    try:
        r = session.get(f'{BASE_URL}/xml_chp_renc.php', params=params, timeout=10)
        data = xmltodict.parse(r.text)['liste']
    except Exception:
        return None

    raw_parties = data.get('partie')
    if raw_parties is None:
        return None
    parties = raw_parties if isinstance(raw_parties, list) else [raw_parties]

    # xml_chp_renc.php has its own equa/equb ordering (may differ from xml_result_equ.php).
    # Check the resultat block directly to determine which side is F3T.
    resultat = data.get('resultat') or {}
    fach_is_equa_in_renc = 'FACH' in (resultat.get('equa') or '')

    wins = {}
    games = []
    for partie in parties:
        ja = partie.get('ja', '') or ''
        jb = partie.get('jb', '') or ''
        sa = partie.get('scorea', '0') == '1'
        sb = partie.get('scoreb', '0') == '1'

        if fach_is_equa_in_renc:
            home_player, away_player, home_won = ja, jb, sa
        else:
            home_player, away_player, home_won = jb, ja, sb

        if home_player:
            wins[home_player] = wins.get(home_player, 0) + (1 if home_won else 0)

        games.append({
            'home': home_player,
            'away': away_player,
            'home_won': home_won,
        })

    players = sorted(
        [{'name': name, 'wins': w} for name, w in wins.items()],
        key=lambda x: -x['wins']
    )
    return {'players': players, 'games': games}


def fetch_pool_ranking(poule, division_id, organisme):
    """Computes standings from all matches in the pool. Returns [{rank, team, played, won, draw, lost, points, is_home_club}]."""
    params = {**auth_params, 'cx_poule': poule, 'D1': division_id, 'organisme_pere': organisme}
    try:
        r = session.get(f'{BASE_URL}/xml_result_equ.php', params=params, timeout=10)
        raw_tours = xmltodict.parse(r.text)['liste'].get('tour')
    except Exception:
        return []

    if not raw_tours:
        return []
    tours = raw_tours if isinstance(raw_tours, list) else [raw_tours]

    standings = {}
    for tour in tours:
        equa = strip_club_code(tour.get('equa') or '')
        equb = strip_club_code(tour.get('equb') or '')
        raw_sa, raw_sb = tour.get('scorea'), tour.get('scoreb')
        if not equa or not equb or not raw_sa or not raw_sb:
            continue
        sa, sb = int(raw_sa), int(raw_sb)

        for team in (equa, equb):
            if team not in standings:
                standings[team] = {'team': team, 'played': 0, 'won': 0, 'draw': 0, 'lost': 0, 'pts_for': 0, 'pts_against': 0}

        if sa > sb:
            standings[equa]['won'] += 1
            standings[equb]['lost'] += 1
        elif sa < sb:
            standings[equb]['won'] += 1
            standings[equa]['lost'] += 1
        else:
            standings[equa]['draw'] += 1
            standings[equb]['draw'] += 1

        standings[equa]['played'] += 1
        standings[equb]['played'] += 1
        standings[equa]['pts_for'] += sa
        standings[equa]['pts_against'] += sb
        standings[equb]['pts_for'] += sb
        standings[equb]['pts_against'] += sa

    sorted_teams = sorted(
        standings.values(),
        key=lambda t: (-(2 * t['won'] + t['draw']), -(t['pts_for'] - t['pts_against']))
    )

    ranking = []
    for i, t in enumerate(sorted_teams, 1):
        ranking.append({
            'rank': i,
            'team': t['team'],
            'played': t['played'],
            'won': t['won'],
            'draw': t['draw'],
            'lost': t['lost'],
            'points': 2 * t['won'] + t['draw'],
            'diff': t['pts_for'] - t['pts_against'],
            'is_home_club': 'FACH' in t['team'],
        })
    return ranking


result = []

for eq in equipes:
    z = re.match(r'cx_poule=(\d+)&D1=(\d+)&organisme_pere=(\d+)', eq['liendivision'])
    if not z:
        continue
    poule, division_id, organisme = z.groups()

    raw_division = eq.get('libdivision', '') or ''
    is_phase2_entry = 'phase 2' in raw_division.lower()

    team = {
        'name': strip_club_code(eq.get('libequipe', '')),
        'division': raw_division,
        'phase1': [],
        'phase2': [],
        '_pool_params': (poule, division_id, organisme),
        '_is_phase2': is_phase2_entry,
    }

    r2 = session.get(f'{BASE_URL}/xml_result_equ.php',
                     params={**auth_params, 'cx_poule': poule,
                             'D1': division_id, 'organisme_pere': organisme})
    raw_tours = xmltodict.parse(r2.text)['liste'].get('tour')
    if raw_tours is None:
        result.append(team)
        continue
    tours = raw_tours if isinstance(raw_tours, list) else [raw_tours]

    for tour in tours:
        equa = tour.get('equa') or ''
        equb = tour.get('equb') or ''
        if 'FACH' not in equa and 'FACH' not in equb:
            continue

        fach_is_equa = 'FACH' in equa
        lien = tour.get('lien', '')

        phase_match = re.search(r'is_retour=(\d+)&phase=(\d+)', lien)
        is_return_leg = phase_match.group(1) == '1' if phase_match else False
        phase = phase_match.group(2) if phase_match else '1'

        raw_sa = tour.get('scorea')
        raw_sb = tour.get('scoreb')
        if raw_sa and raw_sb:
            sa, sb = int(raw_sa), int(raw_sb)
            score_home = sa if fach_is_equa else sb
            score_away = sb if fach_is_equa else sa
        else:
            score_home = score_away = None

        opponent = strip_club_code(equb if fach_is_equa else equa)
        date_str = tour.get('dateprevue') or tour.get('date') or None

        date_iso = None
        if date_str:
            try:
                date_iso = datetime.strptime(date_str, '%d/%m/%Y').strftime('%Y-%m-%d')
            except ValueError:
                pass

        details = fetch_match_details(lien, fach_is_equa) if score_home is not None else None

        match_record = {
            'opponent': opponent,
            'score_home': score_home,
            'score_away': score_away,
            'date': date_str,
            'date_iso': date_iso,
            'is_return_leg': is_return_leg,
            'players': details['players'] if details else None,
            'games': details['games'] if details else None,
        }

        if phase == '1':
            team['phase1'].append(match_record)
        else:
            team['phase2'].append(match_record)

    result.append(team)


# Merge Phase 1 and Phase 2 entries for the same team
def base_team_name(name):
    return re.sub(r'\s*-\s*Phase\s+\d+\s*$', '', name, flags=re.IGNORECASE).strip()

def base_division(division):
    return re.sub(r'\s+(?:phase)\s+\d+.*$', '', division, flags=re.IGNORECASE).strip()

def team_category(division):
    keywords = ['jeune', 'junior', 'cadet', 'benjamin', 'poussin', ' pb ']
    return 'junior' if any(kw in division.lower() for kw in keywords) else 'senior'

def division_short(division):
    m = re.search(r'[Rr][eé]gionale\s+(\d+)', division)
    if m:
        return f'R{m.group(1)}'
    m = re.search(r'[Dd][eé]partementale\s+(\d+)', division, re.IGNORECASE)
    if m:
        return f'D{m.group(1)}'
    m = re.search(r'\s-\s+D(\d+)\s', division)
    if m:
        return f'D{m.group(1)}'
    m = re.search(r'PB\s+\w+\d+', division)
    if m:
        return m.group(0)
    return ''


merged = {}
for team in result:
    key = base_team_name(team['name'])
    if key not in merged:
        div = base_division(team['division'])
        merged[key] = {
            'name': key,
            'division': div,
            'division_short': division_short(div),
            'category': team_category(div),
            'phase1': [],
            'phase2': [],
        }
    merged[key]['phase1'].extend(team['phase1'])
    merged[key]['phase2'].extend(team['phase2'])
    if team['_is_phase2']:
        merged[key]['_phase2_pool_params'] = team['_pool_params']


def team_sort_key(team):
    base = re.sub(r'\s*-\s*REC.*$', '', team['name'], flags=re.IGNORECASE)
    m = re.search(r'(\d+)\s*$', base)
    return int(m.group(1)) if m else float('inf')


final_result = []
for team in merged.values():
    team['phase1_stats'] = compute_stats(team['phase1'])
    team['phase2_stats'] = compute_stats(team['phase2'])
    params = team.pop('_phase2_pool_params', None)
    team['phase2_ranking'] = fetch_pool_ranking(*params) if params else []
    final_result.append(team)

final_result.sort(key=team_sort_key)

# Build agenda: collect all matches across all teams with dates
today_iso = datetime.now().strftime('%Y-%m-%d')
all_matches = []
for team in final_result:
    for phase in ('phase1', 'phase2'):
        for m in team.get(phase) or []:
            if not m.get('date_iso') or not m.get('opponent'):
                continue
            all_matches.append({
                'type': 'match',
                'team': team['name'],
                'division_short': team.get('division_short', ''),
                'category': team.get('category', ''),
                'opponent': m['opponent'],
                'date': m['date'],
                'date_iso': m['date_iso'],
                'score_home': m['score_home'],
                'score_away': m['score_away'],
                'is_return_leg': m['is_return_leg'],
            })

def agenda_sort_key(m):
    n = re.search(r'(\d+)', m['team'])
    team_num = int(n.group(1)) if n else 999
    return team_num

upcoming = sorted(
    [m for m in all_matches if m['score_home'] is None and m['date_iso'] >= today_iso],
    key=lambda x: (x['date_iso'], agenda_sort_key(x))
)[:8]

# Most recent played match per team, sorted by team number
played = [m for m in all_matches if m['score_home'] is not None]
latest_per_team = {}
for m in played:
    t = m['team']
    if t not in latest_per_team or m['date_iso'] > latest_per_team[t]['date_iso']:
        latest_per_team[t] = m
recent = sorted(latest_per_team.values(), key=agenda_sort_key)

output = {
    'teams': final_result,
    'agenda': {'upcoming': upcoming, 'recent': recent},
}

json.dump(output, sys.stdout, ensure_ascii=False, indent=2)
