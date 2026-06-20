#!/bin/sh
# How to obtain a long-lived page token:
# 1. Get a short-lived user token from https://developers.facebook.com/tools/accesstoken
# 2. Exchange for a long-lived user token:
#    curl -i -X GET "https://graph.facebook.com/v10.0/oauth/access_token?grant_type=fb_exchange_token&client_id=493669754577697&client_secret=$secret&fb_exchange_token=$token"
# 3. Get the long-lived page token:
#    curl -i -X GET "https://graph.facebook.com/{graph-api-version}/{user-id}/accounts?access_token={long-lived-user-access-token}"
set -e

FB_DATA=/tmp/fb_posts_$$

curl -sS -X GET "https://graph.facebook.com/1909136939359253/posts?access_token=$facebook_token&limit=15" > "$FB_DATA"

json_data=$(jq '.data[] | select(.message!=null) | {id: .id, message: .message, date: .created_time}' "$FB_DATA")
rm -f "$FB_DATA"

for id in $(printf '%s' "$json_data" | jq -r '.id')
do
  if [ ! -f "content/post/$id.md" ]; then
    title=$(printf '%s' "$json_data" | jq -r ". | select(.id==\"$id\") | .message" | head -n 1 | tr -d '\n' | sed 's/"/\\"/g' | sed 's/\..*//g')
    date=$(printf '%s' "$json_data" | jq -r ". | select(.id==\"$id\") | .date")
    body=$(printf '%s' "$json_data" | jq -r ". | select(.id==\"$id\") | .message" | tail -n +2 \
      | awk 'NF{print $0 "  "} !NF{print ""}')

    printf -- '---\ntitle: "%s"\ndate: %s\n---\n' "$title" "$date" > "content/post/$id.md"
    printf '%s\n\n' "$body" >> "content/post/$id.md"

    img_dir="static/images/posts/$id"
    mkdir -p "$img_dir"
    img_idx=0
    curl -sS -X GET "https://graph.facebook.com/v10.0/$id/attachments?access_token=$facebook_token" \
      | jq -r '.data[] | if .subattachments then .subattachments.data[].media.image.src else (.media.image.src // empty) end' \
      | while IFS= read -r img_url; do
          img_idx=$((img_idx + 1))
          local_path="$img_dir/${img_idx}.jpg"
          if curl -sS -L -o "$local_path" "$img_url"; then
            printf '![](%s)\n' "/images/posts/$id/${img_idx}.jpg" >> "content/post/$id.md"
          fi
        done || true
  fi
done

# Migrate existing posts: fetch fresh image URLs from Facebook API + fix line breaks
python3 - << 'MIGRATE_POSTS'
import json, os, re, pathlib, urllib.request

POST_DIR  = pathlib.Path("content/post")
STATIC_DIR = pathlib.Path("static/images/posts")
FBCDN_RE  = re.compile(r'!\[\]\((https?://[^\s)]*fbcdn\.net[^\s)]*)\)')
LOCAL_IMG_RE = re.compile(r'!\[\]\(/images/posts/[^\)]+\)')
HARD_BREAK_RE = re.compile(r'(?<=[^\s])(  )?\n(?=[^\n])')

token = os.environ.get('facebook_token', '')

def fetch_image_urls(post_id):
    if not token:
        return []
    url = f"https://graph.facebook.com/v10.0/{post_id}/attachments?access_token={token}"
    try:
        with urllib.request.urlopen(url) as r:
            data = json.load(r)
        urls = []
        for item in data.get('data', []):
            subs = (item.get('subattachments') or {}).get('data', [])
            if subs:
                for sub in subs:
                    src = ((sub.get('media') or {}).get('image') or {}).get('src')
                    if src:
                        urls.append(src)
            else:
                src = ((item.get('media') or {}).get('image') or {}).get('src')
                if src:
                    urls.append(src)
        return urls
    except Exception as e:
        print(f"  Warning: could not fetch attachments for {post_id}: {e}")
        return []

def download_images(post_id, urls):
    img_dir = STATIC_DIR / post_id
    img_dir.mkdir(parents=True, exist_ok=True)
    local_paths = []
    for idx, url in enumerate(urls, start=1):
        dest = img_dir / f"{idx}.jpg"
        try:
            urllib.request.urlretrieve(url, dest)
            local_paths.append(f"/images/posts/{post_id}/{idx}.jpg")
        except Exception as e:
            print(f"  Warning: could not download image {idx} for {post_id}: {e}")
    return local_paths

def fix_line_breaks(content):
    lines = content.split('\n')
    result = []
    for line in lines:
        if line.strip() and not line.endswith('  ') and not line.startswith('![]') and not line.startswith('#'):
            result.append(line.rstrip() + '  ')
        else:
            result.append(line)
    return '\n'.join(result)

for md_file in sorted(POST_DIR.glob("*.md")):
    text = md_file.read_text()
    parts = text.split('---\n', 2)
    if len(parts) < 3:
        continue
    front_matter = parts[1]
    content = parts[2]

    has_fbcdn = bool(FBCDN_RE.search(content))
    local_imgs = LOCAL_IMG_RE.findall(content)
    post_id = md_file.stem

    changed = False

    # Re-fetch images for all FB posts: fixes expired fbcdn URLs and incomplete albums
    is_fb_post = '_' in post_id and post_id.replace('_', '').isdigit()
    if has_fbcdn or is_fb_post:
        urls = fetch_image_urls(post_id)
        if urls and len(urls) != len(local_imgs):
            local_paths = download_images(post_id, urls)
            # Strip all existing image lines (fbcdn or local) and append fresh ones
            content = FBCDN_RE.sub('', content)
            content = LOCAL_IMG_RE.sub('', content)
            content = content.rstrip() + '\n\n'
            content += '\n'.join(f'![]({p})' for p in local_paths) + '\n'
            changed = True

    # Fix line breaks: add two trailing spaces to non-blank, non-image, non-heading lines
    new_content = fix_line_breaks(content)
    if new_content != content:
        content = new_content
        changed = True

    if changed:
        md_file.write_text('---\n' + front_matter + '---\n' + content)
        print(f"Updated {md_file.name}")
MIGRATE_POSTS

mkdir -p data
FFTT_TMP=/tmp/fftt_new_$$.json
PLAYERS_TMP=/tmp/players_new_$$.json

uv run api_fftt.py > "$FFTT_TMP" || echo "FFTT fetch failed, keeping existing data"
uv run api_fftt_players.py > "$PLAYERS_TMP" || echo "FFTT players fetch failed, keeping existing data"

python3 - "$FFTT_TMP" "$PLAYERS_TMP" << 'MERGE'
import json, os, sys

def load(p):
    try:
        return json.load(open(p)) if p and os.path.exists(p) else None
    except Exception:
        return None

def save(d, p):
    with open(p, 'w') as f:
        json.dump(d, f, ensure_ascii=False, indent=2)

fftt_tmp, players_tmp = sys.argv[1], sys.argv[2]
new_fftt    = load(fftt_tmp)
new_players = load(players_tmp)
old_fftt    = load('data/fftt.json')
old_players = load('data/players.json')

# --- fftt.json: keep old until at least one match is scheduled or played ---
if new_fftt:
    teams = new_fftt.get('teams', [])
    has_matches = any(
        m.get('date_iso') is not None or m.get('score_home') is not None
        for t in teams
        for ph in ('phase1', 'phase2')
        for m in (t.get(ph) or [])
    )
    if has_matches or not old_fftt:
        save(new_fftt, 'data/fftt.json')
        print(f"Updated fftt.json ({len(teams)} teams)")
    else:
        print("No matches scheduled yet — keeping last season team data (data/fftt.json unchanged)")
elif old_fftt:
    print("FFTT fetch failed — keeping last season team data (data/fftt.json unchanged)")

# --- players.json: keep old if <20 players; preserve match history if none yet ---
if new_players is None:
    print("Players fetch failed — keeping last season player data (data/players.json unchanged)")
elif len(new_players) < 20 and old_players:
    print(f"Only {len(new_players)} players registered — keeping last season player data (data/players.json unchanged)")
else:
    total_matches = sum(len(p.get('matches', [])) for p in new_players)
    if total_matches == 0 and old_players:
        old_by_lic = {p['licence']: p for p in old_players}
        for p in new_players:
            old = old_by_lic.get(p['licence'])
            if old and old.get('matches'):
                p['matches'] = old['matches']
                p['points_estimated'] = old.get('points_estimated', False)
        print("No individual matches yet — carrying over last season match history")
    save(new_players, 'data/players.json')
    print(f"Updated players.json ({len(new_players)} players)")

os.unlink(fftt_tmp) if os.path.exists(fftt_tmp) else None
os.unlink(players_tmp) if os.path.exists(players_tmp) else None
MERGE

python3 -c "
import json, sys, os
from datetime import datetime
from urllib.request import urlopen
from urllib.parse import urlencode

token = os.environ.get('facebook_token', '')
params = urlencode({'access_token': token, 'fields': 'name,start_time,place', 'time_filter': 'upcoming', 'limit': '20'})
url = 'https://graph.facebook.com/v10.0/1909136939359253/events?' + params
with urlopen(url) as r:
    data = json.load(r)
events = []
for e in data.get('data', []):
    st = e.get('start_time', '')
    try:
        dt = datetime.fromisoformat(st)
        date_iso = dt.strftime('%Y-%m-%d')
        date = dt.strftime('%d/%m/%Y')
    except Exception:
        continue
    events.append({
        'type': 'event',
        'name': e.get('name', ''),
        'date': date,
        'date_iso': date_iso,
        'place': (e.get('place') or {}).get('name'),
        'url': 'https://www.facebook.com/events/' + e['id'] + '/',
    })
json.dump(events, sys.stdout, ensure_ascii=False, indent=2)
" > data/events.json || echo "[]" > data/events.json

hugo
printf 'www.fachesthumesniltt.com\n' > public/CNAME
