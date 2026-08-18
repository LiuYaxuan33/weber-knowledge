from import_data import _existing_index_is_current


def test_partial_existing_index_is_not_reused():
    manifest = {"schema_version": 2, "chunks": 42317}

    assert not _existing_index_is_current(
        1299,
        5000,
        1299,
        42317,
        manifest,
        manifest,
    )


def test_complete_matching_index_is_reused():
    manifest = {"schema_version": 2, "chunks": 42317}

    assert _existing_index_is_current(
        1299,
        42317,
        1299,
        42317,
        manifest,
        manifest,
    )


def test_manifest_mismatch_forces_rebuild_even_when_counts_match():
    assert not _existing_index_is_current(
        1299,
        42317,
        1299,
        42317,
        {"schema_version": 1},
        {"schema_version": 2},
    )
