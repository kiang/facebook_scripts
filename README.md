# Facebook Backup Scripts

Scripts to incrementally update a static browsable website from Facebook data backups and push the result to GitHub Pages.

## Quick start

```bash
# 1. Download new backup from Facebook, place ZIP in tmp/
cp ~/Downloads/facebook-kolctw-*.zip tmp/

# 2. Update the site with new posts
python3 001_update_site.py

# 3. Extract media report links from comments
python3 001b_update_media_reports.py

# 4. Push to GitHub
bash 002_push_to_github.sh
```

## Scripts

| Script | Purpose |
|--------|---------|
| `001_update_site.py` | Extract new backup zip from `tmp/`, merge new posts into the static site at `../facebook/` |
| `001b_update_media_reports.py` | Scan comments for '感謝報導', extract URLs, attach as 媒體報導 to matching posts |
| `002_push_to_github.sh` | Push the updated site to GitHub in size-safe batches (batch limit: 500 MB) |
| `003_rebuild_site_from_scratch.py` | (Legacy) Full site regeneration from an extracted backup directory |
| `004_merge_two_backup_dirs.py` | (Legacy) Merge two extracted backup directories into one |

## Directory layout

```
facebook_scripts/              <- this repo
  tmp/                         <- place new backup ZIPs here
    *.zip
  001_update_site.py
  001b_update_media_reports.py
  002_push_to_github.sh
  003_rebuild_site_from_scratch.py
  004_merge_two_backup_dirs.py
facebook/                      <- the generated static site
  index.html
  data/
    index.json
    2026-04.json
    ...
  images/
    2026-04/
    ...
```

## Prerequisites

- Python 3.8+
- `git` with SSH access configured for GitHub

## What `001b_update_media_reports.py` does

1. Reads `comments.json` directly from the backup zip (no extraction needed)
2. Finds all comments containing '感謝報導' with URLs
3. Crawls each URL to fetch the page `<title>` as the display name
4. Writes `data/media_reports.json` with URL, title, and comment date
5. Idempotent: re-running only crawls URLs that previously failed

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
- 媒體報導 (media reports) section on posts with press coverage links
- Responsive layout
