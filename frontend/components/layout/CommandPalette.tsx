"use client";
/* eslint-disable react-hooks/set-state-in-effect -- intentional derived-state resets (clear highlight when list changes; clear query when closed) */

import { useEffect, useMemo, useState } from "react";
import { useRouter } from "next/navigation";
import { Search } from "lucide-react";
import { cn } from "@/lib/utils";
import { Dialog } from "@/components/ui";
import { useChatStore } from "@/stores/chat";

interface Command {
  id: string;
  label: string;
  hint: string;
  run: () => void | Promise<void>;
}

const NAV = [
  { label: "查询", path: "/", hint: "自然语言查询" },
  { label: "数据源", path: "/datasources", hint: "管理数据源" },
  { label: "管理", path: "/admin", hint: "管理控制台" },
];

function isTypingTarget(t: EventTarget | null): boolean {
  const el = t as HTMLElement | null;
  if (!el) return false;
  const tag = el.tagName;
  return tag === "INPUT" || tag === "TEXTAREA" || tag === "SELECT" || el.isContentEditable;
}

export function CommandPalette() {
  const [open, setOpen] = useState(false);
  const [query, setQuery] = useState("");
  const [activeIndex, setActiveIndex] = useState(0);
  const router = useRouter();
  const conversations = useChatStore((s) => s.conversations);
  const createSession = useChatStore((s) => s.createSession);
  const switchSession = useChatStore((s) => s.switchSession);

  useEffect(() => {
    const openHandler = () => setOpen(true);
    const keyHandler = (e: KeyboardEvent) => {
      if (
        e.key === "/" &&
        !isTypingTarget(e.target) &&
        !e.metaKey &&
        !e.ctrlKey &&
        !e.altKey
      ) {
        e.preventDefault();
        setOpen(true);
      }
    };
    window.addEventListener("chatdb:command-palette", openHandler as EventListener);
    window.addEventListener("keydown", keyHandler);
    return () => {
      window.removeEventListener("chatdb:command-palette", openHandler as EventListener);
      window.removeEventListener("keydown", keyHandler);
    };
  }, []);

  const commands = useMemo<Command[]>(() => {
    const navCmds: Command[] = NAV.map((n) => ({
      id: "nav:" + n.path,
      label: n.label,
      hint: n.hint,
      run: () => router.push(n.path),
    }));
    const sessionCmd: Command = {
      id: "new-session",
      label: "新建会话",
      hint: "开始一次新查询",
      run: async () => {
        await createSession();
        router.push("/");
      },
    };
    const convCmds: Command[] = conversations.slice(0, 8).map((c) => ({
      id: "conv:" + c.id,
      label: c.title,
      hint: "恢复会话",
      run: async () => {
        await switchSession(c.id);
        router.push("/");
      },
    }));
    return [sessionCmd, ...navCmds, ...convCmds];
  }, [conversations, router, createSession, switchSession]);

  const filtered = useMemo(() => {
    const q = query.trim().toLowerCase();
    if (!q) return commands;
    return commands.filter(
      (c) => c.label.toLowerCase().includes(q) || c.hint.toLowerCase().includes(q),
    );
  }, [commands, query]);

  useEffect(() => {
    setActiveIndex(0);
  }, [filtered]);

  useEffect(() => {
    if (!open) setQuery("");
  }, [open]);

  const run = (cmd?: Command) => {
    if (!cmd) return;
    cmd.run();
    setOpen(false);
  };

  const onKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === "ArrowDown") {
      e.preventDefault();
      setActiveIndex((i) => Math.min(i + 1, filtered.length - 1));
    } else if (e.key === "ArrowUp") {
      e.preventDefault();
      setActiveIndex((i) => Math.max(i - 1, 0));
    } else if (e.key === "Enter") {
      e.preventDefault();
      run(filtered[activeIndex]);
    }
  };

  return (
    <Dialog.Root open={open} onOpenChange={setOpen}>
      <Dialog.Content className="max-w-lg p-0 overflow-hidden" onKeyDown={onKeyDown}>
        <Dialog.Title className="sr-only">命令面板</Dialog.Title>
        <Dialog.Description className="sr-only">
          输入命令或搜索，方向键选择，回车执行。
        </Dialog.Description>
        <div className="flex items-center gap-2 px-3 border-b border-border">
          <Search className="size-4 text-muted-foreground shrink-0" />
          <input
            // base-ui moves focus into the dialog; keep this as a fallback
            autoFocus
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            placeholder="输入命令或搜索…"
            className="flex-1 h-11 bg-transparent text-sm text-foreground outline-none placeholder:text-muted-foreground"
          />
        </div>
        <div className="max-h-80 overflow-y-auto p-1">
          {filtered.length === 0 ? (
            <div className="px-3 py-6 text-center text-xs text-muted-foreground">无匹配命令</div>
          ) : (
            filtered.map((c, i) => (
              <button
                key={c.id}
                type="button"
                onMouseEnter={() => setActiveIndex(i)}
                onClick={() => run(c)}
                className={cn(
                  "w-full flex items-center justify-between gap-3 px-3 h-9 rounded-md text-sm text-left transition-colors",
                  i === activeIndex ? "bg-accent text-accent-foreground" : "text-foreground",
                )}
              >
                <span className="truncate">{c.label}</span>
                <span className="text-xs text-muted-foreground shrink-0">{c.hint}</span>
              </button>
            ))
          )}
        </div>
      </Dialog.Content>
    </Dialog.Root>
  );
}
