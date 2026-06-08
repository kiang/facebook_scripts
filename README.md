# Facebook Backup Scripts

Scripts to incrementally update a static browsable website from Facebook data backups and push the result to GitHub Pages.

## Quick start

```bash
# 1. Download new backup from Facebook, place ZIP in tmp/
cp ~/Downloads/facebook-kolctw-*.zip tmp/

# 2. Update the site with new posts
python3 001_update_site.py

# 3. Push to GitHub
bash 002_push_to_github.sh
```

## Scripts

| Script | Purpose |
|--------|---------|
| `001_update_site.py` | Extract new backup zip from `tmp/`, merge new posts into the static site at `../facebook/` |
| `002_push_to_github.sh` | Push the updated site to GitHub in size-safe batches (one monthly image folder per commit) |
| `003_rebuild_site_from_scratch.py` | (Legacy) Full site regeneration from an extracted backup directory |
| `004_merge_two_backup_dirs.py` | (Legacy) Merge two extracted backup directories into one |

## Directory layout

```
/home/kiang/public_html/
  facebook_scripts/          <- this repo
    tmp/                     <- place new backup ZIPs here
      *.zip
    001_update_site.py
    002_push_to_github.sh
    003_rebuild_site_from_scratch.py
    004_merge_two_backup_dirs.py
  facebook/                  <- the generated static site
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

## What `001_update_site.py` does

1. Finds the most recent `.zip` in `tmp/` (or uses a path you specify)
2. Extracts into `tmp/<zip-name>/`
3. Loads posts from `profile_posts_*.json`
4. Filters out group posts and video-only posts
5. Deduplicates against existing site data by timestamp
6. Merges new posts into `../facebook/data/YYYY-MM.json` files
7. Updates `../facebook/data/index.json`
8. Copies new images to `../facebook/images/YYYY-MM/`
9. Cleans up the extracted directory

## What `002_push_to_github.sh` does

1. Clones/pulls `git@github.com:kiang/facebook.git` to `/tmp/facebook-gh-push`
2. Commits `index.html` + `data/` (skips if unchanged)
3. Commits each monthly image folder separately and pushes
4. Resumable: re-run if interrupted

## Site features

- Month archive sidebar with post counts
- Hash-based routing (`#2025-11`, `#post/1764252237`, `#search/台南`)
- Full-text search across all months
- Photo lightbox with arrow key navigation
- Responsive layout
