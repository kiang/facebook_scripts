#!/usr/bin/env python3
"""
Step 1: Update the Facebook posts static site from a new backup zip.

Place your new Facebook backup zip in ./tmp/ then run:

    python3 001_update_site.py [zipfile]

If no zipfile is given, uses the most recent .zip in ./tmp/.

Steps:
  1. Extract the zip into ./tmp/
  2. Parse new posts from profile_posts_*.json
  3. Deduplicate against existing site data (by timestamp)
  4. Merge new posts into monthly JSON files and update index.json
  5. Copy new images into ../facebook/images/YYYY-MM/
  6. Update 媒體報導 from comments containing '感謝報導'
  7. Clean up the extracted directory

After this, run 002_push_to_github.sh to publish.
"""

import json
import os
import re
import shutil
import sys
import zipfile
import glob as globmod
from datetime import datetime
from collections import defaultdict
from html.parser import HTMLParser
from urllib.request import urlopen, Request

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
SITE_DIR = os.path.join(SCRIPT_DIR, "..", "facebook")
TMP_DIR = os.path.join(SCRIPT_DIR, "tmp")
DATA_DIR = os.path.join(SITE_DIR, "data")
IMG_DIR = os.path.join(SITE_DIR, "images")
MEDIA_REPORTS_FILE = os.path.join(DATA_DIR, "media_reports.json")

VIDEO_EXTS = ('.mp4', '.mov', '.avi', '.m4v', '.wmv')
URL_RE = re.compile(r'https?://[^\s　　-鿿＀-￯]+')


def fb(s):
    if not s:
        return ''
    try:
        return s.encode('latin-1').decode('utf-8')
    except Exception:
        return s


def is_group_post(post):
    title = fb(post.get('title', ''))
    return '在' in title and '中' in title


def has_video(post):
    for att in post.get('attachments', []):
        for d in att.get('data', []):
            if 'media' in d:
                uri = d['media'].get('uri', '')
                if uri.lower().endswith(VIDEO_EXTS):
                    return True
    return False


def extract_post(post, month, extract_dir):
    ts = post.get('timestamp', 0)
    title = fb(post.get('title', ''))

    text_parts = []
    for d in post.get('data', []):
        if d.get('post'):
            text_parts.append(fb(d['post']))

    images = []
    external = []
    for att in post.get('attachments', []):
        for d in att.get('data', []):
            if 'media' in d:
                m = d['media']
                uri = m.get('uri', '')
                fname = os.path.basename(uri)
                images.append({
                    'src_path': os.path.join(extract_dir, uri),
                    'file': f'{month}/{fname}',
                    'title': fb(m.get('title', '')),
                    'description': fb(m.get('description', '')),
                })
            if 'external_context' in d:
                ec = d['external_context']
                external.append({
                    'url': ec.get('url', ''),
                    'name': fb(ec.get('name', '')),
                })

    return {
        'ts': ts,
        'title': title,
        'text': '\n'.join(text_parts),
        'images': images,
        'external': external,
    }


def find_zip():
    if len(sys.argv) > 1:
        path = sys.argv[1]
        if not os.path.isabs(path):
            path = os.path.join(os.getcwd(), path)
        return path
    zips = sorted(globmod.glob(os.path.join(TMP_DIR, "*.zip")), key=os.path.getmtime)
    if not zips:
        print("No .zip files found in", TMP_DIR)
        sys.exit(1)
    return zips[-1]


def load_existing_timestamps():
    timestamps = set()
    index_path = os.path.join(DATA_DIR, "index.json")
    if not os.path.exists(index_path):
        return timestamps
    with open(index_path, encoding='utf-8') as f:
        manifest = json.load(f)
    for entry in manifest:
        month_file = os.path.join(DATA_DIR, f"{entry['month']}.json")
        if os.path.exists(month_file):
            with open(month_file, encoding='utf-8') as f:
                posts = json.load(f)
            for p in posts:
                timestamps.add(p.get('ts', 0))
    return timestamps


# ── media reports ─────────────────────────────────────────────────────────────

class TitleParser(HTMLParser):
    def __init__(self):
        super().__init__()
        self._in_title = False
        self._parts = []
        self.title = ''

    def handle_starttag(self, tag, attrs):
        if tag.lower() == 'title':
            self._in_title = True
            self._parts = []

    def handle_endtag(self, tag):
        if tag.lower() == 'title' and self._in_title:
            self._in_title = False
            self.title = ''.join(self._parts).strip()

    def handle_data(self, data):
        if self._in_title:
            self._parts.append(data)


def fetch_title(url, timeout=10):
    video_id = None
    m = re.match(r'https?://(?:www\.)?youtube\.com/watch\?v=([A-Za-z0-9_-]+)', url)
    if m:
        video_id = m.group(1)
    else:
        m = re.match(r'https?://youtu\.be/([A-Za-z0-9_-]+)', url)
        if m:
            video_id = m.group(1)

    if video_id:
        try:
            oembed_url = f'https://www.youtube.com/oembed?url=https://www.youtube.com/watch?v={video_id}&format=json'
            req = Request(oembed_url, headers={'User-Agent': 'Mozilla/5.0'})
            with urlopen(req, timeout=timeout) as resp:
                return json.load(resp).get('title', '')
        except Exception:
            return ''

    headers = {
        'User-Agent': 'Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
        'Accept': 'text/html,application/xhtml+xml',
        'Accept-Language': 'zh-TW,zh;q=0.9,en;q=0.8',
    }
    try:
        req = Request(url, headers=headers)
        with urlopen(req, timeout=timeout) as resp:
            content_type = resp.headers.get('Content-Type', '')
            if 'text/html' not in content_type and 'application/xhtml' not in content_type:
                return ''
            raw = resp.read(64 * 1024)
            for enc in ('utf-8', 'big5', 'latin-1'):
                try:
                    html = raw.decode(enc)
                    break
                except (UnicodeDecodeError, LookupError):
                    continue
            parser = TitleParser()
            parser.feed(html)
            return parser.title
    except Exception:
        return ''


def update_media_reports(zip_path):
    """Extract media report links from comments and crawl titles for new ones."""
    comments_path = "this_profile's_activity_across_facebook/comments_and_reactions/comments.json"
    try:
        with zipfile.ZipFile(zip_path, 'r') as zf:
            with zf.open(comments_path) as f:
                data = json.load(f)
    except (KeyError, FileNotFoundError):
        print("\nNo comments file found in zip, skipping media reports.")
        return

    entries = []
    seen_urls = set()
    for c in data.get('comments_v2', []):
        for d in c.get('data', []):
            text = fb(d.get('comment', {}).get('comment', ''))
            if '感謝報導' not in text:
                continue
            urls = URL_RE.findall(text)
            urls = [u.rstrip('.,;:!?\'")}]>') for u in urls]
            ts = c.get('timestamp', 0)
            for url in urls:
                if url in seen_urls:
                    continue
                seen_urls.add(url)
                entries.append({'ts': ts, 'url': url})

    if not entries:
        print("\nNo media report links found in comments.")
        return

    entries.sort(key=lambda x: x['ts'], reverse=True)

    existing = {}
    if os.path.exists(MEDIA_REPORTS_FILE):
        with open(MEDIA_REPORTS_FILE, encoding='utf-8') as f:
            for item in json.load(f):
                existing[item['url']] = item

    new_urls = [e for e in entries if e['url'] not in existing]
    print(f"\nMedia reports: {len(entries)} total links, {len(new_urls)} new to crawl")

    if not new_urls:
        print("  no new links to crawl.")
        return

    results = []
    crawled = 0
    failed = 0
    for entry in entries:
        url = entry['url']
        if url in existing:
            results.append(existing[url])
            continue

        title = fetch_title(url)
        crawled += 1
        results.append({
            'ts': entry['ts'],
            'url': url,
            'title': title or '',
        })
        if not title:
            failed += 1
        if crawled % 20 == 0:
            print(f"  crawled {crawled}/{len(new_urls)}...")

    results.sort(key=lambda x: x['ts'], reverse=True)

    os.makedirs(DATA_DIR, exist_ok=True)
    with open(MEDIA_REPORTS_FILE, 'w', encoding='utf-8') as f:
        json.dump(results, f, ensure_ascii=False, separators=(',', ':'))

    print(f"  {len(results)} media reports saved, crawled {crawled} new ({failed} without title)")


# ── main ──────────────────────────────────────────────────────────────────────

def main():
    zip_path = find_zip()
    print(f"Using zip: {zip_path}")

    zip_name = os.path.splitext(os.path.basename(zip_path))[0]
    extract_dir = os.path.join(TMP_DIR, zip_name)

    # Step 1: Extract
    if os.path.exists(extract_dir):
        print(f"Already extracted: {extract_dir}")
    else:
        print(f"Extracting to {extract_dir} ...")
        with zipfile.ZipFile(zip_path, 'r') as zf:
            zf.extractall(extract_dir)
        print(f"  extracted {len(os.listdir(extract_dir))} top-level items")

    # Step 2: Load new posts
    post_files = sorted(globmod.glob(
        os.path.join(extract_dir, "this_profile's_activity_across_facebook/posts/profile_posts_*.json")
    ))

    if post_files:
        raw_posts = []
        for pf in post_files:
            with open(pf, encoding='utf-8') as f:
                data = json.load(f)
            if isinstance(data, list):
                raw_posts.extend(data)
        print(f"Loaded {len(raw_posts)} posts from backup")

        # Filter
        raw_posts = [p for p in raw_posts if not is_group_post(p) and not has_video(p)]
        print(f"After filtering group/video: {len(raw_posts)} posts")

        # Step 3: Deduplicate against existing site
        existing_ts = load_existing_timestamps()
        print(f"Existing site has {len(existing_ts)} posts")

        new_posts = [p for p in raw_posts if p.get('timestamp', 0) not in existing_ts]
        print(f"New posts to add: {len(new_posts)}")

        if new_posts:
            # Group new posts by month
            new_by_month = defaultdict(list)
            for post in new_posts:
                ts = post.get('timestamp', 0)
                dt = datetime.fromtimestamp(ts) if ts else datetime(1970, 1, 1)
                key = f"{dt.year}-{dt.month:02d}"
                new_by_month[key].append(extract_post(post, key, extract_dir))

            # Step 4: Merge into existing monthly files
            print("Merging into site data...")
            updated_months = set()
            for month, new_month_posts in sorted(new_by_month.items()):
                month_file = os.path.join(DATA_DIR, f"{month}.json")
                if os.path.exists(month_file):
                    with open(month_file, encoding='utf-8') as f:
                        existing = json.load(f)
                else:
                    existing = []

                for post in new_month_posts:
                    clean_post = {
                        'ts': post['ts'],
                        'title': post['title'],
                        'text': post['text'],
                        'images': [
                            {k: v for k, v in img.items() if k != 'src_path'}
                            for img in post.get('images', [])
                        ],
                        'external': post.get('external', []),
                    }
                    existing.append(clean_post)

                existing.sort(key=lambda p: p.get('ts', 0), reverse=True)

                with open(month_file, 'w', encoding='utf-8') as f:
                    json.dump(existing, f, ensure_ascii=False, separators=(',', ':'))

                updated_months.add(month)
                print(f"  {month}: +{len(new_month_posts)} -> {len(existing)} total")

            # Step 5: Update index.json
            index_path = os.path.join(DATA_DIR, "index.json")
            if os.path.exists(index_path):
                with open(index_path, encoding='utf-8') as f:
                    manifest = json.load(f)
            else:
                manifest = []

            manifest_dict = {e['month']: e for e in manifest}

            for month in updated_months:
                month_file = os.path.join(DATA_DIR, f"{month}.json")
                with open(month_file, encoding='utf-8') as f:
                    count = len(json.load(f))
                manifest_dict[month] = {'month': month, 'count': count}

            manifest = sorted(manifest_dict.values(), key=lambda e: e['month'], reverse=True)
            with open(index_path, 'w', encoding='utf-8') as f:
                json.dump(manifest, f, ensure_ascii=False, separators=(',', ':'))
            print(f"Updated index.json ({len(manifest)} months)")

            # Step 6: Copy new images
            print("Copying new images...")
            copied = 0
            missing = 0
            for month, posts in new_by_month.items():
                month_img_dir = os.path.join(IMG_DIR, month)
                os.makedirs(month_img_dir, exist_ok=True)
                for post in posts:
                    for img in post.get('images', []):
                        src = img['src_path']
                        dst = os.path.join(IMG_DIR, img['file'])
                        if not os.path.exists(src):
                            missing += 1
                            continue
                        if os.path.exists(dst):
                            continue
                        shutil.copy2(src, dst)
                        copied += 1

            print(f"  copied {copied} images, {missing} missing sources")
            print(f"Posts: added {len(new_posts)} across {len(updated_months)} months.")
        else:
            print("No new posts to merge.")
    else:
        print("No profile_posts_*.json found in backup, skipping post import.")

    # Step 7: Update media reports (reads directly from zip, no extraction needed)
    update_media_reports(zip_path)

    # Cleanup extracted dir
    print(f"\nCleaning up {extract_dir} ...")
    shutil.rmtree(extract_dir)
    print("Done.")


if __name__ == '__main__':
    main()
