"""Safe, size-limited parsing of CSV, Java, Apache, and plain-text logs."""

from __future__ import annotations

import codecs
import csv
import io
import os
import re
from datetime import datetime
from typing import Any
from uuid import uuid4

import pandas as pd
from charset_normalizer import from_bytes

MAX_UPLOAD_BYTES = int(os.getenv("LOG_ANOMALY_MAX_UPLOAD_MB", "25")) * 1024 * 1024
_APACHE = re.compile(
    r'^(?P<host>\S+) \S+ \S+ \[(?P<timestamp>[^\]]+)\] '
    r'"(?P<request>[^"]*)" (?P<status>\d{3}) (?P<size>\S+)'
)
_JAVA_START = re.compile(
    r"^(?P<timestamp>\d{4}-\d\d-\d\d[T ][\d:.,+-]+).*?"
    r"\b(?P<level>TRACE|DEBUG|INFO|WARN|WARNING|ERROR|FATAL)\b"
    r"(?:\s+[\w$]+(?:[./$][\w$]+)+)?\s*[-:]?\s*(?P<message>.*)$",
    re.IGNORECASE,
)
_GENERIC_START = re.compile(r"^(?P<timestamp>\d{4}-\d\d-\d\d[T ][\d:.,+-]+)\s+(?P<body>.*)")
_LEVEL = re.compile(r"\b(TRACE|DEBUG|INFO|WARN|WARNING|ERROR|FATAL|CRITICAL)\b", re.I)
_ALIASES = {
    "message": {"message", "msg", "log", "content", "event", "text"},
    "timestamp": {"timestamp", "time", "datetime", "date"},
    "severity": {"severity", "level", "log_level"},
    "host": {"host", "hostname", "machine"},
    "service": {"service", "application", "app"},
    "source": {"source", "logger", "component"},
    "label": {"label", "anomaly", "is_anomaly", "ground_truth"},
}
_MESSAGE_ALIASES = _ALIASES["message"]


class IngestionError(ValueError):
    """Raised when an uploaded log cannot be safely parsed."""


def decode_uploaded_text(content: bytes) -> tuple[str, str]:
    """Decode common text encodings and return UTF-8-compatible text plus source encoding."""
    if not content:
        raise IngestionError("The uploaded file is empty.")
    if len(content) > MAX_UPLOAD_BYTES:
        raise IngestionError(
            f"The file exceeds the {MAX_UPLOAD_BYTES // (1024 * 1024)} MB upload limit."
        )

    signatures = (
        (codecs.BOM_UTF32_LE, "utf-32"),
        (codecs.BOM_UTF32_BE, "utf-32"),
        (codecs.BOM_UTF8, "utf-8-sig"),
        (codecs.BOM_UTF16_LE, "utf-16"),
        (codecs.BOM_UTF16_BE, "utf-16"),
    )
    for signature, encoding in signatures:
        if content.startswith(signature):
            try:
                text = content.decode(encoding)
            except UnicodeDecodeError as exc:
                raise IngestionError(f"The file has an invalid {encoding} encoding.") from exc
            return _validate_text(text), encoding

    try:
        return _validate_text(content.decode("utf-8")), "utf-8"
    except UnicodeDecodeError:
        matches = from_bytes(content)
        match = matches.best()
        if match is None:
            raise IngestionError(
                "Could not determine this file's text encoding. Save it as UTF-8 and retry."
            ) from None
        if match.coherence == 0:
            try:
                text = content.decode("cp1252")
            except UnicodeDecodeError:
                pass
            else:
                return _validate_text(text), "cp1252"
        try:
            text = str(match)
        except (UnicodeDecodeError, LookupError) as exc:
            raise IngestionError(
                "Could not decode this file. Save it as UTF-8 and retry."
            ) from exc
        return _validate_text(text), str(match.encoding or "unknown")


def _validate_text(text: str) -> str:
    if "\x00" in text:
        raise IngestionError("The uploaded file appears to be binary; upload a text log file.")
    if not text.strip():
        raise IngestionError("The uploaded file is empty or contains no log entries.")
    non_text = sum(
        not character.isprintable() and character not in "\r\n\t\f" for character in text
    )
    if non_text / len(text) > 0.02:
        raise IngestionError(
            "The file contains too many non-text characters. Check its encoding or file type."
        )
    return text


def detect_format(filename: str, content: bytes) -> tuple[str, float]:
    """Choose the most likely supported format using content evidence."""
    suffix = filename.rsplit(".", 1)[-1].lower() if "." in filename else ""
    if suffix == "pdf":
        return "pdf", 1.0
    if suffix in {"txt", "log"} and content.startswith(b"%PDF-"):
        raise IngestionError("This file is a PDF. Rename it only if it is actually a text log.")
    text, _ = decode_uploaded_text(content)

    lines = [line for line in text.splitlines() if line.strip()][:50]
    if suffix == "csv":
        return "csv", 1.0
    if _has_message_header(text):
        return "csv", 0.9
    apache_hits = sum(bool(_APACHE.match(line)) for line in lines)
    java_hits = sum(bool(_JAVA_START.match(line)) for line in lines)
    if apache_hits:
        return "apache", apache_hits / len(lines)
    if java_hits:
        return "java", java_hits / len(lines)
    return "text", 0.5


def parse_log_file(filename: str, content: bytes) -> tuple[pd.DataFrame, str, float, str]:
    """Parse supported CSV, text, or text-based PDF uploads into normalized events."""
    suffix = filename.rsplit(".", 1)[-1].lower() if "." in filename else ""
    if suffix == "pdf":
        text = _extract_pdf_text(content)
        source_encoding = "PDF text extraction"
        detected_format, confidence = detect_format("extracted.txt", text.encode("utf-8"))
        detected_format = f"pdf/{detected_format}"
    else:
        text, source_encoding = decode_uploaded_text(content)
        detected_format, confidence = detect_format(filename, text.encode("utf-8"))

    utf8_content = text.encode("utf-8")
    utf8_text = utf8_content.decode("utf-8")

    if detected_format in {"csv", "pdf/csv"}:
        events = _parse_csv(utf8_text)
    else:
        line_format = detected_format.removeprefix("pdf/")
        events = _parse_lines(utf8_text, line_format)
    if not events:
        raise IngestionError("No valid log events could be parsed.")
    return pd.DataFrame(events), detected_format, confidence, source_encoding


def _extract_pdf_text(content: bytes) -> str:
    if not content:
        raise IngestionError("The uploaded PDF is empty.")
    if len(content) > MAX_UPLOAD_BYTES:
        raise IngestionError(
            f"The file exceeds the {MAX_UPLOAD_BYTES // (1024 * 1024)} MB upload limit."
        )
    if not content.startswith(b"%PDF-"):
        raise IngestionError("The file extension is PDF, but the file is not a valid PDF.")

    from pypdf import PdfReader
    from pypdf.errors import PdfReadError

    try:
        reader = PdfReader(io.BytesIO(content), strict=True)
        if reader.is_encrypted:
            raise IngestionError("Encrypted PDFs are not supported. Upload an unencrypted PDF.")
        if len(reader.pages) > 500:
            raise IngestionError("PDFs are limited to 500 pages.")
        pages = []
        total_characters = 0
        for page in reader.pages:
            page_text = page.extract_text() or ""
            total_characters += len(page_text)
            if total_characters > MAX_UPLOAD_BYTES:
                raise IngestionError("Extracted PDF text exceeds the upload processing limit.")
            pages.append(page_text)
    except (PdfReadError, OSError, ValueError) as exc:
        if isinstance(exc, IngestionError):
            raise
        raise IngestionError(f"Unable to read PDF: {exc}") from exc

    text = "\n".join(pages).strip()
    if not text:
        raise IngestionError(
            "This PDF has no extractable text. Scanned PDFs require OCR and are not supported."
        )
    lines = [line for line in text.splitlines() if line.strip()]
    if not (
        _has_message_header(text)
        or any(_APACHE.match(line) or _JAVA_START.match(line) or _GENERIC_START.match(line)
               for line in lines)
    ):
        raise IngestionError(
            "The PDF contains text but no recognizable log records. Upload a log dataset, "
            "not a research paper or general document."
        )
    return text


def _has_message_header(text: str) -> bool:
    first_line = next((line for line in text.splitlines() if line.strip()), "")
    if not first_line:
        return False
    try:
        dialect = csv.Sniffer().sniff(first_line, delimiters=",;\t|")
    except csv.Error:
        return False
    columns = next(csv.reader([first_line], dialect))
    return any(column.strip().lower() in _MESSAGE_ALIASES for column in columns)


def _parse_csv(text: str) -> list[dict[str, Any]]:
    try:
        try:
            delimiter = csv.Sniffer().sniff(text[:4096], delimiters=",;\t|").delimiter
        except csv.Error:
            delimiter = ","
        frame = pd.read_csv(
            io.StringIO(text), sep=delimiter, dtype=str, keep_default_na=False
        )
    except (pd.errors.ParserError, pd.errors.EmptyDataError, UnicodeError) as exc:
        raise IngestionError(f"Unable to parse CSV: {exc}") from exc
    if frame.empty:
        raise IngestionError("The CSV contains a header but no log records.")

    column_map: dict[str, str] = {}
    for column in frame.columns:
        normalized = str(column).strip().lower()
        for field, aliases in _ALIASES.items():
            if normalized in aliases:
                column_map[field] = column
                break
    if "message" not in column_map:
        raise IngestionError(
            "CSV must have a message column (for example: message, log, content, or text)."
        )

    events = []
    for row in frame.to_dict(orient="records"):
        message = str(row[column_map["message"]]).strip()
        event = _new_event(message)
        for field, column in column_map.items():
            if field != "message":
                value = str(row[column]).strip()
                event[field] = value or None
        events.append(event)
    return events


def _parse_lines(text: str, log_format: str) -> list[dict[str, Any]]:
    events: list[dict[str, Any]] = []
    for raw_line in text.splitlines():
        line = raw_line.rstrip()
        if not line.strip():
            continue
        if events and _is_continuation(line, log_format):
            events[-1]["message"] += "\n" + line.strip()
            continue
        if log_format == "apache":
            match = _APACHE.match(line)
            if match:
                data = match.groupdict()
                events.append(
                    _new_event(
                        f'{data["request"]} (HTTP {data["status"]}, bytes {data["size"]})',
                        timestamp=_parse_apache_timestamp(data["timestamp"]),
                        severity="ERROR" if int(data["status"]) >= 500 else "WARN"
                        if int(data["status"]) >= 400
                        else "INFO",
                        host=data["host"],
                        source="apache",
                    )
                )
                continue
        match = _JAVA_START.match(line) if log_format == "java" else _GENERIC_START.match(line)
        if match:
            groups = match.groupdict()
            message = groups.get("message") or groups.get("body") or line
            timestamp = _parse_timestamp(groups.get("timestamp"))
            severity = groups.get("level") or _extract_level(line)
        else:
            message, timestamp, severity = line.strip(), None, _extract_level(line)
        events.append(
            _new_event(message, timestamp=timestamp, severity=severity, source=log_format)
        )
    return events


def _is_continuation(line: str, log_format: str) -> bool:
    if log_format == "java":
        return line[:1].isspace() or line.lstrip().startswith(("at ", "... ", "Caused by:"))
    if log_format == "text":
        return bool(line[:1].isspace()) and not _GENERIC_START.match(line)
    return False


def _new_event(
    message: str,
    timestamp: str | None = None,
    severity: str | None = None,
    host: str | None = None,
    source: str | None = None,
) -> dict[str, Any]:
    return {
        "event_id": str(uuid4()),
        "timestamp": timestamp,
        "severity": severity.upper() if severity else None,
        "host": host,
        "service": None,
        "source": source,
        "message": message,
    }


def _parse_timestamp(value: str | None) -> str | None:
    if not value:
        return None
    parsed = pd.to_datetime(value, errors="coerce", utc=True)
    return None if pd.isna(parsed) else parsed.isoformat()


def _parse_apache_timestamp(value: str) -> str | None:
    try:
        parsed = datetime.strptime(value, "%d/%b/%Y:%H:%M:%S %z")
    except ValueError:
        return None
    return parsed.isoformat()


def _extract_level(line: str) -> str | None:
    match = _LEVEL.search(line)
    return match.group(1).upper() if match else None
