"use client";

import { useMemo } from "react";
import type { Message } from "@/stores/chat";
import { ResultPane } from "./ResultPane";

interface ResultCanvasProps {
  messages: Message[];
  activeMessageId: string | null;
  onConfirm: (id: string) => void;
  onCancel: (id: string) => void;
}

export function ResultCanvas({ messages, activeMessageId, onConfirm, onCancel }: ResultCanvasProps) {
  const systemMessages = useMemo(
    () => messages.filter((m) => m.role === "system"),
    [messages],
  );

  const active = useMemo(() => {
    if (activeMessageId) {
      return systemMessages.find((m) => m.id === activeMessageId) ?? null;
    }
    return systemMessages[systemMessages.length - 1] ?? null;
  }, [systemMessages, activeMessageId]);

  if (!active) return null;

  return (
    <div className="flex-1 overflow-y-auto min-w-0">
      <div className="max-w-5xl mx-auto px-6 py-6">
        <ResultPane message={active} onConfirm={onConfirm} onCancel={onCancel} />
      </div>
    </div>
  );
}
