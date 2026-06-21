"use client";

import type { Message } from "@/stores/chat";
import { DataTable } from "@/components/ui";
import { SqlBlock } from "@/components/shared/SqlBlock";
import { TriangleAlert } from "lucide-react";

export function ResultView({ message }: { message: Message }) {
  const columns = message.columns ?? [];
  const rows = message.rows ?? [];
  const notes = message.confirmItems ?? [];

  return (
    <div className="space-y-4">
      <div className="flex items-center gap-3">
        <span className="text-xs text-muted-foreground tabular-nums">
          {columns.length} 列 × {rows.length} 行
        </span>
      </div>

      {message.sql ? <SqlBlock sql={message.sql} /> : null}

      <DataTable columns={columns} rows={rows} />

      {message.summary ? (
        <p className="text-sm text-muted-foreground">{message.summary}</p>
      ) : null}

      {notes.length > 0 ? (
        <div className="rounded-lg border border-warning/30 bg-warning/5 p-3 space-y-1.5">
          <div className="flex items-center gap-1.5 text-xs font-medium text-warning">
            <TriangleAlert className="size-3.5" />
            注意事项
          </div>
          <ul className="text-xs text-muted-foreground space-y-1">
            {notes.map((item, i) => (
              <li key={i}>
                {item.field ? <span className="font-mono text-foreground">{item.field}</span> : null}
                {item.field && item.reason ? " — " : null}
                {item.reason ? <span>{item.reason}</span> : null}
                {item.value ? <span>（查询值：{item.value}）</span> : null}
              </li>
            ))}
          </ul>
        </div>
      ) : null}
    </div>
  );
}
