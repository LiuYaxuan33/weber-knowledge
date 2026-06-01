import re
from bs4 import BeautifulSoup
import ebooklib
from ebooklib import epub


def load_epub(epub_path: str, edition: str, category: str,
              source_name: str = "") -> list[dict]:
    """Load an EPUB and return a list of sections with metadata.

    Each section: {"text": str, "metadata": {"section_id": str, "book": str, ...}}
    """
    book = epub.read_epub(epub_path)
    toc = _parse_ncx(book)  # list of {title, href, level, children}
    html_texts = _extract_html(book)  # dict: href_base -> clean text
    file_index = _build_file_index(toc)  # {file_part: [entry_title, ...]}

    sections = []
    _flatten_toc(toc, html_texts, sections, file_index, edition, category,
                 parent_book="", source_name=source_name)
    return sections


def _parse_ncx(book) -> list[dict]:
    """Parse NCX table of contents into a tree structure."""
    ncx_item = book.get_item_with_id('ncx')
    if not ncx_item:
        return []
    ncx_xml = ncx_item.get_content().decode('utf-8')
    soup = BeautifulSoup(ncx_xml, 'xml')

    navmap = soup.find('navMap')
    if not navmap:
        return []

    return _parse_navpoints(navmap.find_all('navPoint', recursive=False), level=0)


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


def _extract_html(book) -> dict[str, str]:
    """Extract clean text from all HTML documents in the EPUB.

    Returns dict mapping href (filename#anchor) to clean text.
    """
    texts = {}
    for item in book.get_items():
        if item.get_type() != ebooklib.ITEM_DOCUMENT:
            continue
        name = item.get_name()
        content = item.get_content().decode('utf-8', errors='replace')
        soup = BeautifulSoup(content, 'html.parser')
        body = soup.find('body')
        if body:
            text = body.get_text(separator='\n', strip=True)
        else:
            text = soup.get_text(separator='\n', strip=True)
        texts[name] = text
    return texts


def _build_file_index(toc: list[dict]) -> dict[str, list[str]]:
    """Walk TOC and map each HTML file to the ordered list of entry titles within it.

    This enables splitting a shared HTML document into per-section text
    instead of returning the whole file for every entry.
    """
    index: dict[str, list[str]] = {}
    _collect_titles(toc, index)
    return index


def _collect_titles(entries: list[dict], index: dict[str, list[str]]):
    for entry in entries:
        href = entry.get("href", "")
        title = entry.get("title", "")
        if href and title:
            file_part = href.split('#')[0] if '#' in href else href
            index.setdefault(file_part, []).append(title)
        if entry.get("children"):
            _collect_titles(entry["children"], index)


def _flatten_toc(toc: list[dict], html_texts: dict[str, str],
                 sections: list, file_index: dict[str, list[str]],
                 edition: str, category: str,
                 parent_book: str = "", source_name: str = ""):
    """Walk TOC tree, extract text for each section, and append to sections list."""
    for entry in toc:
        title = entry["title"]
        if not title:
            continue

        # Determine book name
        book_name = parent_book
        if entry["level"] == 0:
            book_name = title

        # Get text content for this entry
        text = _get_text_for_entry(entry, html_texts, file_index)

        if len(text) < 30:
            # Skip front-matter fluff but recurse into children
            if entry["children"]:
                _flatten_toc(entry["children"], html_texts, sections,
                            file_index, edition, category, book_name, source_name)
            continue

        # Build hierarchical path: book > chapter > section
        section_id = _make_section_id(edition, entry["href"])
        metadata = {
            "section_id": section_id,
            "book": book_name,
            "chapter": title,
            "level": entry["level"],
            "edition": edition,
            "source_category": category,
            "source_name": source_name,
            "href": entry["href"],
            "chunk_size": 512,
            "chunk_overlap": 128,
        }
        sections.append({"text": text, "metadata": metadata})

        # Recurse into children
        if entry["children"]:
            _flatten_toc(entry["children"], html_texts, sections,
                        file_index, edition, category, book_name, source_name)


def _get_text_for_entry(entry: dict, html_texts: dict[str, str],
                        file_index: dict[str, list[str]]) -> str:
    """Extract the text content for a TOC entry from HTML documents."""
    href = entry["href"]
    if not href:
        return ""

    if '#' in href:
        file_part = href.split('#', 1)[0]
    else:
        file_part = href

    doc_text = _find_html_text(file_part, html_texts)
    if not doc_text:
        return ""

    return _extract_section_text(doc_text, entry, file_part, file_index)


def _find_html_text(file_part: str, html_texts: dict[str, str]) -> str:
    """Find HTML text by file path, trying variants."""
    if file_part in html_texts:
        return html_texts[file_part]
    # Try without 'text/' prefix or with it
    basename = file_part.replace('text/', '')
    for key in html_texts:
        if basename in key or key.endswith(file_part):
            return html_texts[key]
    return ""


def _extract_section_text(doc_text: str, entry: dict, file_part: str,
                          file_index: dict[str, list[str]]) -> str:
    """Extract text for one TOC entry from its HTML document.

    If the document is shared by multiple entries (file_index), extracts
    only the portion between this entry's title and the next entry's title.
    Otherwise returns the whole document.
    """
    titles_in_file = file_index.get(file_part, [])
    title = entry["title"]

    # Single-entry file — safe to return all text
    if len(titles_in_file) <= 1 or title not in titles_in_file:
        return doc_text

    # Find this entry's position among siblings
    pos = titles_in_file.index(title)
    start = doc_text.find(title)
    if start < 0:
        return doc_text  # title not found in body, return whole doc as fallback

    # Find where the next section starts
    if pos + 1 < len(titles_in_file):
        next_title = titles_in_file[pos + 1]
        end = doc_text.find(next_title, start + len(title))
        if end > start:
            return doc_text[start:end].strip()

    # Last entry in this file — take from title to end
    return doc_text[start:].strip()


def _make_section_id(edition: str, href: str) -> str:
    """Create a unique section ID from edition and href."""
    safe_href = re.sub(r'[^a-zA-Z0-9_\-]', '_', href)
    return f"{edition}_{safe_href}"
