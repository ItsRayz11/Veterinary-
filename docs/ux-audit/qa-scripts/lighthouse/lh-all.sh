#!/bin/bash
export CHROME_PATH="C:/Program Files/Google/Chrome/Application/chrome.exe"
rm -f lh/p2-*.json
for rep in 1 2; do for form in mobile desktop; do for page in "home:/" "search:/search?q=amox"; do
  name=${page%%:*}; path=${page#*:}; extra=""; [ $form = desktop ] && extra="--preset=desktop"
  npx lighthouse "http://127.0.0.1:3300$path" $extra --chrome-flags="--headless=new --no-sandbox" --output=json --output-path="lh/p2-$form-$name-r$rep.json" --quiet >/dev/null 2>&1
done; done; done
echo ALL-LH-DONE
