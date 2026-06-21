"use client";

import Link from "next/link";
import {
  MoreHorizontal,
  Pencil,
  Plug,
  Download,
  Brain,
  Trash2,
} from "lucide-react";
import { Card, Badge, Switch, Menu, Spinner } from "@/components/ui";
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
  onSync,
  onLearn,
  testing,
  syncing,
  learning,
}: DataSourceCardProps) {
  const engineLabel = ENGINE_LABELS[ds.engine] || ds.engine;
  const engineAbbr =
    ds.engine === "postgresql"
      ? "PG"
      : ds.engine === "mysql"
        ? "MY"
        : ds.engine.slice(0, 2).toUpperCase();

  return (
    <Card className="p-0 overflow-hidden transition-colors hover:border-primary/40">
      {/* Identity row → detail page */}
      <Link
        href={`/datasources/${ds.id}`}
        className="flex items-center gap-3 px-4 py-3 transition-colors hover:bg-secondary/40"
      >
        <Badge variant="secondary" className="font-mono font-bold shrink-0">
          {engineAbbr}
        </Badge>
        <div className="flex-1 min-w-0">
          <div className="flex items-center gap-2">
            <h3 className="text-sm font-semibold text-foreground truncate">{ds.name}</h3>
            {ds.is_active ? (
              <Badge variant="success" className="shrink-0">
                已激活
              </Badge>
            ) : null}
          </div>
          <p className="text-xs text-muted-foreground truncate">
            {engineLabel} · {ds.host}:{ds.port}/{ds.database}
          </p>
        </div>
      </Link>

      {/* Footer: active toggle + detail link + overflow menu */}
      <div className="flex items-center gap-2 px-4 py-2 border-t border-border bg-secondary/20">
        <span className="text-xs text-muted-foreground mr-1">
          {ds.is_active ? "启用" : "停用"}
        </span>
        <Switch
          checked={ds.is_active}
          onCheckedChange={() => onToggleActive(ds)}
          aria-label={ds.is_active ? "停用数据源" : "激活数据源"}
        />
        <div className="flex-1" />
        <Link
          href={`/datasources/${ds.id}`}
          className="text-xs text-muted-foreground hover:text-foreground transition-colors px-2 h-7 inline-flex items-center rounded"
        >
          详情
        </Link>
        <Menu.Root>
          <Menu.Trigger aria-label="更多操作" className="size-7">
            <MoreHorizontal className="size-4" />
          </Menu.Trigger>
          <Menu.Content>
            <Menu.Item onClick={() => onEdit(ds)}>
              <Pencil className="size-3.5" />
              编辑
            </Menu.Item>
            <Menu.Item onClick={() => onTest(ds)}>
              {testing ? <Spinner className="size-3.5" /> : <Plug className="size-3.5" />}
              {testing ? "测试中…" : "测试连接"}
            </Menu.Item>
            <Menu.Item onClick={() => onSync(ds)} disabled={!ds.is_active || syncing}>
              {syncing ? <Spinner className="size-3.5" /> : <Download className="size-3.5" />}
              {syncing ? "同步中…" : "同步元数据"}
            </Menu.Item>
            <Menu.Item onClick={() => onLearn(ds)} disabled={!ds.is_active || learning}>
              {learning ? <Spinner className="size-3.5" /> : <Brain className="size-3.5" />}
              {learning ? "学习中…" : "学习分析"}
            </Menu.Item>
            <Menu.Separator />
            <Menu.Item variant="destructive" onClick={() => onDelete(ds)}>
              <Trash2 className="size-3.5" />
              删除
            </Menu.Item>
          </Menu.Content>
        </Menu.Root>
      </div>
    </Card>
  );
}
