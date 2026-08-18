import ebooklib

from loaders.epub import _extract_html


class _Document:
    def __init__(self, name: str, html: str):
        self._name = name
        self._html = html

    def get_type(self):
        return ebooklib.ITEM_DOCUMENT

    def get_name(self):
        return self._name

    def get_content(self):
        return self._html.encode("utf-8")


class _Book:
    def __init__(self, items):
        self._items = items

    def get_items(self):
        return self._items


def test_anchor_positions_reference_clean_text_after_all_markers_are_removed():
    html = """
    <html><body>
      <section id="one"><h1>一</h1><p>第一节内容。</p></section>
      <section id="two"><h1>二</h1><p>第二节内容。</p></section>
      <section id="three"><h1>三</h1><p>第三节内容。</p></section>
    </body></html>
    """
    texts, anchors = _extract_html(_Book([_Document("chapter.xhtml", html)]))
    text = texts["chapter.xhtml"]

    assert "ANCHOR" not in text
    assert text[anchors["chapter.xhtml"]["one"]:].startswith("一")
    assert text[anchors["chapter.xhtml"]["two"]:].startswith("二")
    assert text[anchors["chapter.xhtml"]["three"]:].startswith("三")
