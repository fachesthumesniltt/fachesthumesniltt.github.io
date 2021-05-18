#!/bin/sh
set -x
set -e

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
    echo "####$id"
    cat content/post/$id.md
  fi
done
hugo
echo "www.fachesthumesniltt.com" > public/CNAME
