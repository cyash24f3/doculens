from doculens.evaluation import evaluate, relevant


def test_gold_passage_matching_requires_file_and_evidence():
    gold = {"file": "a.md", "contains": "correct evidence"}
    assert relevant({"filename": "a.md", "text": "The correct evidence appears."}, gold)
    assert not relevant({"filename": "b.md", "text": "correct evidence"}, gold)
    assert not relevant({"filename": "a.md", "text": "Unrelated paragraph."}, gold)


def test_keyword_benchmark_is_reproducible_and_keeps_splits(service):
    service.load_demo()
    report = evaluate(service)
    assert report["question_count"] == 66
    assert {r["split"] for r in report["aggregates"]} == {"dev", "test"}
    assert len(report["details"]) == 66
    assert all(0 <= r["recall_at_5"] <= 1 for r in report["aggregates"])
    assert all(r["verbatim_quote_fidelity"] == 1 for r in report["aggregates"])
    assert report["question_set_sha256"]
