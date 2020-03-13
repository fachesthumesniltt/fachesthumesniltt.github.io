#!/bin/sh

json_data=$(curl -X GET  "https://graph.facebook.com/1909136939359253/posts?access_token=$token&limit=15" | jq '.data[] | select(.message!=null)| {id: .id,message: .message, date: .created_time}')
for id in $(echo $json_data | jq -r '.id')
do
  if [ ! -f "content/post/$id.md" ];then
    echo -ne "---\ntitle: " > content/post/$id.md
    echo $json_data | jq -r ". | select(.id==\"$id\") | .message" | head -n 1 >> content/post/$id.md
    echo -ne "date: " >> content/post/$id.md
    echo $json_data | jq -r ". | select(.id==\"$id\") | .date" >> content/post/$id.md
    echo '---' >> content/post/$id.md
    echo $json_data | jq -r ". | select(.id==\"$id\") | .message" | tail +2 >> content/post/$id.md
  fi
done
hugo
echo "www.fachesthumesniltt.com" > public/CNAME
