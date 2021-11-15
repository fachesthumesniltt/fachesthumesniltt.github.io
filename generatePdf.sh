#!/bin/sh
set -x
set -e

for year in $(ls /app/docs/)
do
  mkdir -p /app/public/docs/$year/
  for file in $(ls /app/docs/$year/*.md)
  do 
    filename=$(basename $file)
    filePDF=$(echo $filename | sed 's/md$/pdf/g')
    pandoc -s /app/docs/$year/$filename -o /app/public/docs/$year/$filePDF
  done
done
