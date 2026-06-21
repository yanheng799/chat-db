"use client";

import { useEffect, useState, useCallback } from "react";
import Link from "next/link";
import { useParams } from "next/navigation";
import { ArrowLeft, Download, Brain, RefreshCw, MoreHorizontal, ChevronDown } from "lucide-react";
import { Card, CardHeader, CardTitle, CardContent, Badge, Collapsible, Menu, Select, Skeleton, EmptyState, Spinner } from "@/components/ui";
import { api } from "@/lib/api";
import {
  useDataSourceStore,
  type SyncLog,
  type LearningLog,
  type DataSource,
} from "@/stores/datasources";
import { useToastStore } from "@/stores/toast";

// ── Merged timeline entry ───────────────────────────

type TimelineEntry =
  | { kind: "sync"; data: SyncLog }
  | { kind: "learn"; data: LearningLog };

interface GraphNode {
  name: string;
  schema?: string;
}

interface GraphEdge {
  type: string;
  from_table: string;
  from_column: string;
  to_table: string;
  to_column: string;
  confidence: number;
}

export default function DatasourceDetailPage() {
  const { id } = useParams<{ id: string }>();
  const {
    getDataSource,
    getMetadata,
    getSyncLogs,
    getLearningLogs,
    syncMetadata,
    learnMetadata,
    refreshKnowledge,
  } = useDataSourceStore();
  const showToast = useToastStore((s) => s.showToast);

  const [ds, setDs] = useState<DataSource | null>(null);
  const [tableCount, setTableCount] = useState<number | null>(null);
  const [columnCount, setColumnCount] = useState<number | null>(null);
  const [timeline, setTimeline] = useState<TimelineEntry[]>([]);
  const [loading, setLoading] = useState(true);
  const [syncing, setSyncing] = useState(false);
  const [learning, setLearning] = useState(false);
  const [refreshingKb, setRefreshingKb] = useState(false);

  // ── Graph ──────────────────────────────────────────
  const [nodes, setNodes] = useState<GraphNode[]>([]);
  const [edges, setEdges] = useState<GraphEdge[]>([]);
  const [graphLoading, setGraphLoading] = useState(false);

  const loadGraph = useCallback(async () => {
    if (!id) return;
    setGraphLoading(true);
    try {
      const [n, e] = await Promise.all([
        api.get<any>(`/api/admin/graph/nodes/${id}`),
        api.get<any>(`/api/admin/graph/edges/${id}`),
      ]);
      setNodes(n.tables?.map((t: any) => ({ name: t.name, schema: t.schema })) || []);
      setEdges(e.edges || []);
    } catch {
      // Neo4j unreachable — show empty state
    }
    setGraphLoading(false);
  }, [id]);

  // ── Reachable subgraph ──────────────────────────────
  const [reachableLoading, setReachableLoading] = useState(false);
  const [reachableError, setReachableError] = useState<string | null>(null);
  const [reachableTables, setReachableTables] = useState<
    { name: string; path: { from_table: string; from_column: string; to_table: string; to_column: string; type: string; confidence: number }[] }[]
  >([]);

  const loadReachable = useCallback(
    async (fromTable: string) => {
      if (!id || !fromTable) return;
      setReachableLoading(true);
      setReachableError(null);
      setReachableTables([]);
      try {
        const data = await api.get<any>(
          `/api/admin/graph/reachable/${id}?from=${encodeURIComponent(fromTable)}`,
        );
        setReachableTables(data.tables || []);
      } catch (e: unknown) {
        setReachableError((e as Error).message || "请求失败");
      }
      setReachableLoading(false);
    },
    [id],
  );

  // ── Load all data ─────────────────────────────────
  const loadAll = useCallback(async () => {
    if (!id) return;
    setLoading(true);
    try {
      const [dsData, meta, syncLogs, learnLogs] = await Promise.all([
        getDataSource(id),
        getMetadata(id).catch(() => ({ table_count: 0, column_count: 0 })),
        getSyncLogs(id).catch(() => [] as SyncLog[]),
        getLearningLogs(id).catch(() => [] as LearningLog[]),
      ]);
      loadGraph(); // fire-and-forget (Neo4j may not be running)
      setDs(dsData);
      setTableCount(meta.table_count);
      setColumnCount(meta.column_count);

      const merged: TimelineEntry[] = [
        ...syncLogs.map((s) => ({ kind: "sync" as const, data: s })),
        ...learnLogs.map((l) => ({ kind: "learn" as const, data: l })),
      ].sort(
        (a, b) =>
          new Date(b.data.started_at).getTime() -
          new Date(a.data.started_at).getTime(),
      );
      setTimeline(merged);
    } catch (e: unknown) {
      showToast("error", (e as Error).message || "加载失败");
    } finally {
      setLoading(false);
    }
  }, [id, getDataSource, getMetadata, getSyncLogs, getLearningLogs, showToast]);

  useEffect(() => {
    loadAll();
  }, [loadAll]);

  // ── Auto-refresh while a task is running ──────────
  useEffect(() => {
    const hasRunning = timeline.some((e) => e.data.status === "running");
    if (!hasRunning) return;
    const timer = setInterval(loadAll, 3000);
    return () => clearInterval(timer);
  }, [timeline, loadAll]);

  // ── Actions ───────────────────────────────────────
  const classifyError = (e: unknown): string => {
    if (!(e instanceof Error)) return String(e);
    const msg = e.message;
    if (msg.includes("409")) return "已有任务运行中";
    if (msg.includes("Failed to fetch") || msg.includes("NetworkError"))
      return "网络错误：无法连接后端服务 (localhost:8000)";
    if (msg.startsWith("[后端]")) return msg;
    if (msg.includes("HTTP 5")) return `后端错误: ${msg}`;
    return msg;
  };

  const handleSync = async () => {
    if (!id) return;
    setSyncing(true);
    try {
      const result = await syncMetadata(id);
      showToast("success", result.message);
      await loadAll();
    } catch (e: unknown) {
      showToast("error", classifyError(e));
    } finally {
      setSyncing(false);
    }
  };

  const handleLearn = async () => {
    if (!id) return;
    setLearning(true);
    try {
      const result = await learnMetadata(id);
      showToast("success", result.message);
      await loadAll();
    } catch (e: unknown) {
      showToast("error", classifyError(e));
    } finally {
      setLearning(false);
    }
  };

  const handleRefreshKb = async () => {
    if (!id) return;
    setRefreshingKb(true);
    try {
      const result = await refreshKnowledge(id);
      showToast("success", result.message);
      await loadGraph();
    } catch (e: unknown) {
      showToast("error", classifyError(e));
    } finally {
      setRefreshingKb(false);
    }
  };

  // ── Helpers ───────────────────────────────────────
  const timeAgo = (iso: string) => {
    const diff = Date.now() - new Date(iso).getTime();
    const mins = Math.floor(diff / 60000);
    if (mins < 1) return "刚刚";
    if (mins < 60) return `${mins} 分钟前`;
    const hrs = Math.floor(mins / 60);
    if (hrs < 24) return `${hrs} 小时前`;
    return `${Math.floor(hrs / 24)} 天前`;
  };

  const formatTime = (iso: string | null) => {
    if (!iso) return "—";
    return new Date(iso).toLocaleTimeString("zh-CN", {
      hour: "2-digit",
      minute: "2-digit",
      second: "2-digit",
    });
  };

  // ── Derived stats ─────────────────────────────────
  const fkInferred = timeline
    .filter((e) => e.kind === "learn" && e.data.status === "completed")
    .reduce((sum, e) => sum + ((e.data as LearningLog).fk_inferred || 0), 0);

  const anyActionRunning = syncing || learning || refreshingKb;

  // ── Loading skeleton ──────────────────────────────
  if (loading) {
    return (
      <div className="flex-1 overflow-y-auto px-7 py-6">
        <div className="space-y-4">
          <Skeleton className="h-4 w-24" />
          <div className="flex gap-4">
            <Skeleton className="h-20 w-40 rounded-lg" />
            <Skeleton className="h-20 w-40 rounded-lg" />
            <Skeleton className="h-20 w-40 rounded-lg" />
          </div>
          <Skeleton className="h-64 w-full rounded-lg" />
        </div>
      </div>
    );
  }

  return (
    <div className="flex-1 overflow-y-auto">
      {/* ── Top bar ────────────────────────────────── */}
      <div className="px-7 py-4 border-b border-border flex items-center gap-4 flex-wrap">
        <Link
          href="/datasources"
          className="inline-flex items-center gap-1 text-xs text-muted-foreground hover:text-foreground transition-colors"
        >
          <ArrowLeft className="size-3.5" />
          返回
        </Link>
        <div className="flex-1 min-w-0">
          <h2 className="text-base font-semibold text-foreground truncate">
            {ds?.name || "数据源详情"}
          </h2>
          <p className="text-xs text-muted-foreground tabular-nums">
            {ds?.engine?.toUpperCase()} · {ds?.host}:{ds?.port}/{ds?.database}
          </p>
        </div>
        <Menu.Root>
          <Menu.Trigger
            disabled={anyActionRunning}
            className="h-8 px-3 gap-1.5 bg-background border border-input rounded-md text-sm font-medium text-foreground hover:bg-secondary disabled:opacity-50"
          >
            {anyActionRunning ? <Spinner className="size-4" /> : <MoreHorizontal className="size-4" />}
            操作
          </Menu.Trigger>
          <Menu.Content>
            <Menu.Item onClick={handleSync}>
              {syncing ? <Spinner className="size-3.5" /> : <Download className="size-3.5" />}
              {syncing ? "同步中…" : "同步元数据"}
            </Menu.Item>
            <Menu.Item onClick={handleLearn}>
              {learning ? <Spinner className="size-3.5" /> : <Brain className="size-3.5" />}
              {learning ? "学习中…" : "学习分析"}
            </Menu.Item>
            <Menu.Item onClick={handleRefreshKb}>
              {refreshingKb ? <Spinner className="size-3.5" /> : <RefreshCw className="size-3.5" />}
              {refreshingKb ? "刷新中…" : "刷新知识库"}
            </Menu.Item>
          </Menu.Content>
        </Menu.Root>
      </div>

      <div className="px-7 py-6 space-y-8">
        {/* ── Stats ──────────────────────────────────── */}
        <div className="grid grid-cols-3 gap-4">
          <StatCard label="表" value={tableCount} sub="从数据库提取" />
          <StatCard label="列 / 字段" value={columnCount} sub="含类型与主键" />
          <StatCard label="推断外键" value={fkInferred} sub="值重合度推断" />
        </div>

        {/* ── Knowledge Graph ──────────────────────── */}
        <section>
          <Collapsible.Root defaultOpen={false}>
            <Collapsible.Trigger className="flex items-center gap-2 w-full text-left mb-4 group">
              <ChevronDown className="size-4 text-muted-foreground transition-transform duration-150 group-data-[panel-open]:rotate-180" />
              <h3 className="text-sm font-semibold text-foreground">知识图谱</h3>
              <span className="text-xs text-muted-foreground tabular-nums">
                {graphLoading ? "…" : `${nodes.length} 表 · ${edges.length} 关系`}
              </span>
            </Collapsible.Trigger>
            <Collapsible.Panel>
              <div className="space-y-4 pb-2">
                {/* Tables */}
                <Card>
                  <CardHeader>
                    <span className="text-xs font-medium text-muted-foreground">
                      表节点 ({nodes.length})
                    </span>
                  </CardHeader>
                  <CardContent>
                    {graphLoading ? (
                      <Skeleton className="h-24 w-full" />
                    ) : nodes.length === 0 ? (
                      <EmptyState
                        title="图谱为空"
                        description="同步元数据并学习后，点击「操作 → 刷新知识库」构建图谱"
                      />
                    ) : (
                      <div className="rounded-lg border border-border overflow-hidden max-h-80 overflow-y-auto">
                        <table className="w-full text-sm">
                          <thead className="bg-muted/60">
                            <tr>
                              <th className="text-left px-3 py-2 text-xs font-medium text-muted-foreground">
                                Schema
                              </th>
                              <th className="text-left px-3 py-2 text-xs font-medium text-muted-foreground">
                                表名
                              </th>
                            </tr>
                          </thead>
                          <tbody>
                            {nodes.map((n, i) => (
                              <tr
                                key={`${n.schema ?? ""}.${n.name}`}
                                className={i % 2 ? "bg-muted/30" : ""}
                              >
                                <td className="px-3 py-2 font-mono text-xs text-muted-foreground">
                                  {n.schema ?? "—"}
                                </td>
                                <td className="px-3 py-2 font-mono text-xs">
                                  {n.name}
                                </td>
                              </tr>
                            ))}
                          </tbody>
                        </table>
                      </div>
                    )}
                  </CardContent>
                </Card>

                {/* Edges */}
                <Card>
                  <CardHeader>
                    <span className="text-xs font-medium text-muted-foreground">
                      关系 ({edges.length})
                    </span>
                  </CardHeader>
                  <CardContent>
                    {graphLoading ? (
                      <Skeleton className="h-24 w-full" />
                    ) : edges.length === 0 ? (
                      <EmptyState title="暂无关系" />
                    ) : (
                      <div className="rounded-lg border border-border overflow-hidden max-h-80 overflow-y-auto">
                        <table className="w-full text-sm">
                          <thead className="bg-muted/60">
                            <tr>
                              <th className="text-left px-3 py-2 text-xs font-medium text-muted-foreground">
                                起点
                              </th>
                              <th className="text-left px-3 py-2 text-xs font-medium text-muted-foreground">
                                关系
                              </th>
                              <th className="text-left px-3 py-2 text-xs font-medium text-muted-foreground">
                                终点
                              </th>
                              <th className="text-right px-3 py-2 text-xs font-medium text-muted-foreground">
                                置信度
                              </th>
                            </tr>
                          </thead>
                          <tbody>
                            {edges.slice(0, 200).map((e, i) => (
                              <tr
                                key={i}
                                className={i % 2 ? "bg-muted/30" : ""}
                              >
                                <td className="px-3 py-2 font-mono text-xs">
                                  {e.from_table}.{e.from_column}
                                </td>
                                <td className="px-3 py-2">
                                  <Badge
                                    variant={
                                      e.type === "REFERENCES"
                                        ? "info"
                                        : e.type === "INFERRED_REF"
                                          ? "warning"
                                          : "outline"
                                    }
                                  >
                                    {e.type === "REFERENCES"
                                      ? "外键"
                                      : e.type === "INFERRED_REF"
                                        ? "推断"
                                        : e.type}
                                  </Badge>
                                </td>
                                <td className="px-3 py-2 font-mono text-xs">
                                  {e.to_table}.{e.to_column}
                                </td>
                                <td className="px-3 py-2 text-right tabular-nums text-muted-foreground text-xs">
                                  {e.confidence != null
                                    ? `${Math.round(e.confidence * 100)}%`
                                    : "—"}
                                </td>
                              </tr>
                            ))}
                          </tbody>
                        </table>
                      </div>
                    )}
                  </CardContent>
                </Card>
              </div>

              {/* ── Reachable Network Explorer ─────────── */}
              {nodes.length > 0 && (
                <Card>
                  <CardHeader>
                    <CardTitle>可达网络</CardTitle>
                  </CardHeader>
                  <CardContent className="space-y-3">
                    <Select
                      options={[
                        { value: "", label: "选择一张起始表查看可达网络…" },
                        ...nodes.map((n) => ({
                          value: n.name,
                          label: `${n.schema ? n.schema + "." : ""}${n.name}`,
                        })),
                      ]}
                      value=""
                      onChange={(e) => {
                        const v = e.target.value;
                        if (v) loadReachable(v);
                      }}
                    />
                    {reachableLoading ? (
                      <Skeleton className="h-16 w-full" />
                    ) : reachableError ? (
                      <div className="text-xs text-destructive">{reachableError}</div>
                    ) : reachableTables.length > 0 ? (
                      <div className="space-y-1.5 max-h-64 overflow-y-auto">
                        {reachableTables.map((r) => (
                          <details key={r.name} className="text-sm border border-border rounded-md">
                            <summary className="px-3 py-2 cursor-pointer hover:bg-muted/50 font-mono text-xs">
                              {r.name}
                              <span className="text-muted-foreground ml-2">
                                ({r.path.length} 步)
                              </span>
                            </summary>
                            <div className="px-3 pb-2 space-y-1">
                              {r.path.map((step, si) => (
                                <div
                                  key={si}
                                  className="flex items-center gap-1.5 text-xs text-muted-foreground"
                                >
                                  <span className="font-mono">{step.from_table}.{step.from_column}</span>
                                  <span>→</span>
                                  <Badge
                                    variant={step.type === "REFERENCES" ? "info" : "warning"}
                                  >
                                    {step.type === "REFERENCES" ? "外键" : "推断"}
                                  </Badge>
                                  <span>→</span>
                                  <span className="font-mono">{step.to_table}.{step.to_column}</span>
                                  {step.confidence != null && (
                                    <span className="tabular-nums">
                                      ({Math.round(step.confidence * 100)}%)
                                    </span>
                                  )}
                                </div>
                              ))}
                            </div>
                          </details>
                        ))}
                      </div>
                    ) : reachableTables.length === 0 && !reachableLoading && !reachableError ? (
                      <div className="text-xs text-muted-foreground">
                        选择起始表后查看递归可达网络
                      </div>
                    ) : null}
                  </CardContent>
                </Card>
              )}
            </Collapsible.Panel>
          </Collapsible.Root>
        </section>

        {/* ── Timeline ─────────────────────────────── */}
        <section>
          <div className="flex items-center gap-2 mb-4">
            <h3 className="text-sm font-semibold text-foreground">运行历史</h3>
            <span className="text-xs text-muted-foreground tabular-nums">
              {timeline.length} 条记录
            </span>
          </div>

          {timeline.length === 0 ? (
            <Card>
              <EmptyState
                title="暂无运行记录"
                description="点击右上角「操作 → 同步元数据」开始首次扫描"
              />
            </Card>
          ) : (
            <Card className="p-0 overflow-hidden divide-y divide-border">
              {timeline.map((entry, i) => (
                <TimelineRow
                  key={entry.data.id}
                  entry={entry}
                  isLast={i === timeline.length - 1}
                  timeAgo={timeAgo}
                  formatTime={formatTime}
                />
              ))}
            </Card>
          )}
        </section>
      </div>
    </div>
  );
}

// ── Stat card ───────────────────────────────────────

function StatCard({
  label,
  value,
  sub,
}: {
  label: string;
  value: number | null;
  sub: string;
}) {
  return (
    <Card className="p-5">
      <div className="text-xs text-muted-foreground mb-1">{label}</div>
      <div className="text-2xl font-bold text-foreground tabular-nums">
        {value === null ? "—" : value.toLocaleString()}
      </div>
      <div className="text-[11px] text-muted-foreground mt-0.5">{sub}</div>
    </Card>
  );
}

// ── Status badge ────────────────────────────────────

function StatusBadge({ status }: { status: string }) {
  if (status === "running")
    return (
      <Badge variant="default">
        <Spinner className="size-3" />
        运行中
      </Badge>
    );
  if (status === "completed") return <Badge variant="success">完成</Badge>;
  if (status === "failed") return <Badge variant="destructive">失败</Badge>;
  return <Badge variant="outline">{status}</Badge>;
}

// ── Timeline row ────────────────────────────────────

function TimelineRow({
  entry,
  timeAgo,
  formatTime,
}: {
  entry: TimelineEntry;
  isLast: boolean;
  timeAgo: (iso: string) => string;
  formatTime: (iso: string | null) => string;
}) {
  const isSync = entry.kind === "sync";
  const d = entry.data;

  return (
    <div className="flex gap-3 px-4 py-3.5">
      <div
        className={`size-8 rounded-md grid place-items-center shrink-0 ${
          isSync ? "bg-primary/10 text-primary" : "bg-chart-5/10 text-chart-5"
        }`}
      >
        {isSync ? <Download className="size-4" /> : <Brain className="size-4" />}
      </div>

      <div className="flex-1 min-w-0 space-y-1.5">
        {/* Header row */}
        <div className="flex items-center gap-2 flex-wrap">
          <span className="text-sm font-medium text-foreground">
            {isSync ? "元数据同步" : "学习分析"}
          </span>
          <span className="text-xs text-muted-foreground">
            {isSync
              ? (d as SyncLog).sync_type === "auto"
                ? "自动"
                : "手动"
              : (d as LearningLog).trigger_type === "auto"
                ? "自动"
                : "手动"}
          </span>
          <StatusBadge status={d.status} />
          <span className="text-xs text-muted-foreground ml-auto">
            {timeAgo(d.started_at)}
          </span>
        </div>

        {/* Time range */}
        <div className="text-[11px] text-muted-foreground/70 font-mono">
          {formatTime(d.started_at)}
          {d.finished_at ? ` → ${formatTime(d.finished_at)}` : ""}
        </div>

        {/* Stats — sync */}
        {isSync && d.status === "completed" && (
          <div className="flex gap-3 text-xs text-muted-foreground">
            {(d as SyncLog).tables_added != null && (
              <span className="text-success">+{(d as SyncLog).tables_added} 表</span>
            )}
            {(d as SyncLog).tables_removed != null &&
              (d as SyncLog).tables_removed! > 0 && (
                <span className="text-destructive">
                  -{(d as SyncLog).tables_removed} 表
                </span>
              )}
            {(d as SyncLog).columns_changed != null && (
              <span>{Math.abs((d as SyncLog).columns_changed!)} 列变更</span>
            )}
          </div>
        )}

        {/* Stats — learn */}
        {!isSync && d.status === "completed" && (
          <div className="flex gap-3 text-xs text-muted-foreground flex-wrap">
            {(d as LearningLog).l0_count != null && (
              <span title="L0: 字段描述 (向量检索)">
                <span className="font-mono text-primary">L0</span>{" "}
                {(d as LearningLog).l0_count}
              </span>
            )}
            {(d as LearningLog).l1_count != null && (
              <span title="L1: 值映射/别名 (统计)">
                <span className="font-mono text-warning">L1</span>{" "}
                {(d as LearningLog).l1_count}
              </span>
            )}
            {(d as LearningLog).l2_count != null && (
              <span title="L2: FK推断 (值重合度+LLM)">
                <span className="font-mono text-chart-5">L2</span>{" "}
                {(d as LearningLog).l2_count}
              </span>
            )}
            {(d as LearningLog).fk_inferred != null &&
              (d as LearningLog).fk_inferred! > 0 && (
                <span className="text-muted-foreground/60">
                  FK {(d as LearningLog).fk_inferred}
                </span>
              )}
            {(d as LearningLog).l2_llm_calls != null &&
              (d as LearningLog).l2_llm_calls! > 0 && (
                <span className="text-muted-foreground/60">
                  {(d as LearningLog).l2_llm_calls} LLM 调用
                </span>
              )}
          </div>
        )}

        {/* Error */}
        {d.status === "failed" ? (
          <div className="text-xs bg-destructive/5 border border-destructive/20 rounded-md px-3 py-2 space-y-1">
            <span className="inline-flex items-center gap-1 text-[10px] font-medium text-destructive/80 uppercase tracking-wider">
              任务失败
            </span>
            <div className="text-destructive font-mono break-all leading-relaxed">
              {d.error_message || "(无详细错误信息 — 请查看后端日志)"}
            </div>
          </div>
        ) : null}
      </div>
    </div>
  );
}
