"use client";

import { useEffect, useRef, useCallback } from "react";
import { useChatStore } from "@/stores/chat";
import { useQuerySSE } from "@/hooks/useQuerySSE";
import { MessageBubble } from "@/components/shared/MessageBubble";
import { ProgressBar } from "@/components/shared/ProgressBar";
import { InputArea } from "@/components/chat/InputArea";

const EXAMPLE_QUERIES = [
  "昨天的订单总数",
  "上个月的营收",
  "北京地区的用户数",
  "订单最多的前10个商品",
];

export default function ChatPage() {
  const messages = useChatStore((s) => s.messages);
  const queryState = useChatStore((s) => s.queryState);
  const progressSteps = useChatStore((s) => s.progressSteps);
  const sessionId = useChatStore((s) => s.sessionId);
  const createSession = useChatStore((s) => s.createSession);
  const confirmQuery = useChatStore((s) => s.confirmQuery);
  const cancelConfirm = useChatStore((s) => s.cancelConfirm);
  const { sendQuery } = useQuerySSE();

  const messagesEndRef = useRef<HTMLDivElement>(null);
  const isRunning = queryState === "running";

  // ── Auto-scroll to bottom when messages change ──────
  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages]);

  // ── Auto-create session on first visit ─────────────
  useEffect(() => {
    if (!sessionId) {
      createSession();
    }
  }, [sessionId, createSession]);

  // ── Send handler ───────────────────────────────────
  const handleSend = useCallback(
    (text: string) => {
      // Auto-create session if not yet available (edge case)
      if (!sessionId) {
        createSession().then(() => {
          sendQuery(text);
        });
      } else {
        sendQuery(text);
      }
    },
    [sessionId, createSession, sendQuery],
  );

  const isEmpty = messages.length === 0;

  return (
    <div className="flex-1 flex flex-col">
      {/* Header */}
      <header className="px-7 py-4 border-b border-border flex items-center gap-3">
        <div
          className={`w-2 h-2 rounded-full ${
            isRunning
              ? "bg-primary animate-pulse"
              : "bg-green-500"
          }`}
        />
        <span className="text-sm font-medium text-foreground">Chat-DB</span>
        <span className="text-xs text-muted-foreground ml-auto">
          {isRunning ? "查询中…" : "已连接 :8000"}
        </span>
      </header>

      {/* Messages Area */}
      <div className="flex-1 overflow-y-auto">
        {isEmpty ? (
          /* ── Empty State ─────────────────────────── */
          <div className="h-full flex flex-col items-center justify-center gap-4 text-muted-foreground">
            <div className="text-5xl opacity-20">◆</div>
            <h2 className="text-lg text-foreground/70 font-medium">
              用自然语言查询你的数据库
            </h2>
            <p className="text-sm text-center max-w-md leading-relaxed">
              输入中文口语查询，系统自动理解意图、匹配字段、生成 SQL 并执行。
            </p>
            {/* Example pills */}
            <div className="flex flex-wrap gap-2 max-w-md justify-center mt-2">
              {EXAMPLE_QUERIES.map((q) => (
                <button
                  key={q}
                  onClick={() => handleSend(q)}
                  disabled={isRunning}
                  className="px-3.5 py-2 bg-secondary border border-border rounded-full text-xs text-muted-foreground hover:text-foreground hover:border-primary/50 transition-colors disabled:opacity-50"
                >
                  {q}
                </button>
              ))}
            </div>
          </div>
        ) : (
          /* ── Messages + Progress ─────────────────── */
          <div className="px-7 py-6">
            {messages.map((m) => (
              <MessageBubble
                key={m.id}
                message={m}
                onConfirm={(id) => confirmQuery(id)}
                onCancel={(id) => cancelConfirm(id)}
              />
            ))}

            {/* Inline progress bar during query */}
            {isRunning && (
              <div className="mb-4">
                <ProgressBar steps={progressSteps} />
              </div>
            )}

            <div ref={messagesEndRef} />
          </div>
        )}
      </div>

      {/* Input Area */}
      <InputArea disabled={isRunning} onSend={handleSend} />
    </div>
  );
}
