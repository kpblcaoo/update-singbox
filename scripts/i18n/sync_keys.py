#!/usr/bin/env python3
import argparse
import os
import sys
import json
import re
from pathlib import Path
from collections import defaultdict

# --- CONFIG ---
DEFAULT_LANG_DIR = "src/sboxmgr/i18n"
TEMPLATE_FILE = ".template.json"
PY_FILE_PATTERN = re.compile(r"\.(py|pyi)$")
KEY_PATTERN = re.compile(r"(?:t|lang\.get)\(\s*['\"]([a-zA-Z0-9_.-]+)['\"]\s*(?:,|\))")
I18N_PREFIXES = ("cli.", "error.", "wizard.")

# --- UTILS ---
def find_py_files(root):
    for dirpath, _, files in os.walk(root):
        for f in files:
            if PY_FILE_PATTERN.search(f):
                yield os.path.join(dirpath, f)

def extract_keys_from_file(filepath):
    keys = set()
    with open(filepath, encoding="utf-8") as f:
        for line in f:
            for m in KEY_PATTERN.finditer(line):
                keys.add(m.group(1))
    return keys

def find_used_keys(src_root):
    all_keys = set()
    for pyfile in find_py_files(src_root):
        all_keys |= extract_keys_from_file(pyfile)
    return all_keys

def load_json(path):
    if not os.path.exists(path):
        return {}
    with open(path, encoding="utf-8") as f:
        return json.load(f)

def save_json(path, data):
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

def is_i18n_key(key):
    return key.startswith(I18N_PREFIXES)

# --- MAIN LOGIC ---
def main():
    parser = argparse.ArgumentParser(description="Sync and check i18n keys.")
    parser.add_argument("--lang-dir", default=DEFAULT_LANG_DIR, help="Directory with i18n .json files")
    parser.add_argument("--src", default="src/", help="Source code root for key search")
    parser.add_argument("--check", action="store_true", help="Check only (no changes)")
    parser.add_argument("--autofix", action="store_true", help="Add missing keys to en.json, create template for others")
    parser.add_argument("--remove-unused", action="store_true", help="Remove unused keys from all language files")
    parser.add_argument("--fail-on-unused", action="store_true", help="Fail if unused keys found")
    parser.add_argument("--fail-on-missing", action="store_true", help="Fail if missing keys found")
    parser.add_argument("--json", action="store_true", help="Output diff as JSON")
    parser.add_argument("--template", action="store_true", help="Write missing keys to .template.json for review")
    args = parser.parse_args()

    lang_dir = Path(args.lang_dir)
    src_root = args.src
    en_path = lang_dir / "en.json"
    lang_files = [p for p in lang_dir.glob("*.json") if p.name != TEMPLATE_FILE]
    all_langs = [p.stem for p in lang_files]

    used_keys = find_used_keys(src_root)
    used_keys = set(filter(is_i18n_key, used_keys))
    lang_data = {p.stem: load_json(p) for p in lang_files}

    missing = sorted(list(used_keys - set(lang_data.get("en", {}).keys())))
    unused = {lang: sorted([k for k in d if k not in used_keys]) for lang, d in lang_data.items()}

    # --- DIFF OUTPUT ---
    if args.json:
        print(json.dumps({"missing": missing, "unused": unused}, ensure_ascii=False, indent=2))
    else:
        if missing:
            print("[ERROR] Missing i18n keys:")
            for k in missing:
                print(f"+ {k}")
        for lang, keys in unused.items():
            if keys:
                print(f"[WARN] Unused i18n keys in {lang}.json:")
                for k in keys:
                    print(f"- {k}")
    
    # --- REMOVE UNUSED ---
    if args.remove_unused:
        removed_count = 0
        for lang, keys in unused.items():
            if keys:
                path = lang_dir / f"{lang}.json"
                d = lang_data.get(lang, {})
                for k in keys:
                    if k in d:
                        del d[k]
                        removed_count += 1
                save_json(path, d)
        if removed_count > 0:
            print(f"[INFO] Removed {removed_count} unused keys from language files.")
        else:
            print("[INFO] No unused keys found to remove.")
    
    # --- TEMPLATE ---
    if args.template and missing:
        template_path = lang_dir / TEMPLATE_FILE
        save_json(template_path, {k: "" for k in missing})
        print(f"[INFO] Template with missing keys written to {template_path}")
    
    # --- AUTOFIX ---
    if args.autofix and missing:
        # en.json: автозаполнение ключом
        en = lang_data.get("en", {})
        for k in missing:
            en[k] = k
        save_json(en_path, en)
        # остальные языки: пустые строки
        for lang in all_langs:
            if lang == "en":
                continue
            path = lang_dir / f"{lang}.json"
            d = lang_data.get(lang, {})
            for k in missing:
                d.setdefault(k, "")
            save_json(path, d)
        print(f"[INFO] Missing keys added to en.json and other languages.")
    
    # --- EXIT CODE ---
    fail = False
    if args.fail_on_missing and missing:
        fail = True
    if args.fail_on_unused and any(unused.values()):
        fail = True
    if fail:
        sys.exit(1)

if __name__ == "__main__":
    main() 