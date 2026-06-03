import re


def load_markdown(md_path: str, publisher: str, category: str,
                   source_name: str = "", year: int | None = None,
                   author: str = "", book_title: str = "") -> list[dict]:
    """Load a markdown file and split into sections by ## headings.

    Consecutive sections with the same chapter name (from page-break markers)
    are merged into one section.

    Returns list of {"text": str, "metadata": {...}} for each section.
    """
    with open(md_path, 'r', encoding='utf-8') as f:
        text = f.read()

    raw_sections = []
    # Split on ## headings (level-2 only, not ### which are page markers)
    parts = re.split(r'\n(?=## (?!#))', text)

    # First part before any ## heading is front matter
    front = parts[0].strip()
    if front and len(front) > 100:
        front_heading = _strip_page_num(_extract_main_title(front))
        raw_sections.append({
            "text": front,
            "chapter": "前言",
            "section_id": _make_section_id(source_name or publisher, "front_matter"),
        })

    for part in parts[1:]:
        heading_match = re.match(r'## (.+)', part)
        if not heading_match:
            continue
        raw_heading = heading_match.group(1).strip()
        heading = _strip_page_num(raw_heading)
        content = part[heading_match.end():].strip()

        if len(content) < 100:
            continue

        raw_sections.append({
            "text": content,
            "chapter": heading,
            "section_id": _make_section_id(source_name or publisher, heading),
        })

    # Merge consecutive sections with the same chapter name
    merged = []
    for sec in raw_sections:
        if merged and sec["chapter"] == merged[-1]["chapter"]:
            merged[-1]["text"] += "\n\n" + sec["text"]
        else:
            merged.append(sec)

    # Rebuild section_ids to ensure uniqueness after merging
    results = []
    seen_ids = set()
    chapter_counts = {}
    for sec in merged:
        ch = sec["chapter"]
        chapter_counts[ch] = chapter_counts.get(ch, 0) + 1
        sid = _make_section_id(source_name or publisher, f"{ch}_{chapter_counts[ch]}")

        # Guarantee uniqueness: append counter if collision (can happen when
        # chapter names differ only in Unicode variants that get normalized away)
        if sid in seen_ids:
            dedup_i = 2
            while f"{sid}__{dedup_i}" in seen_ids:
                dedup_i += 1
            sid = f"{sid}__{dedup_i}"
        seen_ids.add(sid)

        results.append({
            "text": sec["text"],
            "metadata": {
                "section_id": sid,
                "book": book_title or "马克斯·韦伯的生平、著述及影响",
                "chapter": ch,
                "level": 1,
                "publisher": publisher,
                "author": author,
                "source_category": category,
                "source_name": source_name,
                "chunk_size": 512,
                "chunk_overlap": 128,
            },
        })
        if year is not None:
            results[-1]["metadata"]["year"] = str(year)

    return results


def _strip_page_num(heading: str) -> str:
    """Strip trailing page numbers like ' 133' or '127' from heading."""
    return re.sub(r'\s+\d{1,3}\s*$', '', heading).strip()


def _extract_main_title(text: str) -> str:
    """Extract the first # heading from front matter."""
    m = re.search(r'^# (.+)$', text, re.MULTILINE)
    return m.group(1).strip() if m else "前言"


def _make_section_id(prefix: str, heading: str) -> str:
    safe = re.sub(r'[^a-zA-Z0-9一-鿿_\-]', '_', heading)
    safe = re.sub(r'_+', '_', safe)
    safe = safe.strip('_')
    # Truncate to leave room for prefix and separator (ChromaDB ID limit is large
    # but keep it reasonable; 200 chars total is plenty for uniqueness)
    max_heading_len = 200 - len(prefix) - 1
    if len(safe) > max_heading_len:
        safe = safe[:max_heading_len]
    return f"{prefix}_{safe}"
