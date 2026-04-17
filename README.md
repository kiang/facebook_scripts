# Facebook Backup Scripts

Scripts to incrementally update a static browsable website from Facebook data backups and push the result to GitHub Pages.

## Overview

Facebook's data export produces a ZIP archive containing JSON files and media. These scripts let you:

1. **Update** the existing site with new posts from a fresh backup ZIP
2. **Push** the updated site to a GitHub repository in size-safe batches

The static site lives at `../facebook/` relative to this scripts directory. New backup ZIPs are placed in `../facebook/tmp/`.

---

## Prerequisites

- Python 3.8+
- `git` with SSH access configured for GitHub
- A Facebook data export ZIP file

### Facebook export format

When you request your data from Facebook, it downloads as a ZIP containing:

```
this_profile's_activity_across_facebook/
  posts/
    profile_posts_1.json
    profile_posts_2.json
    media/
  messages/
    inbox/
    ...
profile_information/
index.html
```

---

## Directory layout

```
/home/kiang/public_html/
  facebook_scripts/          ← this repo
    update_site.py           ← main update script
    push_to_github.sh        ← push to GitHub
    generate_posts_site.py   ← full site regeneration (legacy)
    merge_backup.py          ← backup merging (legacy)
  facebook/                  ← the generated static site
    index.html
    data/
      index.json             ← manifest listing all months
      2026-04.json           ← posts for April 2026
      ...
    images/
      2026-04/               ← images for that month
      ...
    tmp/
      *.zip                  ← new backup ZIPs go here
```

---

## Script: `update_site.py`

Incrementally updates the static site from a new backup ZIP.

### Usage

Place the new backup ZIP in `../facebook/tmp/`, then:

```bash
python3 update_site.py
```

Or specify a ZIP path directly:

```bash
python3 update_site.py /path/to/backup.zip
```

### What it does

1. Extracts the ZIP into a temporary directory
2. Loads posts from `profile_posts_*.json`
3. Filters out group posts (title contains `在...中`) and video-only posts
4. Deduplicates against existing site data by timestamp
5. Merges new posts into the correct monthly `data/YYYY-MM.json` files
6. Updates `data/index.json` with new counts
7. Copies new images to `images/YYYY-MM/`
8. Cleans up the extracted temporary directory

### Output

```
Using zip: ../facebook/tmp/facebook-kolctw-2026-4-17-3XLQGTvQ.zip
Loaded 224 posts from backup
After filtering group/video: 130 posts
Existing site has 9283 posts
New posts to add: 112
  2026-04: +112 -> 207 total
Updated index.json (127 months)
  copied 48 images, 0 missing sources
Done! Added 112 new posts across 1 months.
```

---

## Script: `push_to_github.sh`

Pushes the site to a GitHub repository in small batches.

### Background

The site contains ~2GB of images. GitHub recommends keeping pushes small. This script commits one monthly image folder at a time.

### Setup

Pre-configured for `git@github.com:kiang/facebook.git`. Edit `REPO_URL` to change.

### Usage

```bash
bash push_to_github.sh
```

### What it does

1. Clones the repository to `/tmp/facebook-gh-push` (or pulls latest if already cloned)
2. Copies and commits `index.html` + `data/` files (skips if unchanged)
3. For each monthly image folder, copies new files, commits, and pushes
4. Uses `cp -n` (no clobber) and `git diff --cached` to skip already-pushed content

### Resumable

If interrupted, re-run it — it detects what has already been pushed.

---

## Site features

- **Month archive sidebar** — lists all months with post counts
- **Hash-based routing** — shareable URLs: `#2025-11`, `#post/1764252237`, `#search/台南`
- **Full-text search** — searches across all months' data
- **Photo lightbox** — click images to view full-size, arrow keys navigate
- **Link detection** — URLs in post text become clickable links
- **Responsive layout** — sidebar collapses on narrow screens

### Encoding note

Facebook exports text with UTF-8 characters stored as Latin-1 bytes. The `fb()` helper re-encodes strings correctly:

```python
def fb(s):
    return s.encode('latin-1').decode('utf-8')
```

---

## Typical workflow

```bash
# 1. Download new backup from Facebook, place ZIP in tmp/
# (already at ../facebook/tmp/facebook-kolctw-2026-4-17-3XLQGTvQ.zip)

# 2. Update the site with new posts
python3 update_site.py

# 3. Push to GitHub
bash push_to_github.sh
```

---

## Legacy scripts

- `merge_backup.py` — Merges two extracted backup directories. Used when maintaining a full backup folder. No longer needed with the incremental `update_site.py` approach.
- `generate_posts_site.py` — Full site regeneration from a backup directory. Use only if you need to rebuild the entire site from scratch.
