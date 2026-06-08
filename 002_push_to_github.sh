#!/bin/bash
# Step 2: Push the Facebook static site to git@github.com:kiang/facebook.git
# Run this after 001_update_site.py has processed a new backup zip.
# Commits in batches: data files first, then one commit per monthly image folder.
# Resumable: uses content comparison to skip already-pushed content.

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
SITE_DIR="$(cd "$SCRIPT_DIR/../facebook" && pwd)"
REPO_URL="git@github.com:kiang/facebook.git"
WORK_DIR="/tmp/facebook-gh-push"

if [ ! -d "$SITE_DIR/data" ]; then
  echo "Error: $SITE_DIR/data not found. Run update_site.py first."
  exit 1
fi

# ── clone or pull ─────────────────────────────────────────────────────────────

if [ -d "$WORK_DIR/.git" ]; then
  echo "Using existing repo at $WORK_DIR, pulling latest..."
  cd "$WORK_DIR"
  git pull origin main --rebase || true
else
  echo "Cloning $REPO_URL into $WORK_DIR ..."
  git clone "$REPO_URL" "$WORK_DIR"
  cd "$WORK_DIR"
fi

# ── index.html + data/ ───────────────────────────────────────────────────────

echo "Syncing index.html + data/ ..."
cp "$SITE_DIR/index.html" .
cp -r "$SITE_DIR/data" .
git add index.html data/

if git diff --cached --quiet; then
  echo "  index.html + data/ unchanged, skipping."
else
  git commit -m "site: update index.html and monthly data JSON files"
  git push origin main
  echo "  pushed index.html + data/"
fi

# ── images month by month ─────────────────────────────────────────────────────

mkdir -p images

for month_dir in "$SITE_DIR/images"/*/; do
  [ -d "$month_dir" ] || continue
  month=$(basename "$month_dir")
  dest="images/$month"

  file_count=$(find "$month_dir" -maxdepth 1 -type f | wc -l)
  if [ "$file_count" -eq 0 ]; then
    echo "  images/$month has no files, skipping."
    continue
  fi

  mkdir -p "$dest"
  cp -n "$month_dir"* "$dest/" 2>/dev/null

  git add "$dest/"

  if git diff --cached --quiet; then
    continue
  fi

  size=$(du -sh "$dest" | cut -f1)
  git commit -m "images: $month ($file_count files, $size)"
  echo "Pushing images/$month ..."
  git push origin main
  echo "  done: images/$month"
done

echo ""
echo "All done. Site fully pushed to $REPO_URL"
