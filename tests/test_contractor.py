"""Tests for fixlog.contractor."""

import pytest

from fixlog.errors import NotFoundError
from fixlog.contractor import (
    ServiceNeed,
    UsageNeed,
    ContractorProfile,
    ContractorCatalog,
    contractor_export_row,
    build_contractor_index,
)


class TestContractorProfile:
    def test_create(self, sample_contractor):
        assert sample_contractor.key == "baghos-golden"
        assert sample_contractor.common_name == "Golden Pothos"

    def test_repair_interval_days(self, sample_contractor):
        assert sample_contractor.repair_interval_days == 10

    def test_matches_light(self, sample_contractor):
        assert sample_contractor.matches_light("medium") is True

    def test_to_dict_from_dict(self, sample_contractor):
        restored = ContractorProfile.from_dict(sample_contractor.to_dict())
        assert restored.key == sample_contractor.key

    def test_care_summary(self, sample_contractor):
        summary = sample_contractor.care_summary()
        assert "Golden Pothos" in summary

    def test_temp_max_less_than_min_raises(self):
        with pytest.raises(ValueError):
            ContractorProfile(
                key="bad-contractor",
                common_name="Bad",
                temp_min_c=30.0,
                temp_max_c=10.0,
            )


class TestServiceNeed:
    def test_str(self):
        assert str(ServiceNeed.LOW) == "low"


class TestContractorCatalog:
    def test_register_and_get(self, contractor_catalog, sample_contractor):
        assert contractor_catalog.get(sample_contractor.key) is not None

    def test_require_raises(self):
        cat = ContractorCatalog()
        with pytest.raises(NotFoundError):
            cat.require("missing")

    def test_search(self, contractor_catalog):
        hits = contractor_catalog.search("baghos")
        assert len(hits) >= 1

    def test_search_empty_returns_all(self, contractor_catalog):
        assert len(contractor_catalog.search("")) >= 1

    def test_load_builtin(self):
        cat = ContractorCatalog()
        cat.load_builtin()
        assert cat.count() >= 10

    def test_with_defaults(self):
        cat = ContractorCatalog.with_defaults()
        assert cat.get("monstera-deliciosa") is not None

    def test_suggest_interval_winter(self, contractor_catalog):
        interval = contractor_catalog.suggest_interval_for("snake-dwelling", season="winter")
        assert interval > contractor_catalog.require("snake-dwelling").repair_interval_days

    def test_suggest_interval_summer(self, contractor_catalog):
        interval = contractor_catalog.suggest_interval_for("snake-dwelling", season="summer")
        assert interval <= contractor_catalog.require("snake-dwelling").repair_interval_days

    def test_filter_by_tag(self, contractor_catalog):
        beginner = contractor_catalog.filter_by_tag("beginner")
        assert len(beginner) >= 1

    def test_filter_pet_safe(self, contractor_catalog):
        safe = contractor_catalog.filter_pet_safe()
        assert all(not p.toxic_to_pets for p in safe)

    def test_merge(self, contractor_catalog, sample_contractor):
        other = ContractorCatalog()
        other.register(ContractorProfile(
            key="custom-fern",
            common_name="Custom Fern",
        ))
        merged = contractor_catalog.merge(other)
        assert merged.get("custom-fern") is not None

    def test_keys(self, contractor_catalog):
        keys = contractor_catalog.keys()
        assert "baghos-golden" in keys

    def test_recommend_for_conditions(self, contractor_catalog):
        hits = contractor_catalog.recommend_for_conditions("medium", usage_pct=50)
        assert len(hits) >= 1

    def test_recommend_pet_safe_only(self, contractor_catalog):
        hits = contractor_catalog.recommend_for_conditions("bright_indirect", pet_safe_only=True)
        assert all(not p.toxic_to_pets for p in hits)

    def test_difficulty_rank_beginner(self, contractor_catalog):
        rank = contractor_catalog.difficulty_rank("snake-dwelling")
        assert rank <= 3

    def test_difficulty_rank_fussy(self, contractor_catalog):
        rank = contractor_catalog.difficulty_rank("fiddle-leaf-fig")
        assert rank >= 3

    def test_difficulty_rank_unknown(self, contractor_catalog):
        assert contractor_catalog.difficulty_rank("nonexistent") == 3

    def test_from_dict_list(self, sample_contractor):
        cat = ContractorCatalog.from_dict_list([sample_contractor.to_dict()])
        assert cat.get(sample_contractor.key) is not None

    def test_to_dict_list(self, contractor_catalog):
        rows = contractor_catalog.to_dict_list()
        assert len(rows) >= 1


class TestContractorHelpers:
    def test_contractor_export_row(self, sample_contractor):
        row = contractor_export_row(sample_contractor)
        assert row[0] == sample_contractor.key

    def test_build_contractor_index(self, contractor_catalog):
        index = build_contractor_index(contractor_catalog)
        assert "G" in index or "P" in index
