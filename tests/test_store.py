from store import _format_results, is_non_content_chapter


def test_non_content_filter_does_not_remove_substantive_titles():
    assert not is_non_content_chapter("五、正当性秩序")
    assert not is_non_content_chapter("八、实体法与程序")
    assert not is_non_content_chapter("第六章 种姓的社会阶序概观")
    assert not is_non_content_chapter("附录 “正当性”理论的一个说明")
    assert not is_non_content_chapter("Preface to the New Edition")


def test_non_content_filter_removes_only_navigation_and_legal_pages():
    assert is_non_content_chapter("目录")
    assert is_non_content_chapter("版权信息")
    assert is_non_content_chapter("Contents")
    assert is_non_content_chapter("Original Copyright Page")


def test_result_limit_is_applied_after_filtering():
    result = {
        "ids": [["copyright", "real-1", "real-2"]],
        "documents": [["legal", "first", "second"]],
        "metadatas": [[
            {"chapter": "版权页"},
            {"chapter": "正当性秩序"},
            {"chapter": "法律程序"},
        ]],
        "distances": [[0.01, 0.02, 0.03]],
    }
    formatted = _format_results(result, limit=2)
    assert [item["id"] for item in formatted] == ["real-1", "real-2"]
