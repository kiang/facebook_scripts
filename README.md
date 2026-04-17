# Facebook Backup Scripts

A set of scripts to merge Facebook data backups, generate a static browsable website from personal post history, and push the result to GitHub Pages.

## Overview

Facebook's data export produces a ZIP archive containing JSON files and media. When you have a full historical backup and a more recent incremental backup, these scripts let you:

1. **Merge** the two backups into one complete dataset
2. **Generate** a self-contained static website from the merged posts
3. **Push** the generated site to a GitHub repository in size-safe batches

---

## Prerequisites

- Python 3.8+
- `git` with SSH access configured for GitHub
- Two Facebook data export folders extracted side by side

### Facebook export format

When you request your data from Facebook, it downloads as a ZIP. Extract it and you get a folder like:

```
facebook-kolctw-2026-3-6/
  connections/
  profile_information/
  this_profile's_activity_across_facebook/
    posts/
      profile_posts_1.json
      profile_posts_2.json
      media/
    messages/
      inbox/
      ...
  index.html
```

All scripts assume they are run from the directory containing both backup folders.

---

## Script 1: `merge_backup.py`

Merges a recent incremental backup (DIR2) into a full historical backup (DIR1).

### When to use

Facebook exports are complete snapshots up to the export date. If you exported in March and again in April, the April export only covers a recent window — it does not contain everything. This script combines both so you have a single complete dataset.

### Setup

Edit the two directory name constants at the top of the script to match your actual folder names:

```python
DIR1 = "facebook-kolctw-2026-3-6"       # full historical backup
DIR2 = "facebook-kolctw-2026-4-7-isMpSCJ9"  # recent incremental backup
```

### How it works

**Step 1** — copy files that only exist in DIR2 into DIR1 (non-destructive, no overwrites):

```bash
cp -rn facebook-kolctw-2026-4-7-isMpSCJ9/* facebook-kolctw-2026-3-6/
```

**Step 2** — run the merge script to combine overlapping JSON files:

```bash
python3 merge_backup.py
```

For every JSON file that exists in both backups, the script:
- Extracts the main array from each file (handles both top-level arrays and `{"key": [...]}` structures)
- Deduplicates entries using a stable MD5 hash of each JSON object
- Appends only new items from DIR2 into DIR1's file
- Writes the result back to DIR1 in-place

Non-array JSON files (e.g. profile settings) are skipped — the newer copy is already in place from the `cp -rn` step.

### Output

The script prints a summary line for each file processed:

```
  +527 items -> 10527 total: this_profile's_activity_across_facebook/posts/profile_posts_1.json
  +602 items -> 10641 total: this_profile's_activity_across_facebook/comments_and_reactions/comments.json
  no new items: connections/friends/your_post_audiences.json
  ...
Done. Processed 129 JSON files.
```

---

## Script 2: `generate_posts_site.py`

Generates a self-contained static website from the merged backup's post data.

### Setup

Edit the source directory constant at the top if your backup folder name differs:

```python
SRC_DIR = "facebook-kolctw-2026-3-6"
```

### Usage

Run from the directory containing the backup folder:

```bash
python3 generate_posts_site.py
```

The output is written to `facebook-kolctw-2026-3-6/posts_site/`.

### What it generates

```
posts_site/
  index.html           — single-page app (the entire UI)
  data/
    index.json         — manifest listing all months and post counts
    2026-04.json       — posts for April 2026
    2026-03.json       — posts for March 2026
    ...                — one file per month, newest first
  images/
    2026-04/           — images referenced by posts in that month
    2026-03/
    ...
```

### Filtering rules

The script applies two filters before generating:

- **Group posts are excluded** — posts where the title contains the pattern `在...中` (indicating the post was made inside a Facebook group rather than on the personal timeline)
- **Video posts are excluded** — posts whose only attachments are video files (`.mp4`, `.mov`, `.avi`, `.m4v`, `.wmv`)

### Post data structure

Each `YYYY-MM.json` file contains an array of post objects:

```json
[
  {
    "ts": 1764252237,
    "title": "江明宗分享了 1 條連結。",
    "text": "post body text...",
    "images": [
      {
        "file": "2025-11/1234567890.jpg",
        "title": "相片",
        "description": "caption text"
      }
    ],
    "external": [
      {
        "url": "https://example.com/article",
        "name": "Article title"
      }
    ]
  }
]
```

Image `file` paths are relative to `posts_site/images/`.

### Site features

- **Month archive sidebar** — lists all months with post counts, newest first
- **Hash-based routing** — URLs are shareable and work with browser back/forward:
  - `#2025-11` — November 2025 posts
  - `#2025-11/p3` — page 3 of November 2025
  - `#post/1764252237` — single post permalink (timestamp-based)
  - `#search/台南` — full-text search results
  - `#search/台南/p2` — page 2 of search results
- **Full-text search** — searches across all months' JSON data on the fly
- **Photo lightbox** — click any image to open full-size; arrow keys navigate between images in the same post
- **Link detection** — URLs in post text are converted to clickable links; detection runs on raw text before HTML escaping to avoid mangling URLs containing `&`
- **Responsive layout** — sidebar collapses on narrow screens

### Encoding note

Facebook exports text with UTF-8 characters stored as Latin-1 bytes. The `fb()` helper re-encodes strings correctly:

```python
def fb(s):
    return s.encode('latin-1').decode('utf-8')
```

### Regenerating

The script clears the entire `posts_site/` directory before each run, so re-running always produces a clean result with no stale files.

---

## Script 3: `push_to_github.sh`

Pushes the generated site to a GitHub repository in small batches to stay within GitHub's push size limits.

### Background

The generated site is ~2GB of images. GitHub imposes a 100MB per-file limit and recommends keeping individual pushes small. This script commits one monthly image folder at a time, pushing after each commit.

### Setup

The script is pre-configured for `git@github.com:kiang/facebook.git`. To use a different repository, edit the constant near the top:

```bash
REPO_URL="git@github.com:kiang/facebook.git"
```

The script also reads `SITE_DIR` relative to its own location, so it can be run from any directory as long as the backup folder is a sibling of the script.

SSH access to the target repository must be configured before running.

### Usage

```bash
bash push_to_github.sh
```

Or from the scripts directory:

```bash
cd /home/kiang/public_html/facebook_scripts
bash push_to_github.sh
```

### What it does

1. Clones the repository to `/tmp/facebook-gh-push` (or pulls latest if already cloned)
2. Runs `git ls-files` to get the authoritative list of what is already in the remote
3. Commits and pushes `index.html` + all `data/*.json` files as one commit (~8MB)
4. For each monthly image folder (`images/YYYY-MM/`):
   - Skips if already present in the remote according to `git ls-files`
   - Skips if the source folder contains no files
   - Copies files, commits, and pushes immediately

### Resumable

If the script is interrupted (network error, SSH timeout, etc.), simply re-run it. It checks `git ls-files` against the actual remote state rather than local disk state, so it accurately identifies what still needs to be pushed regardless of what is in `/tmp`.

### Commit structure

```
site: index.html and monthly data JSON files     (~8MB)
images: 2014-07 (5 files, 516K)
images: 2014-09 (3 files, 220K)
...
images: 2024-01 (312 files, 156M)
...
```

---

## Directory layout (full picture)

```
/path/to/working/directory/
  facebook-kolctw-2026-3-6/          ← full backup (DIR1), modified in-place by merge
  facebook-kolctw-2026-4-7-isMpSCJ9/ ← incremental backup (DIR2), read-only
  merge_backup.py
  generate_posts_site.py
  push_to_github.sh
```

After generation:

```
  facebook-kolctw-2026-3-6/
    posts_site/                       ← generated site, pushed to GitHub
      index.html
      data/
      images/
```

## Typical workflow

```bash
# 1. Copy new files from incremental backup (no overwrites)
cp -rn facebook-kolctw-2026-4-7-isMpSCJ9/* facebook-kolctw-2026-3-6/

# 2. Merge overlapping JSON arrays
python3 merge_backup.py

# 3. Generate the static site
python3 generate_posts_site.py

# 4. Push to GitHub (resumable if interrupted)
bash push_to_github.sh
```
