import re
from bs4 import BeautifulSoup
import ebooklib
from ebooklib import epub


def load_epub(epub_path: str, edition: str, category: str) -> list[dict]:
    """Load an EPUB and return a list of sections with metadata.

    Each section: {"text": str, "metadata": {"section_id": str, "book": str, ...}}
    """
    book = epub.read_epub(epub_path)
    toc = _parse_ncx(book)  # list of {title, href, level, children}
    html_texts = _extract_html(book)  # dict: href_base -> clean text

    sections = []
    _flatten_toc(toc, html_texts, sections, edition, category, parent_book="")
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


def _flatten_toc(toc: list[dict], html_texts: dict[str, str],
                 sections: list, edition: str, category: str,
                 parent_book: str = ""):
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
        text = _get_text_for_entry(entry, html_texts)

        if len(text) < 30:
            # Skip front-matter fluff but recurse into children
            if entry["children"]:
                _flatten_toc(entry["children"], html_texts, sections,
                            edition, category, book_name)
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
            "href": entry["href"],
            "chunk_size": 512,
            "chunk_overlap": 128,
        }
        sections.append({"text": text, "metadata": metadata})

        # Recurse into children
        if entry["children"]:
            _flatten_toc(entry["children"], html_texts, sections,
                        edition, category, book_name)


def _get_text_for_entry(entry: dict, html_texts: dict[str, str]) -> str:
    """Extract the text content for a TOC entry from HTML documents.

    Uses the NCX href to find the right part of the HTML.
    """
    href = entry["href"]
    if not href:
        return ""

    # Parse href: "text/part0042.html#anchor_id"
    if '#' in href:
        file_part, anchor = href.split('#', 1)
        # Remove fragment-specific anchor to find the full doc
        doc_text = _find_html_text(file_part, html_texts)
        if doc_text:
            # Try to find text starting near this section
            return _extract_section_text(doc_text, entry, file_part, html_texts)
        return ""
    else:
        return _find_html_text(href, html_texts)


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


def _extract_section_text(doc_text: str, entry: dict,
                          file_part: str, html_texts: dict[str, str]) -> str:
    """Extract text for a specific section from a document.

    Strategy: if siblings exist, extract text between this entry's content
    and the next sibling's content. Otherwise take the whole doc.
    """
    # Try to get just this section's text
    siblings = _get_sibling_hrefs(entry, file_part, html_texts)
    if len(siblings) >= 2:
        # Find the range: from this section's title to the next section's title
        title = entry["title"]
        # Search for the title in the doc
        idx = doc_text.find(title)
        if idx >= 0:
            start = idx
            # Find where the next section starts
            end = len(doc_text)
            for sib in siblings[1:]:
                # Try to find the sibling's title
                sib_text = _get_text_for_sibling(sib, html_texts)
                # We just need a stopping point
                break
            return doc_text[start:end].strip()
    return doc_text


def _get_sibling_hrefs(entry: dict, file_part: str,
                       html_texts: dict[str, str]) -> list[str]:
    """Get the hrefs of siblings in the same HTML file."""
    # Placeholder implementation — returns empty, meaning take the whole doc
    return []


def _get_text_for_sibling(href: str, html_texts: dict[str, str]) -> str:
    """Get text for a sibling href."""
    if '#' in href:
        file_part, anchor = href.split('#', 1)
        return _find_html_text(file_part, html_texts)
    return _find_html_text(href, html_texts)


def _make_section_id(edition: str, href: str) -> str:
    """Create a unique section ID from edition and href."""
    safe_href = re.sub(r'[^a-zA-Z0-9_\-]', '_', href)
    return f"{edition}_{safe_href}"
