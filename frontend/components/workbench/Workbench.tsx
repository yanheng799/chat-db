"use client";
/* eslint-disable react-hooks/set-state-in-effect -- intentional: follow the latest result while a query is running */

import { useEffect, useRef, useState, useCallback } from "react";
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
  const loadConversations = useChatStore((s) => s.loadConversations);
  const confirmQuery = useChatStore((s) => s.confirmQuery);
  const cancelConfirm = useChatStore((s) => s.cancelConfirm);
  const { sendQuery } = useQuerySSE();

  const [activeMessageId, setActiveMessageId] = useState<string | null>(null);
  const initialized = useRef(false);

  // ── one-time init: load existing sessions (no auto-create) ──
  useEffect(() => {
    if (initialized.current) return;
    initialized.current = true;
    loadConversations();
  }, []); // eslint-disable-line react-hooks/exhaustive-deps

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

  const isEmpty = messages.filter((m) => m.role === "system").length === 0;

  return (
    <div className="flex-1 flex min-h-0">
      <HistoryRail />
      <div className="flex-1 flex flex-col min-w-0">
        <div className="flex-1 flex min-h-0">
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
        <TraceStrip />
        <QueryBar />
      </div>
    </div>
  );
}
