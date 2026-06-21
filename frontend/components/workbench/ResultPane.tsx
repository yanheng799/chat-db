"use client";

import type { Message } from "@/stores/chat";
import { ResultView } from "./ResultView";
import { ConfirmPanel } from "./ConfirmPanel";
import { ErrorState } from "./ErrorState";
import { SkeletonResult } from "./SkeletonResult";
import { InlineStatus } from "./InlineStatus";

interface ResultPaneProps {
  message: Message;
  onConfirm: (id: string) => void;
  onCancel: (id: string) => void;
}

/**
 * Branches on the overloaded `content` discriminator of a system message.
 * Order matters: check result/confirm/error first, then the literal status
 * strings, then fall back to arbitrary status text.
 */
export function ResultPane({ message, onConfirm, onCancel }: ResultPaneProps) {
  const c = message.content;

  if (c === "result") return <ResultView message={message} />;
  if (c === "confirm")
    return <ConfirmPanel message={message} onConfirm={onConfirm} onCancel={onCancel} />;
  if (c.startsWith("❌")) return <ErrorState detail={c.replace(/^❌\s*/, "")} />;
  if (c === "思考中…") return <SkeletonResult />;
  if (c === "已确认，继续处理中…") return <InlineStatus spinner text={c} />;
  if (c === "已取消查询") return <InlineStatus text={c} variant="muted" />;

  // any other status-event text (e.g. "正在生成 SQL…")
  return <InlineStatus text={c} />;
}
