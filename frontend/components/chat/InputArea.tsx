"use client";

import { useRef, useCallback, type KeyboardEvent } from "react";

interface InputAreaProps {
  disabled: boolean;
  onSend: (text: string) => void;
}

export function InputArea({ disabled, onSend }: InputAreaProps) {
  const ref = useRef<HTMLTextAreaElement>(null);

  const handleSend = useCallback(() => {
    const text = ref.current?.value.trim();
    if (!text || disabled) return;
    onSend(text);
    if (ref.current) ref.current.value = "";
    // Reset height
    if (ref.current) ref.current.style.height = "auto";
  }, [disabled, onSend]);

  const handleKeyDown = useCallback(
    (e: KeyboardEvent<HTMLTextAreaElement>) => {
      if (e.key === "Enter" && !e.shiftKey) {
        e.preventDefault();
        handleSend();
      }
    },
    [handleSend],
  );

  const handleInput = useCallback(() => {
    const el = ref.current;
    if (!el) return;
    el.style.height = "auto";
    el.style.height = `${Math.min(el.scrollHeight, 120)}px`;
  }, []);

  return (
    <div className="px-7 py-4 pb-5 border-t border-border">
      <div className="flex gap-2.5 items-end">
        <textarea
          ref={ref}
          className="flex-1 px-4 py-3.5 bg-secondary border border-border rounded-2xl text-sm text-foreground placeholder:text-muted-foreground resize-none outline-none transition-colors focus:border-primary min-h-[48px] max-h-[120px] disabled:opacity-50 disabled:cursor-not-allowed"
          placeholder="输入查询，例如「昨天的订单总数」…"
          rows={1}
          disabled={disabled}
          onKeyDown={handleKeyDown}
          onInput={handleInput}
        />
        <button
          className="w-12 h-12 bg-primary text-primary-foreground rounded-2xl flex items-center justify-center text-lg transition-all hover:brightness-110 flex-shrink-0 disabled:opacity-50 disabled:cursor-not-allowed"
          aria-label="发送"
          disabled={disabled}
          onClick={handleSend}
        >
          {disabled ? (
            <span className="inline-block w-4 h-4 border-2 border-primary-foreground/40 border-t-primary-foreground rounded-full animate-spin" />
          ) : (
            <svg
              width="18"
              height="18"
              viewBox="0 0 24 24"
              fill="none"
              stroke="currentColor"
              strokeWidth="2.5"
              strokeLinecap="round"
              strokeLinejoin="round"
            >
              <path d="M5 12h14M12 5l7 7-7 7" />
            </svg>
          )}
        </button>
      </div>
    </div>
  );
}
