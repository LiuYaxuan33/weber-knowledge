import numpy as np

from ingest import assign_section_embeddings, build_publisher_source_map


def test_section_embedding_pools_all_chunk_embeddings():
    sections = [{"metadata": {"section_id": "s1"}}]
    chunks = [
        {"metadata": {"section_id": "s1"}, "embedding": [1.0, 0.0]},
        {"metadata": {"section_id": "s1"}, "embedding": [0.0, 1.0]},
    ]
    assign_section_embeddings(sections, chunks)
    assert np.allclose(sections[0]["embedding"], [2**-0.5, 2**-0.5])


def test_legacy_publisher_map_excludes_ambiguous_publishers():
    mapping = build_publisher_source_map()
    assert "上海人民出版社" not in mapping
    assert "上海三联书店" not in mapping
    assert mapping["University of Chicago Press"] == "Natural Right and History"
