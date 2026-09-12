import app


def test_default_scope_contains_only_the_two_weber_collections():
    sources = app._collection_sources(app.SCOPE_BOTH)

    assert sources
    assert any(name.startswith("上海人民-") for name in sources)
    assert any(name.startswith("上海三联-") for name in sources)
    assert all(name.startswith(("上海人民-", "上海三联-")) for name in sources)
    assert "三联-民族国家与经济政策" not in sources


def test_edition_scope_and_book_selection_are_resolved_safely():
    people_sources = app._collection_sources(app.SCOPE_SHANGHAI_PEOPLE)
    sanlian_sources = app._collection_sources(app.SCOPE_SHANGHAI_SANLIAN)

    assert people_sources
    assert sanlian_sources
    assert all(name.startswith("上海人民-") for name in people_sources)
    assert all(name.startswith("上海三联-") for name in sanlian_sources)

    selected = people_sources[0]
    assert app._collection_sources(
        app.SCOPE_SHANGHAI_PEOPLE,
        [selected, sanlian_sources[0], "不存在的来源"],
    ) == [selected]


def test_invalid_or_empty_book_selection_falls_back_to_scope():
    expected = app._collection_sources(app.SCOPE_SHANGHAI_SANLIAN)
    assert app._collection_sources(
        app.SCOPE_SHANGHAI_SANLIAN,
        ["上海人民-学术与政治"],
    ) == expected
