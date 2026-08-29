"use client";

import { useState, useEffect, useCallback, useRef } from "react";

const API = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

// ═══════════════════════════════════════════════════════════
// HOOKS
// ═══════════════════════════════════════════════════════════

function useAPI(endpoint, interval = 3000) {
  const [data, setData] = useState(null);
  const [error, setError] = useState(null);

  const fetchData = useCallback(async () => {
    try {
      const res = await fetch(`${API}${endpoint}`);
      if (!res.ok) throw new Error(`HTTP ${res.status}`);
      const json = await res.json();
      setData(json);
      setError(null);
    } catch (err) {
      setError(err.message);
    }
  }, [endpoint]);

  useEffect(() => {
    const initial = window.setTimeout(fetchData, 0);
    const id = setInterval(fetchData, interval);
    return () => {
      clearTimeout(initial);
      clearInterval(id);
    };
  }, [fetchData, interval]);

  return { data, error, refetch: fetchData };
}

function useWebSocket() {
  const [wsData, setWsData] = useState(null);
  const [connected, setConnected] = useState(false);
  const wsRef = useRef(null);

  useEffect(() => {
    const wsUrl = API.replace("http", "ws") + "/ws";
    let ws;
    let reconnectTimer;

    function connect() {
      ws = new WebSocket(wsUrl);
      wsRef.current = ws;

      ws.onopen = () => setConnected(true);
      ws.onclose = () => {
        setConnected(false);
        reconnectTimer = setTimeout(connect, 3000);
      };
      ws.onerror = () => ws.close();
      ws.onmessage = (e) => {
        try {
          setWsData(JSON.parse(e.data));
        } catch { }
      };
    }

    connect();
    return () => {
      clearTimeout(reconnectTimer);
      if (wsRef.current) wsRef.current.close();
    };
  }, []);

  return { wsData, connected };
}

// ═══════════════════════════════════════════════════════════
// UTILITY
// ═══════════════════════════════════════════════════════════

function getStatusClass(status) {
  const s = (status || "").toLowerCase();
  if (s === "healthy") return "healthy";
  if (s === "warning") return "warning";
  if (s === "degraded") return "degraded";
  if (s === "critical") return "critical";
  if (s === "offline") return "offline";
  return "healthy";
}

function getMetricClass(value, warnThreshold, critThreshold) {
  if (value >= critThreshold) return "asset-metric--critical";
  if (value >= warnThreshold) return "asset-metric--warning";
  return "";
}

function formatTime(isoStr) {
  if (!isoStr) return "";
  const d = new Date(isoStr);
  return d.toLocaleTimeString("en-US", {
    hour: "2-digit", minute: "2-digit", second: "2-digit", hour12: false,
  });
}

// ═══════════════════════════════════════════════════════════
// COMPONENTS
// ═══════════════════════════════════════════════════════════

function TopBar({ worldState, timeState, wsConnected }) {
  const health = worldState?.overall_health_pct ?? 100;
  const healthColor = health >= 90 ? "var(--status-healthy)"
    : health >= 70 ? "var(--status-warning)"
      : "var(--status-critical)";

  return (
    <header className="topbar">
      <div className="topbar-brand">
        <div className="topbar-logo">Ω</div>
        <div>
          <div className="topbar-title">AEGIS Ω</div>
          <div className="topbar-subtitle">Command Center</div>
        </div>
      </div>

      <div className="topbar-status">
        <div className="topbar-stat">
          <div className="topbar-stat-value" style={{ color: healthColor }}>
            {health.toFixed(1)}%
          </div>
          <div className="topbar-stat-label">System Health</div>
        </div>
        <div className="topbar-stat">
          <div className="topbar-stat-value" style={{ color: "var(--accent-blue)" }}>
            {worldState?.total_assets ?? "—"}
          </div>
          <div className="topbar-stat-label">Assets</div>
        </div>
        <div className="topbar-stat">
          <div className="topbar-stat-value" style={{ color: worldState?.active_incidents > 0 ? "var(--status-critical)" : "var(--accent-emerald)" }}>
            {worldState?.active_incidents ?? 0}
          </div>
          <div className="topbar-stat-label">Incidents</div>
        </div>

        <div className="topbar-time">
          🕐 {timeState?.current_time ?? "—"}
          <span style={{ marginLeft: 8, opacity: 0.6 }}>
            Day {timeState?.sim_day ?? "—"}
          </span>
        </div>

        <div style={{ display: "flex", alignItems: "center", gap: 6 }}>
          <div style={{
            width: 8, height: 8, borderRadius: "50%",
            background: wsConnected ? "var(--status-healthy)" : "var(--status-critical)",
            boxShadow: wsConnected ? "0 0 6px var(--status-healthy)" : "none",
          }} />
          <span style={{ fontSize: 9, color: "var(--text-tertiary)", textTransform: "uppercase" }}>
            {wsConnected ? "Live" : "Offline"}
          </span>
        </div>
      </div>
    </header>
  );
}

function KPIRow({ worldState }) {
  const ws = worldState || {};
  return (
    <div className="kpi-row">
      <div className="kpi-card kpi-card--health">
        <div className="kpi-label">Overall Health</div>
        <div className="kpi-value" style={{ color: ws.overall_health_pct >= 90 ? "var(--status-healthy)" : ws.overall_health_pct >= 70 ? "var(--status-warning)" : "var(--status-critical)" }}>
          {(ws.overall_health_pct ?? 100).toFixed(1)}%
        </div>
        <div className="kpi-sub">{ws.healthy_assets ?? 0} healthy assets</div>
      </div>
      <div className="kpi-card kpi-card--assets">
        <div className="kpi-label">Total Assets</div>
        <div className="kpi-value" style={{ color: "var(--accent-blue)" }}>
          {ws.total_assets ?? 0}
        </div>
        <div className="kpi-sub">Across all departments</div>
      </div>
      <div className="kpi-card kpi-card--incidents">
        <div className="kpi-label">Active Incidents</div>
        <div className="kpi-value" style={{ color: ws.active_incidents > 0 ? "var(--status-critical)" : "var(--accent-emerald)" }}>
          {ws.active_incidents ?? 0}
        </div>
        <div className="kpi-sub">{ws.resolved_incidents_today ?? 0} resolved today</div>
      </div>
      <div className="kpi-card kpi-card--events">
        <div className="kpi-label">Events Today</div>
        <div className="kpi-value" style={{ color: "var(--accent-violet)" }}>
          {ws.total_events_today ?? 0}
        </div>
        <div className="kpi-sub">Stream active</div>
      </div>
      <div className="kpi-card kpi-card--critical">
        <div className="kpi-label">Critical Assets</div>
        <div className="kpi-value" style={{ color: ws.critical_assets > 0 ? "var(--status-critical)" : "var(--text-tertiary)" }}>
          {ws.critical_assets ?? 0}
        </div>
        <div className="kpi-sub">{ws.degraded_assets ?? 0} degraded</div>
      </div>
      <div className="kpi-card kpi-card--agents">
        <div className="kpi-label">AI Agents</div>
        <div className="kpi-value" style={{ color: "var(--accent-cyan)" }}>
          {ws.agent_count ?? 0}
        </div>
        <div className="kpi-sub">Registered &amp; governed</div>
      </div>
    </div>
  );
}

function AssetPanel({ assets }) {
  const list = assets?.assets || [];
  const sorted = [...list].sort((a, b) => {
    const order = { critical: 0, warning: 1, degraded: 2, offline: 3, healthy: 4 };
    return (order[a.status] ?? 5) - (order[b.status] ?? 5);
  });
  const display = sorted.slice(0, 30);

  return (
    <div className="panel">
      <div className="panel-header">
        <div className="panel-title">
          <span className="panel-title-dot" style={{ background: "var(--accent-blue)" }} />
          Infrastructure Assets
        </div>
        <span className="panel-badge" style={{ background: "var(--accent-blue-dim)", color: "var(--accent-blue)" }}>
          {list.length}
        </span>
      </div>
      <div className="panel-body">
        <div className="asset-list">
          <div className="asset-row" style={{ fontSize: 9, color: "var(--text-tertiary)", fontWeight: 600, textTransform: "uppercase", letterSpacing: "0.5px" }}>
            <span></span>
            <span>Asset</span>
            <span style={{ textAlign: "right" }}>Type</span>
            <span style={{ textAlign: "right" }}>CPU</span>
            <span style={{ textAlign: "right" }}>MEM</span>
            <span style={{ textAlign: "right" }}>DISK</span>
            <span style={{ textAlign: "right" }}>LAT</span>
          </div>
          {display.map((a) => (
            <div key={a.asset_id} className="asset-row">
              <div className={`asset-status-dot asset-status-dot--${getStatusClass(a.status)}`} />
              <div className="asset-name" title={a.asset_id}>{a.name}</div>
              <div className="asset-type">{a.type}</div>
              <div className={`asset-metric ${getMetricClass(a.cpu, 75, 90)}`}>{a.cpu}%</div>
              <div className={`asset-metric ${getMetricClass(a.memory, 80, 95)}`}>{a.memory}%</div>
              <div className={`asset-metric ${getMetricClass(a.disk, 80, 95)}`}>{a.disk}%</div>
              <div className={`asset-metric ${getMetricClass(a.latency, 100, 500)}`}>{a.latency}ms</div>
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}

function EventPanel({ events }) {
  const list = events?.events || [];
  const recent = list.slice(-30).reverse();

  return (
    <div className="panel">
      <div className="panel-header">
        <div className="panel-title">
          <span className="panel-title-dot" style={{ background: "var(--accent-violet)" }} />
          Event Stream
        </div>
        <span className="panel-badge" style={{ background: "var(--accent-violet-dim)", color: "var(--accent-violet)" }}>
          LIVE
        </span>
      </div>
      <div className="panel-body">
        <div className="event-stream">
          {recent.length === 0 && (
            <div className="empty-state">
              <div className="empty-state-icon">📡</div>
              <div>Waiting for events...</div>
            </div>
          )}
          {recent.map((e, i) => (
            <div key={e.event_id || i} className={`event-item event-item--${e.severity || "info"}`}>
              <span className="event-time">{formatTime(e.timestamp)}</span>
              <span className="event-asset">{e.asset_id}</span>
              <span className="event-message">{e.message}</span>
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}

function IncidentPanel({ incidents }) {
  const list = incidents?.incidents || [];

  return (
    <div className="panel">
      <div className="panel-header">
        <div className="panel-title">
          <span className="panel-title-dot" style={{ background: list.length > 0 ? "var(--status-critical)" : "var(--accent-emerald)" }} />
          Incident History
        </div>
        <span className="panel-badge" style={{
          background: list.length > 0 ? "var(--status-critical-bg)" : "var(--status-healthy-bg)",
          color: list.length > 0 ? "var(--status-critical)" : "var(--status-healthy)",
        }}>
          {list.length}
        </span>
      </div>
      <div className="panel-body">
        <div className="incident-list">
          {list.length === 0 && (
            <div className="empty-state">
              <div className="empty-state-icon">✅</div>
              <div>No incidents recorded</div>
              <div style={{ fontSize: 10, color: "var(--text-tertiary)" }}>All systems operational</div>
            </div>
          )}
          {list.map((inc) => (
            <div key={inc.incident_id} className={`incident-card incident-card--${inc.severity}`}>
              <div className="incident-header">
                <span className="incident-id">{inc.incident_id}</span>
                <span className={`incident-severity incident-severity--${inc.severity}`}>
                  {inc.severity}
                </span>
              </div>
              <div className="incident-title">{inc.title}</div>
              <div className="incident-desc">{inc.description}</div>
              <div className="incident-meta">
                <span className="incident-status-badge">{inc.status}</span>
                <span>🎯 {inc.affected_assets?.length ?? 0} assets affected</span>
                <span>⏱️ {formatTime(inc.created_at)}</span>
              </div>
              {inc.timeline && inc.timeline.length > 0 && (
                <div style={{ marginTop: 10 }}>
                  <div className="timeline">
                    {inc.timeline.slice(-5).map((t, i) => (
                      <div key={i} className="timeline-item">
                        <div className="timeline-time">{formatTime(t.timestamp)}</div>
                        <div className="timeline-text">
                          <span className="timeline-agent">{t.agent}</span>
                          {t.details}
                        </div>
                      </div>
                    ))}
                  </div>
                </div>
              )}
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}

function ChaosLabPanel({ scenarios, onInject, activeFailures, onRecoverAll }) {
  const list = scenarios?.scenarios || [];
  const active = activeFailures?.failures || [];

  return (
    <div className="panel">
      <div className="panel-header">
        <div className="panel-title">
          <span className="panel-title-dot" style={{ background: "var(--accent-rose)" }} />
          Chaos Lab
        </div>
        <div style={{ display: "flex", gap: 6 }}>
          {active.length > 0 && (
            <button className="btn btn--recover btn--sm" onClick={onRecoverAll}>
              🔄 Recover All
            </button>
          )}
          <span className="panel-badge" style={{ background: "var(--accent-rose-dim)", color: "var(--accent-rose)" }}>
            {active.length} ACTIVE
          </span>
        </div>
      </div>
      <div className="panel-body">
        <div className="chaos-grid">
          {list.map((s) => {
            const isActive = active.some(f => f.scenario_id === s.id);
            return (
              <button
                key={s.id}
                className={`chaos-btn ${isActive ? "chaos-btn--active" : ""}`}
                onClick={() => onInject(s.id)}
              >
                <div className="chaos-btn-icon">
                  {s.name.split(" ")[0]}
                </div>
                <div className="chaos-btn-name">{s.name.split(" ").slice(1).join(" ")}</div>
                <div className="chaos-btn-desc">
                  {s.description}
                </div>
                <div style={{ marginTop: 4, fontSize: 9, color: "var(--text-tertiary)" }}>
                  Target: {s.target} • Severity: {s.severity} • {s.affected_count} steps
                </div>
              </button>
            );
          })}
        </div>
      </div>
    </div>
  );
}

function GraphSummaryPanel({ graphData }) {
  const summary = graphData || {};

  return (
    <div className="panel">
      <div className="panel-header">
        <div className="panel-title">
          <span className="panel-title-dot" style={{ background: "var(--accent-cyan)" }} />
          Dependency Graph
        </div>
      </div>
      <div className="panel-body">
        <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 10 }}>
          <div style={{ background: "var(--bg-tertiary)", borderRadius: "var(--radius-sm)", padding: 12 }}>
            <div style={{ fontSize: 9, color: "var(--text-tertiary)", textTransform: "uppercase", letterSpacing: "1px", marginBottom: 4 }}>Nodes</div>
            <div style={{ fontFamily: "var(--font-mono)", fontSize: 22, fontWeight: 700, color: "var(--accent-cyan)" }}>{summary.total_nodes ?? 0}</div>
          </div>
          <div style={{ background: "var(--bg-tertiary)", borderRadius: "var(--radius-sm)", padding: 12 }}>
            <div style={{ fontSize: 9, color: "var(--text-tertiary)", textTransform: "uppercase", letterSpacing: "1px", marginBottom: 4 }}>Edges</div>
            <div style={{ fontFamily: "var(--font-mono)", fontSize: 22, fontWeight: 700, color: "var(--accent-violet)" }}>{summary.total_edges ?? 0}</div>
          </div>
          <div style={{ background: "var(--bg-tertiary)", borderRadius: "var(--radius-sm)", padding: 12 }}>
            <div style={{ fontSize: 9, color: "var(--text-tertiary)", textTransform: "uppercase", letterSpacing: "1px", marginBottom: 4 }}>Density</div>
            <div style={{ fontFamily: "var(--font-mono)", fontSize: 22, fontWeight: 700, color: "var(--accent-emerald)" }}>{summary.density ?? 0}</div>
          </div>
          <div style={{ background: "var(--bg-tertiary)", borderRadius: "var(--radius-sm)", padding: 12 }}>
            <div style={{ fontSize: 9, color: "var(--text-tertiary)", textTransform: "uppercase", letterSpacing: "1px", marginBottom: 4 }}>DAG</div>
            <div style={{ fontFamily: "var(--font-mono)", fontSize: 22, fontWeight: 700, color: summary.is_dag ? "var(--status-healthy)" : "var(--status-warning)" }}>
              {summary.is_dag ? "✓" : "✗"}
            </div>
          </div>
        </div>

        {summary.node_types && (
          <div style={{ marginTop: 14 }}>
            <div style={{ fontSize: 10, color: "var(--text-tertiary)", marginBottom: 8, fontWeight: 600, textTransform: "uppercase", letterSpacing: "0.5px" }}>
              Asset Distribution
            </div>
            {Object.entries(summary.node_types || {}).map(([type, count]) => (
              <div key={type} style={{ display: "flex", alignItems: "center", justifyContent: "space-between", padding: "4px 0", fontSize: 11 }}>
                <span style={{ color: "var(--text-secondary)", textTransform: "capitalize" }}>{type.replace(/_/g, " ")}</span>
                <span style={{ fontFamily: "var(--font-mono)", color: "var(--accent-blue)" }}>{count}</span>
              </div>
            ))}
          </div>
        )}
      </div>
    </div>
  );
}

function CriticalAssetsPanel({ criticalAssets }) {
  const list = criticalAssets || [];

  return (
    <div className="panel">
      <div className="panel-header">
        <div className="panel-title">
          <span className="panel-title-dot" style={{ background: "var(--accent-amber)" }} />
          Critical Assets (Impact Analysis)
        </div>
      </div>
      <div className="panel-body">
        <div style={{ display: "flex", flexDirection: "column", gap: 4 }}>
          {list.map((a, i) => (
            <div key={a.asset_id} style={{
              display: "grid",
              gridTemplateColumns: "20px 1fr 60px 50px",
              alignItems: "center",
              gap: 8,
              padding: "6px 8px",
              borderRadius: "var(--radius-sm)",
              background: i < 3 ? "var(--accent-amber-dim)" : "transparent",
              fontSize: 11,
            }}>
              <span style={{ fontFamily: "var(--font-mono)", fontSize: 10, color: "var(--text-tertiary)" }}>
                #{i + 1}
              </span>
              <span style={{ fontWeight: 500 }} title={a.asset_id}>
                {a.name}
              </span>
              <span style={{ fontFamily: "var(--font-mono)", fontSize: 10, color: "var(--accent-amber)", textAlign: "right" }}>
                ↓{a.dependent_count}
              </span>
              <span style={{ fontFamily: "var(--font-mono)", fontSize: 10, color: "var(--accent-rose)", textAlign: "right" }}>
                ⚡{a.impact_score}
              </span>
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}

function DemoPanel({ onRun, demoState }) {
  const stages = ["Detect", "Investigate", "Evidence", "Root cause", "Plan", "Simulate", "Risk", "Execute", "Verify", "Learn"];
  return (
    <section className="panel panel--full demo-panel">
      <div className="demo-copy">
        <div className="eyebrow">Autonomous recovery demonstration</div>
        <h2>Break the institution. Watch AEGIS heal it.</h2>
        <p>
          Injects a database cascade, deliberately fails the first remediation,
          rolls back, replans, verifies recovery, and stores what worked.
        </p>
        <div className="stage-strip">
          {stages.map((stage, index) => (
            <span key={stage} className="stage-chip"><b>{String(index + 1).padStart(2, "0")}</b>{stage}</span>
          ))}
        </div>
      </div>
      <div className="demo-action">
        <button className="btn btn--demo" disabled={demoState.running} onClick={onRun}>
          {demoState.running ? "Pipeline running…" : "▶ Run full self-healing demo"}
        </button>
        <span className={`demo-result demo-result--${demoState.kind || "idle"}`}>
          {demoState.message || "Ready · first attempt will fail by design"}
        </span>
      </div>
    </section>
  );
}

function AgentOperationsPanel({ systemStatus, traces }) {
  const registry = systemStatus?.registry || {};
  const list = traces?.traces || [];
  return (
    <section className="panel panel--span2">
      <div className="panel-header">
        <div className="panel-title"><span className="panel-title-dot" style={{ background: "var(--accent-cyan)" }} />Agent Operations</div>
        <span className="panel-badge" style={{ background: "var(--accent-cyan-dim)", color: "var(--accent-cyan)" }}>
          {registry.healthy || 0}/{registry.total || 0} HEALTHY
        </span>
      </div>
      <div className="agent-ops-grid">
        <div className="agent-registry">
          {(registry.agents || []).map((agent) => (
            <div className="agent-card" key={agent.agent_id}>
              <span className="agent-pulse" />
              <div><strong>{agent.name}</strong><small>{agent.permissions.join(" · ")}</small></div>
            </div>
          ))}
        </div>
        <div className="trace-feed">
          {list.length === 0 && <div className="empty-state">Waiting for the first incident pipeline…</div>}
          {list.slice(0, 18).map((trace) => (
            <div className="trace-row" key={trace.trace_id}>
              <span className="trace-time">{formatTime(trace.timestamp)}</span>
              <span className="trace-name">{trace.agent_name}</span>
              <span className="trace-copy">{trace.action}</span>
              <span className={`trace-status trace-status--${trace.status}`}>{trace.duration_ms}ms</span>
            </div>
          ))}
        </div>
      </div>
    </section>
  );
}

function IntelligencePanel({ systemStatus, memory, predictions, onPrevent }) {
  const ai = systemStatus?.ai || {};
  const procedures = memory?.procedures || [];
  const forecast = predictions?.predictions || [];
  return (
    <section className="panel">
      <div className="panel-header">
        <div className="panel-title"><span className="panel-title-dot" style={{ background: "var(--accent-violet)" }} />Learning &amp; Prediction</div>
        <span className="panel-badge" style={{ background: "var(--accent-violet-dim)", color: "var(--accent-violet)" }}>{ai.mode || "starting"}</span>
      </div>
      <div className="panel-body intelligence-stack">
        <div className="mini-stat-row">
          <div><strong>{memory?.summary?.episodic || 0}</strong><span>Episodes</span></div>
          <div><strong>{memory?.summary?.procedural || 0}</strong><span>Procedures</span></div>
          <div><strong>{forecast.length}</strong><span>Forecasts</span></div>
        </div>
        <div className="subsection-label">Learned procedures</div>
        {procedures.length === 0 && <div className="empty-note">Resolved incidents become reusable operating knowledge.</div>}
        {procedures.slice(0, 5).map((item) => (
          <div className="knowledge-row" key={`${item.pattern}-${item.action}`}>
            <div><strong>{item.action.replaceAll("_", " ")}</strong><small>{item.pattern.replaceAll("_", " ")}</small></div>
            <span>{Math.round(item.success_rate * 100)}%</span>
          </div>
        ))}
        <div className="subsection-label">Active predictions</div>
        {forecast.length === 0 && <div className="empty-note">Trend scanner is watching metric history.</div>}
        {forecast.slice(0, 4).map((item) => (
          <div className="knowledge-row" key={item.prediction_id}>
            <div><strong>{item.asset_id}</strong><small>{item.metric_name.replaceAll("_", " ")} approaching threshold</small></div>
            <button className="prevent-btn" onClick={() => onPrevent(item.prediction_id)}>
              Prevent · {Math.round(item.confidence * 100)}%
            </button>
          </div>
        ))}
      </div>
    </section>
  );
}


// ═══════════════════════════════════════════════════════════
// MAIN PAGE
// ═══════════════════════════════════════════════════════════

export default function CommandCenter() {
  const [demoState, setDemoState] = useState({ running: false, message: "", kind: "idle" });
  // Data hooks
  const { data: worldState } = useAPI("/api/world/state", 2000);
  const { data: timeState } = useAPI("/api/world/time", 2000);
  const { data: assets } = useAPI("/api/assets", 3000);
  const { data: events } = useAPI("/api/events?count=50", 2000);
  const { data: incidents, refetch: refetchIncidents } = useAPI("/api/incidents?last_n=12", 1500);
  const { data: scenarios } = useAPI("/api/chaos/scenarios", 10000);
  const { data: activeFailures, refetch: refetchFailures } = useAPI("/api/chaos/active", 3000);
  const { data: graphSummary } = useAPI("/api/graph/summary", 10000);
  const { data: criticalAssets } = useAPI("/api/graph/critical-assets?top_n=10", 10000);
  const { data: systemStatus, error: systemError, refetch: refetchSystem } = useAPI("/api/system/status", 2000);
  const { data: traces, refetch: refetchTraces } = useAPI("/api/traces?limit=30", 1200);
  const { data: memory, refetch: refetchMemory } = useAPI("/api/memory?limit=8", 2500);
  const { data: predictions } = useAPI("/api/predictions", 5000);
  const { connected: wsConnected } = useWebSocket();

  // Chaos actions
  const injectScenario = async (scenarioId) => {
    try {
      await fetch(`${API}/api/chaos/inject`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ scenario_id: scenarioId }),
      });
      refetchFailures();
    } catch (err) {
      console.error("Inject failed:", err);
    }
  };

  const runFullDemo = async () => {
    setDemoState({ running: true, message: "Agents are diagnosing the cascade…", kind: "running" });
    try {
      const response = await fetch(`${API}/api/demo/run`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ scenario_id: "database_crisis", force_first_failure: true, wait_for_completion: true }),
      });
      if (!response.ok) throw new Error(`Demo failed with HTTP ${response.status}`);
      const result = await response.json();
      const incident = result.incident;
      setDemoState({
        running: false,
        kind: incident.status === "resolved" ? "success" : "error",
        message: `${incident.incident_id} · ${incident.status.toUpperCase()} · ${incident.actions_taken.length} execution attempts`,
      });
      refetchFailures();
      refetchIncidents();
      refetchSystem();
      refetchTraces();
      refetchMemory();
    } catch (err) {
      setDemoState({ running: false, message: err.message, kind: "error" });
    }
  };

  const recoverAll = async () => {
    try {
      await fetch(`${API}/api/chaos/recover-all`, { method: "POST" });
      refetchFailures();
    } catch (err) {
      console.error("Recover all failed:", err);
    }
  };

  const preventPrediction = async (predictionId) => {
    try {
      const response = await fetch(`${API}/api/predictions/prevent`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ prediction_id: predictionId, wait_for_completion: false }),
      });
      if (!response.ok) throw new Error(`Prevention failed with HTTP ${response.status}`);
      refetchIncidents();
      refetchSystem();
    } catch (err) {
      setDemoState({ running: false, message: err.message, kind: "error" });
    }
  };

  return (
    <div className="command-center">
      <TopBar
        worldState={worldState}
        timeState={timeState}
        wsConnected={wsConnected}
      />

      <main className="dashboard">
        {systemError && <div className="connection-alert">Backend unavailable at {API} · {systemError}</div>}
        <KPIRow worldState={worldState} />
        <DemoPanel onRun={runFullDemo} demoState={demoState} />

        {/* Row 2: Assets + Events + Incidents */}
        <AssetPanel assets={assets} />
        <EventPanel events={events} />
        <IncidentPanel incidents={incidents} />

        {/* Row 3: Chaos Lab + Graph + Critical */}
        <ChaosLabPanel
          scenarios={scenarios}
          onInject={injectScenario}
          activeFailures={activeFailures}
          onRecoverAll={recoverAll}
        />
        <GraphSummaryPanel graphData={graphSummary} />
        <CriticalAssetsPanel criticalAssets={criticalAssets} />
        <AgentOperationsPanel systemStatus={systemStatus} traces={traces} />
        <IntelligencePanel systemStatus={systemStatus} memory={memory} predictions={predictions} onPrevent={preventPrediction} />
      </main>
    </div>
  );
}
