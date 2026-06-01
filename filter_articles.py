import json
import re
import argparse
import sys
from pathlib import Path
from html import unescape

JUNK_PATTERNS = [
    r"Getty Images",
    r"Image source,.*",
    r"Image caption,.*",
    r"This video can not be played.*",
    r"To play this video.*",
    r"Share this article.*",
    r"Read more:.*",
    r"\bAdvertisement\b",
    r"Follow BBC.*on.*",
    r"You may also like.*",
    r"\[.*?\]",
]
JUNK_RE      = re.compile("|".join(JUNK_PATTERNS), re.IGNORECASE)
WHITESPACE_RE = re.compile(r"\s{2,}")


def clean_text(text: str) -> str:
    text = unescape(text)
    text = JUNK_RE.sub("", text)
    return WHITESPACE_RE.sub(" ", text).strip()


def filter_articles(input_path="raw_articles.json", output_path="clean_articles.json",
                    min_words=80, sections_filter=None):

    path = Path(input_path)
    if not path.exists():
        sys.exit(f"[ERROR] Not found: {input_path}")

    # utf-8 explicit — fixes Windows cp1252 UnicodeDecodeError
    with open(path, encoding="utf-8") as f:
        raw = json.load(f)

    print(f"[INFO] Loaded {len(raw)} raw articles from {input_path}\n")

    cleaned, seen = [], set()
    stats = dict(total=len(raw), kept=0, bad_url=0, duplicate=0, no_body=0, short=0, section=0)

    for a in raw:
        url = (a.get("url") or "").strip()

        # Valid BBC URL
        if not ("bbc.co.uk" in url or "bbc.com" in url):
            stats["bad_url"] += 1; continue

        # Deduplicate
        if url in seen:
            stats["duplicate"] += 1; continue
        seen.add(url)

        # Section filter
        if sections_filter:
            if not any(s.lower() in (a.get("section") or "").lower() for s in sections_filter):
                stats["section"] += 1; continue

        headline  = clean_text(a.get("headline",  ""))
        body_text = clean_text(a.get("body_text", ""))

        if not headline or not body_text:
            stats["no_body"] += 1; continue

        wc = len(body_text.split())
        if wc < min_words:
            stats["short"] += 1; continue

        cleaned.append({
            "url":            url,
            "headline":       headline,
            "description":    clean_text(a.get("description", "")),
            "author":         clean_text(a.get("author", "")),
            "published_date": a.get("published_date", ""),
            "section":        clean_text(a.get("section", "")),
            "tags":           [clean_text(t) for t in a.get("tags", []) if t.strip()],
            "body_text":      body_text,
            "word_count":     wc,
            "images":         a.get("images", []),
            "scraped_at":     a.get("scraped_at", ""),
        })
        stats["kept"] += 1

    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(cleaned, f, ensure_ascii=False, indent=2)

    print("=" * 52)
    print("  FILTERING SUMMARY")
    print("=" * 52)
    print(f"  Total raw articles   : {stats['total']}")
    print(f"  ✅ Kept (clean)      : {stats['kept']}")
    print(f"  ❌ Bad URL           : {stats['bad_url']}")
    print(f"  ❌ Duplicate         : {stats['duplicate']}")
    print(f"  ❌ No body/headline  : {stats['no_body']}")
    print(f"  ❌ Too short         : {stats['short']}")
    print(f"  ❌ Section mismatch  : {stats['section']}")
    print("=" * 52)
    print(f"\n✅ Clean file saved → {Path(output_path).resolve()}\n")


if __name__ == "__main__":
    p = argparse.ArgumentParser()
    p.add_argument("--input",     default="raw_articles.json")
    p.add_argument("--output",    default="clean_articles.json")
    p.add_argument("--min-words", type=int, default=80)
    p.add_argument("--sections",  default="",
                   help="e.g. world,technology,india,sport")
    args = p.parse_args()

    sections = [s.strip() for s in args.sections.split(",") if s.strip()] or None
    filter_articles(args.input, args.output, args.min_words, sections)
