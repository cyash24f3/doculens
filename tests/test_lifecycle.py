import pytest


def test_replace_excludes_old_content_but_allows_explicit_archive_search(service):
    old = service.ingest(
        b"# Policy\n\nThe amber retention interval is 90 days.", "policy.md", "Retention", "Policy", "1"
    )
    new = service.ingest(
        b"# Policy\n\nThe violet retention interval is 30 days.",
        "policy.md",
        "Retention",
        "Policy",
        "2",
        replaces=old["id"],
    )
    assert new["family_id"] == old["family_id"]
    assert not service.store.get_document(old["id"])["active"]
    current, _ = service.search("amber", mode="keyword")
    assert current == []
    archived, _ = service.search("amber", mode="keyword", include_archived=True)
    assert archived[0]["document_id"] == old["id"]
    assert archived[0]["active"] == 0


def test_failed_replace_keeps_current_version(service):
    old = service.ingest(b"An active original policy.", "policy.txt", "Policy", "General", "1")
    with pytest.raises(ValueError, match="version label"):
        service.ingest(b"A different policy.", "policy.txt", "Policy", "General", "1", replaces=old["id"])
    assert service.store.get_document(old["id"])["active"]
    assert len(service.store.documents()) == 1


def test_duplicate_and_delete_clear_retained_excerpts(service):
    original = service.ingest(
        b"Upload limits support exactly 10 MiB per document.", "doc.txt", "Limits", "General", "1"
    )
    with pytest.raises(ValueError, match="already indexed"):
        service.ingest(
            b"Upload limits support exactly 10 MiB per document.", "again.txt", "Again", "General", "1"
        )
    service.ask("What are upload limits?", mode="keyword")
    assert len(service.store.traces()) == 1
    assert not service.store.delete("does-not-exist")
    assert len(service.store.traces()) == 1
    assert service.store.delete(original["id"])
    assert service.store.traces() == []
    assert service.store.chunks(include_archived=True) == []


def test_filter_is_applied_before_ranking(service):
    service.ingest(b"Engineering API rate limit is 120 requests.", "eng.txt", "API", "Engineering", "1")
    service.ingest(
        b"Product supports API rate limits in the interface.", "product.txt", "Product", "Product", "1"
    )
    rows, trace = service.search("API rate limits", mode="keyword", category="Engineering")
    assert trace["candidate_chunks"] == 1
    assert all(r["category"] == "Engineering" for r in rows)


def test_demo_idempotent(service):
    assert len(service.load_demo()) == 12
    assert service.load_demo() == []
    assert len(service.store.documents()) == 12
