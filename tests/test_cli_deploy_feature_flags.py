import pytest

from src.cli.main import _validate_deploy_manifest
from src.common.feature_flags import FeatureFlagValidationError


class TestDeployFeatureFlagValidation:
    def test_deploy_manifest_validates_feature_flags(self, tmp_path):
        manifest = tmp_path / "agent.yaml"
        manifest.write_text(
            """
feature_flags:
  - name: strict_worker_defaults
    default: true
    owner: runtime-platform
services:
  scheduler:
    feature_flags:
      strict_worker_defaults: true
  worker:
    feature_flags:
      strict_worker_defaults: true
"""
        )

        _validate_deploy_manifest(str(manifest))

    def test_deploy_manifest_rejects_mismatched_feature_flags(self, tmp_path):
        manifest = tmp_path / "agent.yaml"
        manifest.write_text(
            """
feature_flags:
  - name: strict_worker_defaults
    default: true
    owner: runtime-platform
services:
  scheduler:
    feature_flags:
      strict_worker_defaults: true
  worker:
    feature_flags:
      strict_worker_defaults: false
"""
        )

        with pytest.raises(FeatureFlagValidationError):
            _validate_deploy_manifest(str(manifest))
