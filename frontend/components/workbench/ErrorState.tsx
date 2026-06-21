"use client";

import { CircleAlert } from "lucide-react";

export function ErrorState({ detail }: { detail: string }) {
  return (
    <div className="rounded-lg border border-destructive/30 bg-destructive/5 p-4 flex gap-2.5">
      <CircleAlert className="size-5 text-destructive shrink-0 mt-0.5" />
      <div className="min-w-0">
        <p className="text-sm font-medium text-destructive">查询失败</p>
        <p className="text-xs text-destructive/80 font-mono break-all mt-1 leading-relaxed">
          {detail || "未知错误，请查看后端日志"}
        </p>
      </div>
    </div>
  );
}
