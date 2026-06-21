"use client";
/* eslint-disable react-hooks/set-state-in-effect -- intentional: follow the latest result while a query is running */

import { useEffect, useState, useCallback, useMemo } from "react";
import { useChatStore } from "@/stores/chat";
import { useQuerySSE } from "@/hooks/useQuerySSE";
import { QueryBar } from "./QueryBar";
import { TraceStrip } from "./TraceStrip";
import { HistoryRail } from "./HistoryRail";
import { ResultCanvas } from "./ResultCanvas";
import { EmptyWorkbench } from "./EmptyWorkbench";

export function Workbench() {
  const messages = useChatStore((s) => s.messages);
  const queryState = useChatStore((s) => s.queryState);
  const sessionId = useChatStore((s) => s.sessionId);
  const createSession = useChatStore((s) => s.createSession);
  const confirmQuery = useChatStore((s) => s.confirmQuery);
  const cancelConfirm = useChatStore((s) => s.cancelConfirm);
  const { sendQuery } = useQuerySSE();

  // local UI state: which result is shown in the canvas (null = follow latest)
  const [activeMessageId, setActiveMessageId] = useState<string | null>(null);

  // ── create session on first visit (preserves X-Session-Id on SSE) ──
  useEffect(() => {
    if (!sessionId) createSession();
  }, [sessionId, createSession]);

  // ── follow the latest result while a query is running ──
  useEffect(() => {
    if (queryState === "running") setActiveMessageId(null);
  }, [queryState]);

  const handleExample = useCallback(
    (text: string) => {
      if (!sessionId) {
        createSession().then(() => sendQuery(text));
      } else {
        sendQuery(text);
      }
    },
    [sessionId, createSession, sendQuery],
  );

  const systemMessages = useMemo(
    () => messages.filter((m) => m.role === "system"),
    [messages],
  );
  const activeSysId =
    activeMessageId ?? systemMessages[systemMessages.length - 1]?.id ?? null;
  const isEmpty = systemMessages.length === 0;

  return (
    <div className="flex-1 flex flex-col min-h-0">
      <QueryBar />
      <TraceStrip />
      <div className="flex-1 flex min-h-0">
        <HistoryRail
          messages={messages}
          activeId={activeSysId}
          onSelect={setActiveMessageId}
        />
        {isEmpty ? (
          <EmptyWorkbench onExample={handleExample} disabled={queryState === "running"} />
        ) : (
          <ResultCanvas
            messages={messages}
            activeMessageId={activeMessageId}
            onConfirm={(id) => confirmQuery(id)}
            onCancel={(id) => cancelConfirm(id)}
          />
        )}
      </div>
    </div>
  );
}
