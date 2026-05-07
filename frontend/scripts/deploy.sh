#!/usr/bin/env bash
# 部署 frontend dist 到 /var/www/patent；重载 nginx
set -euo pipefail

DIR="$(cd "$(dirname "$0")/.." && pwd)"
DIST="$DIR/dist"
TARGET=/var/www/patent

if [ ! -d "$DIST" ]; then
  echo "ERROR: $DIST 不存在，先 pnpm build"; exit 1
fi

sudo mkdir -p "$TARGET"
sudo rsync -av --delete "$DIST/" "$TARGET/"
sudo nginx -t && sudo nginx -s reload
echo "✓ deployed to https://blind.pub/patent/"
