from pathlib import Path

import pandas as pd
import pytest

from log_anomaly.detection.analyze import analyze_events
from log_anomaly.evaluation.metrics import evaluate_predictions
from log_anomaly.grouping.correlate import group_alerts
from log_anomaly.ingestion.parser import IngestionError, parse_log_file
from log_anomaly.persistence.sqlite_store import SQLiteStore
from log_anomaly.preprocessing.normalize import extract_template
from log_anomaly.service import analyze_batch


def test_csv_ingestion_maps_fields_and_labels() -> None:
    events, file_format, confidence, encoding = parse_log_file(
        "logs.csv",
        b"timestamp,level,host,message,label\n2026-01-01T10:00:00Z,ERROR,host-a,failed request,1\n",
    )

    assert file_format == "csv"
    assert confidence == 1
    assert encoding == "utf-8"
    assert events.loc[0, "severity"] == "ERROR"
    assert events.loc[0, "label"] == "1"
    assert events.loc[0, "message"] == "failed request"


def test_java_stack_trace_is_merged_into_starting_event() -> None:
    events, file_format, _, _ = parse_log_file(
        "application.log",
        b"2026-01-01 10:00:00 ERROR com.example.App - operation failed\n"
        b"    at com.example.App.run(App.java:12)\n"
        b"Caused by: java.lang.IllegalStateException\n",
    )

    assert file_format == "java"
    assert len(events) == 1
    assert events.loc[0, "message"].startswith("operation failed")
    assert "Caused by: java.lang.IllegalStateException" in events.loc[0, "message"]
    assert events.loc[0, "severity"] == "ERROR"


def test_apache_parser_extracts_host_timestamp_and_status_severity() -> None:
    events, file_format, confidence, _ = parse_log_file(
        "access.log",
        b'192.0.2.1 - - [01/Jan/2026:10:00:00 +0000] "GET /health HTTP/1.1" 503 12\n',
    )

    assert file_format == "apache"
    assert confidence == 1
    assert events.loc[0, "severity"] == "ERROR"
    assert events.loc[0, "host"] == "192.0.2.1"


@pytest.mark.parametrize(
    ("filename", "content", "error"),
    [
        ("bad.csv", b"time,level\nnow,ERROR\n", "message column"),
        ("binary.log", b"\x00\x01", "binary"),
        ("controls.log", bytes(range(1, 32)) * 4, "non-text"),
        ("empty.txt", b" \n\t", "empty"),
    ],
)
def test_invalid_uploads_raise_clear_errors(
    filename: str, content: bytes, error: str
) -> None:
    with pytest.raises(IngestionError, match=error):
        parse_log_file(filename, content)


def test_template_masks_ip_uuid_and_long_numeric_identifier() -> None:
    template = extract_template(
        "connection 192.0.2.5 request 12345678 id "
        "550e8400-e29b-41d4-a716-446655440000"
    )

    assert template == "connection <IP> request <NUM> id <UUID>"


@pytest.mark.parametrize(
    ("filename", "content", "expected_format"),
    [
        ("legacy.log", "café".encode("cp1252"), "text"),
        ("utf16.any", "INFO café".encode("utf-16"), "text"),
        (
            "renamed.data",
            "message;level\ncafé;INFO\n".encode("cp1252"),
            "csv",
        ),
    ],
)
def test_non_utf8_text_is_converted_and_parsed(
    filename: str, content: bytes, expected_format: str
) -> None:
    events, file_format, _, source_encoding = parse_log_file(filename, content)

    assert file_format == expected_format
    assert source_encoding != "utf-8"
    assert "café" in events["message"].iloc[0]


def test_frequency_detector_flags_rare_template_and_explains_score() -> None:
    events = pd.DataFrame(
        {"message": ["routine heartbeat"] * 9 + ["unexpected database corruption"]}
    )

    result = analyze_events(events, method="baseline")

    assert result.loc[9, "is_anomaly"]
    assert result.loc[9, "anomaly_score"] > result.loc[0, "anomaly_score"]
    assert "occurred 1 time" in result.loc[9, "explanation"]


def test_auto_detector_uses_frequency_for_small_files_and_iforest_for_varied_files() -> None:
    small = analyze_events(
        pd.DataFrame({"message": ["routine heartbeat"] * 9 + ["database failure"]})
    )
    varied = analyze_events(
        pd.DataFrame({"message": [f"service event number {index}" for index in range(25)]})
    )

    assert set(small["detection_method"]) == {"baseline"}
    assert set(varied["detection_method"]) == {"isolation_forest"}


def test_frequency_detector_flags_highest_scores_with_tied_rare_templates() -> None:
    events = pd.DataFrame(
        {
            "message": [
                "Application started",
                "Database connected",
                "High memory usage",
                "Database connection timeout",
                "Database connection timeout",
                "Database connection restored",
            ]
        }
    )

    result = analyze_events(events, method="baseline")

    assert result["is_anomaly"].any()
    assert not result.loc[3, "is_anomaly"]
    assert not result.loc[4, "is_anomaly"]


def test_grouping_uses_key_and_time_window() -> None:
    events = pd.DataFrame(
        {
            "is_anomaly": [True, True, True],
            "host": ["host-a", "host-a", "host-b"],
            "service": ["api", "api", "api"],
            "template": ["failed <NUM>"] * 3,
            "timestamp": [
                "2026-01-01T10:00:00Z",
                "2026-01-01T10:04:00Z",
                "2026-01-01T10:04:00Z",
            ],
        }
    )

    grouped = group_alerts(events, window_minutes=5)

    assert grouped.loc[0, "group_id"] == grouped.loc[1, "group_id"]
    assert grouped.loc[1, "group_id"] != grouped.loc[2, "group_id"]


def test_evaluation_metrics_and_validation() -> None:
    assert evaluate_predictions([True, False, True], [True, True, False]) == {
        "precision": 0.5,
        "recall": 0.5,
        "f1": 0.5,
        "records": 3,
    }
    with pytest.raises(ValueError, match="same number"):
        evaluate_predictions([True], [])


def test_sqlite_persists_analysis_batch(tmp_path: Path) -> None:
    results = analyze_batch(
        pd.DataFrame({"message": ["healthy response"] * 9 + ["database corruption"]}),
        method="baseline",
    )
    store = SQLiteStore(tmp_path / "events.db")

    assert store.save(results) == 10
    assert store.save(results) == 10

    import sqlite3

    with sqlite3.connect(store.path) as connection:
        rows = connection.execute("SELECT COUNT(*) FROM analysis_events").fetchone()[0]
    assert rows == 10


def test_clustering_groups_similar_logs_and_flags_outlier() -> None:
    events = pd.DataFrame(
        {
            "message": (
                ["User login successful for user admin"] * 10
                + ["Database query executed in 12ms"] * 10
                + ["FATAL KERNEL PANIC CPU REGISTER CORRUPTION OUT OF MEMORY"]
            )
        }
    )
    result = analyze_events(events, method="clustering", contamination=0.1)

    assert "cluster_id" in result.columns
    # Routine messages should form clusters
    login_clusters = set(result.iloc[:10]["cluster_id"])
    db_clusters = set(result.iloc[10:20]["cluster_id"])
    assert len(login_clusters) == 1
    assert len(db_clusters) == 1
    assert login_clusters != db_clusters

    # Outlier message should be flagged as anomaly
    outlier_event = result.iloc[20]
    assert outlier_event["is_anomaly"]
    assert outlier_event["anomaly_score"] > result.iloc[0]["anomaly_score"]
    assert "cluster" in outlier_event["explanation"].lower()
