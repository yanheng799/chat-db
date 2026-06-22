"use client";

import { useRef, useEffect, useCallback } from "react";
import { Play, Square } from "lucide-react";
import { Textarea, Button } from "@/components/ui";
import { useChatStore } from "@/stores/chat";
import { useQuerySSE } from "@/hooks/useQuerySSE";

export function QueryBar() {
  const ref = useRef<HTMLTextAreaElement>(null);
  const queryState = useChatStore((s) => s.queryState);
  const sessionId = useChatStore((s) => s.sessionId);
  const createSession = useChatStore((s) => s.createSession);
  const { sendQuery, cancelQuery } = useQuerySSE();
  const isRunning = queryState === "running";

  // ⌘K / Ctrl+K focuses the query bar globally
  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      if ((e.metaKey || e.ctrlKey) && e.key.toLowerCase() === "k") {
        e.preventDefault();
        ref.current?.focus();
        ref.current?.select();
      }
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, []);

  const pending = useRef(false);

  const submit = useCallback(() => {
    const text = ref.current?.value.trim();
    if (!text || isRunning || pending.current) return;
    if (!sessionId) {
      pending.current = true;
      createSession()
        .then(() => sendQuery(text))
        .finally(() => { pending.current = false; });
    } else {
      sendQuery(text);
    }
    if (ref.current) {
      ref.current.value = "";
      ref.current.style.height = "auto";
    }
  }, [isRunning, sessionId, createSession, sendQuery]);

  const onKeyDown = (e: React.KeyboardEvent<HTMLTextAreaElement>) => {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      submit();
    }
  };

  return (
    <div className="shrink-0 border-t border-border bg-background">
      <div className="flex items-end gap-2 max-w-5xl mx-auto px-6 py-3">
        <span aria-hidden="true" className="text-muted-foreground font-mono pb-2.5 select-none">
          ❯
        </span>
        <Textarea
          ref={ref}
          autosize
          maxRows={5}
          aria-label="自然语言查询输入"
          onKeyDown={onKeyDown}
          placeholder="输入查询，例如「昨天的订单总数」…   (Enter 运行)"
          className="flex-1 min-w-0 bg-background"
        />
        {isRunning ? (
          <Button variant="outline" onClick={cancelQuery} className="shrink-0">
            <Square className="size-4" />
            取消
          </Button>
        ) : (
          <Button onClick={submit} className="shrink-0">
            <Play className="size-4" />
            运行
          </Button>
        )}
      </div>
    </div>
  );
}
