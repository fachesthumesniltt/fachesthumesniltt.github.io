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
    body=$(printf '%s' "$json_data" | jq -r ". | select(.id==\"$id\") | .message" | tail -n +2)

    printf -- '---\ntitle: "%s"\ndate: %s\n---\n' "$title" "$date" > "content/post/$id.md"
    printf '%s\n\n' "$body" >> "content/post/$id.md"

    curl -sS -X GET "https://graph.facebook.com/v10.0/$id/attachments?access_token=$facebook_token" \
      | jq -r '.data[].media.image | "![](\(.src))"' \
      >> "content/post/$id.md" || true
  fi
done

mkdir -p data
uv run api_fftt.py > data/fftt.json || echo "FFTT fetch failed, skipping equipes data"

hugo
printf 'www.fachesthumesniltt.com\n' > public/CNAME
