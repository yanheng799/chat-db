"use client";

import { useEffect, useState, useCallback } from "react";
import { api } from "@/lib/api";

// ── Types ──────────────────────────────────────────

interface SyncStatus {
  latest: {
    sync_type: string; status: string;
    started_at: string; finished_at: string | null;
    tables_added: number; tables_removed: number;
    columns_changed: number; error_message?: string | null;
  } | null;
  status: string;
}

interface GraphNode { name: string; schema?: string; table?: string; type?: string; is_pk?: boolean; }
interface GraphEdge { type: string; from_table: string; from_column: string; to_table: string; to_column: string; confidence: number; }

interface MappingItem {
  id?: string; table_name?: string; column_name?: string;
  value?: string; display?: string; code?: string; name?: string;
  short_name?: string; full_name?: string; target_table?: string;
  aliases?: string[];
}

// ── Page ───────────────────────────────────────────

export default function AdminPage() {
  const [activeDsId, setActiveDsId] = useState<string>("");
  const [activeDsName, setActiveDsName] = useState<string>("");

  // Sync
  const [sync, setSync] = useState<SyncStatus | null>(null);
  const [syncLoading, setSyncLoading] = useState(false);

  // Graph
  const [nodes, setNodes] = useState<GraphNode[]>([]);
  const [edges, setEdges] = useState<GraphEdge[]>([]);
  const [graphLoading, setGraphLoading] = useState(false);

  // Mappings
  const [mappingType, setMappingType] = useState("enum");
  const [mappings, setMappings] = useState<MappingItem[]>([]);
  const [mappingsLoading, setMappingsLoading] = useState(false);

  // Hotwords
  const [hotwords, setHotwords] = useState<Record<string, any>>({});
  const [hotwordsLoading, setHotwordsLoading] = useState(false);

  // Periods
  const [periods, setPeriods] = useState<Record<string, string[]>[]>([]);
  const [periodsLoading, setPeriodsLoading] = useState(false);

  // Audit
  const [audit, setAudit] = useState<Record<string, any>>({});
  const [auditLoading, setAuditLoading] = useState(false);

  // ── Load active datasource ────────────────────────
  useEffect(() => {
    (async () => {
      try {
        const dss = await api.get<any[]>("/api/datasources");
        const active = dss.find((d: any) => d.is_active);
        if (active) {
          setActiveDsId(active.id);
          setActiveDsName(active.name);
        }
      } catch { /* ignore */ }
    })();
  }, []);

  // ── Card loaders ──────────────────────────────────
  const loadSync = useCallback(async () => {
    setSyncLoading(true);
    try { setSync(await api.get<SyncStatus>("/api/admin/sync/status")); } catch { }
    setSyncLoading(false);
  }, []);

  const loadGraph = useCallback(async () => {
    if (!activeDsId) return;
    setGraphLoading(true);
    try {
      const [n, e] = await Promise.all([
        api.get<any>(`/api/admin/graph/nodes/${activeDsId}`),
        api.get<any>(`/api/admin/graph/edges/${activeDsId}`),
      ]);
      setNodes(n.tables?.map((t: any) => ({ ...t })) || []);
      setEdges(e.edges || []);
    } catch { }
    setGraphLoading(false);
  }, [activeDsId]);

  const loadMappings = useCallback(async () => {
    if (!activeDsId) return;
    setMappingsLoading(true);
    try {
      const data = await api.get<any>(`/api/admin/mappings/${mappingType}?data_source_id=${activeDsId}`);
      setMappings(data.items || []);
    } catch { setMappings([]); }
    setMappingsLoading(false);
  }, [activeDsId, mappingType]);

  const loadHotwords = useCallback(async () => {
    setHotwordsLoading(true);
    try { const d = await api.get<any>("/api/admin/hotwords"); setHotwords(d.items || []); } catch { }
    setHotwordsLoading(false);
  }, []);

  const loadPeriods = useCallback(async () => {
    setPeriodsLoading(true);
    try { const d = await api.get<any>("/api/admin/fixed-periods"); setPeriods(d.items || []); } catch { }
    setPeriodsLoading(false);
  }, []);

  const loadAudit = useCallback(async () => {
    setAuditLoading(true);
    try { setAudit(await api.get<any>("/api/admin/audit-policy")); } catch { }
    setAuditLoading(false);
  }, []);

  // ── Load on mount / ds change ─────────────────────
  useEffect(() => { loadSync(); }, [loadSync]);
  useEffect(() => { if (activeDsId) { loadGraph(); loadMappings(); } }, [activeDsId, mappingType, loadGraph, loadMappings]);
  useEffect(() => { loadHotwords(); loadPeriods(); loadAudit(); }, [loadHotwords, loadPeriods, loadAudit]);

  // ── Render ────────────────────────────────────────
  return (
    <div className="flex-1 overflow-y-auto px-7 py-6">
      <div className="flex items-center justify-between mb-6">
        <h2 className="text-lg font-semibold text-foreground">管理控制台</h2>
        {activeDsName && (
          <span className="text-xs text-muted-foreground bg-secondary px-3 py-1 rounded-full">
            数据源: {activeDsName}
          </span>
        )}
      </div>

      <div className="grid gap-5">
        <Card title="同步状态" loading={syncLoading} onRetry={loadSync}>
          {!sync || sync.status === "no_sync_yet" ? (
            <Empty text="暂无同步记录" />
          ) : sync.latest ? (
            <div className="space-y-2 text-sm">
              <Row label="状态" value={<StatusBadge s={sync.latest.status} />} />
              <Row label="类型" value={sync.latest.sync_type} />
              <Row label="时间" value={sync.latest.started_at ? new Date(sync.latest.started_at).toLocaleString("zh-CN") : "—"} />
              <Row label="新增表" value={String(sync.latest.tables_added ?? "—")} />
              <Row label="列变更" value={String(sync.latest.columns_changed ?? "—")} />
              {sync.latest.error_message && (
                <div className="text-xs text-red-400 bg-red-500/5 border border-red-500/20 rounded px-3 py-2 font-mono">{sync.latest.error_message}</div>
              )}
            </div>
          ) : null}
        </Card>

        {/* ── Knowledge Graph ──────────────────────── */}
        <Card title="知识图谱" loading={graphLoading} onRetry={loadGraph}
          subtitle={activeDsId ? `${nodes.length} 表, ${edges.length} 关系` : "无激活数据源"}>
          {!activeDsId ? (
            <Empty text="请先在数据源管理中激活一个数据源" />
          ) : nodes.length === 0 ? (
            <Empty text="图谱为空 — 请先同步元数据并刷新知识库" />
          ) : (
            <div className="space-y-4">
              {/* Tables as tag clusters */}
              <div>
                <span className="text-[11px] uppercase tracking-wider text-muted-foreground font-medium">表 ({nodes.length})</span>
                <div className="flex flex-wrap gap-2 mt-2">
                  {nodes.map((n, i) => (
                    <span key={i} className="inline-flex items-center gap-1.5 px-2.5 py-1.5 bg-secondary border border-border rounded-lg text-xs">
                      <span className="w-2 h-2 rounded-full bg-primary" />
                      {n.schema && <span className="text-muted-foreground">{n.schema}.</span>}
                      <span className="text-foreground font-medium">{n.name}</span>
                    </span>
                  ))}
                </div>
              </div>
              {/* Columns */}
              {edges.length > 0 && (
                <div>
                  <span className="text-[11px] uppercase tracking-wider text-muted-foreground font-medium">关系 ({edges.length})</span>
                  <div className="mt-2 space-y-1">
                    {edges.slice(0, 20).map((e, i) => (
                      <div key={i} className="flex items-center gap-2 text-xs">
                        <span className="text-foreground font-medium">{e.from_table}.{e.from_column}</span>
                        <span className={e.type === "REFERENCES" ? "text-green-400" : e.type === "INFERRED_REF" ? "text-amber-400" : "text-muted-foreground"}>
                          {e.type === "REFERENCES" ? "→ FK →" : e.type === "INFERRED_REF" ? "→ 推断 →" : "→"}
                        </span>
                        <span className="text-foreground font-medium">{e.to_table}.{e.to_column}</span>
                        {e.confidence != null && (
                          <span className="text-muted-foreground ml-auto tabular-nums">{Math.round(e.confidence * 100)}%</span>
                        )}
                      </div>
                    ))}
                    {edges.length > 20 && <div className="text-xs text-muted-foreground">...还有 {edges.length - 20} 条关系</div>}
                  </div>
                </div>
              )}
            </div>
          )}
        </Card>

        {/* ── Value Mappings ────────────────────────── */}
        <Card title="值映射" loading={mappingsLoading} onRetry={loadMappings}
          subtitle={activeDsId ? undefined : "无激活数据源"}
          extra={
            <select value={mappingType} onChange={e => setMappingType(e.target.value)}
              className="text-xs bg-secondary border border-border rounded px-2 py-1 text-foreground">
              <option value="enum">枚举别名</option>
              <option value="region">地区</option>
              <option value="name">名称简称</option>
            </select>
          }>
          {!activeDsId ? <Empty text="请先激活数据源" /> :
           mappings.length === 0 ? <Empty text={`暂无${mappingType === 'enum' ? '枚举别名' : mappingType === 'region' ? '地区' : '名称'}映射`} /> : (
            <div className="space-y-1.5 max-h-64 overflow-y-auto">
              {mappings.map((m, i) => (
                <div key={i} className="text-xs flex items-center gap-2 px-2 py-1.5 bg-secondary/50 rounded">
                  {mappingType === "enum" && <><span className="font-mono text-foreground">{m.table_name}.{m.column_name}</span><span className="text-muted-foreground">{m.value} → {m.display}</span></>}
                  {mappingType === "region" && <><span className="text-muted-foreground">[{m.code}]</span><span className="text-foreground">{m.name}</span></>}
                  {mappingType === "name" && <><span className="text-muted-foreground">{m.short_name}</span><span>→</span><span className="text-foreground">{m.full_name}</span></>}
                  {m.aliases && m.aliases.length > 0 && <span className="text-muted-foreground ml-auto text-[10px]">{m.aliases.join(", ")}</span>}
                </div>
              ))}
            </div>
          )}
        </Card>

        {/* ── Hot Words ─────────────────────────────── */}
        <Card title="热词词典" loading={hotwordsLoading} onRetry={loadHotwords}
          subtitle={`${Array.isArray(hotwords) ? hotwords.length : Object.keys(hotwords).length} 条`}>
          {Array.isArray(hotwords) ? (
            hotwords.length === 0 ? <Empty text="暂无热词" /> : (
              <div className="space-y-1.5 max-h-64 overflow-y-auto">
                {hotwords.map((h: any, i: number) => (
                  <div key={i} className="text-xs flex items-center gap-2 px-2 py-1.5 bg-secondary/50 rounded">
                    <span className="font-medium text-foreground">{h.term}</span>
                    <span className="text-muted-foreground">→ {h.target_table}.{h.target_column || "*"}</span>
                    {h.locked && <span className="text-amber-400 text-[10px] ml-auto">🔒 锁定</span>}
                  </div>
                ))}
              </div>
            )
          ) : (
            Object.keys(hotwords).length === 0 ? <Empty text="暂无热词" /> : (
              <div className="space-y-1.5 max-h-64 overflow-y-auto">
                {Object.entries(hotwords).map(([term, entry]: [string, any]) => (
                  <div key={term} className="text-xs flex items-center gap-2 px-2 py-1.5 bg-secondary/50 rounded">
                    <span className="font-medium text-foreground">{term}</span>
                    <span className="text-muted-foreground">→ {entry.target_table}.{entry.target_column || "*"}</span>
                    {entry.locked && <span className="text-amber-400 text-[10px] ml-auto">🔒 锁定</span>}
                  </div>
                ))}
              </div>
            )
          )}
        </Card>

        {/* ── Fixed Periods ─────────────────────────── */}
        <Card title="固定日期周期" loading={periodsLoading} onRetry={loadPeriods}
          subtitle={`${periods.length} 条`}>
          {periods.length === 0 ? <Empty text="暂无周期" /> : (
            <div className="flex flex-wrap gap-2">
              {periods.map((p: any, i: number) => (
                <span key={i} className="px-2.5 py-1.5 bg-secondary border border-border rounded-lg text-xs">
                  <span className="text-foreground font-medium">{p.name}</span>
                  <span className="text-muted-foreground"> {p.start} ~ {p.end}</span>
                </span>
              ))}
            </div>
          )}
        </Card>

        {/* ── Audit Policy ──────────────────────────── */}
        <Card title="审核策略" loading={auditLoading} onRetry={loadAudit}>
          {Object.keys(audit).length === 0 ? <Empty text="未配置" /> : (
            <div className="space-y-2 text-sm">
              <Row label="模式" value={<span className={`font-semibold ${audit.mode === "none" ? "text-green-400" : "text-amber-400"}`}>{audit.mode === "none" ? "无审核" : audit.mode}</span>} />
              <Row label="数据量阈值" value={String(audit.data_threshold ?? "—")} />
              <Row label="复杂度阈值" value={String(audit.complexity_threshold ?? "—")} />
              {audit.sensitive_tables?.length > 0 && (
                <Row label="敏感表" value={(audit.sensitive_tables as string[]).join(", ")} />
              )}
            </div>
          )}
        </Card>
      </div>
    </div>
  );
}

// ── Sub-components ─────────────────────────────────

function Card({ title, subtitle, extra, loading, onRetry, children }: {
  title: string; subtitle?: string; extra?: React.ReactNode;
  loading: boolean; onRetry?: () => void; children: React.ReactNode;
}) {
  return (
    <section className="bg-card border border-border rounded-xl overflow-hidden">
      <h3 className="px-4 py-3.5 text-sm font-semibold border-b border-border flex items-center justify-between text-foreground">
        <span>
          {title}
          {subtitle && <span className="text-xs text-muted-foreground font-normal ml-2">{subtitle}</span>}
        </span>
        <span className="flex items-center gap-2">
          {extra}
          {onRetry && (
            <button onClick={onRetry} className="text-xs text-muted-foreground hover:text-foreground">刷新</button>
          )}
        </span>
      </h3>
      <div className="px-4 py-3.5">
        {loading ? <div className="text-sm text-muted-foreground animate-pulse">加载中…</div> : children}
      </div>
    </section>
  );
}

function Row({ label, value }: { label: string; value: React.ReactNode }) {
  return (
    <div className="flex gap-3">
      <span className="text-muted-foreground w-20 shrink-0">{label}</span>
      <span className="text-foreground">{value}</span>
    </div>
  );
}

function StatusBadge({ s }: { s: string }) {
  const map: Record<string, string> = {
    success: "bg-green-500/10 text-green-400 border-green-500/30",
    running: "bg-primary/10 text-primary border-primary/30",
    failed: "bg-red-500/10 text-red-400 border-red-500/30",
  };
  return (
    <span className={`inline-flex items-center gap-1 px-2 py-0.5 rounded text-xs font-medium border ${map[s] || "bg-muted text-muted-foreground border-border"}`}>
      {s === "running" && <span className="w-1.5 h-1.5 rounded-full bg-primary animate-pulse" />}
      {s}
    </span>
  );
}

function Empty({ text }: { text: string }) {
  return <div className="text-sm text-muted-foreground py-4 text-center">{text}</div>;
}
