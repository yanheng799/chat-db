"use client";

import { useCallback } from "react";
import { useChatStore } from "@/stores/chat";

/**
 * React hook wrapping the chat store's SSE query actions.
 *
 * Encapsulates {@link import('@microsoft/fetch-event-source').fetchEventSource}
 * via the Zustand store — POST /api/query with X-Session-Id header,
 * 60s AbortController timeout, and onmessage parsing for 5 SSE event types
 * (status / result / error / need_confirm / done).
 */
export function useQuerySSE() {
  const queryState = useChatStore((s) => s.queryState);
  const sendQuery = useChatStore((s) => s.sendQuery);
  const cancelQuery = useChatStore((s) => s.cancelQuery);

  const send = useCallback(
    (text: string) => sendQuery(text),
    [sendQuery],
  );

  const cancel = useCallback(() => cancelQuery(), [cancelQuery]);

  return {
    /** Send a natural-language query; no-op when queryState === 'running' */
    sendQuery: send,
    /** Abort the in-flight SSE connection */
    cancelQuery: cancel,
    /** Current query state: idle | running | await_confirm */
    queryState,
  };
}
