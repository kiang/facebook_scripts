#!/usr/bin/env python3
"""
Merge Facebook backup DIR2 (recent) into DIR1 (full).
For JSON files that exist in both: merge arrays, deduplicate by content hash.
For files only in DIR2: already copied by cp -rn, skip.
"""

import json
import os
import hashlib
import sys

DIR1 = "facebook-kolctw-2026-3-6"
DIR2 = "facebook-kolctw-2026-4-7-isMpSCJ9"

def item_key(item):
    """Stable dedup key for a JSON object."""
    return hashlib.md5(json.dumps(item, sort_keys=True, ensure_ascii=False).encode()).hexdigest()

def get_array(data):
    """Extract the main array from various Facebook JSON structures."""
    if isinstance(data, list):
        return data, None  # (items, key_in_dict)
    if isinstance(data, dict):
        for key, val in data.items():
            if isinstance(val, list):
                return val, key
    return None, None

def merge_json_file(rel_path):
    path1 = os.path.join(DIR1, rel_path)
    path2 = os.path.join(DIR2, rel_path)

    if not os.path.exists(path2):
        return  # nothing to merge

    with open(path1, encoding='utf-8') as f:
        data1 = json.load(f)
    with open(path2, encoding='utf-8') as f:
        data2 = json.load(f)

    items1, key1 = get_array(data1)
    items2, key2 = get_array(data2)

    if items1 is None or items2 is None:
        print(f"  SKIP (not array-based): {rel_path}")
        return

    seen = {item_key(i) for i in items1}
    new_items = [i for i in items2 if item_key(i) not in seen]

    if not new_items:
        print(f"  no new items: {rel_path}")
        return

    merged = items1 + new_items
    print(f"  +{len(new_items)} items -> {len(merged)} total: {rel_path}")

    if key1 is None:
        out = merged
    else:
        out = dict(data1)
        out[key1] = merged

    with open(path1, 'w', encoding='utf-8') as f:
        json.dump(out, f, ensure_ascii=False, separators=(',', ':'))

# Walk all JSON files in DIR2 and merge into DIR1
merged_count = 0
skipped_count = 0

for root, dirs, files in os.walk(DIR2):
    for fname in files:
        if not fname.endswith('.json'):
            continue
        full2 = os.path.join(root, fname)
        rel = os.path.relpath(full2, DIR2)
        full1 = os.path.join(DIR1, rel)

        if not os.path.exists(full1):
            # Should have been copied by cp -rn already
            print(f"  MISSING in DIR1 (not copied?): {rel}")
            continue

        merge_json_file(rel)
        merged_count += 1

print(f"\nDone. Processed {merged_count} JSON files.")
