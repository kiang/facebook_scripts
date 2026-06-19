# Facebook Backup Scripts

Scripts to incrementally update a static browsable website from Facebook data backups and push the result to GitHub Pages.

## Quick start

```bash
# 1. Download new backup from Facebook, place ZIP in tmp/
cp ~/Downloads/facebook-kolctw-*.zip tmp/

# 2. Update the site (posts + media reports)
python3 001_update_site.py

# 3. Push to GitHub
bash 002_push_to_github.sh
```

## Scripts

| Script | Purpose |
|--------|---------|
| `001_update_site.py` | Extract backup zip from `tmp/`, merge new posts, and update 媒體報導 links |
| `002_push_to_github.sh` | Push the updated site to GitHub in size-safe batches (batch limit: 500 MB) |
| `003_rebuild_site_from_scratch.py` | (Legacy) Full site regeneration from an extracted backup directory |
| `004_merge_two_backup_dirs.py` | (Legacy) Merge two extracted backup directories into one |

## Directory layout

```
facebook_scripts/              <- this repo
  tmp/                         <- place new backup ZIPs here
    *.zip
  001_update_site.py
  002_push_to_github.sh
  003_rebuild_site_from_scratch.py
  004_merge_two_backup_dirs.py
facebook/                      <- the generated static site
  index.html
  data/
    index.json
    media_reports.json
    2026-04.json
    ...
  images/
    2026-04/
    ...
```

## Prerequisites

- Python 3.8+
- `git` with SSH access configured for GitHub

## What `001_update_site.py` does

1. Finds the most recent `.zip` in `tmp/` (or uses a path you specify)
2. Extracts into `tmp/<zip-name>/`
3. Imports new posts (filter, dedup, merge, copy images)
4. Scans comments for '感謝報導', extracts URLs
5. Crawls only new URLs for page titles (YouTube via oEmbed, others via HTML)
6. Writes `data/media_reports.json`
7. Cleans up the extracted directory

## What `002_push_to_github.sh` does

1. Works directly in the `../facebook/` git repo
2. Commits `index.html` + `data/` (skips if unchanged)
3. Commits image files in batches under 500 MB and pushes
4. Resumable: re-run if interrupted

## Site features

- Month archive sidebar with post counts
- Hash-based routing (`#2025-11`, `#post/1764252237`, `#search/台南`)
- Full-text search across all months
- Photo lightbox with arrow key navigation
- 媒體報導 page with crawled article titles and dates
- Responsive layout
