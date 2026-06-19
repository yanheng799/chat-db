"use client";

import { type DataSource } from "@/stores/datasources";

const ENGINE_LABELS: Record<string, string> = {
  postgresql: "PostgreSQL",
  mysql: "MySQL",
};

interface DataSourceCardProps {
  ds: DataSource;
  onEdit: (ds: DataSource) => void;
  onTest: (ds: DataSource) => void;
  onToggleActive: (ds: DataSource) => void;
  onDelete: (ds: DataSource) => void;
  onViewDetail: (ds: DataSource) => void;
  onSync: (ds: DataSource) => void;
  onLearn: (ds: DataSource) => void;
  testing: boolean;
  syncing: boolean;
  learning: boolean;
}

export function DataSourceCard({
  ds,
  onEdit,
  onTest,
  onToggleActive,
  onDelete,
  onViewDetail,
  onSync,
  onLearn,
  testing,
  syncing,
  learning,
}: DataSourceCardProps) {
  const engineLabel = ENGINE_LABELS[ds.engine] || ds.engine;

  return (
    <div className="bg-card border border-border rounded-xl overflow-hidden hover:border-primary/30 transition-colors">
      {/* Top row: engine + name + status */}
      <div className="px-4 py-3.5 flex items-center gap-3 border-b border-border/50">
        {/* Engine icon */}
        <span className="text-xs font-mono font-bold uppercase px-2 py-0.5 rounded bg-primary/10 text-primary">
          {ds.engine === "postgresql" ? "PG" : ds.engine === "mysql" ? "MY" : ds.engine.slice(0, 2).toUpperCase()}
        </span>
        <div className="flex-1 min-w-0">
          <h3 className="text-sm font-semibold text-foreground truncate">
            {ds.name}
          </h3>
          <p className="text-xs text-muted-foreground truncate">
            {engineLabel} · {ds.host}:{ds.port}/{ds.database}
          </p>
        </div>
        {/* Active / inactive indicator */}
        <span
          className={`inline-flex items-center gap-1.5 text-xs font-medium ${
            ds.is_active ? "text-green-400" : "text-muted-foreground"
          }`}
        >
          <span
            className={`w-2 h-2 rounded-full ${
              ds.is_active ? "bg-green-500" : "bg-muted-foreground/40"
            }`}
          />
          {ds.is_active ? "已激活" : "未激活"}
        </span>
      </div>

      {/* Action buttons */}
      <div className="px-4 py-2.5 flex items-center gap-2 flex-wrap">
        <button
          onClick={() => onViewDetail(ds)}
          className="text-xs text-muted-foreground hover:text-foreground transition-colors px-2 py-1 rounded"
        >
          详情
        </button>
        <button
          onClick={() => onEdit(ds)}
          className="text-xs text-muted-foreground hover:text-foreground transition-colors px-2 py-1 rounded"
        >
          编辑
        </button>
        <button
          onClick={() => onTest(ds)}
          disabled={testing}
          className="text-xs text-muted-foreground hover:text-foreground transition-colors px-2 py-1 rounded disabled:opacity-50"
        >
          {testing ? "测试中…" : "测试连接"}
        </button>
        {/* Sync / Learn — only for active datasources */}
        {ds.is_active && (
          <>
            <button
              onClick={() => onSync(ds)}
              disabled={syncing}
              className="text-xs text-blue-400 hover:text-blue-300 transition-colors px-2 py-1 rounded disabled:opacity-50"
            >
              {syncing ? "同步中…" : "同步"}
            </button>
            <button
              onClick={() => onLearn(ds)}
              disabled={learning}
              className="text-xs text-purple-400 hover:text-purple-300 transition-colors px-2 py-1 rounded disabled:opacity-50"
            >
              {learning ? "学习中…" : "学习"}
            </button>
          </>
        )}
        <button
          onClick={() => onToggleActive(ds)}
          className={`text-xs transition-colors px-2 py-1 rounded ${
            ds.is_active
              ? "text-amber-400 hover:text-amber-300"
              : "text-green-400 hover:text-green-300"
          }`}
        >
          {ds.is_active ? "停用" : "激活"}
        </button>
        <button
          onClick={() => onDelete(ds)}
          className="text-xs text-red-400 hover:text-red-300 transition-colors px-2 py-1 rounded ml-auto"
        >
          删除
        </button>
      </div>
    </div>
  );
}
