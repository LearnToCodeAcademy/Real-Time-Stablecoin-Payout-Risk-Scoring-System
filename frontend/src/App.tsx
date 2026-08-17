import {
  Activity,
  AlertTriangle,
  BarChart3,
  Blocks,
  Check,
  ChevronRight,
  CircleDot,
  Gauge,
  GraduationCap,
  Network,
  Pause,
  Play,
  RefreshCw,
  RotateCcw,
  Search,
  Settings,
  ShieldAlert,
  ShieldCheck,
  TerminalSquare,
  WalletCards,
  X
} from "lucide-react";
import cytoscape from "cytoscape";
import { FormEvent, useCallback, useEffect, useMemo, useRef, useState } from "react";
import {
  Area,
  AreaChart,
  Bar,
  BarChart,
  CartesianGrid,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis
} from "recharts";
import { api } from "./api";
import type {
  AlertEvent,
  AlertStatistics,
  CollectionJob,
  GraphPayload,
  Health,
  LiveStatus,
  ModelVersion,
  RiskCase,
  TrainingJob,
  WalletScore
} from "./types";

type View = "command" | "investigate" | "live" | "graph" | "cases" | "models" | "training" | "settings";

const views: { id: View; label: string; icon: typeof Gauge }[] = [
  { id: "command", label: "Command center", icon: Gauge },
  { id: "investigate", label: "Investigate", icon: Search },
  { id: "live", label: "Live stream", icon: Activity },
  { id: "graph", label: "Wallet network", icon: Network },
  { id: "cases", label: "Cases", icon: ShieldAlert },
  { id: "models", label: "Models", icon: BarChart3 },
  { id: "training", label: "Local training", icon: GraduationCap },
  { id: "settings", label: "Settings", icon: Settings }
];

const fmt = new Intl.NumberFormat("en-US", { maximumFractionDigits: 2 });

function shortAddress(value?: string | null) {
  if (!value) return "-";
  return `${value.slice(0, 7)}...${value.slice(-5)}`;
}

function timeAgo(value?: string | null) {
  if (!value) return "never";
  const seconds = Math.max(0, Math.floor((Date.now() - new Date(value).getTime()) / 1000));
  if (seconds < 60) return `${seconds}s ago`;
  if (seconds < 3600) return `${Math.floor(seconds / 60)}m ago`;
  return `${Math.floor(seconds / 3600)}h ago`;
}

function DecisionBadge({ decision }: { decision?: string }) {
  return <span className={`decision decision-${(decision || "observed").toLowerCase()}`}>{decision || "OBSERVED"}</span>;
}

function Panel({ title, meta, children, className = "" }: { title: string; meta?: string; children: React.ReactNode; className?: string }) {
  return (
    <section className={`panel ${className}`}>
      <header className="panel-head">
        <div>
          <h2>{title}</h2>
          {meta && <p>{meta}</p>}
        </div>
      </header>
      {children}
    </section>
  );
}

function LiveIndicator({ status }: { status?: LiveStatus }) {
  const live = status?.state === "live";
  return (
    <div className={`live-indicator ${live ? "is-live" : ""}`} title={status?.error || status?.state}>
      <span />
      {live ? `${status.source} live` : status?.state || "offline"}
    </div>
  );
}

function CommandCenter({
  health,
  events,
  statistics,
  onInvestigate
}: {
  health: Health | null;
  events: AlertEvent[];
  statistics: AlertStatistics;
  onInvestigate: (wallet: string) => void;
}) {
  const decisions = statistics.decisions || {};
  const total = Object.values(decisions).reduce((sum: number, value) => sum + Number(value), 0);
  const timeline = useMemo(() => {
    const buckets = new Map<string, { time: string; observed: number; risk: number }>();
    [...events].reverse().forEach((event) => {
      const date = new Date(event.timestamp);
      const time = `${date.getHours().toString().padStart(2, "0")}:${date.getMinutes().toString().padStart(2, "0")}`;
      const bucket = buckets.get(time) || { time, observed: 0, risk: 0 };
      bucket.observed += 1;
      if (event.decision === "BLOCK" || event.decision === "REVIEW") bucket.risk += 1;
      buckets.set(time, bucket);
    });
    return [...buckets.values()].slice(-18);
  }, [events]);
  const tokenRisk = useMemo(() => {
    const result: Record<string, { token: string; observed: number; risk: number }> = {};
    events.forEach((event) => {
      const token = event.token || "OTHER";
      result[token] ||= { token, observed: 0, risk: 0 };
      result[token].observed += 1;
      if (event.decision === "BLOCK" || event.decision === "REVIEW") result[token].risk += 1;
    });
    return Object.values(result);
  }, [events]);

  return (
    <>
      <div className="page-title">
        <div>
          <p className="eyebrow">Ethereum mainnet / risk operations</p>
          <h1>Command center</h1>
        </div>
        <LiveIndicator status={health?.live_stream} />
      </div>
      <div className="metric-strip">
        <div><span>Events indexed</span><strong>{fmt.format(total)}</strong><small>persistent chain + manual</small></div>
        <div><span>Open cases</span><strong>{fmt.format(statistics.open_cases || 0)}</strong><small>review and block queue</small></div>
        <div><span>Risk events</span><strong>{fmt.format((decisions.REVIEW || 0) + (decisions.BLOCK || 0))}</strong><small>{total ? (((decisions.REVIEW || 0) + (decisions.BLOCK || 0)) / total * 100).toFixed(1) : "0.0"}% of indexed</small></div>
        <div><span>Active models</span><strong>{Object.keys(health?.active_models || {}).length}</strong><small>version-controlled tokens</small></div>
      </div>
      <div className="command-grid">
        <Panel title="Network pulse" meta="Confirmed transfer events and scored risk events">
          <div className="chart-wrap">
            <ResponsiveContainer width="100%" height="100%">
              <AreaChart data={timeline} margin={{ top: 8, right: 10, left: -24, bottom: 0 }}>
                <defs>
                  <linearGradient id="observedFill" x1="0" x2="0" y1="0" y2="1">
                    <stop offset="0%" stopColor="#35c7d0" stopOpacity={0.38} />
                    <stop offset="100%" stopColor="#35c7d0" stopOpacity={0} />
                  </linearGradient>
                  <linearGradient id="riskFill" x1="0" x2="0" y1="0" y2="1">
                    <stop offset="0%" stopColor="#ff5d62" stopOpacity={0.42} />
                    <stop offset="100%" stopColor="#ff5d62" stopOpacity={0} />
                  </linearGradient>
                </defs>
                <CartesianGrid stroke="#202631" vertical={false} />
                <XAxis dataKey="time" stroke="#667080" tickLine={false} axisLine={false} />
                <YAxis stroke="#667080" tickLine={false} axisLine={false} allowDecimals={false} />
                <Tooltip contentStyle={{ background: "#0e1218", border: "1px solid #29303c", borderRadius: 4 }} />
                <Area dataKey="observed" stroke="#35c7d0" fill="url(#observedFill)" strokeWidth={2} />
                <Area dataKey="risk" stroke="#ff5d62" fill="url(#riskFill)" strokeWidth={2} />
              </AreaChart>
            </ResponsiveContainer>
          </div>
        </Panel>
        <Panel title="Token exposure" meta="Latest retained live window">
          <div className="chart-wrap">
            <ResponsiveContainer width="100%" height="100%">
              <BarChart data={tokenRisk} margin={{ top: 8, right: 8, left: -24, bottom: 0 }}>
                <CartesianGrid stroke="#202631" vertical={false} />
                <XAxis dataKey="token" stroke="#667080" tickLine={false} axisLine={false} />
                <YAxis stroke="#667080" tickLine={false} axisLine={false} allowDecimals={false} />
                <Tooltip contentStyle={{ background: "#0e1218", border: "1px solid #29303c", borderRadius: 4 }} />
                <Bar dataKey="observed" fill="#536274" radius={[2, 2, 0, 0]} />
                <Bar dataKey="risk" fill="#f0ad4e" radius={[2, 2, 0, 0]} />
              </BarChart>
            </ResponsiveContainer>
          </div>
        </Panel>
        <Panel title="Live alert feed" meta="Only provider-confirmed transfers and actual scoring results" className="span-two">
          <EventTable events={events.slice(0, 12)} onInvestigate={onInvestigate} compact />
        </Panel>
        <Panel title="Top risky wallets" meta="Ranked from persisted REVIEW and BLOCK cases">
          <div className="rank-list">
            {(statistics.top_risky_wallets || []).map((item, index) => (
              <button key={`${item.wallet}-${item.token || "unknown"}`} onClick={() => onInvestigate(item.wallet)}>
                <span className="rank">{String(index + 1).padStart(2, "0")}</span>
                <span className="mono">{shortAddress(item.wallet)}</span>
                <span>{item.token || "-"}</span>
                <strong>{item.max_score == null ? "n/a" : `${(item.max_score * 100).toFixed(1)}%`}</strong>
              </button>
            ))}
            {!statistics.top_risky_wallets?.length && <Empty text="No scored risk cases yet" />}
          </div>
        </Panel>
      </div>
    </>
  );
}

function EventTable({ events, onInvestigate, compact = false }: { events: AlertEvent[]; onInvestigate: (wallet: string) => void; compact?: boolean }) {
  return (
    <div className="table-scroll">
      <table className={compact ? "compact" : ""}>
        <thead><tr><th>Time</th><th>Wallet</th><th>Token</th><th>State</th><th>Risk</th><th>Block</th><th /></tr></thead>
        <tbody>
          {events.map((event) => (
            <tr key={`${event.event_id}-${event.decision}`}>
              <td>{new Date(event.timestamp).toLocaleTimeString([], { hour12: false })}</td>
              <td className="mono" title={event.wallet}>{shortAddress(event.wallet)}</td>
              <td>{event.token || "-"}</td>
              <td><DecisionBadge decision={event.decision} /></td>
              <td>{event.score == null ? "pending" : `${(event.score * 100).toFixed(1)}%`}</td>
              <td className="mono">{event.block_number || "-"}</td>
              <td><button className="icon-button" title="Investigate wallet" onClick={() => onInvestigate(event.wallet)}><ChevronRight size={16} /></button></td>
            </tr>
          ))}
        </tbody>
      </table>
      {!events.length && <Empty text="Waiting for a real provider event" />}
    </div>
  );
}

function WalletInvestigate({ initialWallet }: { initialWallet: string }) {
  const [wallet, setWallet] = useState(initialWallet);
  const [token, setToken] = useState("");
  const [result, setResult] = useState<WalletScore | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");
  async function submit(event: FormEvent) {
    event.preventDefault();
    setLoading(true);
    setError("");
    try {
      const score = await api.request<WalletScore>("/score_wallet", {
        method: "POST",
        body: JSON.stringify({ address: wallet, manual_token: token || null })
      });
      setResult(score);
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : String(reason));
    } finally {
      setLoading(false);
    }
  }

  const probabilities = result ? [
    ["Safe", result.prob_normal, "safe"],
    ["Malicious", result.prob_malicious, "malicious"],
    ["Poisoned", result.prob_poisoned, "poisoned"]
  ] as const : [];

  return (
    <>
      <div className="page-title"><div><p className="eyebrow">Deep wallet analysis</p><h1>Wallet investigate</h1></div></div>
      <form className="investigate-bar" onSubmit={submit}>
        <div className="address-input"><Search size={18} /><input aria-label="Wallet address" value={wallet} onChange={(event) => setWallet(event.target.value)} placeholder="0x wallet address" pattern="^0x[a-fA-F0-9]{40}$" required /></div>
        <select aria-label="Token override" value={token} onChange={(event) => setToken(event.target.value)}><option value="">Auto token</option>{["USDT", "USDC", "DAI", "BUSD", "USDP", "TUSD"].map((value) => <option key={value}>{value}</option>)}</select>
        <button className="primary-button" disabled={loading}>{loading ? <RefreshCw className="spin" size={17} /> : <Search size={17} />} Analyze</button>
      </form>
      {error && <div className="error-banner"><AlertTriangle size={17} />{error}</div>}
      {!result && !error && <div className="investigate-empty"><WalletCards size={42} /><h2>Enter a wallet to begin</h2><p>The backend fetches real Etherscan history, applies the active token model, then persists REVIEW and BLOCK results as cases.</p></div>}
      {result && (
        <div className="result-grid">
          <Panel title="Decision" meta={`${result.token || "No token"} / ${result.processing_time_ms?.toFixed(0) || "-"} ms`}>
            <div className={`decision-hero decision-hero-${result.decision.toLowerCase()}`}><DecisionBadge decision={result.decision} /><strong>{result.assessment_status === "UNSCORABLE" ? "UNSCORABLE" : result.score == null ? "No model score" : `${(result.score * 100).toFixed(1)}% risk`}</strong><p>{result.reason}</p><small>{result.cache_hit ? "cache hit" : result.data_status || "provider analysis"}</small></div>
          </Panel>
          <Panel title="Class probabilities" meta={result.assessment_status === "SCORED" ? "Active model output" : "Not calculated"}>
            <div className="probabilities">{probabilities.map(([label, value, key]) => <div key={key}><div><span>{label}</span><strong>{value == null ? "not calculated" : `${(value * 100).toFixed(2)}%`}</strong></div><div className={`probability-track probability-${key}`}><span style={{ width: value == null ? "0%" : `${value * 100}%` }} /></div></div>)}</div>
          </Panel>
          <Panel title="Threat intelligence" meta={result.threat_intelligence?.status || "UNAVAILABLE"} className="span-two">
            {result.threat_intelligence?.findings?.length ? <div className="feature-grid">{result.threat_intelligence.findings.map((finding, index) => <div key={`${finding.source}-${index}`}><span>{finding.source}</span><strong>{finding.nametag || finding.labels?.join(", ") || "Risk match"}</strong></div>)}</div> : <p className="field-help">No risky provider match was returned. This does not replace transaction/model analysis.</p>}
          </Panel>
          <Panel title="Behavioral features" meta="Values aligned to the training schema" className="span-two">
            <div className="feature-grid">{Object.entries(result.features || {}).slice(0, 24).map(([name, value]) => <div key={name}><span>{name.replaceAll("_", " ")}</span><strong>{typeof value === "number" ? Number(value).toPrecision(4) : String(value)}</strong></div>)}</div>
          </Panel>
        </div>
      )}
    </>
  );
}

function LiveStream({ events, status, onInvestigate }: { events: AlertEvent[]; status?: LiveStatus; onInvestigate: (wallet: string) => void }) {
  const [decision, setDecision] = useState("ALL");
  const [token, setToken] = useState("ALL");
  const filtered = events.filter((event) => (decision === "ALL" || event.decision === decision) && (token === "ALL" || event.token === token));
  return (
    <>
      <div className="page-title"><div><p className="eyebrow">Provider-confirmed chain events</p><h1>Live transaction stream</h1></div><LiveIndicator status={status} /></div>
      <div className="toolbar"><select value={decision} onChange={(event) => setDecision(event.target.value)}><option>ALL</option><option>OBSERVED</option><option>ALLOW</option><option>REVIEW</option><option>BLOCK</option></select><select value={token} onChange={(event) => setToken(event.target.value)}><option>ALL</option>{["USDT", "USDC", "DAI", "BUSD", "USDP", "TUSD"].map((value) => <option key={value}>{value}</option>)}</select><span>{filtered.length} retained events</span></div>
      {status?.state !== "live" && <div className="warning-banner"><CircleDot size={17} /><div><strong>Live provider is {status?.state || "offline"}</strong><p>{status?.error || "Configure a provider in Settings. No synthetic events will be shown."}</p></div></div>}
      <Panel title="Chain events" meta="WebSocket status pulses once per second; transfers arrive with block production">
        <EventTable events={filtered} onInvestigate={onInvestigate} />
      </Panel>
    </>
  );
}

function GraphView() {
  const container = useRef<HTMLDivElement>(null);
  const [meta, setMeta] = useState({ nodes: 0, edges: 0 });
  const [error, setError] = useState("");
  const load = useCallback(async () => {
    try {
      const graph = await api.request<GraphPayload>("/graph?limit=500");
      setMeta({ nodes: graph.nodes.length, edges: graph.edges.length });
      if (!container.current) return;
      const instance = cytoscape({
        container: container.current,
        elements: [
          ...graph.nodes.map((node) => ({ data: node })),
          ...graph.edges.map((edge, index) => ({ data: { id: `edge-${index}`, ...edge } }))
        ],
        style: [
          { selector: "node", style: { "background-color": "#35c7d0", label: "data(token)", color: "#cbd5e1", "font-size": 8, width: 14, height: 14, "text-valign": "bottom", "text-margin-y": 6 } },
          { selector: 'node[decision = "BLOCK"]', style: { "background-color": "#ff5d62", width: 24, height: 24 } },
          { selector: 'node[decision = "REVIEW"]', style: { "background-color": "#f0ad4e", width: 20, height: 20 } },
          { selector: 'node[decision = "ALLOW"]', style: { "background-color": "#47d18c" } },
          { selector: "edge", style: { width: 1, "line-color": "#35404e", "target-arrow-color": "#35404e", "target-arrow-shape": "triangle", "curve-style": "bezier", opacity: 0.7 } }
        ],
        layout: { name: "cose", animate: false, padding: 32 },
        minZoom: 0.25,
        maxZoom: 4
      });
      return () => instance.destroy();
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : String(reason));
    }
  }, []);
  useEffect(() => {
    const timer = window.setTimeout(() => void load(), 0);
    return () => window.clearTimeout(timer);
  }, [load]);
  return (
    <>
      <div className="page-title"><div><p className="eyebrow">Graph intelligence</p><h1>Wallet network</h1></div><button className="secondary-button" onClick={() => void load()}><RefreshCw size={16} /> Refresh</button></div>
      {error && <div className="error-banner"><AlertTriangle size={17} />{error}</div>}
      <div className="graph-shell"><div className="graph-meta"><span>{meta.nodes} wallets</span><span>{meta.edges} transfers</span><span className="legend-block">Block</span><span className="legend-review">Review</span><span className="legend-observed">Observed</span></div><div className="graph-canvas" ref={container} /></div>
    </>
  );
}

function CasesView() {
  const [cases, setCases] = useState<RiskCase[]>([]);
  const [status, setStatus] = useState("open");
  const [error, setError] = useState("");
  const load = useCallback(async () => {
    try { setCases(await api.request<RiskCase[]>(`/cases?limit=250${status ? `&status=${status}` : ""}`)); setError(""); }
    catch (reason) { setError(reason instanceof Error ? reason.message : String(reason)); }
  }, [status]);
  useEffect(() => {
    const timer = window.setTimeout(() => void load(), 0);
    return () => window.clearTimeout(timer);
  }, [load]);
  async function update(caseId: string, next: string) {
    await api.request(`/cases/${caseId}`, { method: "PATCH", body: JSON.stringify({ status: next }) });
    await load();
  }
  return (
    <>
      <div className="page-title"><div><p className="eyebrow">Human review queue</p><h1>Alerts & cases</h1></div></div>
      <div className="toolbar"><select value={status} onChange={(event) => setStatus(event.target.value)}><option value="open">Open</option><option value="reviewed">Reviewed</option><option value="escalated">Escalated</option><option value="dismissed">Dismissed</option><option value="">All</option></select><span>{cases.length} cases</span></div>
      {error && <div className="error-banner"><AlertTriangle size={17} />{error}</div>}
      <div className="case-list">{cases.map((item) => <article key={item.case_id}><div className="case-icon"><ShieldAlert size={20} /></div><div><div className="case-heading"><DecisionBadge decision={item.decision} /><span>{item.token || "-"}</span><span className="mono">{shortAddress(item.wallet)}</span></div><p>{item.case_id}</p><small>Updated {timeAgo(item.updated_at)}</small></div><strong>{item.score == null ? "n/a" : `${(item.score * 100).toFixed(1)}%`}</strong><div className="case-actions"><button title="Mark reviewed" onClick={() => void update(item.case_id, "reviewed")}><Check size={16} /></button><button title="Escalate" onClick={() => void update(item.case_id, "escalated")}><AlertTriangle size={16} /></button><button title="Dismiss" onClick={() => void update(item.case_id, "dismissed")}><X size={16} /></button></div></article>)}{!cases.length && <Empty text="No cases match this queue" />}</div>
    </>
  );
}

function ModelsView({ versions, refresh }: { versions: ModelVersion[]; refresh: () => void }) {
  return (
    <>
      <div className="page-title"><div><p className="eyebrow">Held-out evaluation</p><h1>Model performance</h1></div><button className="secondary-button" onClick={refresh}><RefreshCw size={16} /> Refresh</button></div>
      <div className="model-grid">{versions.map((version) => <article className={`model-card ${version.active ? "active-model" : ""}`} key={version.version}><header><div><span>{version.token.toUpperCase()}</span><h2>{version.metrics.test_macro_f1 == null ? "No report" : `${(Number(version.metrics.test_macro_f1) * 100).toFixed(1)}% macro F1`}</h2></div>{version.active && <span className="active-chip"><ShieldCheck size={14} /> Active</span>}</header><div className="model-metrics"><div><span>Accuracy</span><strong>{version.metrics.test_accuracy == null ? "-" : `${(Number(version.metrics.test_accuracy) * 100).toFixed(1)}%`}</strong></div><div><span>Malicious recall</span><strong className={Number(version.metrics.malicious_recall) < .9 ? "metric-warn" : ""}>{version.metrics.malicious_recall == null ? "-" : `${(Number(version.metrics.malicious_recall) * 100).toFixed(1)}%`}</strong></div><div><span>Poisoned recall</span><strong>{version.metrics.poisoned_recall == null ? "-" : `${(Number(version.metrics.poisoned_recall) * 100).toFixed(1)}%`}</strong></div><div><span>CV macro F1</span><strong>{version.metrics.cv_macro_f1_mean == null ? "-" : `${(Number(version.metrics.cv_macro_f1_mean) * 100).toFixed(1)}%`}</strong></div></div><footer><code>{version.version}</code></footer></article>)}{!versions.length && <Empty text="No versioned training reports yet" />}</div>
    </>
  );
}

function TrainingView({ localEnabled, versions, refreshVersions }: { localEnabled: boolean; versions: ModelVersion[]; refreshVersions: () => void }) {
  const [walletTarget, setWalletTarget] = useState(50000);
  const [collectionTokens, setCollectionTokens] = useState(["USDT", "USDC"]);
  const [seedText, setSeedText] = useState("");
  const [trainToken, setTrainToken] = useState("usdt");
  const [model, setModel] = useState("auto");
  const [tuningTrials, setTuningTrials] = useState(50);
  const [collections, setCollections] = useState<CollectionJob[]>([]);
  const [trainings, setTrainings] = useState<TrainingJob[]>([]);
  const [message, setMessage] = useState("");
  const isLocalHost = ["localhost", "127.0.0.1"].includes(location.hostname);
  const canOperate = localEnabled && isLocalHost;

  const refresh = useCallback(async () => {
    try {
      const [collectionData, trainingData] = await Promise.all([
        api.request<CollectionJob[]>("/collection/jobs"),
        api.request<TrainingJob[]>("/training/history")
      ]);
      setCollections(collectionData);
      setTrainings(trainingData);
    } catch (reason) { setMessage(reason instanceof Error ? reason.message : String(reason)); }
  }, []);
  useEffect(() => {
    const initial = window.setTimeout(() => void refresh(), 0);
    const timer = setInterval(() => void refresh(), 2500);
    return () => {
      window.clearTimeout(initial);
      clearInterval(timer);
    };
  }, [refresh]);

  function toggleToken(token: string) {
    setCollectionTokens((current) => current.includes(token) ? current.filter((value) => value !== token) : [...current, token]);
  }
  async function startCollection() {
    setMessage("Starting real Etherscan collection...");
    try {
      await api.request("/collection/start", { method: "POST", body: JSON.stringify({ target_wallets: walletTarget, tokens: collectionTokens, seed_wallets: seedText.split(/[\s,]+/).filter(Boolean), max_neighbors_per_wallet: 25, transactions_per_wallet: 100, resume: true }) });
      setMessage("Collection queued. You can leave this page open or return later.");
      await refresh();
    } catch (reason) { setMessage(reason instanceof Error ? reason.message : String(reason)); }
  }
  async function syncThreatIntel() {
    setMessage("Syncing explicitly risk-labeled Etherscan Gas Guzzlers rows...");
    try {
      const result = await api.request<{ records: number }>("/threat-intel/sync/etherscan-gas-guzzlers", { method: "POST" });
      setMessage(`Imported ${result.records} current Etherscan risk labels. Untagged gas users were ignored.`);
    } catch (reason) { setMessage(reason instanceof Error ? reason.message : String(reason)); }
  }
  async function startTraining() {
    setMessage("Starting leakage-safe training...");
    try {
      await api.request("/training/train", { method: "POST", body: JSON.stringify({ token: trainToken, model, estimators: 300, max_depth: 16, cv_folds: 5, tuning_trials: tuningTrials }) });
      setMessage("Training queued. Final metrics will come from the untouched test split.");
      await refresh();
    } catch (reason) { setMessage(reason instanceof Error ? reason.message : String(reason)); }
  }
  async function rollback(token: string, version: string) {
    try { await api.request("/training/rollback", { method: "POST", body: JSON.stringify({ token, version }) }); refreshVersions(); setMessage(`${token.toUpperCase()} restored to ${version}`); }
    catch (reason) { setMessage(reason instanceof Error ? reason.message : String(reason)); }
  }

  return (
    <>
      <div className="page-title"><div><p className="eyebrow">Standalone operations only</p><h1>Collection & training</h1></div><span className={`mode-chip ${canOperate ? "mode-local" : "mode-locked"}`}>{canOperate ? <TerminalSquare size={15} /> : <Pause size={15} />}{canOperate ? "Local controls enabled" : "Read-only host"}</span></div>
      {!canOperate && <div className="warning-banner"><AlertTriangle size={17} /><div><strong>Training controls are locked</strong><p>Open this page on localhost and start the API with local training enabled. Static/Netlify builds can inspect models but cannot collect or train.</p></div></div>}
      <div className="training-grid">
        <Panel title="1. Collect wallet data" meta="Resumable Etherscan V2 graph expansion">
          <div className="form-stack"><label>Wallet target<div className="number-control"><input type="number" min="1" max="1000000" value={walletTarget} onChange={(event) => setWalletTarget(Number(event.target.value))} /><span>wallets</span></div></label><div><span className="field-label">Tokens</span><div className="token-selector">{["USDT", "USDC", "DAI", "BUSD", "USDP", "TUSD"].map((token) => <button type="button" className={collectionTokens.includes(token) ? "selected" : ""} key={token} onClick={() => toggleToken(token)}>{token}</button>)}</div></div><label>Optional seed wallets<textarea rows={3} value={seedText} onChange={(event) => setSeedText(event.target.value)} placeholder="One or more 0x addresses. Existing local pools are used when blank." /></label><button className="secondary-button" disabled={!canOperate} onClick={() => void syncThreatIntel()}><ShieldAlert size={17} /> Sync flagged gas users</button><button className="primary-button" disabled={!canOperate || !collectionTokens.length} onClick={() => void startCollection()}><Play size={17} /> Start collection</button><p className="field-help">Only explorer rows with explicit phishing/scam labels become trusted malicious seeds. Other graph neighbors remain label -1.</p></div>
        </Panel>
        <Panel title="2. Train a version" meta="Wallet-separated train / validation / untouched test">
          <div className="form-stack"><label>Token<select value={trainToken} onChange={(event) => setTrainToken(event.target.value)}><option value="all">All eligible tokens</option>{["usdt", "usdc", "dai", "busd", "usdp", "tusd"].map((token) => <option key={token} value={token}>{token.toUpperCase()}</option>)}</select></label><label>Model selection<select value={model} onChange={(event) => setModel(event.target.value)}><option value="auto">Auto compare RF / XGB / LightGBM</option><option value="rf">Random Forest</option><option value="xgb">XGBoost</option><option value="lgb">LightGBM</option></select></label><label>Optuna tuning trials<div className="number-control"><input type="number" min="0" max="200" value={tuningTrials} onChange={(event) => setTuningTrials(Number(event.target.value))} /><span>trials</span></div></label><button className="primary-button" disabled={!canOperate} onClick={() => void startTraining()}><GraduationCap size={17} /> Train model</button><p className="field-help">USDT and USDC currently support honest three-class evaluation. Other tokens stay blocked until each class has enough trusted labels.</p></div>
        </Panel>
      </div>
      {message && <div className="status-message">{message}</div>}
      <div className="training-grid lower-grid">
        <Panel title="Collection jobs" meta="Checkpoints survive restarts"><JobList jobs={collections} kind="collection" /></Panel>
        <Panel title="Training jobs" meta="Progress and real held-out metrics"><JobList jobs={trainings} kind="training" /></Panel>
      </div>
      <Panel title="Version history" meta="Activate an earlier model without deleting newer artifacts">
        <div className="version-table table-scroll"><table><thead><tr><th>Token</th><th>Version</th><th>Macro F1</th><th>Malicious recall</th><th>State</th><th /></tr></thead><tbody>{versions.map((item) => <tr key={item.version}><td>{item.token.toUpperCase()}</td><td className="mono">{item.version}</td><td>{item.metrics.test_macro_f1 == null ? "-" : `${(Number(item.metrics.test_macro_f1) * 100).toFixed(1)}%`}</td><td className={Number(item.metrics.malicious_recall) < .9 ? "metric-warn" : ""}>{item.metrics.malicious_recall == null ? "-" : `${(Number(item.metrics.malicious_recall) * 100).toFixed(1)}%`}</td><td>{item.active ? <span className="active-chip">Active</span> : "Stored"}</td><td><button className="secondary-button small" disabled={!canOperate || item.active} onClick={() => void rollback(item.token, item.version)}><RotateCcw size={14} /> Restore</button></td></tr>)}</tbody></table></div>
      </Panel>
    </>
  );
}

function JobList({ jobs, kind }: { jobs: Array<CollectionJob | TrainingJob>; kind: "collection" | "training" }) {
  return <div className="job-list">{jobs.slice(0, 8).map((job) => { const collection = job as CollectionJob; const training = job as TrainingJob; const id = kind === "collection" ? collection.job_id : training.run_id; const progress = kind === "collection" ? Math.min(1, (collection.discovered || 0) / Math.max(collection.settings?.target_wallets || 1, 1)) : training.progress || 0; const detail = kind === "collection" ? `${fmt.format(collection.discovered || 0)} wallets` : `${training.token.toUpperCase()} / ${training.model}`; return <article key={id}><div><strong className="mono">{id}</strong><DecisionBadge decision={job.status.toUpperCase()} /><span>{detail}</span></div><div className="job-progress"><span style={{ width: `${progress * 100}%` }} /></div><p>{job.message}</p></article>; })}{!jobs.length && <Empty text={`No ${kind} jobs yet`} />}</div>;
}

function SettingsView({ health, onSaved }: { health: Health | null; onSaved: () => void }) {
  const [base, setBase] = useState(api.baseUrl);
  const [key, setKey] = useState(api.apiKey);
  function save(event: FormEvent) { event.preventDefault(); api.configure(base, key); onSaved(); }
  const items = [
    ["API", health?.status || "offline", health?.version || "-"],
    ["Etherscan", health?.etherscan_keys_configured ? "configured" : "missing", `${health?.etherscan_keys_configured || 0} key slots`],
    ["Live provider", health?.live_stream.state || "offline", health?.live_stream.source || health?.live_stream.error || "-"],
    ["Database", health?.database || "-", "Postgres durable feature cache"],
    ["Cache", health?.cache || "-", "Redis when REDIS_URL is configured"],
    ["API auth", health?.api_auth_enabled ? "enabled" : "local open", health?.api_auth_enabled ? "SHA-256 key verification" : "set API_KEYS_SHA256 to protect"]
  ];
  return (
    <>
      <div className="page-title"><div><p className="eyebrow">Connections and runtime</p><h1>Settings</h1></div></div>
      <div className="settings-grid"><Panel title="Console connection" meta="Stored only in this browser"><form className="form-stack" onSubmit={save}><label>API base URL<input value={base} onChange={(event) => setBase(event.target.value)} placeholder="/api or https://api.example.com" /></label><label>API key<input type="password" value={key} onChange={(event) => setKey(event.target.value)} placeholder="Leave blank when local auth is disabled" /></label><button className="primary-button"><Check size={16} /> Save & reconnect</button></form></Panel><Panel title="Environment status" meta="Secrets are never returned to this screen"><div className="status-list">{items.map(([label, value, detail]) => <div key={label}><span className={`status-dot status-${value === "configured" || value === "healthy" || value === "live" || value === "connected" || value === "redis" || value === "enabled" ? "good" : "neutral"}`} /><div><strong>{label}</strong><p>{detail}</p></div><span>{value}</span></div>)}</div></Panel></div>
    </>
  );
}

function Empty({ text }: { text: string }) { return <div className="empty"><Blocks size={24} /><span>{text}</span></div>; }

export default function App({ initialView }: { initialView: string }) {
  const [view, setView] = useState<View>((views.some((item) => item.id === initialView) ? initialView : "command") as View);
  const [health, setHealth] = useState<Health | null>(null);
  const [events, setEvents] = useState<AlertEvent[]>([]);
  const [statistics, setStatistics] = useState<AlertStatistics>({ decisions: {}, open_cases: 0, top_risky_wallets: [] });
  const [versions, setVersions] = useState<ModelVersion[]>([]);
  const [investigateWallet, setInvestigateWallet] = useState("");
  const [connectionError, setConnectionError] = useState("");

  const refresh = useCallback(async () => {
    try {
      const [healthData, alertData, statsData, versionData] = await Promise.all([
        api.request<Health>("/health"),
        api.request<AlertEvent[]>("/alerts?limit=250"),
        api.request<AlertStatistics>("/alerts/statistics"),
        api.request<{ versions: ModelVersion[] }>("/training/versions")
      ]);
      setHealth(healthData); setEvents(alertData); setStatistics(statsData); setVersions(versionData.versions); setConnectionError("");
    } catch (reason) { setConnectionError(reason instanceof Error ? reason.message : String(reason)); }
  }, []);

  useEffect(() => {
    const initial = window.setTimeout(() => void refresh(), 0);
    const timer = setInterval(() => void refresh(), 10000);
    return () => {
      window.clearTimeout(initial);
      clearInterval(timer);
    };
  }, [refresh]);
  useEffect(() => {
    let socket: WebSocket | null = null;
    let reconnect: number | undefined;
    let closed = false;
    const connect = () => {
      socket = new WebSocket(api.websocketUrl());
      socket.onmessage = (message) => {
        const data = JSON.parse(message.data);
        if (data.type === "status") setHealth((current) => current ? { ...current, live_stream: data.live } : current);
        if (data.type === "event") setEvents((current) => [data, ...current.filter((item) => item.event_id !== data.event_id)].slice(0, 500));
      };
      socket.onclose = () => { if (!closed) reconnect = window.setTimeout(connect, 2500); };
    };
    connect();
    return () => { closed = true; if (reconnect) clearTimeout(reconnect); socket?.close(); };
  }, []);

  function investigate(wallet: string) { setInvestigateWallet(wallet); setView("investigate"); }
  const currentLabel = views.find((item) => item.id === view)?.label;
  return (
    <div className="app-shell">
      <aside className="sidebar">
        <div className="brand-mark"><ShieldCheck size={22} /><span>SL</span></div>
        <nav>{views.map(({ id, label, icon: Icon }) => <button key={id} className={view === id ? "active" : ""} title={label} aria-label={label} onClick={() => setView(id)}><Icon size={19} /><span>{label}</span></button>)}</nav>
        <div className="sidebar-foot"><LiveIndicator status={health?.live_stream} /></div>
      </aside>
      <main>
        <header className="topbar"><div><span>Sentinel Ledger</span><ChevronRight size={14} /><strong>{currentLabel}</strong></div><div className="topbar-right"><span className="chain-chip"><CircleDot size={13} /> ETH mainnet</span><button className="icon-button" title="Refresh data" onClick={() => void refresh()}><RefreshCw size={16} /></button></div></header>
        <div className="content">
          {connectionError && <div className="error-banner persistent"><AlertTriangle size={17} /><span>API connection: {connectionError}</span></div>}
          {view === "command" && <CommandCenter health={health} events={events} statistics={statistics} onInvestigate={investigate} />}
          {view === "investigate" && <WalletInvestigate key={investigateWallet} initialWallet={investigateWallet} />}
          {view === "live" && <LiveStream events={events} status={health?.live_stream} onInvestigate={investigate} />}
          {view === "graph" && <GraphView />}
          {view === "cases" && <CasesView />}
          {view === "models" && <ModelsView versions={versions} refresh={() => void refresh()} />}
          {view === "training" && <TrainingView localEnabled={Boolean(health?.local_training_enabled)} versions={versions} refreshVersions={() => void refresh()} />}
          {view === "settings" && <SettingsView health={health} onSaved={() => { location.reload(); }} />}
        </div>
      </main>
      <nav className="mobile-nav">{views.slice(0, 5).map(({ id, label, icon: Icon }) => <button key={id} className={view === id ? "active" : ""} aria-label={label} onClick={() => setView(id)}><Icon size={19} /></button>)}</nav>
    </div>
  );
}
