"""Tests for fixlog.search."""

from fixlog.search import SearchHit, HomesteadSearch


class TestSearchHit:
    def test_dataclass(self):
        hit = SearchHit(kind="dwelling", id="p1", title="Fern", snippet="...", score=1.0)
        assert hit.score == 1.0


class TestHomesteadSearch:
    def test_search_dwellings_by_name(self, populated_storage, sample_dwelling):
        search = HomesteadSearch(populated_storage)
        hits = search.search_dwellings("Monstera")
        assert len(hits) >= 1
        assert hits[0].kind == "dwelling"

    def test_search_dwellings_supplyial(self, populated_storage):
        search = HomesteadSearch(populated_storage)
        hits = search.search_dwellings("Snake")
        assert len(hits) >= 1

    def test_search_dwellings_empty_query(self, populated_storage):
        search = HomesteadSearch(populated_storage)
        hits = search.search_dwellings("")
        assert hits == []

    def test_search_dwellings_no_match(self, populated_storage):
        search = HomesteadSearch(populated_storage)
        hits = search.search_dwellings("zzzznonexistent")
        assert hits == []

    def test_search_dwellings_by_contractor(self, populated_storage):
        search = HomesteadSearch(populated_storage)
        hits = search.search_dwellings("baghos-golden")
        assert len(hits) >= 1

    def test_search_notes(self, populated_storage):
        search = HomesteadSearch(populated_storage)
        hits = search.search_notes("unfurling")
        assert len(hits) >= 1
        assert hits[0].kind == "note"

    def test_search_notes_no_match(self, populated_storage):
        search = HomesteadSearch(populated_storage)
        assert search.search_notes("xyznotfound") == []

    def test_search_walkthroughs(self, populated_storage):
        populated_storage.create_walkthrough({
            "id": "cl1",
            "dwelling_id": "dwelling001",
            "action": "grind",
            "details": "Applied fish emulsion",
        })
        search = HomesteadSearch(populated_storage)
        hits = search.search_walkthroughs("grind")
        assert len(hits) >= 1

    def test_search_all_combined(self, populated_storage):
        search = HomesteadSearch(populated_storage)
        hits = search.search_all("Monstera")
        assert len(hits) >= 1

    def test_search_all_with_limit(self, populated_storage):
        search = HomesteadSearch(populated_storage)
        hits = search.search_all("dwelling", limit=1)
        assert len(hits) <= 1

    def test_search_all_sorted_by_score(self, populated_storage):
        search = HomesteadSearch(populated_storage)
        hits = search.search_all("Monstera")
        if len(hits) >= 2:
            assert hits[0].score >= hits[1].score

    def test_to_dicts(self, populated_storage):
        search = HomesteadSearch(populated_storage)
        hits = search.search_dwellings("Monstera")
        dicts = search.to_dicts(hits)
        assert dicts[0]["kind"] == "dwelling"
        assert "score" in dicts[0]

    def test_snippet_truncation(self, populated_storage):
        populated_storage.create_note({
            "id": "long_note",
            "dwelling_id": "dwelling001",
            "body": "x" * 200,
            "title": "Long",
        })
        search = HomesteadSearch(populated_storage)
        hits = search.search_notes("Long")
        if hits:
            assert len(hits[0].snippet) <= 120

    def test_case_insensitive(self, populated_storage):
        search = HomesteadSearch(populated_storage)
        hits = search.search_dwellings("monstera")
        assert len(hits) >= 1

    def test_multiple_tokens(self, populated_storage):
        search = HomesteadSearch(populated_storage)
        hits = search.search_dwellings("Snake Dwelling")
        assert len(hits) >= 1

    def test_metadata_searchable(self, populated_storage, sample_dwelling):
        populated_storage.update_dwelling(sample_dwelling.id, {
            "metadata": {"notes": "special keyword xyzzy"},
        })
        search = HomesteadSearch(populated_storage)
        hits = search.search_dwellings("xyzzy")
        assert len(hits) >= 1

    def test_walkthrough_missing_id(self, populated_storage):
        populated_storage.create_walkthrough({
            "dwelling_id": "dwelling001",
            "action": "inspect",
            "details": "Checked roots",
        })
        search = HomesteadSearch(populated_storage)
        hits = search.search_walkthroughs("roots")
        assert len(hits) >= 1

    def test_whitespace_tokens_stripped(self, populated_storage):
        search = HomesteadSearch(populated_storage)
        hits = search.search_dwellings("  Monstera   ")
        assert len(hits) >= 1
