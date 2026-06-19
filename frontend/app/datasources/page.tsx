"use client";

import { useEffect, useState, useCallback } from "react";
import { useRouter } from "next/navigation";
import { useDataSourceStore, type DataSource } from "@/stores/datasources";
import { useToastStore } from "@/stores/toast";
import { DataSourceCard } from "@/components/datasources/DataSourceCard";
import { DataSourceForm } from "@/components/datasources/DataSourceForm";
import { ConfirmDialog } from "@/components/shared/ConfirmDialog";

function classifyError(e: unknown, action: string): string {
  if (!(e instanceof Error)) return String(e);
  const msg = e.message;
  if (msg.includes("409")) return `${action}任务已在运行中`;
  if (msg.includes("Failed to fetch") || msg.includes("NetworkError"))
    return `🌐 网络错误：无法连接后端 (localhost:8000)`;
  if (msg.startsWith("[后端]")) return `🖥 ${msg}`;
  if (msg.includes("HTTP 5")) return `🖥 后端错误 (${msg})`;
  return `⚠ ${msg}`;
}

export default function DatasourcesPage() {
  const router = useRouter();
  const {
    dataSources,
    loading,
    error,
    loadDataSources,
    createDataSource,
    updateDataSource,
    deleteDataSource,
    testConnection,
    activate,
    deactivate,
    syncMetadata,
    learnMetadata,
  } = useDataSourceStore();
  const showToast = useToastStore((s) => s.showToast);

  // ── UI state ──────────────────────────────────────
  const [formOpen, setFormOpen] = useState(false);
  const [editTarget, setEditTarget] = useState<DataSource | null>(null);
  const [deleteTarget, setDeleteTarget] = useState<DataSource | null>(null);
  const [syncingId, setSyncingId] = useState<string | null>(null);
  const [learningId, setLearningId] = useState<string | null>(null);
  const [testingId, setTestingId] = useState<string | null>(null);

  // ── Load on mount ─────────────────────────────────
  useEffect(() => {
    loadDataSources();
  }, [loadDataSources]);

  // ── Handlers ──────────────────────────────────────
  const handleCreate = useCallback(() => {
    setEditTarget(null);
    setFormOpen(true);
  }, []);

  const handleEdit = useCallback((ds: DataSource) => {
    setEditTarget(ds);
    setFormOpen(true);
  }, []);

  const handleSave = useCallback(
    async (data: Record<string, unknown>) => {
      if (editTarget) {
        await updateDataSource(editTarget.id, data);
        showToast("success", "数据源已更新");
      } else {
        await createDataSource(data);
        showToast("success", "数据源已创建");
      }
      await loadDataSources();
    },
    [editTarget, createDataSource, updateDataSource, loadDataSources, showToast],
  );

  const handleTest = useCallback(
    async (ds: DataSource) => {
      setTestingId(ds.id);
      try {
        const result = await testConnection(ds.id);
        if (result.success) {
          showToast("success", "连接成功");
        } else {
          showToast("error", result.message || "连接失败");
        }
      } catch (e: unknown) {
        showToast("error", (e as Error).message || "连接失败");
      } finally {
        setTestingId(null);
      }
    },
    [testConnection, showToast],
  );

  const handleToggleActive = useCallback(
    async (ds: DataSource) => {
      try {
        if (ds.is_active) {
          await deactivate(ds.id);
          showToast("info", "已停用");
        } else {
          await activate(ds.id);
          showToast("success", "已激活");
        }
        await loadDataSources();
      } catch (e: unknown) {
        showToast("error", (e as Error).message || "操作失败");
      }
    },
    [activate, deactivate, loadDataSources, showToast],
  );

  const handleDelete = useCallback(
    async (ds: DataSource) => {
      setDeleteTarget(ds);
    },
    [],
  );

  const confirmDelete = useCallback(async () => {
    if (!deleteTarget) return;
    try {
      await deleteDataSource(deleteTarget.id);
      showToast("success", "数据源已删除");
    } catch (e: unknown) {
      showToast("error", (e as Error).message || "删除失败");
    }
    setDeleteTarget(null);
  }, [deleteTarget, deleteDataSource, showToast]);

  const handleViewDetail = useCallback(
    (ds: DataSource) => {
      router.push(`/datasources/${ds.id}`);
    },
    [router],
  );

  const handleSync = useCallback(
    async (ds: DataSource) => {
      setSyncingId(ds.id);
      try {
        const result = await syncMetadata(ds.id);
        showToast("success", `同步已启动: ${result.message}`);
      } catch (e: unknown) {
        showToast("error", classifyError(e, "同步"));
      } finally {
        setSyncingId(null);
      }
    },
    [syncMetadata, showToast],
  );

  const handleLearn = useCallback(
    async (ds: DataSource) => {
      setLearningId(ds.id);
      try {
        const result = await learnMetadata(ds.id);
        showToast("success", `学习已启动: ${result.message}`);
      } catch (e: unknown) {
        showToast("error", classifyError(e, "学习"));
      } finally {
        setLearningId(null);
      }
    },
    [learnMetadata, showToast],
  );

  // ── Render ────────────────────────────────────────
  return (
    <div className="flex-1 overflow-y-auto">
      <div className="px-7 py-6">
        {/* Header */}
        <div className="flex items-center justify-between mb-6">
          <div>
            <h2 className="text-lg font-semibold text-foreground">数据源管理</h2>
            <p className="text-xs text-muted-foreground mt-0.5">
              {dataSources.length} 个数据源
            </p>
          </div>
          <button
            onClick={handleCreate}
            className="px-4 py-2 bg-primary text-primary-foreground rounded-lg text-sm font-semibold transition-all hover:brightness-110"
          >
            + 新建数据源
          </button>
        </div>

        {/* Content */}
        {loading ? (
          <div className="text-center text-muted-foreground text-sm py-16">
            加载中…
          </div>
        ) : error ? (
          <div className="text-center text-red-400 text-sm py-16">
            加载失败: {error}
            <button
              onClick={loadDataSources}
              className="ml-3 underline hover:text-red-300"
            >
              重试
            </button>
          </div>
        ) : dataSources.length === 0 ? (
          <div className="text-center text-muted-foreground text-sm py-16">
            暂无数据源配置，点击上方按钮新建
          </div>
        ) : (
          <div className="grid gap-4 sm:grid-cols-1 lg:grid-cols-2">
            {dataSources.map((ds) => (
              <DataSourceCard
                key={ds.id}
                ds={ds}
                onEdit={handleEdit}
                onTest={handleTest}
                onToggleActive={handleToggleActive}
                onDelete={handleDelete}
                onViewDetail={handleViewDetail}
                onSync={handleSync}
                onLearn={handleLearn}
                testing={testingId === ds.id}
                syncing={syncingId === ds.id}
                learning={learningId === ds.id}
              />
            ))}
          </div>
        )}
      </div>

      {/* Slide-over form */}
      <DataSourceForm
        open={formOpen}
        initial={
          editTarget
            ? {
                name: editTarget.name,
                engine: editTarget.engine,
                host: editTarget.host,
                port: editTarget.port,
                username: editTarget.username,
                database: editTarget.database,
                schema_whitelist: editTarget.schema_whitelist,
              }
            : null
        }
        onSave={handleSave}
        onClose={() => {
          setFormOpen(false);
          setEditTarget(null);
        }}
      />

      {/* Delete confirmation */}
      <ConfirmDialog
        open={!!deleteTarget}
        title="删除数据源"
        message={`确定要删除「${deleteTarget?.name}」吗？此操作不可撤销。`}
        confirmLabel="删除"
        variant="destructive"
        onConfirm={confirmDelete}
        onCancel={() => setDeleteTarget(null)}
      />
    </div>
  );
}
