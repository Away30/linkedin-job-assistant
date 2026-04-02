"""Test cross-page job ID deduplication."""


def test_dedup_preserves_order():
    """Duplicate IDs from multiple pages should be removed, order preserved."""
    all_job_ids = ["a", "b", "c"]
    next_ids = ["c", "d", "e"]
    seen = set(all_job_ids)
    new_ids = [jid for jid in next_ids if jid not in seen]
    all_job_ids.extend(new_ids)
    assert all_job_ids == ["a", "b", "c", "d", "e"]


def test_dedup_all_duplicates():
    all_job_ids = ["a", "b"]
    next_ids = ["a", "b"]
    seen = set(all_job_ids)
    new_ids = [jid for jid in next_ids if jid not in seen]
    all_job_ids.extend(new_ids)
    assert all_job_ids == ["a", "b"]
