#!/bin/bash
# Step 2: Push the Facebook static site to git@github.com:kiang/facebook.git
# Run this after 001_update_site.py has processed a new backup zip.
# Commits in controlled batches to stay under GitHub's push size limits.
# Resumable: re-run safely — already-pushed content is skipped.

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
SITE_DIR="$(cd "$SCRIPT_DIR/../facebook" && pwd)"
REPO_URL="git@github.com:kiang/facebook.git"
WORK_DIR="/tmp/facebook-gh-push"
BATCH_MAX_BYTES=$((500 * 1024 * 1024))  # 500 MB per push

if [ ! -d "$SITE_DIR/data" ]; then
  echo "Error: $SITE_DIR/data not found. Run 001_update_site.py first."
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

# ── images in controlled batches ──────────────────────────────────────────────

mkdir -p images

batch_bytes=0
batch_files=0
batch_months=""

flush_batch() {
  if [ "$batch_files" -eq 0 ]; then
    return
  fi
  if git diff --cached --quiet; then
    batch_bytes=0
    batch_files=0
    batch_months=""
    return
  fi
  local size_human
  size_human=$(numfmt --to=iec "$batch_bytes" 2>/dev/null || echo "${batch_bytes}B")
  git commit -m "images:${batch_months} (${batch_files} files, ${size_human})"
  echo "Pushing batch: ${batch_files} files, ${size_human} ..."
  git push origin main
  echo "  done."
  batch_bytes=0
  batch_files=0
  batch_months=""
}

for month_dir in "$SITE_DIR/images"/*/; do
  [ -d "$month_dir" ] || continue
  month=$(basename "$month_dir")
  dest="images/$month"

  new_files=()
  mkdir -p "$dest"

  while IFS= read -r -d '' src_file; do
    fname=$(basename "$src_file")
    dst_file="$dest/$fname"
    if [ -f "$dst_file" ]; then
      continue
    fi
    new_files+=("$src_file")
  done < <(find "$month_dir" -maxdepth 1 -type f -print0)

  if [ ${#new_files[@]} -eq 0 ]; then
    continue
  fi

  for src_file in "${new_files[@]}"; do
    fname=$(basename "$src_file")
    dst_file="$dest/$fname"
    file_bytes=$(stat -c%s "$src_file" 2>/dev/null || stat -f%z "$src_file" 2>/dev/null)

    if [ "$batch_bytes" -gt 0 ] && [ $((batch_bytes + file_bytes)) -gt "$BATCH_MAX_BYTES" ]; then
      flush_batch
    fi

    cp "$src_file" "$dst_file"
    git add "$dst_file"
    batch_bytes=$((batch_bytes + file_bytes))
    batch_files=$((batch_files + 1))
  done

  if [ -n "$batch_months" ]; then
    batch_months="$batch_months $month"
  else
    batch_months=" $month"
  fi
done

flush_batch

echo ""
echo "All done. Site fully pushed to $REPO_URL"
