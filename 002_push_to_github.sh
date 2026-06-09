#!/bin/bash
# Step 2: Push the Facebook static site to git@github.com:kiang/facebook.git
# Run this after 001_update_site.py has processed a new backup zip.
# Commits in controlled batches to stay under GitHub's push size limits.
# Resumable: re-run safely — already-pushed content is skipped.

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
SITE_DIR="$(cd "$SCRIPT_DIR/../facebook" && pwd)"
BATCH_MAX_BYTES=$((500 * 1024 * 1024))  # 500 MB per push

if [ ! -d "$SITE_DIR/.git" ]; then
  echo "Error: $SITE_DIR is not a git repository."
  exit 1
fi

cd "$SITE_DIR"

git pull origin main --rebase || true

# ── index.html + data/ ───────────────────────────────────────────────────────

echo "Checking index.html + data/ ..."
git add index.html data/

if git diff --cached --quiet; then
  echo "  index.html + data/ unchanged, skipping."
else
  git commit -m "site: update index.html and monthly data JSON files"
  git push origin main
  echo "  pushed index.html + data/"
fi

# ── images in controlled batches ──────────────────────────────────────────────

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

for month_dir in images/*/; do
  [ -d "$month_dir" ] || continue
  month=$(basename "$month_dir")

  new_files=()
  while IFS= read -r -d '' img_file; do
    if git ls-files --error-unmatch "$img_file" >/dev/null 2>&1; then
      continue
    fi
    new_files+=("$img_file")
  done < <(find "$month_dir" -maxdepth 1 -type f -print0)

  if [ ${#new_files[@]} -eq 0 ]; then
    continue
  fi

  for img_file in "${new_files[@]}"; do
    file_bytes=$(stat -c%s "$img_file" 2>/dev/null || stat -f%z "$img_file" 2>/dev/null)

    if [ "$batch_bytes" -gt 0 ] && [ $((batch_bytes + file_bytes)) -gt "$BATCH_MAX_BYTES" ]; then
      flush_batch
    fi

    git add "$img_file"
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
echo "All done. Site fully pushed."
