"use client";

import { useCallback } from "react";
import { Plus, Trash2 } from "lucide-react";
import { useChatStore } from "@/stores/chat";
import { cn } from "@/lib/utils";
import { Button } from "@/components/ui";

export function HistoryRail() {
  const conversations = useChatStore((s) => s.conversations);
  const sessionId = useChatStore((s) => s.sessionId);
  const createSession = useChatStore((s) => s.createSession);
  const switchSession = useChatStore((s) => s.switchSession);
  const deleteConversation = useChatStore((s) => s.deleteConversation);

  const handleNew = useCallback(async () => {
    await createSession();
  }, [createSession]);

  const handleDelete = useCallback(
    async (e: React.MouseEvent, sid: string) => {
      e.stopPropagation(); // don't trigger switchSession
      await deleteConversation(sid);
    },
    [deleteConversation],
  );

  return (
    <aside className="w-56 shrink-0 border-r border-border bg-background flex flex-col h-full">
      <div className="px-3 py-2 flex items-center justify-between border-b border-border">
        <span className="text-xs font-medium text-muted-foreground">会话</span>
        <Button size="xs" variant="ghost" onClick={handleNew} title="新建会话">
          <Plus className="size-3.5" />
        </Button>
      </div>

      <div className="flex-1 overflow-y-auto">
        {conversations.length === 0 ? (
          <div className="px-3 py-6 text-xs text-muted-foreground/60 text-center">
            点击 + 新建会话
          </div>
        ) : (
          conversations.map((conv) => (
            <div
              key={conv.id}
              className={cn(
                "group flex items-center border-l-2 transition-colors",
                conv.id === sessionId
                  ? "border-primary bg-primary/5"
                  : "border-transparent hover:bg-secondary/60",
              )}
            >
              <button
                type="button"
                onClick={() => switchSession(conv.id)}
                className="flex-1 text-left px-3 py-2 text-xs min-w-0"
              >
                <div className="truncate font-medium">{conv.title}</div>
                {conv.time ? (
                  <div className="text-[10px] text-muted-foreground/60 mt-0.5">
                    {conv.time}
                  </div>
                ) : null}
              </button>
              <button
                type="button"
                onClick={(e) => handleDelete(e, conv.id)}
                className="shrink-0 px-1.5 py-2 text-muted-foreground/40 hover:text-destructive opacity-0 group-hover:opacity-100 transition-opacity"
                title="删除会话"
              >
                <Trash2 className="size-3" />
              </button>
            </div>
          ))
        )}
      </div>
    </aside>
  );
}
