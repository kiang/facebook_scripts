#!/usr/bin/env python3
"""
Step 1b: Build the 媒體報導 (media reports) page from backup comments.

Scans the backup zip for comments containing '感謝報導', extracts URLs,
crawls each URL for its <title>, and writes data/media_reports.json
to the site directory.

Usage:
    python3 001b_update_media_reports.py [zipfile]

Run after 001_update_site.py. Then run 002_push_to_github.sh to publish.
"""

import json
import os
import re
import sys
import zipfile
import glob as globmod
from datetime import datetime
from html.parser import HTMLParser
from urllib.request import urlopen, Request
from urllib.error import URLError

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
SITE_DIR = os.path.join(SCRIPT_DIR, "..", "facebook")
TMP_DIR = os.path.join(SCRIPT_DIR, "tmp")
DATA_DIR = os.path.join(SITE_DIR, "data")

URL_RE = re.compile(r'https?://[^\s　　-鿿＀-￯]+')
MEDIA_REPORTS_FILE = os.path.join(DATA_DIR, "media_reports.json")


def fb(s):
    if not s:
        return ''
    try:
        return s.encode('latin-1').decode('utf-8')
    except Exception:
        return s


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


def normalize_youtube_url(url):
    """Extract video ID and return a canonical youtube.com URL, or None."""
    m = re.match(r'https?://(?:www\.)?youtube\.com/watch\?v=([A-Za-z0-9_-]+)', url)
    if m:
        return m.group(1)
    m = re.match(r'https?://youtu\.be/([A-Za-z0-9_-]+)', url)
    if m:
        return m.group(1)
    return None


def fetch_youtube_title(video_id, timeout=10):
    oembed_url = f'https://www.youtube.com/oembed?url=https://www.youtube.com/watch?v={video_id}&format=json'
    try:
        req = Request(oembed_url, headers={'User-Agent': 'Mozilla/5.0'})
        with urlopen(req, timeout=timeout) as resp:
            data = json.load(resp)
        return data.get('title', '')
    except Exception:
        return ''


def fetch_title(url, timeout=10):
    video_id = normalize_youtube_url(url)
    if video_id:
        return fetch_youtube_title(video_id, timeout)

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


def main():
    zip_path = find_zip()
    print(f"Using zip: {zip_path}")

    comments_path = "this_profile's_activity_across_facebook/comments_and_reactions/comments.json"
    with zipfile.ZipFile(zip_path, 'r') as zf:
        try:
            with zf.open(comments_path) as f:
                data = json.load(f)
        except KeyError:
            print("No comments file found in zip.")
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

    entries.sort(key=lambda x: x['ts'], reverse=True)
    print(f"Found {len(entries)} unique media report links")

    if not entries:
        return

    existing = {}
    if os.path.exists(MEDIA_REPORTS_FILE):
        with open(MEDIA_REPORTS_FILE, encoding='utf-8') as f:
            for item in json.load(f):
                existing[item['url']] = item

    to_crawl = [e for e in entries if e['url'] not in existing or not existing[e['url']].get('title')]
    already = len(entries) - len(to_crawl)
    if already:
        print(f"  {already} already have titles, {len(to_crawl)} to crawl")

    results = []
    crawled = 0
    failed = 0
    for i, entry in enumerate(entries):
        url = entry['url']
        if url in existing and existing[url].get('title'):
            results.append(existing[url])
            continue

        title = fetch_title(url)
        crawled += 1
        if title:
            results.append({
                'ts': entry['ts'],
                'url': url,
                'title': title,
            })
        else:
            failed += 1
            results.append({
                'ts': entry['ts'],
                'url': url,
                'title': '',
            })

        if crawled % 20 == 0:
            print(f"  crawled {crawled}/{len(to_crawl)}...")

    results.sort(key=lambda x: x['ts'], reverse=True)

    os.makedirs(DATA_DIR, exist_ok=True)
    with open(MEDIA_REPORTS_FILE, 'w', encoding='utf-8') as f:
        json.dump(results, f, ensure_ascii=False, separators=(',', ':'))

    print(f"\nDone! {len(results)} media reports -> {MEDIA_REPORTS_FILE}")
    print(f"  crawled: {crawled}, failed to get title: {failed}")


if __name__ == '__main__':
    main()
