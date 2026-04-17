#!/bin/bash
# Push posts_site to git@github.com:kiang/facebook.git
# Commits in batches, one per monthly image folder.
# Resumable: checks git ls-files to skip already-pushed months.

SITE_DIR="$(cd "$(dirname "$0")" && pwd)/facebook-kolctw-2026-3-6/posts_site"
REPO_URL="git@github.com:kiang/facebook.git"
WORK_DIR="/tmp/facebook-gh-push"

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

# Build set of paths already tracked in git
git ls-files > /tmp/fb-git-files.txt
echo "Remote has $(wc -l < /tmp/fb-git-files.txt) tracked files."

# ── index.html + data/ ───────────────────────────────────────────────────────

if grep -q "^index.html$" /tmp/fb-git-files.txt; then
  echo "  index.html already committed, skipping."
else
  echo "Copying and committing index.html + data/ ..."
  cp "$SITE_DIR/index.html" .
  cp -r "$SITE_DIR/data" .
  git add index.html data/
  git commit -m "site: index.html and monthly data JSON files"
  git push origin main
  echo "  pushed index.html + data/"
fi

# ── images month by month ─────────────────────────────────────────────────────

mkdir -p images

for month_dir in "$SITE_DIR/images"/*/; do
  month=$(basename "$month_dir")
  dest="images/$month"

  # Skip if already in remote
  if grep -q "^images/$month/" /tmp/fb-git-files.txt; then
    echo "  images/$month already in remote, skipping."
    continue
  fi

  # Skip if folder has no files
  file_count=$(ls "$month_dir" 2>/dev/null | wc -l)
  if [ "$file_count" -eq 0 ]; then
    echo "  images/$month has no files, skipping."
    continue
  fi

  echo "Copying images/$month ($file_count files)..."
  mkdir -p "$dest"
  cp "$month_dir"* "$dest/"

  size=$(du -sh "$dest" | cut -f1)
  git add "$dest/"

  # Only commit if there's actually something staged
  if git diff --cached --quiet; then
    echo "  nothing new to commit for images/$month, skipping."
    continue
  fi

  git commit -m "images: $month ($file_count files, $size)"
  echo "Pushing images/$month ..."
  git push origin main
  echo "  done: images/$month"
done

echo ""
echo "All done. Site fully pushed to $REPO_URL"
