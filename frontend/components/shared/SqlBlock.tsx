"use client";

import { useState, useCallback } from "react";
import { Check, Copy } from "lucide-react";

interface SqlBlockProps {
  sql: string;
}

export function SqlBlock({ sql }: SqlBlockProps) {
  const [collapsed, setCollapsed] = useState(false);
  const [copied, setCopied] = useState(false);

  const handleCopy = useCallback(async () => {
    try {
      await navigator.clipboard.writeText(sql);
      setCopied(true);
      setTimeout(() => setCopied(false), 2000);
    } catch {
      // clipboard API not available — silently ignore
    }
  }, [sql]);

  return (
    <div className="rounded-lg border border-border bg-secondary/40 overflow-hidden">
      {/* Header bar */}
      <div className="flex items-center gap-2 px-3 h-8 border-b border-border">
        <span className="text-[11px] font-semibold text-muted-foreground uppercase tracking-wider">
          SQL
        </span>
        <div className="ml-auto flex items-center gap-1">
          <button
            onClick={handleCopy}
            className="inline-flex items-center gap-1 text-xs text-muted-foreground hover:text-foreground transition-colors px-1.5 h-6 rounded"
            aria-label="复制 SQL"
          >
            {copied ? <Check className="size-3.5 text-success" /> : <Copy className="size-3.5" />}
            {copied ? "已复制" : "复制"}
          </button>
          <button
            onClick={() => setCollapsed((c) => !c)}
            className="text-xs text-muted-foreground hover:text-foreground transition-colors px-1.5 h-6 rounded"
            aria-label={collapsed ? "展开 SQL" : "折叠 SQL"}
          >
            {collapsed ? "展开 ▸" : "折叠 ▾"}
          </button>
        </div>
      </div>
      {/* Code body */}
      {!collapsed && (
        <pre className="px-3 py-2.5 text-xs font-mono text-foreground overflow-x-auto whitespace-pre-wrap break-all max-h-[240px] overflow-y-auto">
          <code>{sql}</code>
        </pre>
      )}
    </div>
  );
}
