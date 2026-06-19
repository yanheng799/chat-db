"use client";

import { useEffect, useState, useCallback } from "react";
import { useParams, useRouter } from "next/navigation";
import { useDataSourceStore, type SyncLog, type LearningLog, type DataSource } from "@/stores/datasources";
import { useToastStore } from "@/stores/toast";

// ── Merged timeline entry ───────────────────────────

type TimelineEntry =
  | { kind: "sync"; data: SyncLog }
  | { kind: "learn"; data: LearningLog };

export default function DatasourceDetailPage() {
  const { id } = useParams<{ id: string }>();
  const router = useRouter();
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
      setDs(dsData);
      setTableCount(meta.table_count);
      setColumnCount(meta.column_count);

      // Merge into unified timeline, newest first
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
    const hasRunning = timeline.some(
      (e) => e.data.status === "running",
    );
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
      return "🌐 网络错误：无法连接后端服务 (localhost:8000)";
    if (msg.startsWith("[后端]")) return `🖥 ${msg}`;
    if (msg.includes("HTTP 5")) return `🖥 后端错误: ${msg}`;
    return `⚠ ${msg}`;
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
    } catch (e: unknown) {
      showToast("error", classifyError(e));
    } finally {
      setRefreshingKb(false);
    }
  };

  // ── Helpers ───────────────────────────────────────
  const statusBadge = (status: string) => {
    const map: Record<string, { label: string; cls: string }> = {
      running: { label: "运行中", cls: "bg-primary/15 text-primary border-primary/30" },
      completed: { label: "完成", cls: "bg-green-500/10 text-green-400 border-green-500/30" },
      failed: { label: "失败", cls: "bg-red-500/10 text-red-400 border-red-500/30" },
    };
    const s = map[status] || { label: status, cls: "bg-muted text-muted-foreground border-border" };
    return (
      <span className={`inline-flex items-center gap-1 px-2 py-0.5 rounded text-[11px] font-medium border ${s.cls}`}>
        {status === "running" && <span className="w-1.5 h-1.5 rounded-full bg-primary animate-pulse" />}
        {s.label}
      </span>
    );
  };

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
  const l2Count = timeline
    .filter((e) => e.kind === "learn" && e.data.status === "completed")
    .reduce((sum, e) => sum + ((e.data as LearningLog).l2_count || 0), 0);

  // ── Loading skeleton ──────────────────────────────
  if (loading) {
    return (
      <div className="flex-1 overflow-y-auto px-7 py-6">
        <div className="animate-pulse space-y-4">
          <div className="h-6 w-48 bg-secondary rounded" />
          <div className="flex gap-4">
            <div className="h-20 w-40 bg-secondary rounded-xl" />
            <div className="h-20 w-40 bg-secondary rounded-xl" />
            <div className="h-20 w-40 bg-secondary rounded-xl" />
          </div>
          <div className="h-64 bg-secondary rounded-xl" />
        </div>
      </div>
    );
  }

  return (
    <div className="flex-1 overflow-y-auto">
      {/* ── Top bar ────────────────────────────────── */}
      <div className="px-7 py-5 border-b border-border flex items-center gap-4 flex-wrap">
        <button
          onClick={() => router.push("/datasources")}
          className="text-xs text-muted-foreground hover:text-foreground transition-colors"
        >
          ← 返回
        </button>
        <div className="flex-1 min-w-0">
          <h2 className="text-base font-semibold text-foreground truncate">
            {ds?.name || "数据源详情"}
          </h2>
          <p className="text-xs text-muted-foreground">
            {ds?.engine?.toUpperCase()} · {ds?.host}:{ds?.port}/{ds?.database}
          </p>
        </div>
        <div className="flex gap-2">
          <button
            onClick={handleSync}
            disabled={syncing}
            className="px-4 py-2 rounded-lg text-sm font-medium bg-blue-500/15 text-blue-400 border border-blue-500/30 hover:bg-blue-500/25 transition-colors disabled:opacity-50"
          >
            {syncing ? "同步中…" : "同步元数据"}
          </button>
          <button
            onClick={handleLearn}
            disabled={learning}
            className="px-4 py-2 rounded-lg text-sm font-medium bg-purple-500/15 text-purple-400 border border-purple-500/30 hover:bg-purple-500/25 transition-colors disabled:opacity-50"
          >
            {learning ? "学习中…" : "学习分析"}
          </button>
          <button
            onClick={handleRefreshKb}
            disabled={refreshingKb}
            className="px-4 py-2 rounded-lg text-sm font-medium bg-emerald-500/15 text-emerald-400 border border-emerald-500/30 hover:bg-emerald-500/25 transition-colors disabled:opacity-50"
          >
            {refreshingKb ? "刷新中…" : "刷新知识库"}
          </button>
        </div>
      </div>

      <div className="px-7 py-6 space-y-8">
        {/* ── Stats cards ──────────────────────────── */}
        <div className="grid grid-cols-3 gap-4">
          <StatCard
            label="表"
            value={tableCount}
            sub="从数据库提取"
            accent="border-l-primary"
          />
          <StatCard
            label="列 / 字段"
            value={columnCount}
            sub="含类型与主键"
            accent="border-l-blue-500"
          />
          <StatCard
            label="推断外键 (L2)"
            value={l2Count}
            sub="值重合度推断"
            accent="border-l-purple-500"
          />
        </div>

        {/* ── Timeline ─────────────────────────────── */}
        <section>
          <div className="flex items-center gap-2 mb-4">
            <h3 className="text-sm font-semibold text-foreground">运行历史</h3>
            <span className="text-xs text-muted-foreground">
              {timeline.length} 条记录
            </span>
          </div>

          {timeline.length === 0 ? (
            <div className="text-center py-16 text-sm text-muted-foreground bg-card border border-border rounded-xl">
              <p className="mb-2">暂无运行记录</p>
              <p className="text-xs text-muted-foreground/60">
                点击上方「同步元数据」开始首次扫描
              </p>
            </div>
          ) : (
            <div className="bg-card border border-border rounded-xl overflow-hidden">
              {timeline.map((entry, i) => (
                <TimelineRow
                  key={entry.data.id}
                  entry={entry}
                  isLast={i === timeline.length - 1}
                  statusBadge={statusBadge}
                  timeAgo={timeAgo}
                  formatTime={formatTime}
                />
              ))}
            </div>
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
  accent,
}: {
  label: string;
  value: number | null;
  sub: string;
  accent: string;
}) {
  return (
    <div
      className={`bg-card border border-border rounded-xl px-5 py-4 border-l-2 ${accent}`}
    >
      <div className="text-xs text-muted-foreground mb-1">{label}</div>
      <div className="text-2xl font-bold text-foreground tabular-nums">
        {value === null ? "—" : value.toLocaleString()}
      </div>
      <div className="text-[11px] text-muted-foreground mt-0.5">{sub}</div>
    </div>
  );
}

// ── Timeline row ────────────────────────────────────

function TimelineRow({
  entry,
  isLast,
  statusBadge,
  timeAgo,
  formatTime,
}: {
  entry: TimelineEntry;
  isLast: boolean;
  statusBadge: (s: string) => React.ReactNode;
  timeAgo: (iso: string) => string;
  formatTime: (iso: string | null) => string;
}) {
  const isSync = entry.kind === "sync";
  const d = entry.data;

  const barColor =
    d.status === "completed"
      ? "bg-green-500"
      : d.status === "failed"
        ? "bg-red-500"
        : "bg-primary";

  return (
    <div
      className={`flex gap-4 px-5 py-4 ${
        !isLast ? "border-b border-border/60" : ""
      } ${d.status === "running" ? "bg-primary/[0.02]" : ""}`}
    >
      {/* Left: timeline bar + icon */}
      <div className="flex flex-col items-center">
        <div
          className={`w-8 h-8 rounded-full flex items-center justify-center text-sm shrink-0 ${
            isSync
              ? "bg-blue-500/10 text-blue-400"
              : "bg-purple-500/10 text-purple-400"
          }`}
        >
          {isSync ? "⬇" : "🧠"}
        </div>
        {!isLast && <div className={`w-0.5 flex-1 min-h-[16px] mt-1 ${barColor}/30`} />}
      </div>

      {/* Right: content */}
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
          {statusBadge(d.status)}
          <span className="text-xs text-muted-foreground ml-auto">
            {timeAgo(d.started_at)}
          </span>
        </div>

        {/* Time range */}
        <div className="text-[11px] text-muted-foreground/60 font-mono">
          {formatTime(d.started_at)}
          {d.finished_at && ` → ${formatTime(d.finished_at)}`}
        </div>

        {/* Stats — sync */}
        {isSync && d.status === "completed" && (
          <div className="flex gap-3 text-xs text-muted-foreground">
            {(d as SyncLog).tables_added != null && (
              <span className="text-green-400">
                +{(d as SyncLog).tables_added} 表
              </span>
            )}
            {(d as SyncLog).tables_removed != null &&
              (d as SyncLog).tables_removed! > 0 && (
                <span className="text-red-400">
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
                <span className="text-blue-400 font-mono">L0</span>{" "}
                {(d as LearningLog).l0_count}
              </span>
            )}
            {(d as LearningLog).l1_count != null && (
              <span title="L1: 值映射/别名 (统计)">
                <span className="text-amber-400 font-mono">L1</span>{" "}
                {(d as LearningLog).l1_count}
              </span>
            )}
            {(d as LearningLog).l2_count != null && (
              <span title="L2: FK推断 (值重合度+LLM)">
                <span className="text-purple-400 font-mono">L2</span>{" "}
                {(d as LearningLog).l2_count}
              </span>
            )}
            {(d as LearningLog).l2_llm_calls != null &&
              (d as LearningLog).l2_llm_calls! > 0 && (
                <span className="text-muted-foreground/50">
                  {(d as LearningLog).l2_llm_calls} LLM 调用
                </span>
              )}
          </div>
        )}

        {/* Error */}
        {d.status === "failed" && (
          <div className="text-xs bg-red-500/5 border border-red-500/20 rounded-lg px-3 py-2.5 space-y-1.5">
            <span className="inline-flex items-center gap-1 text-[10px] font-medium text-red-400/70 uppercase tracking-wider">
              {d.error_message?.startsWith("[后端]") ? "🖥 后端错误" : "⚠ 任务失败"}
            </span>
            <div className="text-red-400 font-mono break-all leading-relaxed">
              {d.error_message || "(无详细错误信息 — 请查看后端日志)"}
            </div>
          </div>
        )}
      </div>
    </div>
  );
}
