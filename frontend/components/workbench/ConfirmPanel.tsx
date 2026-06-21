"use client";

import type { Message } from "@/stores/chat";
import { Button, Card } from "@/components/ui";
import { SqlBlock } from "@/components/shared/SqlBlock";
import { TriangleAlert } from "lucide-react";

interface ConfirmPanelProps {
  message: Message;
  onConfirm: (id: string) => void;
  onCancel: (id: string) => void;
}

export function ConfirmPanel({ message, onConfirm, onCancel }: ConfirmPanelProps) {
  const items = message.confirmItems ?? [];

  return (
    <Card className="p-0 overflow-hidden border-warning/40 max-w-2xl">
      <div className="flex items-start gap-2.5 p-4 bg-warning/5 border-b border-warning/30">
        <TriangleAlert className="size-5 text-warning shrink-0 mt-0.5" />
        <div>
          <p className="text-sm font-semibold text-foreground">需要确认以下查询条件</p>
          <p className="text-xs text-muted-foreground mt-0.5">
            系统对部分术语有歧义，请确认后继续
          </p>
        </div>
      </div>
      <div className="p-4 space-y-3">
        {message.sql ? <SqlBlock sql={message.sql} /> : null}
        <div className="space-y-2">
          {items.map((item, i) => (
            <div
              key={i}
              className="rounded-md border border-border bg-secondary/40 p-2.5 text-xs space-y-0.5"
            >
              {item.field ? (
                <div>
                  <span className="text-muted-foreground">字段 </span>
                  <span className="font-mono font-medium text-foreground">{item.field}</span>
                </div>
              ) : null}
              {item.reason ? (
                <div>
                  <span className="text-muted-foreground">原因 </span>
                  <span className="text-foreground">{item.reason}</span>
                </div>
              ) : null}
              {item.value ? (
                <div>
                  <span className="text-muted-foreground">查询值 </span>
                  <span className="text-foreground">{item.value}</span>
                </div>
              ) : null}
            </div>
          ))}
        </div>
        <div className="flex gap-2 justify-end">
          <Button variant="outline" onClick={() => onCancel(message.id)}>
            取消
          </Button>
          <Button onClick={() => onConfirm(message.id)}>确认</Button>
        </div>
      </div>
    </Card>
  );
}
