"use client";

import { useCallback, useEffect, useMemo, useState } from "react";
import type { ChangeEvent, DragEvent, FormEvent } from "react";
import Link from "next/link";
import {
  Area,
  AreaChart,
  Bar,
  BarChart,
  CartesianGrid,
  Cell,
  Legend,
  Pie,
  PieChart,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";

const API_BASE =
  process.env.NEXT_PUBLIC_API_BASE_URL?.replace(/\/$/, "") ?? "http://127.0.0.1:8000";
const API_KEY = process.env.NEXT_PUBLIC_API_KEY ?? "";
const ACCEPTED_EXTENSIONS = new Set(["csv", "txt", "log", "pdf"]);

function apiHeaders(): HeadersInit {
  return API_KEY ? { Authorization: `Bearer ${API_KEY}` } : {};
}

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

type PageView = "upload" | "analytics" | "logs" | "history";

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
  const [activeView, setActiveView] = useState<PageView>("upload");
  const [theme, setTheme] = useState<"light" | "dark">("light");
  const [historySearch, setHistorySearch] = useState("");
  const [historyFormat, setHistoryFormat] = useState("all");
  const [file, setFile] = useState<File | null>(null);
  const [maxUploadMb, setMaxUploadMb] = useState(100);
  const [contamination] = useState(0.1);
  const [groupingWindow, setGroupingWindow] = useState(5);
  const [excludeAnomalies, setExcludeAnomalies] = useState(true);
  const [result, setResult] = useState<AnalysisResult | null>(null);
  const [history, setHistory] = useState<AnalysisSummary[]>([]);
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);
  const [uploadProgress, setUploadProgress] = useState(0);
  const [method] = useState("auto");
  const [selectedCluster, setSelectedCluster] = useState<string | null>(null);
  const [viewFilter, setViewFilter] = useState<"anomalies" | "normal" | "all">("anomalies");

  const refreshHistory = useCallback(async () => {
    try {
      const [health, historyResponse] = await Promise.all([
        fetch(`${API_BASE}/api/health`, { cache: "no-store" }),
        fetch(`${API_BASE}/api/analyses?limit=20`, {
          cache: "no-store",
          headers: apiHeaders(),
        }),
      ]);
      if (health.ok) {
        const healthData = (await health.json()) as { max_upload_mb?: number };
        if (typeof healthData.max_upload_mb === "number") {
          setMaxUploadMb(healthData.max_upload_mb);
        }
      }
      if (historyResponse.ok) {
        const data = (await historyResponse.json()) as { analyses: AnalysisSummary[] };
        setHistory(data.analyses);
      }
    } catch {
      // background refresh, silent error
    }
  }, []);

  useEffect(() => {
    document.documentElement.dataset.theme = theme;
  }, [theme]);

  useEffect(() => {
    const initialCheck = window.setTimeout(() => void refreshHistory(), 0);
    const intervalId = window.setInterval(() => void refreshHistory(), 5000);
    return () => {
      window.clearTimeout(initialCheck);
      window.clearInterval(intervalId);
    };
  }, [refreshHistory]);

  const anomalies = useMemo(
    () => result?.events.filter((event) => event.is_anomaly) ?? [],
    [result],
  );
  const normalEvents = useMemo(
    () => result?.events.filter((event) => !event.is_anomaly) ?? [],
    [result],
  );
  const anomalyDistribution = useMemo(
    () => [
      { name: "Normal", value: normalEvents.length, color: "#16A34A" },
      { name: "Anomaly", value: anomalies.length, color: "#DC2626" },
    ],
    [anomalies, normalEvents],
  );

  const scoreDistribution = useMemo(() => {
    if (!result) return [];
    const buckets = [
      { range: "0.0-0.2", min: 0, max: 0.2, count: 0 },
      { range: "0.2-0.4", min: 0.2, max: 0.4, count: 0 },
      { range: "0.4-0.6", min: 0.4, max: 0.6, count: 0 },
      { range: "0.6-0.8", min: 0.6, max: 0.8, count: 0 },
      { range: "0.8-1.0", min: 0.8, max: 1.01, count: 0 },
    ];
    for (const event of result.events) {
      const bucket = buckets.find(
        (item) => event.anomaly_score >= item.min && event.anomaly_score < item.max,
      );
      if (bucket) bucket.count += 1;
    }
    return buckets.map(({ range, count }) => ({ range, events: count }));
  }, [result]);

  const timelineData = useMemo(() => {
    if (!result?.events.length) return [];
    const events = result.events.filter((e) => e.timestamp);
    if (events.length < 2) return [];
    const times = events.map((e) => new Date(e.timestamp!).getTime()).filter(Number.isFinite);
    if (!times.length) return [];
    const minTime = Math.min(...times);
    const maxTime = Math.max(...times);
    const range = maxTime - minTime;
    const bucketCount = Math.min(20, Math.max(5, Math.ceil(events.length / 4)));
    const bucketSize = range / bucketCount || 60000;
    const buckets: { time: string; normal: number; anomaly: number }[] = Array.from({ length: bucketCount }, (_, i) => ({
      time: new Date(minTime + i * bucketSize).toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" }),
      normal: 0,
      anomaly: 0,
    }));
    for (const event of events) {
      const t = new Date(event.timestamp!).getTime();
      if (!Number.isFinite(t)) continue;
      const idx = Math.min(bucketCount - 1, Math.floor((t - minTime) / bucketSize));
      if (event.is_anomaly) buckets[idx].anomaly += 1;
      else buckets[idx].normal += 1;
    }
    return buckets;
  }, [result]);

  const severityData = useMemo(() => {
    if (!result?.events.length) return [];
    const counts: Record<string, { normal: number; anomaly: number }> = {};
    const order = ["CRITICAL", "ERROR", "WARN", "WARNING", "INFO", "DEBUG"];
    for (const event of result.events) {
      const sev = (event.severity ?? "INFO").toUpperCase();
      if (!counts[sev]) counts[sev] = { normal: 0, anomaly: 0 };
      if (event.is_anomaly) counts[sev].anomaly += 1;
      else counts[sev].normal += 1;
    }
    return order
      .filter((s) => counts[s])
      .map((s) => ({ severity: s, ...counts[s] }))
      .concat(
        Object.keys(counts)
          .filter((s) => !order.includes(s))
          .map((s) => ({ severity: s, ...counts[s] })),
      );
  }, [result]);

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

  const filteredHistory = useMemo(() => {
    const query = historySearch.trim().toLowerCase();
    return history.filter((item) => {
      const matchesSearch =
        !query ||
        item.filename.toLowerCase().includes(query) ||
        item.file_format.toLowerCase().includes(query);
      return matchesSearch && (historyFormat === "all" || item.file_format === historyFormat);
    });
  }, [history, historyFormat, historySearch]);

  const historyFormats = useMemo(
    () => [...new Set(history.map((item) => item.file_format))].sort(),
    [history],
  );

  // Clusters with detailed differentiation
  const clusterDetails = useMemo(() => {
    if (!result?.events) return [];
    const map = new Map<string, { total: number; anomalies: number; sampleMessage: string }>();
    for (const ev of result.events) {
      const cid = ev.cluster_id || "Outlier";
      const existing = map.get(cid) || { total: 0, anomalies: 0, sampleMessage: ev.message };
      existing.total += 1;
      if (ev.is_anomaly) existing.anomalies += 1;
      map.set(cid, existing);
    }
    return Array.from(map.entries())
      .map(([name, data]) => ({
        name,
        total: data.total,
        anomalies: data.anomalies,
        sampleMessage: data.sampleMessage,
        isOutlier: name.toLowerCase().includes("outlier"),
      }))
      .sort((a, b) => {
        if (a.isOutlier) return 1;
        if (b.isOutlier) return -1;
        return b.total - a.total;
      });
  }, [result]);

  const clusterChartData = useMemo(() => {
    return clusterDetails.slice(0, 8).map((c) => ({
      name: c.name.length > 25 ? `${c.name.slice(0, 22)}...` : c.name,
      fullName: c.name,
      events: c.total,
      anomalies: c.anomalies,
    }));
  }, [clusterDetails]);

  function acceptFile(selected: File | null) {
    setError("");
    if (!selected) {
      setFile(null);
      return;
    }
    if (!isAcceptedFile(selected)) {
      setFile(null);
      setError("Unsupported file format. Please choose a .csv, .txt, .log, or .pdf file.");
      return;
    }
    if (selected.size > maxUploadMb * 1024 * 1024) {
      setFile(null);
      setError(`File exceeds the ${maxUploadMb} MB upload limit.`);
      return;
    }
    setFile(selected);
  }

  function chooseFile(event: ChangeEvent<HTMLInputElement>) {
    acceptFile(event.target.files?.[0] ?? null);
  }

  function dropFile(event: DragEvent<HTMLDivElement>) {
    event.preventDefault();
    acceptFile(event.dataTransfer.files?.[0] ?? null);
  }

  async function submitUpload(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!file) {
      setError("Please select a log file before starting analysis.");
      return;
    }
    setBusy(true);
    setUploadProgress(0);
    setError("");
    const body = new FormData();
    body.append("file", file);
    body.append("method", method);
    body.append("contamination", String(contamination));
    body.append("grouping_window_minutes", String(groupingWindow));
    try {
      const payload = await new Promise<AnalysisResult>((resolve, reject) => {
        const xhr = new XMLHttpRequest();
        xhr.open("POST", `${API_BASE}/api/upload`);
        if (API_KEY) xhr.setRequestHeader("Authorization", `Bearer ${API_KEY}`);
        xhr.upload.onprogress = (progressEvent) => {
          if (progressEvent.lengthComputable) {
            setUploadProgress(Math.round((progressEvent.loaded / progressEvent.total) * 100));
          }
        };
        xhr.onload = () => {
          if (xhr.status >= 200 && xhr.status < 300) {
            try {
              resolve(JSON.parse(xhr.responseText) as AnalysisResult);
            } catch {
              reject(new Error("Server returned invalid response."));
            }
            return;
          }
          try {
            const bodyRes = JSON.parse(xhr.responseText) as { detail?: string };
            reject(new Error(bodyRes.detail ?? `Upload failed (${xhr.status}).`));
          } catch {
            reject(new Error(`Upload failed (${xhr.status}).`));
          }
        };
        xhr.onerror = () => reject(new Error("Could not connect to the backend API. Please make sure the backend is running."));
        xhr.send(body);
      });
      setResult(payload);
      setSelectedCluster(null);
      setViewFilter("anomalies");
      setActiveView("analytics"); // automatically navigate to visual analytics
      await refreshHistory();
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : "Analysis failed.");
    } finally {
      setBusy(false);
      setUploadProgress(0);
    }
  }

  async function openAnalysis(analysisId: string) {
    setBusy(true);
    setError("");
    try {
      const response = await fetch(`${API_BASE}/api/analyses/${analysisId}`, {
        cache: "no-store",
        headers: apiHeaders(),
      });
      if (!response.ok) throw new Error(await readError(response));
      setResult((await response.json()) as AnalysisResult);
      setSelectedCluster(null);
      setViewFilter("anomalies");
      setActiveView("analytics");
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : "Could not load this analysis.");
    } finally {
      setBusy(false);
    }
  }

  const displayedEvents = useMemo(() => {
    let list = result?.events ?? [];
    if (viewFilter === "anomalies") {
      list = anomalies;
    } else if (viewFilter === "normal") {
      list = normalEvents;
    }
    if (selectedCluster) {
      list = list.filter((event) => (event.cluster_id || "Outlier") === selectedCluster);
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
        { headers: apiHeaders() },
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
      {/* Top Header */}
      <header className="topbar">
        <Link className="brand" href="/" aria-label="Anomaly Detect home">
          <span className="brand-mark">A</span>
          <span>Anomaly Detect</span>
        </Link>
        <div className="topbar-actions">
          <button
            className="button button-secondary theme-toggle"
            onClick={() => setTheme(theme === "dark" ? "light" : "dark")}
            type="button"
            title={theme === "dark" ? "Switch to light mode" : "Switch to dark mode"}
            aria-label={theme === "dark" ? "Switch to light mode" : "Switch to dark mode"}
          >
            {theme === "dark" ? (
              /* Sun icon (switch to light mode) */
              <svg
                width="18"
                height="18"
                viewBox="0 0 24 24"
                fill="none"
                xmlns="http://www.w3.org/2000/svg"
                className="theme-icon"
                aria-hidden="true"
              >
                <circle cx="12" cy="12" r="5" fill="currentColor" />
                <line x1="12" y1="1.5" x2="12" y2="4.5" stroke="currentColor" strokeWidth="2.2" strokeLinecap="round" />
                <line x1="12" y1="19.5" x2="12" y2="22.5" stroke="currentColor" strokeWidth="2.2" strokeLinecap="round" />
                <line x1="1.5" y1="12" x2="4.5" y2="12" stroke="currentColor" strokeWidth="2.2" strokeLinecap="round" />
                <line x1="19.5" y1="12" x2="22.5" y2="12" stroke="currentColor" strokeWidth="2.2" strokeLinecap="round" />
                <line x1="4.5" y1="4.5" x2="6.6" y2="6.6" stroke="currentColor" strokeWidth="2.2" strokeLinecap="round" />
                <line x1="17.4" y1="17.4" x2="19.5" y2="19.5" stroke="currentColor" strokeWidth="2.2" strokeLinecap="round" />
                <line x1="4.5" y1="19.5" x2="6.6" y2="17.4" stroke="currentColor" strokeWidth="2.2" strokeLinecap="round" />
                <line x1="17.4" y1="6.6" x2="19.5" y2="4.5" stroke="currentColor" strokeWidth="2.2" strokeLinecap="round" />
              </svg>
            ) : (
              /* Moon icon (switch to dark mode) */
              <svg
                width="18"
                height="18"
                viewBox="0 0 24 24"
                fill="currentColor"
                xmlns="http://www.w3.org/2000/svg"
                className="theme-icon"
                aria-hidden="true"
              >
                <path d="M21 12.79A9 9 0 1 1 11.21 3 7 7 0 0 0 21 12.79z" />
              </svg>
            )}
          </button>
        </div>
      </header>

      <div className="layout">
        {/* Navigation Sidebar with page-wise views */}
        <aside className="sidebar">
          <div className="sidebar-label">NAVIGATION</div>
          <button
            className={`nav-item ${activeView === "upload" ? "active" : ""}`}
            onClick={() => setActiveView("upload")}
            type="button"
          >
            <span>▤</span> Upload & Ingest
          </button>
          <button
            className={`nav-item ${activeView === "analytics" ? "active" : ""}`}
            onClick={() => {
              if (result) setActiveView("analytics");
              else setError("Please upload or open an analysis first.");
            }}
            type="button"
          >
            <span>📊</span> Visual Analytics
            {result && <span className="nav-badge">{anomalies.length}</span>}
          </button>
          <button
            className={`nav-item ${activeView === "logs" ? "active" : ""}`}
            onClick={() => {
              if (result) setActiveView("logs");
              else setError("Please upload or open an analysis first.");
            }}
            type="button"
          >
            <span>📋</span> Log Evidence
            {result && <span className="nav-badge">{result.events.length}</span>}
          </button>
          <button
            className={`nav-item ${activeView === "history" ? "active" : ""}`}
            onClick={() => setActiveView("history")}
            type="button"
          >
            <span>◷</span> Analysis History
            {history.length > 0 && <span className="nav-badge">{history.length}</span>}
          </button>

          <div className="sidebar-note">
            <span className="note-icon">i</span>
            <p>Anomalies represent statistical deviations that warrant investigation.</p>
          </div>
          <div className="sidebar-footer">LOG ANOMALY DETECTOR</div>
        </aside>

        {/* Main Content Area */}
        <section className="content">
          {error && <div className="banner banner-error" role="alert">{error}</div>}

          {/* Active Result Sub-navigation Banner */}
          {result && activeView !== "history" && (
            <div className="result-subbar">
              <div className="result-meta">
                <span className="file-tag">{result.file_format.toUpperCase()}</span>
                <strong>{result.filename}</strong>
                <span>({result.events.length.toLocaleString()} events · {anomalies.length} flagged)</span>
              </div>
              <div className="result-tabs">
                <button
                  className={`subbar-btn ${activeView === "analytics" ? "active" : ""}`}
                  onClick={() => setActiveView("analytics")}
                  type="button"
                >
                  📊 Visual Analytics
                </button>
                <button
                  className={`subbar-btn ${activeView === "logs" ? "active" : ""}`}
                  onClick={() => setActiveView("logs")}
                  type="button"
                >
                  📋 Log Evidence
                </button>
                <button
                  className={`subbar-btn ${activeView === "upload" ? "active" : ""}`}
                  onClick={() => setActiveView("upload")}
                  type="button"
                >
                  + Upload New
                </button>
              </div>
            </div>
          )}

          {/* PAGE 1: Upload & Ingest */}
          {activeView === "upload" && (
            <div className="page-section">
              <div className="page-heading">
                <div>
                  <div className="eyebrow">DATA INGESTION</div>
                  <h1>Upload log file</h1>
                  <p>Upload system, application, or server logs for anomaly detection and clustering.</p>
                </div>
              </div>

              <section className="panel upload-panel">
                <form onSubmit={submitUpload}>
                  <div
                    className="dropzone"
                    onDragOver={(event) => event.preventDefault()}
                    onDrop={dropFile}
                  >
                    <input
                      accept=".csv,.txt,.log,.pdf"
                      className="visually-hidden"
                      id="log-file"
                      onChange={chooseFile}
                      type="file"
                    />
                    <span className="upload-icon">↑</span>
                    <label className="drop-title" htmlFor="log-file">
                      {file ? file.name : "Choose a log file or drag & drop here"}
                    </label>
                    <span className="drop-hint">
                      {file
                        ? `${(file.size / 1024).toFixed(1)} KB · Ready to analyze`
                        : `Supports .csv, .txt, .log, and .pdf files up to ${maxUploadMb} MB`}
                    </span>
                    {file && (
                      <button
                        className="button button-secondary"
                        onClick={() => setFile(null)}
                        style={{ marginTop: "12px", fontSize: "11px", padding: "4px 10px" }}
                        type="button"
                      >
                        Remove file
                      </button>
                    )}
                  </div>

                  <div className="settings-row" style={{ marginTop: "18px" }}>
                    <label style={{ maxWidth: "320px" }}>
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
                        <option value={60}>60 minutes</option>
                      </select>
                      <small className="field-hint">
                        Events with matching host/service within this window are grouped.
                      </small>
                    </label>
                  </div>

                  <div className="form-footer">
                    <span className="privacy-hint">Processing is performed locally on your machine.</span>
                    <button className="button button-primary" disabled={busy || !file} type="submit">
                      {busy ? <><span className="spinner" /> Analyzing logs…</> : "Analyze logs"}
                    </button>
                  </div>

                  {busy && (
                    <div className="upload-progress" role="progressbar" aria-valuemin={0} aria-valuemax={100} aria-valuenow={uploadProgress}>
                      <span style={{ width: `${uploadProgress}%` }} />
                      <small>{uploadProgress > 0 ? `Uploading: ${uploadProgress}%` : "Processing logs..."}</small>
                    </div>
                  )}
                </form>
              </section>
            </div>
          )}

          {/* PAGE 2: Visual Analytics & Graphs */}
          {activeView === "analytics" && result && (
            <div className="page-section">
              <div className="page-heading">
                <div>
                  <div className="eyebrow">VISUAL DASHBOARD</div>
                  <h1>Anomaly analytics & patterns</h1>
                  <p>Visual breakdown of anomalous events, temporal distribution, and semantic log clusters.</p>
                </div>
                <button
                  className="button button-primary"
                  onClick={() => setActiveView("logs")}
                  type="button"
                >
                  View Log Evidence →
                </button>
              </div>

              {/* Metrics Grid */}
              <section className="metrics-grid" aria-label="Analysis summary">
                <Metric label="Total Log Events" value={result.events.length.toLocaleString()} />
                <Metric label="Detected Anomalies" value={anomalies.length.toLocaleString()} accent />
                <Metric
                  label="Anomaly Ratio"
                  value={`${((anomalies.length / result.events.length) * 100 || 0).toFixed(1)}%`}
                />
                <Metric label="Identified Clusters" value={clusterDetails.length.toLocaleString()} />
                <Metric label="Alert Groups" value={groupCount.toLocaleString()} />
              </section>

              {evaluation && (
                <section className="metrics-grid evaluation-grid" aria-label="Evaluation metrics">
                  <Metric label="Precision" value={evaluation.precision.toFixed(3)} />
                  <Metric label="Recall" value={evaluation.recall.toFixed(3)} />
                  <Metric label="F1 score" value={evaluation.f1.toFixed(3)} />
                </section>
              )}

              {/* Primary Graphs */}
              <section className="visual-grid" aria-label="Anomaly visualizations">
                {/* Event Status Pie Chart */}
                <article className="panel chart-panel">
                  <div className="chart-heading">
                    <h3>Event status</h3>
                    <p>Clean vs anomalous log events</p>
                  </div>
                  <div className="chart-body chart-pie">
                    <ResponsiveContainer width="100%" height="100%">
                      <PieChart>
                        <Pie
                          data={anomalyDistribution}
                          dataKey="value"
                          nameKey="name"
                          innerRadius={48}
                          outerRadius={82}
                          paddingAngle={3}
                          stroke="none"
                        >
                          {anomalyDistribution.map((entry) => (
                            <Cell key={entry.name} fill={entry.color} />
                          ))}
                        </Pie>
                        <Tooltip
                          contentStyle={{
                            background: theme === "dark" ? "#111827" : "#FFFFFF",
                            border: `1px solid ${theme === "dark" ? "#1F2937" : "#E4E7EC"}`,
                            borderRadius: 8,
                            color: theme === "dark" ? "#F3F4F6" : "#111827",
                          }}
                        />
                        <Legend />
                      </PieChart>
                    </ResponsiveContainer>
                  </div>
                </article>

                {/* Score Distribution */}
                <article className="panel chart-panel">
                  <div className="chart-heading">
                    <h3>Score distribution</h3>
                    <p>Anomaly score bands (0.0 to 1.0)</p>
                  </div>
                  <div className="chart-body">
                    <ResponsiveContainer width="100%" height="100%">
                      <BarChart data={scoreDistribution}>
                        <CartesianGrid stroke={theme === "dark" ? "#1F2937" : "#E4E7EC"} strokeDasharray="3 3" />
                        <XAxis dataKey="range" stroke={theme === "dark" ? "#9CA3AF" : "#6B7280"} tick={{ fontSize: 10 }} />
                        <YAxis stroke={theme === "dark" ? "#9CA3AF" : "#6B7280"} tick={{ fontSize: 10 }} allowDecimals={false} />
                        <Tooltip
                          contentStyle={{
                            background: theme === "dark" ? "#111827" : "#FFFFFF",
                            border: `1px solid ${theme === "dark" ? "#1F2937" : "#E4E7EC"}`,
                            borderRadius: 8,
                            color: theme === "dark" ? "#F3F4F6" : "#111827",
                          }}
                        />
                        <Bar dataKey="events" fill="#2563EB" radius={[4, 4, 0, 0]} />
                      </BarChart>
                    </ResponsiveContainer>
                  </div>
                </article>

                {/* Cluster Distribution Bar Chart */}
                <article className="panel chart-panel">
                  <div className="chart-heading">
                    <h3>Cluster distribution</h3>
                    <p>Size of log pattern groups</p>
                  </div>
                  <div className="chart-body">
                    <ResponsiveContainer width="100%" height="100%">
                      <BarChart data={clusterChartData} layout="vertical">
                        <CartesianGrid stroke={theme === "dark" ? "#1F2937" : "#E4E7EC"} strokeDasharray="3 3" />
                        <XAxis type="number" stroke={theme === "dark" ? "#9CA3AF" : "#6B7280"} tick={{ fontSize: 10 }} allowDecimals={false} />
                        <YAxis
                          type="category"
                          dataKey="name"
                          width={110}
                          stroke={theme === "dark" ? "#9CA3AF" : "#6B7280"}
                          tick={{ fontSize: 9 }}
                        />
                        <Tooltip
                          contentStyle={{
                            background: theme === "dark" ? "#111827" : "#FFFFFF",
                            border: `1px solid ${theme === "dark" ? "#1F2937" : "#E4E7EC"}`,
                            borderRadius: 8,
                            color: theme === "dark" ? "#F3F4F6" : "#111827",
                          }}
                        />
                        <Bar dataKey="events" fill="#0EA5E9" radius={[0, 4, 4, 0]} />
                      </BarChart>
                    </ResponsiveContainer>
                  </div>
                </article>
              </section>

              {/* Anomaly Timeline */}
              {timelineData.length > 0 && (
                <section className="visual-grid visual-grid-wide" aria-label="Anomaly timeline">
                  <article className="panel chart-panel chart-panel-wide">
                    <div className="chart-heading">
                      <h3>Anomaly timeline</h3>
                      <p>Time series showing normal traffic vs anomaly spikes</p>
                    </div>
                    <div className="chart-body chart-body-tall">
                      <ResponsiveContainer width="100%" height="100%">
                        <AreaChart data={timelineData} margin={{ top: 10, right: 20, left: 0, bottom: 0 }}>
                          <defs>
                            <linearGradient id="normalGrad" x1="0" y1="0" x2="0" y2="1">
                              <stop offset="5%" stopColor="#16A34A" stopOpacity={0.3} />
                              <stop offset="95%" stopColor="#16A34A" stopOpacity={0.03} />
                            </linearGradient>
                            <linearGradient id="anomalyGrad" x1="0" y1="0" x2="0" y2="1">
                              <stop offset="5%" stopColor="#DC2626" stopOpacity={0.4} />
                              <stop offset="95%" stopColor="#DC2626" stopOpacity={0.03} />
                            </linearGradient>
                          </defs>
                          <CartesianGrid stroke={theme === "dark" ? "#1F2937" : "#E4E7EC"} strokeDasharray="3 3" />
                          <XAxis dataKey="time" stroke={theme === "dark" ? "#9CA3AF" : "#6B7280"} tick={{ fontSize: 10 }} />
                          <YAxis stroke={theme === "dark" ? "#9CA3AF" : "#6B7280"} tick={{ fontSize: 10 }} allowDecimals={false} />
                          <Tooltip
                            contentStyle={{
                              background: theme === "dark" ? "#111827" : "#FFFFFF",
                              border: `1px solid ${theme === "dark" ? "#1F2937" : "#E4E7EC"}`,
                              borderRadius: 8,
                              color: theme === "dark" ? "#F3F4F6" : "#111827",
                            }}
                          />
                          <Legend />
                          <Area type="monotone" dataKey="normal" name="Normal" stroke="#16A34A" fill="url(#normalGrad)" strokeWidth={2} dot={false} />
                          <Area type="monotone" dataKey="anomaly" name="Anomaly" stroke="#DC2626" fill="url(#anomalyGrad)" strokeWidth={2} dot={false} />
                        </AreaChart>
                      </ResponsiveContainer>
                    </div>
                  </article>
                </section>
              )}

              {/* Severity Breakdown */}
              {severityData.length > 0 && (
                <section className="visual-grid" aria-label="Severity breakdown">
                  <article className="panel chart-panel chart-panel-wide">
                    <div className="chart-heading">
                      <h3>Severity level breakdown</h3>
                      <p>Normal vs anomaly distribution across log severity levels</p>
                    </div>
                    <div className="chart-body">
                      <ResponsiveContainer width="100%" height="100%">
                        <BarChart data={severityData} margin={{ top: 10, right: 20, left: 0, bottom: 0 }}>
                          <CartesianGrid stroke={theme === "dark" ? "#1F2937" : "#E4E7EC"} strokeDasharray="3 3" />
                          <XAxis dataKey="severity" stroke={theme === "dark" ? "#9CA3AF" : "#6B7280"} tick={{ fontSize: 11 }} />
                          <YAxis stroke={theme === "dark" ? "#9CA3AF" : "#6B7280"} tick={{ fontSize: 10 }} allowDecimals={false} />
                          <Tooltip
                            contentStyle={{
                              background: theme === "dark" ? "#111827" : "#FFFFFF",
                              border: `1px solid ${theme === "dark" ? "#1F2937" : "#E4E7EC"}`,
                              borderRadius: 8,
                              color: theme === "dark" ? "#F3F4F6" : "#111827",
                            }}
                          />
                          <Legend />
                          <Bar dataKey="normal" name="Normal" fill="#16A34A" radius={[4, 4, 0, 0]} />
                          <Bar dataKey="anomaly" name="Anomaly" fill="#DC2626" radius={[4, 4, 0, 0]} />
                        </BarChart>
                      </ResponsiveContainer>
                    </div>
                  </article>
                </section>
              )}

              {/* Cluster Differentiation & Meaning Table */}
              <section className="panel cluster-explanation-panel">
                <div className="panel-heading">
                  <div>
                    <h2>Cluster differentiation & semantics</h2>
                    <p>What each identified cluster represents and its anomaly distribution.</p>
                  </div>
                </div>
                <div className="table-wrap">
                  <table>
                    <thead>
                      <tr>
                        <th>Cluster ID & Semantic Name</th>
                        <th>Type / Pattern</th>
                        <th>Sample Log Pattern</th>
                        <th>Total Events</th>
                        <th>Anomalies</th>
                        <th>Action</th>
                      </tr>
                    </thead>
                    <tbody>
                      {clusterDetails.map((c) => (
                        <tr key={c.name}>
                          <td>
                            <span className={`cluster-badge ${c.isOutlier ? "cluster-badge-outlier" : ""}`}>
                              {c.name}
                            </span>
                          </td>
                          <td>
                            {c.isOutlier ? (
                              <span style={{ color: "#EF4444", fontWeight: 600 }}>Unmatched / Rare Outlier</span>
                            ) : (
                              <span style={{ color: "#10B981" }}>Dense Routine Pattern</span>
                            )}
                          </td>
                          <td className="message-cell">
                            <code>{c.sampleMessage}</code>
                          </td>
                          <td>{c.total.toLocaleString()}</td>
                          <td>
                            <span style={{ color: c.anomalies > 0 ? "#EF4444" : "inherit", fontWeight: c.anomalies > 0 ? 600 : "normal" }}>
                              {c.anomalies} ({((c.anomalies / c.total) * 100).toFixed(0)}%)
                            </span>
                          </td>
                          <td>
                            <button
                              className="button button-secondary"
                              style={{ fontSize: "11px", padding: "4px 8px" }}
                              onClick={() => {
                                setSelectedCluster(c.name);
                                setActiveView("logs");
                              }}
                              type="button"
                            >
                              Inspect Logs
                            </button>
                          </td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              </section>
            </div>
          )}

          {/* PAGE 3: Investigation Evidence & Log Table */}
          {activeView === "logs" && result && (
            <div className="page-section">
              <div className="page-heading">
                <div>
                  <div className="eyebrow">INVESTIGATION EVIDENCE</div>
                  <h1>Log records & anomaly evidence</h1>
                  <p>Inspect individual log events, detection reasoning, and export reports.</p>
                </div>
                <div className="export-actions">
                  <button className="button button-secondary" onClick={() => void exportReport("pdf")} type="button">
                    Export PDF
                  </button>
                  <button className="button button-secondary" onClick={() => void exportReport("xlsx")} type="button">
                    Export Excel
                  </button>
                  <button
                    className="button button-secondary"
                    onClick={() =>
                      downloadFile("log-anomaly-results.json", JSON.stringify(exportEvents, null, 2), "application/json")
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
                          columns.map((col) => csvEscape(row[col as keyof EventRecord])).join(","),
                        ),
                      ].join("\r\n");
                      downloadFile("log-anomaly-results.csv", `\uFEFF${csv}`, "text/csv;charset=utf-8");
                    }}
                    type="button"
                  >
                    Export CSV
                  </button>
                </div>
              </div>

              {/* Exclusion toggle */}
              <label className="export-filter">
                <input
                  checked={excludeAnomalies}
                  onChange={(event) => setExcludeAnomalies(event.target.checked)}
                  type="checkbox"
                />
                Exclude detected anomalies from exported files ({exportEvents.length} clean events retained)
              </label>

              {/* Evidence Table Panel */}
              <section className="panel results-panel">
                <div className="panel-heading results-heading">
                  <div>
                    <h2>Log events table</h2>
                    <p>Review individual records, assigned cluster, anomaly score, and explanation.</p>
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
                      Anomalies ({anomalies.length})
                    </button>
                    <button
                      className={`filter-button ${viewFilter === "normal" ? "selected" : ""}`}
                      onClick={() => {
                        setViewFilter("normal");
                        setSelectedCluster(null);
                      }}
                      type="button"
                    >
                      Clean ({normalEvents.length})
                    </button>
                    <button
                      className={`filter-button ${viewFilter === "all" ? "selected" : ""}`}
                      onClick={() => {
                        setViewFilter("all");
                        setSelectedCluster(null);
                      }}
                      type="button"
                    >
                      All ({result.events.length})
                    </button>
                  </div>
                </div>

                {/* Cluster filter bar */}
                {clusterDetails.length > 0 && (
                  <div className="cluster-bar">
                    <span className="cluster-bar-label">Filter by Cluster:</span>
                    <button
                      className={`cluster-pill ${selectedCluster === null ? "selected" : ""}`}
                      onClick={() => setSelectedCluster(null)}
                      type="button"
                    >
                      All
                    </button>
                    {clusterDetails.map((c) => (
                      <button
                        key={c.name}
                        className={`cluster-pill ${c.isOutlier ? "outlier" : ""} ${
                          selectedCluster === c.name ? "selected" : ""
                        }`}
                        onClick={() => setSelectedCluster(selectedCluster === c.name ? null : c.name)}
                        type="button"
                      >
                        {c.name} ({c.total})
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
                          <th>Timestamp</th>
                          <th>Severity</th>
                          <th>Cluster (Meaning)</th>
                          <th>Message</th>
                          <th>Anomaly Score</th>
                          <th>Group</th>
                          <th>Reason Flagged</th>
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
                                {event.is_anomaly ? "ANOMALY" : "CLEAN"}
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
                                  event.cluster_id?.toLowerCase().includes("outlier") ? "cluster-badge-outlier" : ""
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
                    <div className="empty-state">No matching log records found for this filter.</div>
                  )}
                </div>
              </section>
            </div>
          )}

          {/* PAGE 4: Analysis History */}
          {activeView === "history" && (
            <div className="page-section">
              <section className="panel history-panel history-page">
                <div className="panel-heading">
                  <div>
                    <div className="eyebrow">AUDIT & HISTORY</div>
                    <h1>Analysis history</h1>
                    <p>Review past analyzed logs stored in local SQLite database.</p>
                  </div>
                  <button className="text-button" onClick={() => void refreshHistory()} type="button">
                    Refresh history
                  </button>
                </div>
                <div className="history-controls">
                  <label>
                    <span className="visually-hidden">Search analyses</span>
                    <input
                      onChange={(event) => setHistorySearch(event.target.value)}
                      placeholder="Search by file name or format"
                      type="search"
                      value={historySearch}
                    />
                  </label>
                  <label>
                    <span className="visually-hidden">Filter by format</span>
                    <select onChange={(event) => setHistoryFormat(event.target.value)} value={historyFormat}>
                      <option value="all">All formats</option>
                      {historyFormats.map((format) => <option key={format} value={format}>{format}</option>)}
                    </select>
                  </label>
                  <span className="history-count">{filteredHistory.length} run(s)</span>
                </div>
                {filteredHistory.length ? (
                  <div className="table-wrap history-table-wrap">
                    <table>
                      <thead>
                        <tr><th>File Name</th><th>Format</th><th>Events</th><th>Analyzed At</th><th /></tr>
                      </thead>
                      <tbody>
                        {filteredHistory.map((item) => (
                          <tr key={item.analysis_id}>
                            <td className="history-file-name">{item.filename}</td>
                            <td>{item.file_format}</td>
                            <td>{item.event_count.toLocaleString()}</td>
                            <td className="timestamp-cell">{new Date(item.created_at).toLocaleString()}</td>
                            <td>
                              <button
                                className="button button-secondary"
                                disabled={busy}
                                onClick={() => void openAnalysis(item.analysis_id)}
                                type="button"
                              >
                                View Analytics
                              </button>
                            </td>
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  </div>
                ) : (
                  <div className="history-empty">
                    {history.length ? "No analyses match your search." : "No saved analyses found yet."}
                  </div>
                )}
              </section>
            </div>
          )}

          {/* Footer */}
          <footer className="page-footer">
            Anomaly Detect · Explainable log anomaly detection system.
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
