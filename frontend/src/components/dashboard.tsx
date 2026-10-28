"use client";

import { useCallback, useEffect, useMemo, useState } from "react";
import type { ChangeEvent, FormEvent } from "react";
import Link from "next/link";

const API_BASE =
  process.env.NEXT_PUBLIC_API_BASE_URL?.replace(/\/$/, "") ?? "http://127.0.0.1:8000";
const MAX_FILE_BYTES = 25 * 1024 * 1024;
const ACCEPTED_EXTENSIONS = new Set(["csv", "txt", "log", "pdf"]);

type EventRecord = {
  event_id: string;
  timestamp: string | null;
  severity: string | null;
  host: string | null;
  service: string | null;
  message: string;
  template: string;
  anomaly_score: number;
  baseline_score: number;
  is_anomaly: boolean;
  group_id: string | null;
  cluster_id?: string | null;
  explanation: string;
  label?: string | number | boolean | null;
};

type AnalysisResult = {
  analysis_id: string;
  filename: string;
  file_format: string;
  format_confidence?: number;
  source_encoding: string;
  normalized_encoding: string;
  method: string;
  events: EventRecord[];
};

type AnalysisSummary = {
  analysis_id: string;
  created_at: string;
  filename: string;
  file_format: string;
  source_encoding: string;
  method: string;
  event_count: number;
};

function isAcceptedFile(file: File): boolean {
  return ACCEPTED_EXTENSIONS.has(file.name.split(".").pop()?.toLowerCase() ?? "");
}

async function readError(response: Response): Promise<string> {
  try {
    const body = (await response.json()) as { detail?: string };
    return body.detail ?? `Request failed (${response.status}).`;
  } catch {
    return `Request failed (${response.status}).`;
  }
}

function labelValue(value: EventRecord["label"]): boolean | null {
  const normalized = String(value ?? "").trim().toLowerCase();
  if (["1", "true", "anomaly", "abnormal", "yes"].includes(normalized)) return true;
  if (["0", "false", "normal", "no"].includes(normalized)) return false;
  return null;
}

function downloadFile(filename: string, content: string, type: string) {
  const blob = new Blob([content], { type });
  const url = URL.createObjectURL(blob);
  const link = document.createElement("a");
  link.href = url;
  link.download = filename;
  link.click();
  window.setTimeout(() => URL.revokeObjectURL(url), 1000);
}

function csvEscape(value: unknown): string {
  const text = value == null ? "" : String(value);
  return `"${text.replaceAll('"', '""')}"`;
}

export function Dashboard() {
  const [file, setFile] = useState<File | null>(null);
  const [contamination] = useState(0.1);
  const [groupingWindow, setGroupingWindow] = useState(5);
  const [excludeAnomalies, setExcludeAnomalies] = useState(true);
  const [result, setResult] = useState<AnalysisResult | null>(null);
  const [history, setHistory] = useState<AnalysisSummary[]>([]);
  const [error, setError] = useState("");
  const [apiOnline, setApiOnline] = useState(false);
  const [busy, setBusy] = useState(false);
  const [method] = useState("auto");
  const [selectedCluster, setSelectedCluster] = useState<string | null>(null);
  const [viewFilter, setViewFilter] = useState<"anomalies" | "normal" | "all">("anomalies");

  const refreshHistory = useCallback(async () => {
    try {
      const [health, historyResponse] = await Promise.all([
        fetch(`${API_BASE}/api/health`, { cache: "no-store" }),
        fetch(`${API_BASE}/api/analyses?limit=20`, { cache: "no-store" }),
      ]);
      if (!health.ok || !historyResponse.ok) throw new Error("API unavailable");
      const data = (await historyResponse.json()) as { analyses: AnalysisSummary[] };
      setHistory(data.analyses);
      setApiOnline(true);
    } catch {
      setApiOnline(false);
    }
  }, []);

  useEffect(() => {
    let active = true;
    Promise.all([
      fetch(`${API_BASE}/api/health`, { cache: "no-store" }),
      fetch(`${API_BASE}/api/analyses?limit=20`, { cache: "no-store" }),
    ])
      .then(async ([health, historyResponse]) => {
        if (!health.ok || !historyResponse.ok) throw new Error("API unavailable");
        const data = (await historyResponse.json()) as { analyses: AnalysisSummary[] };
        if (!active) return;
        setHistory(data.analyses);
        setApiOnline(true);
      })
      .catch(() => {
        if (active) setApiOnline(false);
      });
    return () => {
      active = false;
    };
  }, []);

  const anomalies = useMemo(
    () => result?.events.filter((event) => event.is_anomaly) ?? [],
    [result],
  );
  const normalEvents = useMemo(
    () => result?.events.filter((event) => !event.is_anomaly) ?? [],
    [result],
  );
  const groupCount = useMemo(
    () => new Set(anomalies.map((event) => event.group_id).filter(Boolean)).size,
    [anomalies],
  );
  const evaluation = useMemo(() => {
    if (!result?.events.length || !result.events.every((event) => labelValue(event.label) !== null)) {
      return null;
    }
    let truePositive = 0;
    let falsePositive = 0;
    let falseNegative = 0;
    for (const event of result.events) {
      const truth = labelValue(event.label);
      if (truth && event.is_anomaly) truePositive += 1;
      else if (!truth && event.is_anomaly) falsePositive += 1;
      else if (truth && !event.is_anomaly) falseNegative += 1;
    }
    const precision = truePositive / (truePositive + falsePositive) || 0;
    const recall = truePositive / (truePositive + falseNegative) || 0;
    return {
      precision,
      recall,
      f1: precision + recall ? (2 * precision * recall) / (precision + recall) : 0,
    };
  }, [result]);

  function chooseFile(event: ChangeEvent<HTMLInputElement>) {
    const selected = event.target.files?.[0] ?? null;
    setError("");
    setResult(null);
    if (!selected) {
      setFile(null);
      return;
    }
    if (!isAcceptedFile(selected)) {
      setFile(null);
      setError("Unsupported file. Choose a .csv, .txt, .log, or text-based .pdf file.");
      return;
    }
    if (selected.size > MAX_FILE_BYTES) {
      setFile(null);
      setError("File exceeds the 25 MB upload limit.");
      return;
    }
    setFile(selected);
  }

  async function submitUpload(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!file) {
      setError("Choose a log file before starting analysis.");
      return;
    }
    setBusy(true);
    setError("");
    setResult(null);
    const body = new FormData();
    body.append("file", file);
    body.append("method", method);
    body.append("contamination", String(contamination));
    body.append("grouping_window_minutes", String(groupingWindow));
    try {
      const response = await fetch(`${API_BASE}/api/upload`, { method: "POST", body });
      if (!response.ok) throw new Error(await readError(response));
      const payload = (await response.json()) as AnalysisResult;
      setResult(payload);
      setSelectedCluster(null);
      setApiOnline(true);
      await refreshHistory();
    } catch (reason) {
      setApiOnline(false);
      setError(reason instanceof Error ? reason.message : "The analysis request failed.");
    } finally {
      setBusy(false);
    }
  }

  async function openAnalysis(analysisId: string) {
    setBusy(true);
    setError("");
    try {
      const response = await fetch(`${API_BASE}/api/analyses/${analysisId}`, {
        cache: "no-store",
      });
      if (!response.ok) throw new Error(await readError(response));
      setResult((await response.json()) as AnalysisResult);
      setSelectedCluster(null);
      setViewFilter("anomalies");
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : "Could not load this analysis.");
    } finally {
      setBusy(false);
    }
  }

  const clusters = useMemo(() => {
    if (!result?.events) return [];
    const counts: Record<string, number> = {};
    for (const ev of result.events) {
      const cid = ev.cluster_id || "Unassigned";
      counts[cid] = (counts[cid] || 0) + 1;
    }
    return Object.entries(counts).sort((a, b) => {
      if (a[0] === "Outlier") return 1;
      if (b[0] === "Outlier") return -1;
      return b[1] - a[1];
    });
  }, [result]);

  const displayedEvents = useMemo(() => {
    let list = result?.events ?? [];
    if (viewFilter === "anomalies") {
      list = anomalies;
    } else if (viewFilter === "normal") {
      list = normalEvents;
    }
    if (selectedCluster) {
      list = list.filter((event) => (event.cluster_id || "Unassigned") === selectedCluster);
    }
    return list;
  }, [viewFilter, result, anomalies, normalEvents, selectedCluster]);

  const exportEvents = result?.events.filter(
    (event) => !excludeAnomalies || !event.is_anomaly,
  ) ?? [];

  async function exportReport(format: "pdf" | "xlsx") {
    if (!result) return;
    setError("");
    try {
      const query = new URLSearchParams({
        format,
        exclude_anomalies: String(excludeAnomalies),
      });
      const response = await fetch(
        `${API_BASE}/api/analyses/${result.analysis_id}/export?${query.toString()}`,
      );
      if (!response.ok) throw new Error(await readError(response));
      const blob = await response.blob();
      const url = URL.createObjectURL(blob);
      const link = document.createElement("a");
      link.href = url;
      link.download = `anomaly-detect-results.${format}`;
      link.click();
      window.setTimeout(() => URL.revokeObjectURL(url), 1000);
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : "Could not export this report.");
    }
  }

  return (
    <main className="app-shell">
      <header className="topbar">
        <Link className="brand" href="/" aria-label="Anomaly Detect home">
          <span className="brand-mark">A</span>
          <span>Anomaly Detect</span>
        </Link>
        <div className={`api-status ${apiOnline ? "online" : "offline"}`}>
          <span className="status-dot" />
          {apiOnline ? "API connected" : "API disconnected"}
        </div>
      </header>

      <div className="layout">
        <aside className="sidebar">
          <div className="sidebar-label">WORKSPACE</div>
          <a className="nav-item active" href="#analyze">
            <span>▤</span> Analyze logs
          </a>
          <a className="nav-item" href="#history">
            <span>◷</span> Analysis history
          </a>
          <div className="sidebar-note">
            <span className="note-icon">i</span>
            <p>An anomaly is a signal to investigate—not confirmation of an incident or cause.</p>
          </div>
          <div className="sidebar-footer">LOCAL DEVELOPMENT · v0.2</div>
        </aside>

        <section className="content">
          <div className="page-heading">
            <div>
              <div className="eyebrow">OBSERVABILITY / BATCH ANALYSIS</div>
              <h1>Log anomaly detection</h1>
              <p>Find unusual log patterns, inspect evidence, and reduce repetitive alerts.</p>
            </div>
            {result && (
              <button
                className="button button-secondary"
                onClick={() => {
                  setResult(null);
                  setFile(null);
                  setError("");
                  setViewFilter("anomalies");
                }}
                type="button"
              >
                + New analysis
              </button>
            )}
          </div>

          {!apiOnline && (
            <div className="banner banner-warning" role="status">
              <strong>Backend not connected.</strong> Start the FastAPI server on port 8000, then
              refresh this page.
              <code>python -m uvicorn log_anomaly.api.app:app --reload</code>
            </div>
          )}

          <section className="panel upload-panel" id="analyze">
            <div className="panel-heading">
              <div>
                <h2>Upload a log file</h2>
                <p>CSV, text logs, and text-based PDFs · up to 25 MB</p>
              </div>
              <span className="step-badge">01 / INGEST</span>
            </div>
            <form onSubmit={submitUpload}>
              <label className="dropzone" htmlFor="log-file">
                <input
                  accept=".csv,.txt,.log,.pdf"
                  className="visually-hidden"
                  id="log-file"
                  onChange={chooseFile}
                  type="file"
                />
                <span className="upload-icon">↑</span>
                <span className="drop-title">
                  {file ? file.name : "Drop your file here or browse"}
                </span>
                <span className="drop-hint">
                  {file
                    ? `${(file.size / 1024).toFixed(1)} KB · Ready for analysis`
                    : "Encoding is detected automatically and normalized to UTF-8"}
                </span>
              </label>

              <div className="settings-row settings-adjusted">
                <label>
                  <span>
                    Grouping window
                    <strong>Correlate alerts</strong>
                  </span>
                  <select
                    onChange={(event) => setGroupingWindow(Number(event.target.value))}
                    value={groupingWindow}
                  >
                    <option value={1}>1 minute</option>
                    <option value={5}>5 minutes (Recommended)</option>
                    <option value={10}>10 minutes</option>
                    <option value={15}>15 minutes</option>
                    <option value={30}>30 minutes</option>
                    <option value={60}>60 minutes (1 hour)</option>
                  </select>
                  <small className="field-hint">
                    Alerts with matching host, service, and template within this window are grouped into a single incident.
                  </small>
                </label>
                <div className="backend-auto-badge">
                  <div className="auto-badge-header">
                    <span className="badge-dot" />
                    <strong>Backend Auto-Detection</strong>
                  </div>
                  <p>
                    Detection method is automatically selected by the backend (TF-IDF + Isolation Forest &amp; semantic clustering) with an optimal 10% anomaly threshold.
                  </p>
                </div>
              </div>
              <div className="form-footer">
                <span className="privacy-hint">Files are processed locally by your backend.</span>
                <button className="button button-primary" disabled={busy || !file} type="submit">
                  {busy ? <><span className="spinner" /> Analyzing…</> : "Analyze logs"}
                </button>
              </div>
            </form>
          </section>

          {error && <div className="banner banner-error" role="alert">{error}</div>}

          {result && (
            <>
              <section className="result-header">
                <div>
                  <div className="eyebrow">ANALYSIS RESULT</div>
                  <h2>{result.filename}</h2>
                  <p>
                    {result.file_format} · {result.source_encoding} → UTF-8 · Automatic analysis
                    {typeof result.format_confidence === "number" &&
                      ` · format confidence ${(result.format_confidence * 100).toFixed(0)}%`}
                  </p>
                </div>
                <div className="export-actions">
                  <button
                    className="button button-secondary"
                    onClick={() => void exportReport("pdf")}
                    type="button"
                  >
                    Export PDF
                  </button>
                  <button
                    className="button button-secondary"
                    onClick={() => void exportReport("xlsx")}
                    type="button"
                  >
                    Export Excel
                  </button>
                  <button
                    className="button button-secondary"
                    onClick={() =>
                      downloadFile(
                        "log-anomaly-results.json",
                        JSON.stringify(exportEvents, null, 2),
                        "application/json",
                      )
                    }
                    type="button"
                  >
                    Export JSON
                  </button>
                  <button
                    className="button button-secondary"
                    onClick={() => {
                      const columns = Object.keys(result.events[0] ?? {});
                      const csv = [
                        columns.map(csvEscape).join(","),
                        ...exportEvents.map((row) =>
                          columns.map((column) => csvEscape(row[column as keyof EventRecord])).join(","),
                        ),
                      ].join("\r\n");
                      downloadFile("log-anomaly-results.csv", `\uFEFF${csv}`, "text/csv;charset=utf-8");
                    }}
                    type="button"
                  >
                    Export CSV
                  </button>
                </div>
              </section>
              <label className="export-filter">
                <input
                  checked={excludeAnomalies}
                  onChange={(event) => setExcludeAnomalies(event.target.checked)}
                  type="checkbox"
                />
                Remove detected anomalies from exported files
                <span>
                  {exportEvents.length} normal record(s) included;{" "}
                  {result.events.length - exportEvents.length} anomalous record(s) excluded
                </span>
              </label>

              <section className="metrics-grid" aria-label="Analysis summary">
                <Metric label="Log events" value={result.events.length.toLocaleString()} />
                <Metric label="Anomalies" value={anomalies.length.toLocaleString()} accent />
                <Metric label="Clusters" value={clusters.length.toLocaleString()} />
                <Metric label="Alert groups" value={groupCount.toLocaleString()} />
                <Metric
                  label="Anomaly rate"
                  value={`${((anomalies.length / result.events.length) * 100 || 0).toFixed(1)}%`}
                />
              </section>
              {anomalies.length / result.events.length > contamination && (
                <p className="tie-note">
                  The flagged rate is above the configured {Math.round(contamination * 100)}%
                  threshold because multiple records share the same boundary score; equal
                  scores are included rather than arbitrarily discarding evidence.
                </p>
              )}

              {evaluation && (
                <section className="metrics-grid evaluation-grid" aria-label="Evaluation metrics">
                  <Metric label="Precision" value={evaluation.precision.toFixed(3)} />
                  <Metric label="Recall" value={evaluation.recall.toFixed(3)} />
                  <Metric label="F1 score" value={evaluation.f1.toFixed(3)} />
                  <div className="evaluation-note">Calculated from the uploaded per-event labels.</div>
                </section>
              )}

              <section className="panel results-panel">
                <div className="panel-heading results-heading">
                  <div>
                    <h2>Investigation evidence</h2>
                    <p>Review flagged messages, score, grouping, clusters, and detector explanation.</p>
                  </div>
                  <div className="table-actions">
                    <button
                      className={`filter-button ${viewFilter === "anomalies" ? "selected" : ""}`}
                      onClick={() => {
                        setViewFilter("anomalies");
                        setSelectedCluster(null);
                      }}
                      type="button"
                    >
                      Detected Anomalies ({anomalies.length})
                    </button>
                    <button
                      className={`filter-button ${viewFilter === "normal" ? "selected" : ""}`}
                      onClick={() => {
                        setViewFilter("normal");
                        setSelectedCluster(null);
                      }}
                      type="button"
                    >
                      Clean / Normal ({normalEvents.length})
                    </button>
                    <button
                      className={`filter-button ${viewFilter === "all" ? "selected" : ""}`}
                      onClick={() => {
                        setViewFilter("all");
                        setSelectedCluster(null);
                      }}
                      type="button"
                    >
                      All Events ({result.events.length})
                    </button>
                  </div>
                </div>

                {clusters.length > 0 && (
                  <div className="cluster-bar">
                    <span className="cluster-bar-label">Filter by Cluster:</span>
                    <button
                      className={`cluster-pill ${selectedCluster === null ? "selected" : ""}`}
                      onClick={() => setSelectedCluster(null)}
                      type="button"
                    >
                      All ({viewFilter === "all" ? result.events.length : viewFilter === "normal" ? normalEvents.length : anomalies.length})
                    </button>
                    {clusters.map(([cName, count]) => (
                      <button
                        key={cName}
                        className={`cluster-pill ${cName === "Outlier" ? "outlier" : ""} ${
                          selectedCluster === cName ? "selected" : ""
                        }`}
                        onClick={() => setSelectedCluster(selectedCluster === cName ? null : cName)}
                        type="button"
                      >
                        {cName} ({count})
                      </button>
                    ))}
                  </div>
                )}

                <div className="table-wrap">
                  {displayedEvents.length ? (
                    <table>
                      <thead>
                        <tr>
                          <th>Status</th>
                          <th>Time</th>
                          <th>Severity</th>
                          <th>Cluster</th>
                          <th>Message / evidence</th>
                          <th>Score</th>
                          <th>Group</th>
                          <th>Why flagged</th>
                        </tr>
                      </thead>
                      <tbody>
                        {displayedEvents.map((event) => (
                          <tr key={event.event_id}>
                            <td>
                              <span
                                className={`status-pill ${
                                  event.is_anomaly ? "status-pill-anomaly" : "status-pill-normal"
                                }`}
                              >
                                {event.is_anomaly ? "ANOMALY (Excluded)" : "CLEAN (Retained)"}
                              </span>
                            </td>
                            <td className="timestamp-cell">
                              {event.timestamp ? new Date(event.timestamp).toLocaleString() : "—"}
                            </td>
                            <td>
                              <span className={`severity severity-${(event.severity ?? "info").toLowerCase()}`}>
                                {event.severity ?? "INFO"}
                              </span>
                            </td>
                            <td>
                              <span
                                className={`cluster-badge ${
                                  event.cluster_id === "Outlier" ? "cluster-badge-outlier" : ""
                                }`}
                              >
                                {event.cluster_id ?? "—"}
                              </span>
                            </td>
                            <td className="message-cell">
                              <span>{event.message}</span>
                              <small>{event.host ?? event.service ?? event.template}</small>
                            </td>
                            <td>
                              <div className="score-cell">
                                <span>{event.anomaly_score.toFixed(3)}</span>
                                <span className="score-track">
                                  <span style={{ width: `${Math.min(100, event.anomaly_score * 100)}%` }} />
                                </span>
                              </div>
                            </td>
                            <td>{event.group_id ?? "—"}</td>
                            <td className="explanation-cell">{event.explanation}</td>
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  ) : (
                    <div className="empty-state">
                      {viewFilter === "anomalies" && "No anomalies were flagged."}
                      {viewFilter === "normal" && "No normal events found."}
                      {viewFilter === "all" && "No events in this analysis."}
                    </div>
                  )}
                </div>
              </section>
            </>
          )}

          <section className="panel history-panel" id="history">
            <div className="panel-heading">
              <div>
                <h2>Recent analyses</h2>
                <p>Stored locally in SQLite on the API server.</p>
              </div>
              <button className="text-button" onClick={() => void refreshHistory()} type="button">
                Refresh
              </button>
            </div>
            {history.length ? (
              <div className="history-list">
                {history.map((item) => (
                  <button
                    className="history-row"
                    disabled={busy}
                    key={item.analysis_id}
                    onClick={() => void openAnalysis(item.analysis_id)}
                    type="button"
                  >
                    <span className="history-file-icon">▤</span>
                    <span className="history-name">
                      <strong>{item.filename}</strong>
                      <small>
                        {item.file_format} · {item.event_count} events ·{" "}
                        {new Date(item.created_at).toLocaleString()}
                      </small>
                    </span>
                    <span className="history-open">Open →</span>
                  </button>
                ))}
              </div>
            ) : (
              <div className="history-empty">
                {apiOnline ? "No saved analyses yet. Upload a log file to begin." : "Connect the API to view local analysis history."}
              </div>
            )}
          </section>

          <footer className="page-footer">
            Anomaly Detect · No log is proof of an incident without human investigation.
            <a href={`${API_BASE}/api/alerts/export?format=csv`} rel="noreferrer" target="_blank">
              Export saved alerts
            </a>
          </footer>
        </section>
      </div>
    </main>
  );
}

function Metric({ label, value, accent = false }: { label: string; value: string; accent?: boolean }) {
  return (
    <div className={`metric-card ${accent ? "metric-accent" : ""}`}>
      <span>{label}</span>
      <strong>{value}</strong>
    </div>
  );
}
