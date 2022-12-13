#!/bin/sh
set -x
set -e
env
# How to obtain token page long live
# request user token ( token tool debugging after facebook developper login)
# https://developers.facebook.com/tools/accesstoken
# request a long live user token
# request secret key for app (https://developers.facebook.com/apps/493669754577697/settings/basic/https://developers.facebook.com/apps/493669754577697/settings/basic/   parameters-> general)
# curl -i -X GET "https://graph.facebook.com/v10.0/oauth/access_token?grant_type=fb_exchange_token&client_id=493669754577697&client_secret=$secret&fb_exchange_token=$token"
# request a long live token page with previous token
# curl -i -X GET "https://graph.facebook.com/{graph-api-version}/{user-id}/accounts?access_token={long-lived-user-access-token}"


echo $facebook_token | sed 's/./& /g'
curl -X GET  "https://graph.facebook.com/1909136939359253/posts?access_token=$facebook_token&limit=15" > json_data
cat json_data
json_data=$(cat json_data | jq '.data[] | select(.message!=null)| {id: .id,message: .message, date: .created_time}')
for id in $(echo $json_data | jq -r '.id')
do
  if [ ! -f "content/post/$id.md" ];then
    echo -ne "---\ntitle: \"" > content/post/$id.md
    echo $json_data | jq -r ". | select(.id==\"$id\") | .message" | head -n 1 | tr -d '\n' | sed 's/"/\\\"/g' >> content/post/$id.md
    echo -ne "\"\ndate: " >> content/post/$id.md
    echo $json_data | jq -r ". | select(.id==\"$id\") | .date" >> content/post/$id.md
    echo '---' >> content/post/$id.md
    echo $json_data | jq -r ". | select(.id==\"$id\") | .message" | tail +2 >> content/post/$id.md
    echo "  " >> content/post/$id.md
    echo "  " >> content/post/$id.md
    curl -X GET "https://graph.facebook.com/v10.0/$id/attachments?access_token=$facebook_token" | jq  '.data[].media.image' | jq -jr '"<img src=\"", .src, "\" width=\"", .width, "\" height=\"", .height, "\">"' >> content/post/$id.md
    echo "####$id"
    cat content/post/$id.md
  fi
done

/usr/bin/python3 api_fftt.py >> content/pages/results.md


hugo
echo "www.fachesthumesniltt.com" > public/CNAME
