#!/bin/bash
set -e

DIR="/Users/jianouyang/Project/WorkGPT"
FIND_CMD="find $DIR -type f \( -name '*.rs' -o -name '*.toml' -o -name '*.md' -o -name '*.yml' -o -name '*.yaml' -o -name '*.json' -o -name '*.sh' -o -name '*.html' -o -name '*.js' -o -name '*.ts' -o -name '*.css' -o -name '*.txt' -o -name '*.cfg' -o -name '*.lock' -o -name 'Dockerfile' -o -name '.dockerignore' -o -name '.gitignore' -o -name '.gitattributes' -o -name '.env*' \) -not -path '*/.git/*' -not -path '*/target/*' -not -path '*/node_modules/*'"

echo "Step 1: Replace repo URLs"
eval "$FIND_CMD -exec sed -i '' 's|jackyang1989/WorkGPT|jackyang1989/WorkGPT|g' {} +"
eval "$FIND_CMD -exec sed -i '' 's|@jackyang1989/WorkGPT|@jackyang1989/workgpt|g' {} +"

echo "Step 2: Replace wg_ to wg_"
eval "$FIND_CMD -exec sed -i '' 's/wg_/wg_/g' {} +"

echo "Step 3: Replace _wg. to _wg."
eval "$FIND_CMD -exec sed -i '' 's/_wc\./_wg\./g' {} +"

echo "Step 4: Replace wg-persistent-shell"
eval "$FIND_CMD -exec sed -i '' 's/wg-persistent-shell/wg-persistent-shell/g' {} +"

echo "Step 5: Replace WORKGPT"
eval "$FIND_CMD -exec sed -i '' 's/WORKGPT/WORKGPT/g' {} +"

echo "Step 6: Replace WorkGPT"
eval "$FIND_CMD -exec sed -i '' 's/WorkGPT/WorkGPT/g' {} +"

echo "Step 7: Replace workgpt"
eval "$FIND_CMD -exec sed -i '' 's/workgpt/workgpt/g' {} +"

echo "Verifying remaining occurrences:"
grep -riE 'jackyang1989/WorkGPT|wg_|_wc\.|wg-persistent-shell|WORKGPT|WorkGPT|workgpt' $DIR --exclude-dir=.git --exclude-dir=target --exclude-dir=node_modules || echo "No matches found (which is good!)"

