import { useEffect, useMemo, useRef, useState, type ChangeEvent } from "react";
import {
  Activity,
  AlertCircle,
  ArrowDownToLine,
  ArrowUpRight,
  Check,
  ChevronDown,
  ClipboardCheck,
  Database,
  FileUp,
  Gauge,
  Layers3,
  RefreshCw,
  Search,
  ShieldCheck,
  SlidersHorizontal,
  TriangleAlert,
  X,
} from "lucide-react";

type RunStatus = "PASS" | "REVIEW" | "FAIL";
type TabKey = "overview" | "runs" | "findings";

type Run = {
  run_id: string;
  recorded_at: string;
  vehicle_program: string;
  component: string;
  design_revision: string;
  load_case: string;
  solver: string;
  mesh_elements: number;
  mass_kg: number;
  target_mass_kg: number;
  max_stress_mpa: number;
  allowable_stress_mpa: number;
  yield_strength_mpa: number;
  safety_factor: number;
  max_displacement_mm: number;
  allowable_displacement_mm: number;
  first_mode_hz: number;
  minimum_mode_hz: number;
  minimum_safety_factor: number;
  stress_margin_pct: number;
  displacement_margin_pct: number;
  status: RunStatus;
  finding_count: number;
};

type Summary = {
  totalRuns: number;
  passed: number;
  review: number;
  failed: number;
  openFindings: number;
  avgSafetyFactor: number;
  evaluationEngine: string;
  revisions: {
    revision: string;
    run_count: number;
    passed: number;
    review: number;
    failed: number;
  }[];
  recentRuns: Run[];
};

type ComponentRow = {
  component: string;
  run_count: number;
  latest_at: string;
  latest_status: RunStatus;
  latest_revision: string;
  open_findings: number;
};

type Finding = {
  finding_id: string;
  run_id: string;
  component: string;
  design_revision: string;
  load_case: string;
  rule_name: string;
  severity: "Critical" | "Monitor";
  measured_value: number;
  limit_value: number;
  unit: string;
  gap_pct: number;
  recommendation: string;
  status: "Open" | "Resolved";
  recorded_at: string;
  solver: string;
};

type RunDetail = Run & { findings: Finding[] };

type Comparison = {
  component: string;
  load_case: string;
  previous_revision: string;
  current_revision: string;
  recorded_at: string;
  stress_delta_pct: number;
  displacement_delta_pct: number;
  mass_delta_pct: number;
  previous_status: RunStatus;
  current_status: RunStatus;
};

async function api<T>(path: string, init?: RequestInit): Promise<T> {
  const response = await fetch(path, init);
  if (!response.ok) {
    let message = "Request failed (" + response.status + ")";
    try {
      const body = await response.json();
      message = typeof body.detail === "string" ? body.detail : message;
    } catch {
      // Keep the HTTP status message when a response has no JSON body.
    }
    throw new Error(message);
  }
  return response.json() as Promise<T>;
}

function fmtDate(value: string) {
  return new Intl.DateTimeFormat("en", {
    month: "short",
    day: "numeric",
    hour: "2-digit",
    minute: "2-digit",
  }).format(new Date(value));
}

function statusLabel(status: RunStatus | "Open" | "Resolved") {
  return status.toLowerCase();
}

function StatusPill({ status }: { status: RunStatus | "Open" | "Resolved" }) {
  const Icon = status === "PASS" ? Check : status === "FAIL" || status === "Open" ? AlertCircle : TriangleAlert;
  return (
    <span className={"statusPill status-" + statusLabel(status)}>
      <Icon size={13} strokeWidth={2.5} />
      {status}
    </span>
  );
}

function StatCard({
  label,
  value,
  note,
  icon: Icon,
  tone,
}: {
  label: string;
  value: string | number;
  note: string;
  icon: typeof Gauge;
  tone: "mint" | "amber" | "rose" | "slate";
}) {
  return (
    <article className="statCard">
      <div className={"statIcon tone-" + tone}><Icon size={18} /></div>
      <div className="statLabel">{label}</div>
      <div className="statValue">{value}</div>
      <div className="statNote">{note}</div>
    </article>
  );
}

function RevisionBars({ revisions }: { revisions: Summary["revisions"] }) {
  return (
    <div className="revisionList">
      {revisions.map((revision) => {
        const denominator = Math.max(revision.run_count, 1);
        return (
          <div className="revisionRow" key={revision.revision}>
            <div className="revisionMeta">
              <span className="revisionName">{revision.revision}</span>
              <span className="muted">{revision.run_count} simulation runs</span>
            </div>
            <div className="stackBar" aria-label={revision.revision + " outcome distribution"}>
              {revision.passed > 0 && <div className="stackPass" style={{ width: (revision.passed / denominator * 100) + "%" }} />}
              {revision.review > 0 && <div className="stackReview" style={{ width: (revision.review / denominator * 100) + "%" }} />}
              {revision.failed > 0 && <div className="stackFail" style={{ width: (revision.failed / denominator * 100) + "%" }} />}
            </div>
            <div className="revisionCounts">
              <span><i className="dot dot-pass" />{revision.passed} pass</span>
              <span><i className="dot dot-review" />{revision.review} review</span>
              <span><i className="dot dot-fail" />{revision.failed} fail</span>
            </div>
          </div>
        );
      })}
    </div>
  );
}

function RunsTable({
  rows,
  onSelect,
}: {
  rows: Run[];
  onSelect: (run: Run) => void;
}) {
  return (
    <div className="tableWrap">
      <table>
        <thead>
          <tr>
            <th>Component / run</th>
            <th>Revision</th>
            <th>Load case</th>
            <th>Peak stress</th>
            <th>Safety factor</th>
            <th>Review result</th>
          </tr>
        </thead>
        <tbody>
          {rows.map((run) => (
            <tr key={run.run_id} className="clickableRow" onClick={() => onSelect(run)}>
              <td>
                <div className="primaryCell">{run.component}</div>
                <div className="secondaryCell">{run.run_id}</div>
              </td>
              <td><span className="revisionChip">{run.design_revision}</span></td>
              <td>{run.load_case}</td>
              <td>{run.max_stress_mpa.toFixed(1)} <span className="unit">MPa</span></td>
              <td>{run.safety_factor.toFixed(2)}x</td>
              <td><StatusPill status={run.status} /></td>
            </tr>
          ))}
          {rows.length === 0 && (
            <tr><td className="emptyCell" colSpan={6}>No simulation runs match those filters.</td></tr>
          )}
        </tbody>
      </table>
    </div>
  );
}

function FindingCard({
  finding,
  onResolve,
  resolving,
}: {
  finding: Finding;
  onResolve: (finding: Finding) => void;
  resolving: boolean;
}) {
  return (
    <article className="findingCard">
      <div className="findingStripe" />
      <div className="findingBody">
        <div className="findingTopline">
          <span className={"severityChip severity-" + finding.severity.toLowerCase()}>
            <AlertCircle size={13} /> {finding.severity}
          </span>
          <span className="findingTime">{fmtDate(finding.recorded_at)}</span>
        </div>
        <h3>{finding.rule_name} limit exceeded</h3>
        <p className="findingContext">
          {finding.component} <span>·</span> {finding.design_revision} <span>·</span> {finding.load_case}
        </p>
        <div className="findingMeasurement">
          <strong>{finding.measured_value.toFixed(2)} {finding.unit}</strong>
          <span>limit {finding.limit_value.toFixed(2)} {finding.unit}</span>
          <span className="findingGap">{finding.gap_pct > 0 ? "+" : ""}{finding.gap_pct.toFixed(1)}%</span>
        </div>
        <p className="recommendation">{finding.recommendation}</p>
        <div className="findingFooter">
          <span className="runLink"><Database size={13} /> {finding.run_id}</span>
          <button
            className="textButton"
            disabled={resolving || finding.status === "Resolved"}
            onClick={() => onResolve(finding)}
          >
            {finding.status === "Resolved" ? <><Check size={14} /> Resolved</> : <><ClipboardCheck size={14} /> Mark reviewed</>}
          </button>
        </div>
      </div>
    </article>
  );
}

export default function App() {
  const [tab, setTab] = useState<TabKey>("overview");
  const [summary, setSummary] = useState<Summary | null>(null);
  const [components, setComponents] = useState<ComponentRow[]>([]);
  const [runs, setRuns] = useState<Run[]>([]);
  const [findings, setFindings] = useState<Finding[]>([]);
  const [comparisons, setComparisons] = useState<Comparison[]>([]);
  const [error, setError] = useState("");
  const [search, setSearch] = useState("");
  const [statusFilter, setStatusFilter] = useState("all");
  const [selected, setSelected] = useState<RunDetail | null>(null);
  const [uploading, setUploading] = useState(false);
  const [toast, setToast] = useState("");
  const [refreshing, setRefreshing] = useState(false);
  const fileRef = useRef<HTMLInputElement>(null);

  async function refresh() {
    setRefreshing(true);
    try {
      const [summaryData, componentData, runData, findingData, comparisonData] = await Promise.all([
        api<Summary>("/api/summary"),
        api<ComponentRow[]>("/api/components"),
        api<Run[]>("/api/runs"),
        api<Finding[]>("/api/findings"),
        api<Comparison[]>("/api/comparisons?limit=24"),
      ]);
      setSummary(summaryData);
      setComponents(componentData);
      setRuns(runData);
      setFindings(findingData);
      setComparisons(comparisonData);
      setError("");
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : "Could not reach the FEMTrace API.");
    } finally {
      setRefreshing(false);
    }
  }

  useEffect(() => {
    void refresh();
    const timer = window.setInterval(() => void refresh(), 60000);
    return () => window.clearInterval(timer);
  }, []);

  const visibleRuns = useMemo(() => {
    const query = search.trim().toLowerCase();
    return runs.filter((run) => {
      const matchesStatus = statusFilter === "all" || run.status === statusFilter;
      const matchesSearch = !query || [
        run.run_id,
        run.component,
        run.vehicle_program,
        run.design_revision,
        run.load_case,
      ].some((value) => value.toLowerCase().includes(query));
      return matchesStatus && matchesSearch;
    });
  }, [runs, search, statusFilter]);

  async function openRun(run: Run) {
    try {
      const detail = await api<RunDetail>("/api/runs/" + encodeURIComponent(run.run_id));
      setSelected(detail);
    } catch (reason) {
      setToast(reason instanceof Error ? reason.message : "Could not load run details.");
    }
  }

  async function handleUpload(event: ChangeEvent<HTMLInputElement>) {
    const input = event.currentTarget;
    const file = input.files?.[0];
    if (!file) return;
    const form = new FormData();
    form.append("file", file);
    setUploading(true);
    setToast("");
    try {
      const result = await api<{ received: number; inserted: number; duplicatesSkipped: number; message: string }>(
        "/api/runs/import",
        { method: "POST", body: form },
      );
      setToast(result.inserted + " new runs evaluated; " + result.duplicatesSkipped + " duplicate IDs skipped.");
      await refresh();
      setTab("runs");
    } catch (reason) {
      setToast(reason instanceof Error ? reason.message : "Import failed.");
    } finally {
      setUploading(false);
      input.value = "";
    }
  }

  async function resolveFinding(finding: Finding) {
    try {
      await api("/api/findings/" + encodeURIComponent(finding.finding_id) + "/resolve", {
        method: "POST",
      });
      setToast("Finding marked reviewed.");
      await refresh();
      if (selected) await openRun(selected);
    } catch (reason) {
      setToast(reason instanceof Error ? reason.message : "Could not update finding.");
    }
  }

  const navItems: { key: TabKey; label: string; icon: typeof Gauge; count?: number }[] = [
    { key: "overview", label: "Overview", icon: Gauge },
    { key: "runs", label: "CAE runs", icon: Layers3 },
    { key: "findings", label: "Finding queue", icon: ClipboardCheck, count: summary?.openFindings },
  ];

  return (
    <div className="appShell">
      <aside className="sidebar">
        <div className="brand">
          <div className="brandMark"><span>F</span><i /></div>
          <div>
            <div className="brandName">FEMTRACE</div>
            <div className="brandSub">ENGINEERING WORKBENCH</div>
          </div>
        </div>
        <div className="sideLabel">WORKSPACE</div>
        <nav className="sideNav" aria-label="Main navigation">
          {navItems.map((item) => {
            const Icon = item.icon;
            return (
              <button key={item.key} className={"navItem " + (tab === item.key ? "active" : "")} onClick={() => setTab(item.key)}>
                <Icon size={17} strokeWidth={1.9} />
                <span>{item.label}</span>
                {item.count ? <b>{item.count}</b> : null}
              </button>
            );
          })}
        </nav>
        <div className="sidebarBottom">
          <div className="sideLabel">ACTIVE PROGRAM</div>
          <div className="programCard">
            <div className="programIcon"><Activity size={15} /></div>
            <div><strong>EV Platform</strong><span>Design validation</span></div>
            <ChevronDown size={14} className="programChevron" />
          </div>
          <div className="workspaceFlag"><span className="liveDot" /> Demo workspace</div>
          <div className="sidebarFooter">FEMTRACE <span>v1.0.0</span></div>
        </div>
      </aside>

      <main className="mainArea">
        <header className="topBar">
          <div className="crumbs"><span>ENGINEERING</span><span>/</span><strong>CAE QUALITY</strong></div>
          <div className="topActions">
            <span className="syntheticTag"><span /> Synthetic data · {summary?.evaluationEngine ?? "engine starting"}</span>
            <button className="iconButton" aria-label="Refresh data" disabled={refreshing} onClick={() => void refresh()}>
              <RefreshCw size={16} className={refreshing ? "spin" : ""} />
            </button>
            <div className="avatar">CS</div>
          </div>
        </header>

        <div className="pageContent">
          <section className="pageHeading">
            <div>
              <div className="eyebrow">CAE RESULT REVIEW <span>•</span> DESIGN QUALITY</div>
              <h1>{tab === "overview" ? "Engineering overview" : tab === "runs" ? "Simulation runs" : "Engineering findings"}</h1>
              <p>
                {tab === "overview"
                  ? "A review trail from simulation output to an actionable design decision."
                  : tab === "runs"
                    ? "Search runs, compare revisions and inspect the criteria applied to each result."
                    : "Prioritize out-of-envelope results and record the review action for each finding."}
              </p>
            </div>
            <div className="headingActions">
              <a className="secondaryButton" href="/api/template" download>
                <ArrowDownToLine size={16} /> CSV template
              </a>
              <button className="primaryButton" disabled={uploading} onClick={() => fileRef.current?.click()}>
                {uploading ? <RefreshCw size={16} className="spin" /> : <FileUp size={16} />}
                {uploading ? "Evaluating…" : "Import CAE results"}
              </button>
              <input ref={fileRef} className="hiddenInput" type="file" accept=".csv,text/csv" onChange={handleUpload} />
            </div>
          </section>

          {error && (
            <div className="errorBanner">
              <AlertCircle size={17} />
              <div><strong>API unavailable</strong><span>{error}. Run the backend or use the Docker instructions in README.</span></div>
              <button onClick={() => void refresh()} aria-label="Retry connection"><RefreshCw size={15} /></button>
            </div>
          )}

          {toast && (
            <div className="toast">
              <span>{toast}</span>
              <button onClick={() => setToast("")} aria-label="Dismiss notification"><X size={15} /></button>
            </div>
          )}

          {!summary && !error && <div className="loadingState"><RefreshCw className="spin" size={18} /> Loading engineering data…</div>}

          {summary && (
            <>
              {tab === "overview" && (
                <>
                  <section className="statGrid">
                    <StatCard label="Simulation runs" value={summary.totalRuns} note="across all design revisions" icon={Layers3} tone="slate" />
                    <StatCard label="Within criteria" value={summary.passed} note="all configured checks passed" icon={ShieldCheck} tone="mint" />
                    <StatCard label="Need review" value={summary.review + summary.failed} note={summary.review + " review · " + summary.failed + " fail"} icon={TriangleAlert} tone="amber" />
                    <StatCard label="Open findings" value={summary.openFindings} note={"Avg safety factor " + summary.avgSafetyFactor.toFixed(2) + "x"} icon={ClipboardCheck} tone="rose" />
                  </section>

                  <section className="overviewGrid">
                    <article className="panel revisionPanel">
                      <div className="panelHeading">
                        <div>
                          <div className="panelKicker"><Activity size={14} /> REVISION HEALTH</div>
                          <h2>Outcome by design revision</h2>
                        </div>
                        <span className="infoTag"><span className="liveDot" /> Run review data</span>
                      </div>
                      <p className="panelDescription">Each run is checked against the limits included with its result row.</p>
                      <RevisionBars revisions={summary.revisions} />
                      <div className="panelLegend">
                        <span><i className="dot dot-pass" /> Pass</span>
                        <span><i className="dot dot-review" /> Review band</span>
                        <span><i className="dot dot-fail" /> Limit exceeded</span>
                      </div>
                    </article>

                    <article className="panel focusPanel">
                      <div className="panelKicker"><ShieldCheck size={14} /> REVIEW PRINCIPLE</div>
                      <h2>Make every result explainable.</h2>
                      <p>FEMTrace keeps the measured value, limit, margin and recommended next action together with its source run.</p>
                      <div className="focusMetric">
                        <div className="metricRing"><span>{summary.totalRuns ? Math.round(summary.passed / summary.totalRuns * 100) : 0}<small>%</small></span></div>
                        <div><strong>Inside configured criteria</strong><span>Demonstration dataset · not an engineering release decision</span></div>
                      </div>
                      <div className="focusFoot"><Database size={14} /> Run IDs and revisions are retained for traceability.</div>
                    </article>
                  </section>

                  <section className="panel tablePanel">
                    <div className="panelHeading tableHeading">
                      <div>
                        <div className="panelKicker"><Layers3 size={14} /> RECENT SIMULATIONS</div>
                        <h2>Latest CAE runs</h2>
                      </div>
                      <button className="linkButton" onClick={() => setTab("runs")}>View all runs <ArrowUpRight size={15} /></button>
                    </div>
                    <RunsTable rows={summary.recentRuns} onSelect={(run) => void openRun(run)} />
                  </section>

                  <section className="lowerGrid">
                    <article className="panel componentPanel">
                      <div className="panelHeading">
                        <div>
                          <div className="panelKicker"><Layers3 size={14} /> COMPONENT COVERAGE</div>
                          <h2>Design components</h2>
                        </div>
                        <span className="countTag">{components.length} parts</span>
                      </div>
                      <div className="componentList">
                        {components.slice(0, 6).map((component) => (
                          <div className="componentRow" key={component.component}>
                            <div className="componentAvatar"><Layers3 size={15} /></div>
                            <div className="componentName"><strong>{component.component}</strong><span>{component.run_count} runs · {component.latest_revision}</span></div>
                            <div className="componentFindings">{component.open_findings ? component.open_findings + " open" : "Clear"}</div>
                            <StatusPill status={component.latest_status} />
                          </div>
                        ))}
                      </div>
                    </article>

                    <article className="panel attentionPanel">
                      <div className="panelHeading">
                        <div>
                          <div className="panelKicker"><ClipboardCheck size={14} /> PRIORITY QUEUE</div>
                          <h2>Needs engineering review</h2>
                        </div>
                        <span className="countTag countWarn">{findings.length} open</span>
                      </div>
                      <div className="attentionList">
                        {findings.slice(0, 4).map((finding) => (
                          <button className="attentionRow" key={finding.finding_id} onClick={() => setTab("findings")}>
                            <span className={"attentionIcon " + (finding.severity === "Critical" ? "isCritical" : "")}>
                              <AlertCircle size={15} />
                            </span>
                            <span><strong>{finding.component}</strong><small>{finding.rule_name} · {finding.design_revision}</small></span>
                            <ArrowUpRight size={14} />
                          </button>
                        ))}
                        {findings.length === 0 && <p className="clearQueue"><Check size={15} /> No open findings.</p>}
                      </div>
                      <button className="queueButton" onClick={() => setTab("findings")}>Open finding queue <ArrowUpRight size={15} /></button>
                    </article>
                  </section>

                  <section className="panel comparisonPanel">
                    <div className="panelHeading">
                      <div>
                        <div className="panelKicker"><Activity size={14} /> DESIGN CHANGE TRACE</div>
                        <h2>Revision-to-revision deltas</h2>
                      </div>
                      <span className="countTag">{comparisons.length} comparisons</span>
                    </div>
                    <p className="panelDescription">Matched by component and load case. Positive stress or displacement deltas mean the measured value increased.</p>
                    <div className="tableWrap">
                      <table>
                        <thead><tr><th>Component / load case</th><th>Revision change</th><th>Stress Δ</th><th>Displacement Δ</th><th>Current outcome</th></tr></thead>
                        <tbody>
                          {comparisons.slice(0, 8).map((item, index) => (
                            <tr key={item.component + item.load_case + item.previous_revision + index}>
                              <td><div className="primaryCell">{item.component}</div><div className="secondaryCell">{item.load_case}</div></td>
                              <td><span className="revisionChip">{item.previous_revision} → {item.current_revision}</span></td>
                              <td className={item.stress_delta_pct > 0 ? "deltaUp" : "deltaDown"}>{item.stress_delta_pct > 0 ? "+" : ""}{item.stress_delta_pct.toFixed(1)}%</td>
                              <td className={item.displacement_delta_pct > 0 ? "deltaUp" : "deltaDown"}>{item.displacement_delta_pct > 0 ? "+" : ""}{item.displacement_delta_pct.toFixed(1)}%</td>
                              <td><StatusPill status={item.current_status} /></td>
                            </tr>
                          ))}
                          {comparisons.length === 0 && <tr><td colSpan={5} className="emptyCell">Import a later revision to create a comparison.</td></tr>}
                        </tbody>
                      </table>
                    </div>
                  </section>
                </>
              )}

              {tab === "runs" && (
                <section className="panel tablePanel fullPanel">
                  <div className="filterBar">
                    <div className="filterTitle">
                      <div className="panelKicker"><Layers3 size={14} /> ALL RESULTS</div>
                      <h2>{visibleRuns.length} simulation runs</h2>
                    </div>
                    <div className="filterControls">
                      <label className="searchBox">
                        <Search size={15} />
                        <input value={search} onChange={(event) => setSearch(event.target.value)} placeholder="Search component, revision…" />
                      </label>
                      <label className="selectBox"><SlidersHorizontal size={14} />
                        <select value={statusFilter} onChange={(event) => setStatusFilter(event.target.value)}>
                          <option value="all">All outcomes</option>
                          <option value="PASS">Pass</option>
                          <option value="REVIEW">Review</option>
                          <option value="FAIL">Fail</option>
                        </select>
                      </label>
                    </div>
                  </div>
                  <RunsTable rows={visibleRuns} onSelect={(run) => void openRun(run)} />
                  <div className="tableFoot"><span>Up to 500 most recent runs</span><span><span className="liveDot" /> Criteria evaluated on import</span></div>
                </section>
              )}

              {tab === "findings" && (
                <section className="findingPage">
                  <div className="findingPageIntro">
                    <div>
                      <div className="panelKicker"><ClipboardCheck size={14} /> REVIEW QUEUE</div>
                      <h2>{findings.length} open engineering findings</h2>
                      <p>Check context and recommendation, then mark the item reviewed after your engineering assessment.</p>
                    </div>
                    <div className="queueSummary"><AlertCircle size={16} /><strong>{findings.filter((item) => item.severity === "Critical").length}</strong><span>critical limit breaches</span></div>
                  </div>
                  <div className="findingGrid">
                    {findings.map((finding) => (
                      <FindingCard
                        key={finding.finding_id}
                        finding={finding}
                        resolving={false}
                        onResolve={(item) => void resolveFinding(item)}
                      />
                    ))}
                    {findings.length === 0 && <div className="emptyFindings"><Check size={24} /><h3>Queue is clear</h3><p>New findings will appear when an imported result leaves its review envelope.</p></div>}
                  </div>
                </section>
              )}
            </>
          )}

          <footer className="pageFooter">
            <span>FEMTRACE · CAE VALIDATION WORKBENCH</span>
            <span>Portfolio demo · synthetic inputs · example criteria only</span>
          </footer>
        </div>
      </main>

      {selected && (
        <div className="drawerBackdrop" onMouseDown={(event) => { if (event.target === event.currentTarget) setSelected(null); }}>
          <aside className="detailDrawer" aria-label="Simulation run detail">
            <div className="drawerHeader">
              <div><div className="panelKicker"><Database size={14} /> RUN RECORD</div><h2>{selected.component}</h2></div>
              <button className="iconButton" onClick={() => setSelected(null)} aria-label="Close details"><X size={17} /></button>
            </div>
            <div className="drawerMeta"><span>{selected.run_id}</span><StatusPill status={selected.status} /></div>
            <div className="drawerTags"><span>{selected.design_revision}</span><span>{selected.load_case}</span><span>{selected.solver}</span></div>
            <div className="detailSectionTitle">RESULT SUMMARY</div>
            <div className="detailMetrics">
              <div><span>Peak stress</span><strong>{selected.max_stress_mpa.toFixed(1)} <small>MPa</small></strong><em>limit {selected.allowable_stress_mpa} MPa</em></div>
              <div><span>Safety factor</span><strong>{selected.safety_factor.toFixed(2)}<small>x</small></strong><em>minimum {selected.minimum_safety_factor}x</em></div>
              <div><span>Max displacement</span><strong>{selected.max_displacement_mm.toFixed(2)} <small>mm</small></strong><em>limit {selected.allowable_displacement_mm} mm</em></div>
              <div><span>First mode</span><strong>{selected.first_mode_hz.toFixed(1)} <small>Hz</small></strong><em>minimum {selected.minimum_mode_hz} Hz</em></div>
              <div><span>Mass</span><strong>{selected.mass_kg.toFixed(2)} <small>kg</small></strong><em>target {selected.target_mass_kg} kg</em></div>
              <div><span>Mesh size</span><strong>{selected.mesh_elements.toLocaleString()}</strong><em>finite elements</em></div>
            </div>
            <div className="detailSectionTitle detailFindingTitle">RULE FINDINGS <span>{selected.findings.length}</span></div>
            {selected.findings.length === 0 ? (
              <div className="noRunFindings"><Check size={18} /><span>All configured criteria passed for this run.</span></div>
            ) : (
              selected.findings.map((finding) => (
                <div className="drawerFinding" key={finding.finding_id}>
                  <div><StatusPill status={finding.status === "Open" ? "FAIL" : "PASS"} /><strong>{finding.rule_name}</strong></div>
                  <p>{finding.recommendation}</p>
                  <button className="textButton" onClick={() => void resolveFinding(finding)}>
                    <ClipboardCheck size={14} /> {finding.status === "Open" ? "Mark reviewed" : "Reviewed"}
                  </button>
                </div>
              ))
            )}
            <div className="drawerDisclaimer">
              <TriangleAlert size={15} />
              <span>Example review criteria support triage only. Confirm all engineering limits and solver assumptions with the responsible design authority.</span>
            </div>
            <div className="drawerBottom"><span>Recorded {fmtDate(selected.recorded_at)}</span><button className="textButton" onClick={() => setSelected(null)}>Close details</button></div>
          </aside>
        </div>
      )}
    </div>
  );
}
