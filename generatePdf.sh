#!/bin/sh
set -x
set -e

for year in $(ls /app/docs/)
do
  mkdir -p /app/public/docs/$year/
  echo "<html><body>" > /app/public/docs/$year/index.html
  for file in $(ls /app/docs/$year/*.md)
  do 
    filename=$(basename $file)
    filePDF=$(echo $filename | sed 's/md$/pdf/g')
    pandoc -s /app/docs/$year/$filename -o /app/public/docs/$year/$filePDF
    echo "<a href=\"$filePDF\">$filePDF</a></br>" >> /app/public/docs/$year/index.html
  done
  echo "</body></html>" >> /app/public/docs/$year/index.html
done
