"""Severity assignment using configurable YAML mappings and score thresholds."""

from __future__ import annotations

from pathlib import Path

import pandas as pd
import yaml

DEFAULT_RULES = Path(__file__).resolve().parents[3] / "config" / "severity_rules.yaml"


def assess_severity(frame: pd.DataFrame, rules_path: Path = DEFAULT_RULES) -> pd.DataFrame:
    """Add severity labels using log levels, then anomaly score as a fallback."""
    try:
        config = yaml.safe_load(rules_path.read_text(encoding="utf-8"))
    except (OSError, yaml.YAMLError) as exc:
        raise ValueError(f"Unable to load severity rules from {rules_path}: {exc}") from exc
    levels = config["severity_levels"]
    thresholds = config["anomaly_score_thresholds"]

    def severity(row: pd.Series) -> str:
        level = str(row.get("severity") or "").upper()
        if level in levels:
            return level
        score = float(row.get("anomaly_score", 0))
        if score >= thresholds["HIGH"]:
            return "HIGH"
        if score >= thresholds["MEDIUM"]:
            return "MEDIUM"
        return str(config["default"])

    result = frame.copy()
    result["severity"] = result.apply(severity, axis=1)
    return result
