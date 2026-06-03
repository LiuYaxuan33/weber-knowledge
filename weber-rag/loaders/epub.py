import re
from urllib.parse import unquote
from bs4 import BeautifulSoup
import ebooklib
from ebooklib import epub


def load_epub(epub_path: str, publisher: str, category: str,
              source_name: str = "", year: int | None = None,
              author: str = "") -> list[dict]:
    """Load an EPUB and return a list of sections with metadata.

    Each section: {"text": str, "metadata": {"section_id": str, "book": str, ...}}
    """
    book = epub.read_epub(epub_path)
    toc = _parse_ncx(book)  # list of {title, href, level, children}
    html_texts, anchor_positions = _extract_html(book)  # texts + anchor positions
    file_index = _build_file_index(toc)  # {file_part: [entry_title, ...]}
    fragment_map = _build_fragment_map(toc)  # {file_part: {title: fragment, ...}}

    sections = []
    _flatten_toc(toc, html_texts, sections, file_index, publisher, category,
                 parent_book="", source_name=source_name,
                 year=year, author=author,
                 anchor_positions=anchor_positions,
                 fragment_map=fragment_map)

    # Fallback: if TOC produced no sections (e.g. TOC points to image-only
    # pages), scan all HTML files and treat each as a chapter.
    if len(sections) == 0 and len(html_texts) > 0:
        sections = _fallback_html_scan(html_texts, publisher, category,
                                        source_name, year, author)

    return sections


def _parse_ncx(book) -> list[dict]:
    """Parse NCX table of contents into a tree structure.

    Falls back to EPUB3 NAV (book.toc) if NCX is absent.
    """
    ncx_item = book.get_item_with_id('ncx')
    if ncx_item:
        ncx_xml = ncx_item.get_content().decode('utf-8')
        soup = BeautifulSoup(ncx_xml, 'xml')
        navmap = soup.find('navMap')
        if navmap:
            return _parse_navpoints(navmap.find_all('navPoint', recursive=False), level=0)

    # EPUB3: no NCX — try ebooklib's parsed NAV toc
    try:
        return _parse_ebooklib_toc(book.toc, level=0)
    except Exception:
        return []


def _parse_ebooklib_toc(toc_entries, level: int) -> list[dict]:
    """Parse ebooklib's book.toc (EPUB3 NAV) into our tree format."""
    result = []
    for item in toc_entries:
        if isinstance(item, epub.Link):
            result.append({
                "title": item.title or "",
                "href": item.href or "",
                "level": level,
                "children": [],
            })
        elif isinstance(item, tuple):
            parent, children = item[0], item[1]
            title = parent.title if hasattr(parent, 'title') else ""
            href = parent.href if hasattr(parent, 'href') and not isinstance(parent, epub.Section) else ""
            result.append({
                "title": title or "",
                "href": href or "",
                "level": level,
                "children": _parse_ebooklib_toc(children, level + 1),
            })
    return result


def _parse_navpoints(navpoints, level: int) -> list[dict]:
    """Recursively parse navPoint elements."""
    result = []
    for np in navpoints:
        label = np.find('navLabel')
        title = label.text.strip() if label and label.find('text') else ""
        content = np.find('content')
        src = content.get('src', '') if content else ""

        entry = {
            "title": title,
            "href": src,
            "level": level,
            "children": _parse_navpoints(np.find_all('navPoint', recursive=False), level + 1),
        }
        result.append(entry)
    return result


def _extract_html(book) -> tuple[dict[str, str], dict[str, dict[str, int]]]:
    """Extract clean text from all HTML documents in the EPUB.

    Returns:
        texts: dict mapping href (filename) to clean text
        anchor_positions: dict mapping filename -> {anchor_id: text_position}

    Inserts markers at anchor element positions so we can later locate
    section boundaries precisely using the NCX fragment identifiers.
    """
    ANCHOR_MARKER = '\nANCHOR\n'

    BLOCK_TAGS = {'p', 'div', 'h1', 'h2', 'h3', 'h4', 'h5', 'h6',
                  'li', 'tr', 'section', 'article', 'header', 'blockquote',
                  'table', 'hr', 'pre', 'figure', 'figcaption'}

    texts = {}
    anchor_positions = {}

    for item in book.get_items():
        if item.get_type() != ebooklib.ITEM_DOCUMENT:
            continue
        name = item.get_name()
        content = item.get_content().decode('utf-8', errors='replace')

        # 1. Replace <br> with newlines
        content = re.sub(r'<br\s*/?>', '\n', content)

        # 2. Parse HTML and insert anchor markers inside elements with IDs
        soup = BeautifulSoup(content, 'html.parser')
        for elem in soup.find_all(id=True):
            anchor_id = elem['id']
            marker = soup.new_string(
                f'{ANCHOR_MARKER}{anchor_id}{ANCHOR_MARKER}')
            elem.insert(0, marker)

        # 3. Add \n\n after block-level closing tags in the modified HTML
        html_str = str(soup)
        for tag in BLOCK_TAGS:
            html_str = re.sub(
                rf'</{tag}\s*>',
                f'</{tag}>\n\n',
                html_str,
                flags=re.IGNORECASE
            )

        # 4. Extract text
        soup2 = BeautifulSoup(html_str, 'html.parser')
        text = soup2.get_text(separator='', strip=True)

        # 5. Clean up whitespace
        text = re.sub(r'[ \t]+\n', '\n', text)
        text = re.sub(r'\n[ \t]+', '\n', text)
        text = re.sub(r'\n{3,}', '\n\n', text)
        text = re.sub(r'(\n\n)+', '\n\n', text)
        text = text.strip()

        # 6. Find marker positions, then remove markers
        file_anchors = {}
        for m in re.finditer(r'\n?ANCHOR\n?([^]+)ANCHOR\n?', text):
            anchor_id = m.group(1).strip()
            pos = m.start()
            file_anchors[anchor_id] = pos

        # Remove markers from text
        text = re.sub(r'\n?ANCHOR\n?[^]+ANCHOR\n?', '', text)
        text = text.strip()

        texts[name] = text
        if file_anchors:
            anchor_positions[name] = file_anchors

    return texts, anchor_positions


def _build_file_index(toc: list[dict]) -> dict[str, list[str]]:
    """Walk TOC and map each HTML file to the ordered list of entry titles within it."""
    index: dict[str, list[str]] = {}
    _collect_toc_info(toc, index, None)
    return index


def _build_fragment_map(toc: list[dict]) -> dict[str, dict[str, str]]:
    """Walk TOC and map each HTML file to {title: fragment} for anchor lookups."""
    fmap: dict[str, dict[str, str]] = {}
    _collect_toc_info(toc, None, fmap)
    return fmap


def _collect_toc_info(entries: list[dict], index: dict | None,
                       fmap: dict | None):
    for entry in entries:
        href = entry.get("href", "")
        title = entry.get("title", "")
        if href and title:
            href = unquote(href)
            file_part = href.split('#')[0] if '#' in href else href
            fragment = href.split('#')[1] if '#' in href else None
            if index is not None:
                index.setdefault(file_part, []).append(title)
            if fmap is not None:
                fmap.setdefault(file_part, {})[title] = fragment
        if entry.get("children"):
            _collect_toc_info(entry["children"], index, fmap)


def _flatten_toc(toc: list[dict], html_texts: dict[str, str],
                 sections: list, file_index: dict[str, list[str]],
                 publisher: str, category: str,
                 parent_book: str = "", source_name: str = "",
                 year: int | None = None, author: str = "",
                 anchor_positions: dict | None = None,
                 fragment_map: dict | None = None):
    """Walk TOC tree, extract text for each section, and append to sections list."""
    if anchor_positions is None:
        anchor_positions = {}
    for entry in toc:
        title = entry["title"]
        if not title:
            continue

        # Determine book name
        book_name = parent_book
        if entry["level"] == 0 and not parent_book:
            book_name = source_name or title

        # Get text content for this entry
        text = _get_text_for_entry(entry, html_texts, file_index,
                                    anchor_positions, fragment_map)

        if len(text) < 30:
            # Skip front-matter fluff but recurse into children
            if entry["children"]:
                _flatten_toc(entry["children"], html_texts, sections,
                            file_index, publisher, category, book_name, source_name,
                            year=year, author=author,
                            anchor_positions=anchor_positions,
                            fragment_map=fragment_map)
            continue

        # Build hierarchical path: book > chapter > section
        section_id = _make_section_id(source_name or publisher,
                                      entry["href"] + "_" + title)
        metadata = {
            "section_id": section_id,
            "book": book_name,
            "chapter": title,
            "level": entry["level"],
            "publisher": publisher,
            "author": author,
            "source_category": category,
            "source_name": source_name,
            "href": entry["href"],
            "chunk_size": 512,
            "chunk_overlap": 128,
        }
        if year is not None:
            metadata["year"] = str(year)
        sections.append({"text": text, "metadata": metadata})

        # Recurse into children
        if entry["children"]:
            _flatten_toc(entry["children"], html_texts, sections,
                        file_index, publisher, category, book_name, source_name,
                        year=year, author=author,
                        anchor_positions=anchor_positions,
                        fragment_map=fragment_map)


def _get_text_for_entry(entry: dict, html_texts: dict[str, str],
                        file_index: dict[str, list[str]],
                        anchor_positions: dict | None = None,
                        fragment_map: dict | None = None) -> str:
    """Extract the text content for a TOC entry from HTML documents."""
    href = entry["href"]
    if not href:
        return ""

    href = unquote(href)

    if '#' in href:
        file_part = href.split('#', 1)[0]
        fragment = href.split('#', 1)[1]
    else:
        file_part = href
        fragment = None

    doc_text = _find_html_text(file_part, html_texts)
    if not doc_text:
        return ""

    if anchor_positions is None:
        anchor_positions = {}
    if fragment_map is None:
        fragment_map = {}
    return _extract_section_text(doc_text, entry, file_part, file_index,
                                 fragment, anchor_positions, fragment_map)


def _find_html_text(file_part: str, html_texts: dict[str, str]) -> str:
    """Find HTML text by file path, trying variants (URL-encoded, basename, etc.)."""
    if file_part in html_texts:
        return html_texts[file_part]

    # Strip leading path prefix and try both encoded / decoded basenames
    basename = file_part.split('/')[-1] if '/' in file_part else file_part
    basename = basename.split('\\')[-1] if '\\' in basename else basename

    # Also URL-decode the basename in case we got an encoded path
    basename_decoded = unquote(basename)

    for key in html_texts:
        key_basename = key.split('/')[-1] if '/' in key else key
        key_basename = key_basename.split('\\')[-1] if '\\' in key_basename else key_basename
        if basename_decoded == key_basename or basename == key_basename:
            return html_texts[key]

    # Last resort: try partial match
    for key in html_texts:
        if basename in key or key.endswith(file_part) or basename_decoded in key:
            return html_texts[key]

    return ""


def _normalize_title(t: str) -> str:
    """Normalize a title for matching: collapse whitespace variants, strip
    footnote markers like [3], and normalize full-width punctuation."""
    import unicodedata
    # Replace full-width spaces and other Unicode spaces with ASCII space
    t = re.sub(r'[　  -   ]', ' ', t)
    # Normalize full-width punctuation to half-width equivalents
    t = t.replace('：', ':')   # full-width colon →
    t = t.replace('（', '(')   # full-width left paren
    t = t.replace('）', ')')   # full-width right paren
    t = t.replace('，', ',')   # full-width comma
    t = t.replace('；', ';')   # full-width semicolon
    t = t.replace('．', '.')   # full-width period
    # Normalize Unicode (NFKC handles many compat chars but not all spaces)
    t = unicodedata.normalize('NFKC', t)
    # Strip footnote markers like [3], [12] — but only at end of title
    t = re.sub(r'\[\d+\]\s*$', '', t)
    # Collapse multiple spaces
    t = re.sub(r'\s+', ' ', t)
    return t.strip()


def _find_title_in_text(doc_text: str, title: str) -> int:
    """Find a title in document text, trying multiple matching strategies.
    Returns position in original doc_text or -1 if not found.

    Uses only 1:1 character normalization so positions stay aligned with
    the original text (no whitespace collapsing that would shift indices).
    For short titles (≤3 chars), requires the match to be at a paragraph
    boundary to avoid false matches inside running text.
    """
    # 1. Exact match (with boundary check for short titles)
    pos = doc_text.find(title)
    if pos >= 0 and _is_heading_boundary(doc_text, pos, title):
        return pos

    # 2. 1:1 character normalization
    norm_doc = _char_normalize(doc_text)
    norm_title = _char_normalize(title)
    pos = _search_with_boundary(norm_doc, norm_title, doc_text)
    if pos >= 0:
        return pos

    # 3. Try with ALL bracketed numbers stripped
    strip_brackets = lambda s: re.sub(r'\[\d+\]', '', s)
    clean_title = strip_brackets(norm_title)
    if clean_title != norm_title:
        clean_doc = strip_brackets(norm_doc)
        pos = _search_with_boundary(clean_doc, clean_title, doc_text)
        if pos >= 0:
            return pos

    return -1


def _is_heading_boundary(text: str, pos: int, title: str) -> bool:
    """Check if a match at `pos` looks like a section heading (at paragraph
    start) rather than an inline occurrence. Only enforced for short titles
    (≤3 chars) where false positives are likely."""
    if len(title) > 3:
        return True  # long titles are distinctive enough
    # Must be at start of text, after a newline, or after a full-width space
    if pos == 0:
        return True
    before = text[pos - 1]
    return before in ('\n', '　', ' ')


def _search_with_boundary(norm_doc: str, norm_title: str,
                           orig_doc: str) -> int:
    """Search for norm_title in norm_doc, requiring heading boundary for
    short titles. Returns position in orig_doc."""
    search_start = 0
    while True:
        pos = norm_doc.find(norm_title, search_start)
        if pos < 0:
            return -1
        if _is_heading_boundary(norm_doc, pos, norm_title):
            return pos
        search_start = pos + 1


def _char_normalize(s: str) -> str:
    """Apply only 1:1 character replacements for matching.
    No length-changing transforms (no whitespace collapse, no NFKC).
    """
    import unicodedata
    # Full-width → half-width (all 1:1)
    s = s.replace('　', ' ')   # full-width space → ASCII space
    s = s.replace('：', ':')   # full-width colon
    s = s.replace('（', '(')   # full-width left paren
    s = s.replace('）', ')')   # full-width right paren
    s = s.replace('，', ',')   # full-width comma
    s = s.replace('；', ';')   # full-width semicolon
    s = s.replace('．', '.')   # full-width period
    # NFKC normalization (almost always 1:1 for CJK contexts)
    s = unicodedata.normalize('NFKC', s)
    return s


def _flex_match(text: str, target: str) -> int:
    """Fallback: search for target in text with flexible whitespace between
    chars. Used when 1:1 normalization isn't enough."""
    if len(target) < 3:
        return text.find(target)
    fingerprint = target[:min(15, len(target))]
    pattern = r'[\s　]*'.join(re.escape(c) for c in fingerprint)
    m = re.search(pattern, text)
    return m.start() if m else -1


def _extract_section_text(doc_text: str, entry: dict, file_part: str,
                          file_index: dict[str, list[str]],
                          fragment: str | None = None,
                          anchor_positions: dict | None = None,
                          fragment_map: dict | None = None) -> str:
    """Extract text for one TOC entry from its HTML document.

    Uses anchor positions from NCX fragment identifiers when available,
    falls back to text matching when anchors are absent.
    """
    if anchor_positions is None:
        anchor_positions = {}
    if fragment_map is None:
        fragment_map = {}
    titles_in_file = file_index.get(file_part, [])
    title = entry["title"]

    if len(titles_in_file) <= 1 or title not in titles_in_file:
        return doc_text

    pos = titles_in_file.index(title)
    file_anchors = anchor_positions.get(file_part, {})
    file_fragments = fragment_map.get(file_part, {})  # {title: fragment}

    start = _find_start(doc_text, title, fragment, file_anchors)
    end = _find_end(doc_text, titles_in_file, pos, file_anchors,
                    file_fragments, start)

    if start is not None and end is not None and end > start:
        return doc_text[start:end].strip()
    elif start is not None and end is None:
        return doc_text[start:].strip()
    elif start is None and pos == 0:
        return doc_text
    else:
        return ""


def _find_start(doc_text: str, title: str, fragment: str | None,
                file_anchors: dict) -> int | None:
    """Find the start position of a section within a document.
    Priority: anchor position > text match."""
    if fragment and fragment in file_anchors:
        return file_anchors[fragment]
    return _text_search(doc_text, title)


def _find_end(doc_text: str, titles_in_file: list, pos: int,
              file_anchors: dict, file_fragments: dict,
              start: int | None) -> int | None:
    """Find the end position (start of next section).
    Returns None if this is the last entry.
    Tries: next entry's anchor position > text search."""
    if pos + 1 >= len(titles_in_file):
        return None

    next_title = titles_in_file[pos + 1]

    # 1. Try next entry's anchor fragment
    next_fragment = file_fragments.get(next_title)
    if next_fragment and next_fragment in file_anchors:
        return file_anchors[next_fragment]

    # 2. Text search
    end = _text_search(doc_text, next_title)
    if end is not None and (start is None or end > start):
        return end

    return None


def _text_search(doc_text: str, title: str) -> int | None:
    """Search for a title in document text with normalization.
    Returns position or None."""
    # 1. Exact match
    pos = doc_text.find(title)
    if pos >= 0:
        return pos

    # 2. Char-normalized match (full-width → half-width, 1:1)
    import unicodedata
    def cnorm(s):
        s = s.replace('　', ' ').replace('：', ':').replace('（', '(')
        s = s.replace('）', ')').replace('，', ',').replace('；', ';')
        s = s.replace('．', '.')
        s = unicodedata.normalize('NFKC', s)
        return s

    ndoc = cnorm(doc_text)
    ntitle = cnorm(title)
    pos = ndoc.find(ntitle)
    if pos >= 0:
        return pos

    # 3. Strip footnote markers and retry
    import re
    clean_title = re.sub(r'\[\d+\]', '', ntitle)
    if clean_title != ntitle:
        clean_doc = re.sub(r'\[\d+\]', '', ndoc)
        pos = clean_doc.find(clean_title)
        if pos >= 0:
            return pos

    return None


def _make_section_id(publisher: str, href: str) -> str:
    """Create a unique section ID from publisher and href."""
    safe_href = re.sub(r'[^a-zA-Z0-9_\-]', '_', href)
    return f"{publisher}_{safe_href}"


def _fallback_html_scan(html_texts: dict[str, str], publisher: str,
                          category: str, source_name: str = "",
                          year: int | None = None,
                          author: str = "") -> list[dict]:
    """Fallback when TOC-based loading produces no sections.

    Scans all HTML files, skipping image-only pages and front matter,
    treating each remaining file as one chapter. Detects volume boundaries
    by looking for second copyright page (CIP data).
    """
    SKIP_IF_CONTAINS = ['图字：', '图书在版编目', '内容简介', '英文版权页',
                         '出版前言', '目录']

    sections = []
    sorted_keys = sorted(html_texts.keys(),
                         key=lambda k: (len(k), k))

    # Detect volumes: a second "图书在版编目" page marks vol.2
    volume = 1
    vol_title = source_name

    for file_key in sorted_keys:
        text = html_texts[file_key].strip()
        if len(text) < 500:
            continue

        # Detect volume boundary: second CIP page
        if '图书在版编目' in text[:200]:
            if volume == 1 and len(sections) > 0:
                volume = 2
                vol_title = f'{source_name}（第12卷）'
            if volume == 1:
                vol_title = f'{source_name}（第11卷）'
            continue

        # Skip other front matter
        should_skip = False
        for marker in SKIP_IF_CONTAINS:
            if marker in text[:200]:
                should_skip = True
                break
        if should_skip:
            continue

        first_line = text.split('\n')[0].strip()
        if len(first_line) > 50:
            first_line = first_line[:50]
        if not first_line:
            first_line = file_key.split('/')[-1].replace('.xhtml', '').replace('.html', '')

        # Skip index pages (just name/term lists, useless for RAG)
        if first_line.startswith('索引'):
            continue

        section_id = _make_section_id(source_name or publisher,
                                       file_key + "_" + first_line)
        sections.append({
            "text": text,
            "metadata": {
                "section_id": section_id,
                "book": vol_title,
                "chapter": first_line,
                "level": 1,
                "publisher": publisher,
                "author": author,
                "source_category": category,
                "source_name": source_name,
                "href": file_key,
                "chunk_size": 512,
                "chunk_overlap": 128,
            },
        })
        if year is not None:
            sections[-1]["metadata"]["year"] = str(year)

    return sections
