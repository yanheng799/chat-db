"use client";

import { usePathname, useRouter } from "next/navigation";
import { cn } from "@/lib/utils";

export function Sidebar() {
  const pathname = usePathname();
  const router = useRouter();

  const modes = [
    { key: "chat", label: "对话", path: "/" },
    { key: "admin", label: "管理", path: "/admin" },
    { key: "datasources", label: "数据源", path: "/datasources" },
  ] as const;

  return (
    <aside className="w-[280px] min-w-[280px] bg-sidebar border-r border-sidebar-border flex flex-col">
      {/* Logo */}
      <div className="px-5 py-6 border-b border-sidebar-border flex items-center gap-3">
        <div className="w-8 h-8 rounded-lg bg-primary flex items-center justify-center text-sm font-extrabold text-primary-foreground">
          Q
        </div>
        <span className="text-[17px] font-bold tracking-tight text-sidebar-foreground">
          Chat-DB
        </span>
      </div>

      {/* New Session */}
      <div className="px-4 py-3">
        <button
          onClick={() => router.push("/")}
          className="w-full py-2.5 px-4 bg-primary text-primary-foreground rounded-[10px] text-sm font-semibold transition-all hover:brightness-110 hover:-translate-y-px"
        >
          + 新建会话
        </button>
      </div>

      {/* Conversation List (placeholder) */}
      <div className="flex-1 overflow-y-auto px-3 py-2">
        <div className="text-xs text-muted-foreground/50 text-center py-8">
          暂无会话
        </div>
      </div>

      {/* Mode Switcher */}
      <div className="p-3 border-t border-sidebar-border flex gap-1.5">
        {modes.map((m) => (
          <button
            key={m.key}
            onClick={() => router.push(m.path)}
            className={cn(
              "flex-1 py-2 rounded-lg text-xs font-medium transition-all",
              pathname === m.path
                ? "bg-primary text-primary-foreground"
                : "text-muted-foreground hover:text-sidebar-foreground hover:bg-sidebar-accent"
            )}
          >
            {m.label}
          </button>
        ))}
      </div>
    </aside>
  );
}
