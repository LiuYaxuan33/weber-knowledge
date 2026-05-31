import re
import config


def chunk_text(text: str, chunk_size: int = 512, overlap: int = 128) -> list[str]:
    """Split Chinese text into overlapping chunks at natural boundaries.

    Break priority: paragraph (\\n\\n) > sentence-ending punctuation (。？！) >
    clause boundary (，；) > character boundary (fallback).
    """
    if len(text) <= chunk_size * 1.1:
        return [text] if text.strip() else []

    chunks = []
    start = 0

    while start < len(text):
        end = min(start + chunk_size, len(text))

        if end < len(text):
            # Look for natural break points within last 20% of the chunk
            search_start = max(start, end - int(chunk_size * 0.2))
            window = text[search_start:end]

            # Prefer paragraph break
            m = re.search(r'\n\n', window)
            if m:
                end = search_start + m.start()
            else:
                # Then sentence-ending punctuation
                m = re.search(r'[。？！]', window)
                if m:
                    end = search_start + m.end()
                else:
                    # Then clause boundary
                    m = re.search(r'[，；]', window)
                    if m:
                        end = search_start + m.end()

        chunk = text[start:end].strip()
        if chunk and len(chunk) >= 20:
            chunks.append(chunk)

        start = end - overlap if end < len(text) else len(text)
        if start >= len(text):
            break

    return chunks


def chunk_with_metadata(
    text: str, base_metadata: dict, chunk_size: int = 512, overlap: int = 128
) -> list[dict]:
    """Split text into chunks, propagating and extending metadata."""
    c_size = base_metadata.get("chunk_size", chunk_size)
    c_overlap = base_metadata.get("chunk_overlap", overlap)
    chunks = chunk_text(text, c_size, c_overlap)

    results = []
    for i, c in enumerate(chunks):
        meta = {**base_metadata, "chunk_index": i}
        results.append({"text": c, "metadata": meta})
    return results
