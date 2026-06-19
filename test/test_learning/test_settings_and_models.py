"""Tests for learning settings and data models."""

import pytest

from config.settings import Settings


class TestLearningSettings:
    """Verify learning-related config items are read from settings."""

    def test_default_l2_max_concurrency(self):
        settings = Settings()
        assert settings.learning_l2_max_concurrency == 5

    def test_default_learning_job_timeout_minutes(self):
        settings = Settings()
        assert settings.learning_job_timeout_minutes == 60

    def test_l2_max_concurrency_from_env(self, monkeypatch):
        monkeypatch.setenv("LEARNING_L2_MAX_CONCURRENCY", "10")
        settings = Settings()
        assert settings.learning_l2_max_concurrency == 10

    def test_learning_job_timeout_from_env(self, monkeypatch):
        monkeypatch.setenv("LEARNING_JOB_TIMEOUT_MINUTES", "120")
        settings = Settings()
        assert settings.learning_job_timeout_minutes == 120

    def test_default_learning_l2_max_calls(self):
        settings = Settings()
        assert settings.learning_l2_max_calls == 200

    def test_learning_l2_max_calls_from_env(self, monkeypatch):
        monkeypatch.setenv("LEARNING_L2_MAX_CALLS", "0")
        settings = Settings()
        assert settings.learning_l2_max_calls == 0


class TestLearningLogModel:
    """Verify MetadataLearningLog model fields and ENUM types."""

    def test_model_has_required_fields(self):
        from metadata.models import MetadataLearningLog

        columns = {c.name for c in MetadataLearningLog.__table__.columns}
        expected = {
            "id",
            "data_source_id",
            "trigger_type",
            "status",
            "started_at",
            "finished_at",
            "tables_processed",
            "columns_described",
            "l0_count",
            "l1_count",
            "l2_count",
            "l2_llm_calls",
            "error_message",
        }
        assert expected.issubset(columns)

    def test_status_enum_values(self):
        from metadata.models import MetadataLearningLog

        status_col = MetadataLearningLog.__table__.columns["status"]
        # ENUM type stores allowed values
        enum_values = {v.value if hasattr(v, "value") else str(v) for v in status_col.type.enums}
        assert enum_values == {"running", "success", "partial_success", "failed", "aborted"}

    def test_trigger_type_enum_values(self):
        from metadata.models import MetadataLearningLog

        trigger_col = MetadataLearningLog.__table__.columns["trigger_type"]
        enum_values = {v.value if hasattr(v, "value") else str(v) for v in trigger_col.type.enums}
        assert enum_values == {"auto", "manual"}


class TestMetadataColumnsNewFields:
    """Verify new fields on metadata_columns and metadata_tables."""

    def test_metadata_columns_new_fields(self):
        from metadata.models import MetadataColumn

        columns = {c.name for c in MetadataColumn.__table__.columns}
        expected = {
            "semantic_description",
            "description_source",
            "description_confidence",
            "detected_enum_values",
            "null_ratio",
            "numeric_range",
        }
        assert expected.issubset(columns)

    def test_metadata_tables_new_fields(self):
        from metadata.models import MetadataTable

        columns = {c.name for c in MetadataTable.__table__.columns}
        expected = {
            "semantic_description",
            "description_source",
            "description_confidence",
        }
        assert expected.issubset(columns)
