#!/usr/bin/python

import hashlib
import hmac
import time
import requests
import xmltodict
import json
import re
import os

password = os.environ['FFTT_PASSWD']
key = hashlib.md5(password.encode())

fftt_id = "SW790"
serie = "DHVZWO23BF3DPHT"
tm = time.strftime("%Y%m%d%H%M%S000", time.localtime())
tmc = hmac.new(key.hexdigest().encode(), tm.encode(), hashlib.sha1).hexdigest()

auth_url = 'http://www.fftt.com/mobile/pxml/xml_initialisation.php'
params = { 'tm': tm, 'tmc': tmc, 'serie': serie, 'id': fftt_id }
r = requests.get(auth_url, params=params)

url = 'http://www.fftt.com/mobile/pxml/xml_equipe.php'
params = { 'tm': tm, 'tmc': tmc, 'serie': serie, 'id': fftt_id, 'numclu': '07590074','type': 'm' }
r = requests.get(url, params=params)
#print(json.dumps(xmltodict.parse(r.text)))
equipes = xmltodict.parse(r.text)['liste']['equipe']

for i in range(0, len(equipes)):
    z = re.match("cx_poule=(\d+)&D1=(\d+)&organisme_pere=(\d+)", equipes[i]['liendivision'])
    poule = z.groups()[0]
    division = z.groups()[1]
    organisme = z.groups()[2]

    url = 'http://www.fftt.com/mobile/pxml/xml_result_equ.php'
    params = { 'tm': tm, 'tmc': tmc, 'serie': serie, 'id': fftt_id, 'cx_poule': poule, 'D1': division, 'organisme_pere': organisme }
    r = requests.get(url, params=params)
    for tour in reversed(xmltodict.parse(r.text)['liste']['tour']):
        if tour['equa'] is None:
            tour['equa'] = 'Null'
        if tour['equb'] is None:
            tour['equb'] = 'Null'
        if 'FACH' in tour['equa'] or 'FACH' in tour['equb']:
            equipea = re.sub("\(.*\)", '', tour['equa'])
            equipeb = re.sub("\(.*\)", '', tour['equb'])
            if 'FACH' in tour['equa']:
                print(equipea + " | " + tour['scorea'] + " - " + tour['scoreb'] + " | " + equipeb)
            if 'FACH' in tour['equb']:
                print(equipeb + " | " + tour['scoreb'] + " - " + tour['scorea'] + " | " + equipea)
            lien = tour['lien']
            break

    z2 = re.match("renc_id=(\d+)&is_retour=(\d+)&phase=(\d+)&res_1=(\d+)&res_2=(\d+)&equip_1=([\w\-\+\%]+)&equip_2=([\w\-\+\%]+)&equip_id1=(\d+)&equip_id2=(\d+)&clubnum_1=(\d+)&clubnum_2=(\d+)", lien)
    renc_id = z2.groups()[0]
    is_retour = z2.groups()[1]
    phase = z2.groups()[2]
    res_1 = z2.groups()[3]
    res_2 = z2.groups()[4]
    equip_1 = z2.groups()[5]
    equip_2 = z2.groups()[6]
    equip_id1 = z2.groups()[7]
    equip_id2 = z2.groups()[8]
    clubnum_1 = z2.groups()[9]
    clubnum_2 = z2.groups()[10]

    params = {'tm': tm, 'tmc': tmc, 'serie': serie, 'id': fftt_id, 'renc_id': renc_id, 'is_retour': is_retour, 'phase': phase, 'res_1': res_1, 'res_2': res_2, 'equip_1': equip_1, 'equip_2': equip_2, 'equip_id1': equip_id1, 'equip_id2': equip_id2, 'clubnum_1': clubnum_1, 'clubnum_2': clubnum_2}
    url = 'http://www.fftt.com/mobile/pxml/xml_chp_renc.php'
    r = requests.get(url, params=params)
    resultat = xmltodict.parse(r.text)['liste']
    res = dict()
    if 'FACH' in resultat['resultat']['equa']:
        if resultat['partie'] is not None:
            for partie in resultat['partie']:
                if partie['ja'] not in res:
                    res[partie['ja']] = 0
                if partie['scorea'] == '1':
                    res[partie['ja']] = res[partie['ja']] + 1
            print(res)
    elif 'FACH' in resultat['resultat']['equb']:
        if resultat['partie'] is not None:
            for partie in resultat['partie']:
                if partie['jb'] not in res:
                    res[partie['jb']] = 0
                if partie['scoreb'] == '1':
                    res[partie['jb']] = res[partie['jb']] + 1
            print(res)
    print('____')
