#!/usr/bin/env python3
"""
(Legacy) Full site regeneration from a backup directory.

Only needed if you want to rebuild the entire site from scratch.
For normal incremental updates, use 001_update_site.py instead.

Reads from an extracted backup directory and generates:
  index.html, data/index.json, data/YYYY-MM.json, images/

NOTE: Hardcoded SRC_DIR below must be updated to your backup directory path.
"""

import json
import os
import shutil
from datetime import datetime
from collections import defaultdict

SRC_DIR  = "facebook-kolctw-2026-3-6"
OUT_DIR  = os.path.join(SRC_DIR, "posts_site")
DATA_DIR = os.path.join(OUT_DIR, "data")
IMG_DIR  = os.path.join(OUT_DIR, "images")

POST_FILES = [
    os.path.join(SRC_DIR, "this_profile's_activity_across_facebook/posts/profile_posts_1.json"),
    os.path.join(SRC_DIR, "this_profile's_activity_across_facebook/posts/profile_posts_2.json"),
]

# ── helpers ───────────────────────────────────────────────────────────────────

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
                if uri.lower().endswith(('.mp4', '.mov', '.avi', '.m4v', '.wmv')):
                    return True
    return False

def extract_post(post, month):
    """Return a clean dict for JSON output."""
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
                    'src': uri,                    # original source path (relative to SRC_DIR)
                    'file': f'{month}/{fname}',    # path under posts_site/images/
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

# ── load & filter ─────────────────────────────────────────────────────────────

print("Loading posts...")
raw_posts = []
for f in POST_FILES:
    if os.path.exists(f):
        with open(f, encoding='utf-8') as fh:
            data = json.load(fh)
        if isinstance(data, list):
            raw_posts.extend(data)

before = len(raw_posts)
raw_posts = [p for p in raw_posts if not is_group_post(p) and not has_video(p)]
print(f"Filtered: {before} -> {len(raw_posts)} posts "
      f"(removed {before - len(raw_posts)} group/video posts)")

raw_posts.sort(key=lambda p: p.get('timestamp', 0), reverse=True)

# ── group posts by month ──────────────────────────────────────────────────────

by_month = defaultdict(list)
for post in raw_posts:
    ts = post.get('timestamp', 0)
    dt = datetime.fromtimestamp(ts) if ts else datetime(1970, 1, 1)
    key = f"{dt.year}-{dt.month:02d}"
    by_month[key].append(extract_post(post, key))

# ── write output ──────────────────────────────────────────────────────────────

if os.path.exists(OUT_DIR):
    print(f"Cleaning {OUT_DIR} ...")
    shutil.rmtree(OUT_DIR)
os.makedirs(DATA_DIR, exist_ok=True)

# data/YYYY-MM.json
print("Writing monthly JSON data files...")
manifest = []
for key in sorted(by_month.keys(), reverse=True):
    posts_in_month = by_month[key]
    out_path = os.path.join(DATA_DIR, f"{key}.json")
    # Strip internal 'src' field before writing (only needed during copy)
    clean = [{k: v for k, v in p.items() if k != 'images'} |
             {'images': [{k: v for k, v in img.items() if k != 'src'} for img in p.get('images', [])]}
             for p in posts_in_month]
    with open(out_path, 'w', encoding='utf-8') as fh:
        json.dump(clean, fh, ensure_ascii=False, separators=(',', ':'))
    manifest.append({'month': key, 'count': len(posts_in_month)})
    print(f"  {key}: {len(posts_in_month)} posts")

# data/index.json
with open(os.path.join(DATA_DIR, 'index.json'), 'w', encoding='utf-8') as fh:
    json.dump(manifest, fh, ensure_ascii=False, separators=(',', ':'))
print(f"Wrote data/index.json ({len(manifest)} months)")

# Copy images into monthly subfolders
print("Copying images to posts_site/images/YYYY-MM/ ...")
copied = 0
missing = 0
for month, posts_in_month in by_month.items():
    month_img_dir = os.path.join(IMG_DIR, month)
    os.makedirs(month_img_dir, exist_ok=True)
    for post in posts_in_month:
        for img in post.get('images', []):
            src = os.path.join(SRC_DIR, img['src'])
            dst = os.path.join(IMG_DIR, img['file'])  # images/YYYY-MM/fname
            if not os.path.exists(src):
                missing += 1
                continue
            shutil.copy2(src, dst)
            copied += 1
            if copied % 500 == 0:
                print(f"  copied {copied}...")

print(f"  done: {copied} copied, {missing} source missing")

# ── write index.html ──────────────────────────────────────────────────────────

HTML = r"""<!DOCTYPE html>
<html lang="zh-TW">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>江明宗 (kiang) - Facebook 貼文存檔</title>
<meta name="description" content="江明宗 (kiang) 的 Facebook 個人頁面貼文存檔，涵蓋 2014 年至今的公開貼文。">
<meta name="author" content="江明宗 (kiang)">
<meta property="og:title" content="江明宗 (kiang) - Facebook 貼文存檔">
<meta property="og:description" content="江明宗 (kiang) 的 Facebook 個人頁面貼文存檔，涵蓋 2014 年至今的公開貼文。">
<meta property="og:type" content="website">
<style>
*{box-sizing:border-box;margin:0;padding:0}
body{font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',Roboto,sans-serif;background:#f0f2f5;color:#1c1e21;line-height:1.5}
a{color:#1877f2;text-decoration:none}
a:hover{text-decoration:underline}

/* layout */
header{background:#1877f2;color:white;padding:10px 20px;position:sticky;top:0;z-index:100;display:flex;align-items:center;gap:16px}
header h1{font-size:17px;font-weight:700;white-space:nowrap}
#search-input{flex:1;max-width:320px;padding:6px 12px;border:none;border-radius:20px;font-size:14px;outline:none}
.layout{display:grid;grid-template-columns:220px 1fr;gap:16px;max-width:960px;margin:16px auto;padding:0 12px}
@media(max-width:680px){.layout{grid-template-columns:1fr}.sidebar{display:none}}

/* sidebar */
.sidebar{align-self:start;position:sticky;top:56px;max-height:calc(100vh - 72px);overflow-y:auto}
.sidebar-box{background:white;border-radius:8px;box-shadow:0 1px 2px rgba(0,0,0,.1);padding:14px}
.sidebar-box h2{font-size:14px;font-weight:700;color:#1877f2;margin-bottom:10px}
.month-list{list-style:none}
.month-list li{font-size:13px;padding:3px 0}
.month-list li a{color:#1c1e21;display:flex;justify-content:space-between}
.month-list li a:hover{color:#1877f2;text-decoration:none}
.month-list li a.active{color:#1877f2;font-weight:600}
.month-list .count{color:#65676b;font-size:12px}

/* posts */
.main{}
.section-title{font-size:15px;font-weight:600;color:#65676b;margin-bottom:12px}
.post-card{background:white;border-radius:8px;box-shadow:0 1px 2px rgba(0,0,0,.1);margin-bottom:14px;padding:16px;overflow:hidden}
.post-meta{font-size:12px;color:#65676b;margin-bottom:7px}
.post-body{font-size:15px;white-space:pre-wrap;word-break:break-word;margin-bottom:10px}
.post-body a{color:#1877f2}
.media-grid{display:grid;gap:3px;margin-top:8px}
.media-grid.n1{grid-template-columns:1fr}
.media-grid.n2{grid-template-columns:1fr 1fr}
.media-grid.n3{grid-template-columns:1fr 1fr 1fr}
.media-grid.n4,.media-grid.nN{grid-template-columns:1fr 1fr}
.media-grid img{width:100%;object-fit:cover;border-radius:4px;cursor:pointer;display:block}
.media-grid.n1 img{max-height:480px;object-fit:contain;background:#f0f2f5}
.media-grid.n2 img,.media-grid.n3 img{height:180px}
.media-grid.n4 img,.media-grid.nN img{height:160px}
.ext-link{background:#f0f2f5;border-radius:6px;padding:10px 12px;margin-top:8px;font-size:13px}
.more-images{background:#00000033;color:white;display:flex;align-items:center;justify-content:center;font-size:20px;font-weight:700;border-radius:4px;height:160px;cursor:default}

/* pagination */
.pagination{display:flex;justify-content:center;align-items:center;gap:8px;padding:20px 0}
.pg-btn{background:#1877f2;color:white;border:none;padding:7px 18px;border-radius:6px;cursor:pointer;font-size:14px;text-decoration:none;display:inline-block}
.pg-btn:hover{background:#1669d4;text-decoration:none;color:white}
.pg-btn.disabled{background:#bec3c9;cursor:default;pointer-events:none}
.pagination .page-info{font-size:14px;color:#65676b}
.post-permalink{color:#bec3c9;font-size:13px;margin-left:6px;text-decoration:none}
.post-permalink:hover{color:#1877f2}

/* lightbox */
#lightbox{display:none;position:fixed;inset:0;background:rgba(0,0,0,.9);z-index:1000;justify-content:center;align-items:center;cursor:pointer}
#lightbox.open{display:flex}
#lightbox img{max-width:95%;max-height:95%;object-fit:contain}

.loading{text-align:center;padding:40px;color:#65676b;font-size:15px}
.no-results{text-align:center;padding:40px;color:#65676b;font-size:15px}
</style>
</head>
<body>

<header>
  <h1><a href="https://facebook.com/k.olc.tw" target="_blank" rel="noopener" style="color:white;text-decoration:none">江明宗 (kiang)</a></h1>
  <input id="search-input" type="search" placeholder="搜尋貼文..." autocomplete="off">
  <span id="header-info" style="font-size:13px;opacity:.8;white-space:nowrap"></span>
</header>

<div class="layout">
  <aside class="sidebar">
    <div class="sidebar-box">
      <h2>月份封存</h2>
      <ul class="month-list" id="month-list"></ul>
    </div>
  </aside>
  <main class="main" id="main">
    <div class="loading">Loading...</div>
  </main>
</div>

<div id="lightbox"><img id="lightbox-img" src="" alt=""></div>

<script>
const PAGE_SIZE = 20;
let manifest = [];
let currentPosts = [];
let currentPage = 0;
let searchTimer = null;

// ── data loading ──────────────────────────────────────────────────────────────

const cache = {};
async function loadJSON(url) {
  if (cache[url]) return cache[url];
  const r = await fetch(url);
  if (!r.ok) return null;
  const d = await r.json();
  cache[url] = d;
  return d;
}

async function init() {
  manifest = await loadJSON('data/index.json');
  if (!manifest) { document.getElementById('main').innerHTML = '<div class="loading">Failed to load data.</div>'; return; }
  renderSidebar();
  window.addEventListener('hashchange', () => route());
  route();
}

// ── routing ───────────────────────────────────────────────────────────────────
// Hash formats:
//   #YYYY-MM          month view, page 1
//   #YYYY-MM/p2       month view, page N
//   #post/TIMESTAMP   single post view
//   #search/TERM      search results
//   (empty)           most recent month

async function route() {
  const hash = decodeURIComponent(location.hash.slice(1));
  document.getElementById('main').innerHTML = '<div class="loading">Loading...</div>';

  if (!hash) {
    setHash(manifest[0].month);
    return;
  }

  const postMatch = hash.match(/^post\/(\d+)$/);
  if (postMatch) {
    await showPost(parseInt(postMatch[1], 10));
    return;
  }

  const searchMatch = hash.match(/^search\/(.+?)(?:\/p(\d+))?$/);
  if (searchMatch) {
    const term = decodeURIComponent(searchMatch[1]);
    const page = searchMatch[2] ? parseInt(searchMatch[2], 10) - 1 : 0;
    document.getElementById('search-input').value = term;
    await showSearch(term, page);
    return;
  }

  const monthMatch = hash.match(/^(\d{4}-\d{2})(?:\/p(\d+))?$/);
  if (monthMatch) {
    const month = monthMatch[1];
    const page = monthMatch[2] ? parseInt(monthMatch[2], 10) - 1 : 0;
    await showMonth(month, page);
    return;
  }

  setHash(manifest[0].month);
}

function setHash(hash, replace = false) {
  const encoded = encodeURIComponent(hash).replace(/%2F/g, '/');
  if (replace) {
    history.replaceState(null, '', '#' + encoded);
  } else {
    location.hash = encoded;
  }
}

// ── views ─────────────────────────────────────────────────────────────────────

async function showMonth(month, page = 0) {
  document.getElementById('search-input').value = '';
  document.querySelectorAll('.month-list a').forEach(a =>
    a.classList.toggle('active', a.dataset.month === month));
  const posts = await loadJSON(`data/${month}.json`);
  currentPosts = posts || [];
  currentPage = page;
  renderList(`${month} — ${currentPosts.length} posts`,
    hash => `${month}/p${hash}`,
    month);
}

async function showSearch(term, page = 0) {
  document.querySelectorAll('.month-list a').forEach(a => a.classList.remove('active'));
  const lc = term.toLowerCase();
  let results = [];
  for (const {month} of manifest) {
    const posts = await loadJSON(`data/${month}.json`);
    if (posts) results = results.concat(posts.filter(p =>
      (p.text && p.text.toLowerCase().includes(lc)) ||
      (p.title && p.title.toLowerCase().includes(lc))
    ));
  }
  currentPosts = results;
  currentPage = page;
  renderList(`Search: "${term}" — ${results.length} results`,
    page => `search/${encodeURIComponent(term)}/p${page}`,
    `search/${encodeURIComponent(term)}`);
}

async function showPost(ts) {
  // Find which month this post belongs to, load it
  const dt = new Date(ts * 1000);
  const month = `${dt.getFullYear()}-${String(dt.getMonth()+1).padStart(2,'0')}`;
  const posts = await loadJSON(`data/${month}.json`);
  const post = posts && posts.find(p => p.ts === ts);
  if (!post) {
    document.getElementById('main').innerHTML = '<div class="no-results">Post not found.</div>';
    return;
  }
  document.querySelectorAll('.month-list a').forEach(a =>
    a.classList.toggle('active', a.dataset.month === month));
  const postDate = new Date(ts*1000).toLocaleDateString('zh-TW');
  document.getElementById('header-info').textContent = postDate;
  document.title = `${postDate} - 江明宗 (kiang) Facebook 貼文存檔`;

  let html = `<div class="section-title">
    <a href="#${month}" style="color:#65676b;font-size:13px">&#8592; ${month}</a>
  </div>`;
  html += renderPostHTML(post, true);
  document.getElementById('main').innerHTML = html;
  window.scrollTo(0, 0);
}

function renderList(label, pageHashFn, month) {
  const total = currentPosts.length;
  const totalPages = Math.max(1, Math.ceil(total / PAGE_SIZE));
  if (currentPage >= totalPages) currentPage = 0;
  const slice = currentPosts.slice(currentPage * PAGE_SIZE, (currentPage + 1) * PAGE_SIZE);

  document.getElementById('header-info').textContent = label;
  document.title = `${label} - 江明宗 (kiang) Facebook 貼文存檔`;

  if (total === 0) {
    document.getElementById('main').innerHTML = '<div class="no-results">No posts found.</div>';
    return;
  }

  let html = `<div class="section-title">${esc(label)}</div>`;
  for (const post of slice) html += renderPostHTML(post, false);
  html += renderPagination(totalPages, pageHashFn, month);
  document.getElementById('main').innerHTML = html;
  window.scrollTo(0, 0);
}

// ── search input ──────────────────────────────────────────────────────────────

document.getElementById('search-input').addEventListener('input', e => {
  clearTimeout(searchTimer);
  const val = e.target.value.trim();
  searchTimer = setTimeout(() => {
    if (!val) {
      setHash(manifest[0].month);
    } else {
      setHash('search/' + val);
    }
  }, 400);
});

// ── render helpers ────────────────────────────────────────────────────────────

function renderPostHTML(post, isSingle) {
  const date = post.ts ? new Date(post.ts * 1000).toLocaleString('zh-TW', {
    year:'numeric', month:'2-digit', day:'2-digit', hour:'2-digit', minute:'2-digit'
  }) : '';
  const postHash = `post/${post.ts}`;

  let html = '<article class="post-card">';
  html += `<div class="post-meta">`;
  html += `<time>${esc(date)}</time>`;
  if (!isSingle) html += ` <a class="post-permalink" href="#${postHash}" title="Permalink">#</a>`;
  html += `</div>`;

  if (post.text) {
    html += `<div class="post-body">${textToHtml(post.text)}</div>`;
  }

  if (post.images && post.images.length > 0) {
    const imgs = post.images;
    const show = imgs.slice(0, 4);
    const extra = imgs.length - 4;
    const nClass = imgs.length === 1 ? 'n1' : imgs.length === 2 ? 'n2' : imgs.length === 3 ? 'n3' : imgs.length === 4 ? 'n4' : 'nN';
    const allSrcs = imgs.map(m => 'images/' + m.file);
    const dataSrcs = encodeURIComponent(JSON.stringify(allSrcs));
    html += `<div class="media-grid ${nClass}" data-srcs="${dataSrcs}">`;
    for (let i = 0; i < show.length; i++) {
      const img = show[i];
      const src = `images/${encodeURIComponent(img.file)}`;
      const alt = esc(img.title || img.description || '');
      if (i === 3 && extra > 0) {
        html += `<div class="more-images" data-idx="3">+${extra}</div>`;
      } else {
        html += `<img src="${src}" alt="${alt}" loading="lazy" data-idx="${i}">`;
      }
    }
    html += '</div>';
  }

  for (const ext of (post.external || [])) {
    if (!ext.url) continue;
    html += `<div class="ext-link"><a href="${esc(ext.url)}" target="_blank" rel="noopener">${esc(ext.name || ext.url)}</a></div>`;
  }

  html += '</article>';
  return html;
}

function renderPagination(totalPages, pageHashFn, month) {
  if (totalPages <= 1) return '';
  const prevHash = currentPage > 0
    ? (currentPage === 1 ? month : pageHashFn(currentPage)) : null;
  const nextHash = currentPage < totalPages - 1
    ? pageHashFn(currentPage + 2) : null;
  return `<div class="pagination">
    ${prevHash ? `<a class="pg-btn" href="#${prevHash}">&#8592; Newer</a>` : `<span class="pg-btn disabled">&#8592; Newer</span>`}
    <span class="page-info">${currentPage+1} / ${totalPages}</span>
    ${nextHash ? `<a class="pg-btn" href="#${nextHash}">Older &#8594;</a>` : `<span class="pg-btn disabled">Older &#8594;</span>`}
  </div>`;
}

// ── sidebar ───────────────────────────────────────────────────────────────────

function renderSidebar() {
  const ul = document.getElementById('month-list');
  ul.innerHTML = manifest.map(({month, count}) =>
    `<li><a href="#${month}" data-month="${month}">
      <span>${month}</span><span class="count">${count}</span>
    </a></li>`
  ).join('');
}

// ── lightbox ──────────────────────────────────────────────────────────────────

let lbImages = [];
let lbIndex = 0;

function openLightbox(srcs, idx) {
  lbImages = srcs;
  lbIndex = idx;
  document.getElementById('lightbox-img').src = lbImages[lbIndex];
  document.getElementById('lightbox').classList.add('open');
}

document.getElementById('main').addEventListener('click', e => {
  const target = e.target.closest('img[data-idx], .more-images[data-idx]');
  if (!target) return;
  const grid = target.closest('.media-grid[data-srcs]');
  if (!grid) return;
  const srcs = JSON.parse(decodeURIComponent(grid.dataset.srcs));
  const idx = parseInt(target.dataset.idx, 10);
  openLightbox(srcs, idx);
});

document.getElementById('lightbox').addEventListener('click', () => {
  document.getElementById('lightbox').classList.remove('open');
});

document.addEventListener('keydown', e => {
  const lb = document.getElementById('lightbox');
  if (!lb.classList.contains('open')) return;
  if (e.key === 'Escape') lb.classList.remove('open');
  if (e.key === 'ArrowRight') { lbIndex = (lbIndex+1) % lbImages.length; document.getElementById('lightbox-img').src = lbImages[lbIndex]; }
  if (e.key === 'ArrowLeft') { lbIndex = (lbIndex-1+lbImages.length) % lbImages.length; document.getElementById('lightbox-img').src = lbImages[lbIndex]; }
});

// ── utils ─────────────────────────────────────────────────────────────────────

function esc(s) {
  if (!s) return '';
  return s.replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;').replace(/"/g,'&quot;');
}

// URL regex operating on raw text (before HTML escaping).
// Matches http/https URLs including paths, query strings, and fragments.
// Trailing punctuation (.,;:!?) not part of the URL is excluded.
const URL_RE = /https?:\/\/[^\s\u3000-\u9fff\uff00-\uffef<>"']+/g;

function textToHtml(text) {
  if (!text) return '';
  let result = '';
  let last = 0;
  for (const m of text.matchAll(URL_RE)) {
    // Strip trailing punctuation that is unlikely part of the URL
    let url = m[0].replace(/[.,;:!?'")\]}>]+$/, '');
    result += esc(text.slice(last, m.index));
    result += `<a href="${esc(url)}" target="_blank" rel="noopener">${esc(url)}</a>`;
    last = m.index + url.length;
  }
  result += esc(text.slice(last));
  return result;
}

init();
</script>
</body>
</html>
"""

with open(os.path.join(OUT_DIR, 'index.html'), 'w', encoding='utf-8') as fh:
    fh.write(HTML)

print(f"\nDone!")
print(f"  {len(raw_posts)} posts, {len(manifest)} months")
print(f"  Site: {OUT_DIR}/index.html")
