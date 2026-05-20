"""Feature flag rollout validation."""

from dataclasses import dataclass
from typing import Any, Dict, Iterable, Mapping, Sequence, Tuple


SENSITIVE_FLAG_TERMS = ("key", "secret", "token", "password", "credential")


@dataclass(frozen=True)
class RequiredFeatureFlag:
    """Feature flag metadata required before production rollout."""

    name: str
    default: Any
    owner: str
    services: Tuple[str, ...] = ("scheduler", "worker")
    sensitive: bool = False

    def __post_init__(self) -> None:
        if not self.name:
            raise ValueError("feature flag name is required")
        if not self.owner:
            raise ValueError(
                f"feature flag {self.name!r} must declare an owner"
            )
        if not self.services:
            raise ValueError(
                f"feature flag {self.name!r} must target at least one service"
            )

    @property
    def redacts_values(self) -> bool:
        lowered = self.name.lower()
        return self.sensitive or any(
            term in lowered for term in SENSITIVE_FLAG_TERMS
        )


@dataclass(frozen=True)
class FeatureFlagIssue:
    service: str
    flag: str
    reason: str
    detail: str = ""

    def describe(self) -> str:
        if self.detail:
            return (
                f"{self.service}.{self.flag}: {self.reason} "
                f"({self.detail})"
            )
        return f"{self.service}.{self.flag}: {self.reason}"


class FeatureFlagValidationError(ValueError):
    """Raised when rendered service flags are unsafe for rollout."""

    def __init__(self, issues: Sequence[FeatureFlagIssue]):
        self.issues = tuple(issues)
        message = "feature flag rollout validation failed: " + "; ".join(
            issue.describe() for issue in self.issues
        )
        super().__init__(message)


@dataclass(frozen=True)
class FeatureFlagManifest:
    required_flags: Tuple[RequiredFeatureFlag, ...]

    @classmethod
    def from_mapping(cls, raw: Mapping[str, Any]) -> "FeatureFlagManifest":
        raw_flags = raw.get(
            "feature_flags",
            raw.get("flags", raw.get("required_flags", [])),
        )
        if not isinstance(raw_flags, list):
            raise ValueError("feature_flags must be a list")

        flags = []
        missing_default = object()
        for raw_flag in raw_flags:
            if not isinstance(raw_flag, Mapping):
                raise ValueError("feature flag entries must be objects")
            default = raw_flag.get("default", missing_default)
            if default is missing_default:
                raise ValueError(
                    f"feature flag {raw_flag.get('name')!r} must "
                    "declare a default"
                )
            services = raw_flag.get("services", ("scheduler", "worker"))
            flags.append(
                RequiredFeatureFlag(
                    name=str(raw_flag.get("name", "")),
                    default=default,
                    owner=str(raw_flag.get("owner", "")),
                    services=tuple(str(service) for service in services),
                    sensitive=bool(raw_flag.get("sensitive", False)),
                )
            )
        return cls(tuple(flags))


def validate_feature_flag_rollout(
    manifest: FeatureFlagManifest,
    rendered_services: Mapping[str, Mapping[str, Any]],
) -> None:
    """Validate required flags before production rollout.

    The validator fails closed for missing flags and cross-service mismatch.
    Error messages are intentionally sanitized for sensitive flags.
    """

    issues = []
    for flag in manifest.required_flags:
        observed_values: Dict[str, Any] = {}
        for service in flag.services:
            service_flags = _extract_service_flags(
                rendered_services.get(service)
            )
            if flag.name not in service_flags:
                issues.append(
                    FeatureFlagIssue(
                        service=service,
                        flag=flag.name,
                        reason="missing required flag",
                        detail=(
                            f"default={_format_value(flag.default, flag)} "
                            f"owner={flag.owner}"
                        ),
                    )
                )
                continue
            observed_value = service_flags[flag.name]
            observed_values[service] = observed_value
            if observed_value != flag.default:
                issues.append(
                    FeatureFlagIssue(
                        service=service,
                        flag=flag.name,
                        reason="value differs from documented default",
                        detail=(
                            f"default={_format_value(flag.default, flag)} "
                            f"actual={_format_value(observed_value, flag)} "
                            f"owner={flag.owner}"
                        ),
                    )
                )

        issues.extend(_compare_service_values(flag, observed_values.items()))

    if issues:
        raise FeatureFlagValidationError(issues)


def _extract_service_flags(
    service_config: Mapping[str, Any] | None,
) -> Mapping[str, Any]:
    if not service_config:
        return {}
    for key in ("feature_flags", "flags"):
        candidate = service_config.get(key)
        if isinstance(candidate, Mapping):
            return candidate
    return service_config


def _compare_service_values(
    flag: RequiredFeatureFlag,
    observed_values: Iterable[tuple[str, Any]],
) -> list[FeatureFlagIssue]:
    values = list(observed_values)
    if len(values) < 2:
        return []

    reference_service, reference_value = values[0]
    issues = []
    for service, value in values[1:]:
        if value != reference_value:
            issues.append(
                FeatureFlagIssue(
                    service=service,
                    flag=flag.name,
                    reason="value differs from scheduler/worker peer",
                    detail=(
                        f"{reference_service}="
                        f"{_format_value(reference_value, flag)} "
                        f"{service}={_format_value(value, flag)}"
                    ),
                )
            )
    return issues


def _format_value(value: Any, flag: RequiredFeatureFlag) -> str:
    if flag.redacts_values:
        return "<redacted>"
    return repr(value)
