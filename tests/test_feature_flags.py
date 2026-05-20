import pytest

from src.common.feature_flags import (
    FeatureFlagManifest,
    FeatureFlagValidationError,
    validate_feature_flag_rollout,
)


class TestFeatureFlagRolloutValidation:
    def test_accepts_matching_scheduler_and_worker_defaults(self):
        manifest = FeatureFlagManifest.from_mapping(
            {
                "feature_flags": [
                    {
                        "name": "safe_completion_events",
                        "default": True,
                        "owner": "runtime-platform",
                    }
                ]
            }
        )

        validate_feature_flag_rollout(
            manifest,
            {
                "scheduler": {
                    "feature_flags": {"safe_completion_events": True}
                },
                "worker": {
                    "feature_flags": {"safe_completion_events": True}
                },
            },
        )

    def test_missing_required_flag_blocks_rollout(self):
        manifest = FeatureFlagManifest.from_mapping(
            {
                "feature_flags": [
                    {
                        "name": "safe_completion_events",
                        "default": True,
                        "owner": "runtime-platform",
                    }
                ]
            }
        )

        with pytest.raises(FeatureFlagValidationError) as exc_info:
            validate_feature_flag_rollout(
                manifest,
                {
                    "scheduler": {
                        "feature_flags": {"safe_completion_events": True}
                    },
                    "worker": {"feature_flags": {}},
                },
            )

        message = str(exc_info.value)
        assert "worker.safe_completion_events" in message
        assert "missing required flag" in message
        assert "owner=runtime-platform" in message

    def test_non_default_value_blocks_rollout(self):
        manifest = FeatureFlagManifest.from_mapping(
            {
                "feature_flags": [
                    {
                        "name": "safe_completion_events",
                        "default": True,
                        "owner": "runtime-platform",
                    }
                ]
            }
        )

        with pytest.raises(FeatureFlagValidationError) as exc_info:
            validate_feature_flag_rollout(
                manifest,
                {
                    "scheduler": {
                        "feature_flags": {"safe_completion_events": True}
                    },
                    "worker": {
                        "feature_flags": {"safe_completion_events": False}
                    },
                },
            )

        message = str(exc_info.value)
        assert "worker.safe_completion_events" in message
        assert "differs from documented default" in message
        assert "default=True" in message
        assert "actual=False" in message

    def test_scheduler_worker_mismatch_redacts_sensitive_values(self):
        manifest = FeatureFlagManifest.from_mapping(
            {
                "feature_flags": [
                    {
                        "name": "worker_api_token_rotation",
                        "default": "disabled",
                        "owner": "security",
                        "sensitive": True,
                    }
                ]
            }
        )

        with pytest.raises(FeatureFlagValidationError) as exc_info:
            validate_feature_flag_rollout(
                manifest,
                {
                    "scheduler": {
                        "feature_flags": {
                            "worker_api_token_rotation": "token-a",
                        }
                    },
                    "worker": {
                        "feature_flags": {
                            "worker_api_token_rotation": "token-b",
                        }
                    },
                },
            )

        message = str(exc_info.value)
        assert "worker.worker_api_token_rotation" in message
        assert "value differs" in message
        assert "token-a" not in message
        assert "token-b" not in message
        assert "<redacted>" in message

    def test_manifest_requires_documented_default_and_owner(self):
        with pytest.raises(ValueError, match="must declare a default"):
            FeatureFlagManifest.from_mapping(
                {
                    "feature_flags": [
                        {
                            "name": "new_flag",
                            "owner": "runtime-platform",
                        }
                    ]
                }
            )

        with pytest.raises(ValueError, match="must declare an owner"):
            FeatureFlagManifest.from_mapping(
                {"feature_flags": [{"name": "new_flag", "default": False}]}
            )
