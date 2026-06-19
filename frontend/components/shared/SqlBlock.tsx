"use client";

import { useState, useCallback } from "react";

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
    <div className="bg-secondary/50 border border-border rounded-xl overflow-hidden">
      {/* Header bar */}
      <div className="flex items-center gap-2 px-3 py-2 border-b border-border">
        <span className="text-xs font-semibold text-green-400 uppercase tracking-wider">
          SQL
        </span>
        <div className="ml-auto flex items-center gap-1">
          <button
            onClick={handleCopy}
            className="text-xs text-muted-foreground hover:text-foreground transition-colors px-1.5 py-0.5 rounded"
            aria-label="复制 SQL"
          >
            {copied ? "已复制" : "复制"}
          </button>
          <button
            onClick={() => setCollapsed((c) => !c)}
            className="text-xs text-muted-foreground hover:text-foreground transition-colors px-1.5 py-0.5 rounded"
            aria-label={collapsed ? "展开 SQL" : "折叠 SQL"}
          >
            {collapsed ? "展开 ▸" : "折叠 ▾"}
          </button>
        </div>
      </div>
      {/* Code body */}
      {!collapsed && (
        <pre className="px-3 py-2.5 text-xs font-mono text-green-300 overflow-x-auto whitespace-pre-wrap break-all max-h-[240px] overflow-y-auto">
          <code>{sql}</code>
        </pre>
      )}
    </div>
  );
}
