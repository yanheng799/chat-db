"use client";

import { useMemo } from "react";
import type { Message } from "@/stores/chat";
import { cn } from "@/lib/utils";

interface HistoryRailProps {
  messages: Message[];
  activeId: string | null;
  onSelect: (systemMessageId: string) => void;
}

export function HistoryRail({ messages, activeId, onSelect }: HistoryRailProps) {
  // pair each user message with its following system message; newest first
  const pairs = useMemo(() => {
    const result: { user: Message; sys: Message }[] = [];
    for (let i = 0; i < messages.length; i++) {
      if (messages[i].role === "user") {
        const sys = messages[i + 1]?.role === "system" ? messages[i + 1] : undefined;
        if (sys) result.push({ user: messages[i], sys });
      }
    }
    return result.reverse();
  }, [messages]);

  return (
    <aside className="w-56 shrink-0 border-r border-border bg-background overflow-y-auto hidden md:block">
      <div className="px-3 py-2 text-xs font-medium text-muted-foreground">历史查询</div>
      {pairs.length === 0 ? (
        <div className="px-3 py-6 text-xs text-muted-foreground/60 text-center">暂无查询</div>
      ) : (
        <ul className="px-1.5 pb-2 space-y-0.5">
          {pairs.map(({ user, sys }) => (
            <li key={user.id}>
              <button
                type="button"
                onClick={() => onSelect(sys.id)}
                className={cn(
                  "w-full text-left px-2 py-1.5 rounded-md text-xs leading-snug line-clamp-2 transition-colors",
                  activeId === sys.id
                    ? "bg-secondary text-foreground"
                    : "text-muted-foreground hover:bg-secondary/60 hover:text-foreground",
                )}
              >
                {user.content}
              </button>
            </li>
          ))}
        </ul>
      )}
    </aside>
  );
}
