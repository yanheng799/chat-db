"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { Search } from "lucide-react";
import { cn } from "@/lib/utils";
import { apiPort } from "@/lib/api";
import { Kbd, Tooltip } from "@/components/ui";
import { useChatStore } from "@/stores/chat";
import { DataSourceSwitcher } from "@/components/workbench/DataSourceSwitcher";

const NAV = [
  { label: "查询", path: "/" },
  { label: "数据源", path: "/datasources" },
  { label: "管理", path: "/admin" },
] as const;

export function AppHeader() {
  const pathname = usePathname();
  const backendUnreachable = useChatStore((s) => s.backendUnreachable);

  const isActive = (path: string) =>
    path === "/" ? pathname === "/" : pathname.startsWith(path);

  return (
    <header className="h-14 shrink-0 border-b border-border bg-background/95 backdrop-blur flex items-center gap-3 px-4 sticky top-0 z-40">
      {/* Brand */}
      <Link href="/" className="flex items-center gap-2 shrink-0">
        <span className="size-7 rounded-md bg-primary text-primary-foreground grid place-items-center text-sm font-extrabold">
          Q
        </span>
        <span className="font-semibold tracking-tight text-foreground hidden sm:block">
          Chat-DB
        </span>
      </Link>

      {/* Nav */}
      <nav className="flex items-center gap-1 ml-2" aria-label="主导航">
        {NAV.map((n) => {
          const active = isActive(n.path);
          return (
            <Link
              key={n.path}
              href={n.path}
              aria-current={active ? "page" : undefined}
              className={cn(
                "px-3 h-8 inline-flex items-center rounded-md text-sm font-medium transition-colors",
                active
                  ? "bg-secondary text-foreground"
                  : "text-muted-foreground hover:text-foreground hover:bg-secondary/60",
              )}
            >
              {n.label}
            </Link>
          );
        })}
      </nav>

      <div className="flex-1" />

      {/* DataSource switcher */}
      <DataSourceSwitcher />

      {/* Command palette trigger */}
      <Tooltip
        content={
          <span className="inline-flex items-center gap-1">
            命令面板 <Kbd>/</Kbd>
          </span>
        }
      >
        <button
          type="button"
          onClick={() => window.dispatchEvent(new CustomEvent("chatdb:command-palette"))}
          aria-label="打开命令面板"
          className="inline-flex items-center gap-2 h-8 px-2.5 rounded-md border border-input bg-background text-muted-foreground hover:bg-secondary hover:text-foreground transition-colors text-sm"
        >
          <Search className="size-4" />
          <Kbd className="hidden md:inline-flex">/</Kbd>
        </button>
      </Tooltip>

      {/* Connection status */}
      <span
        className="hidden lg:inline-flex items-center gap-1.5 text-xs text-muted-foreground shrink-0"
        title={backendUnreachable ? "后端不可达" : "已连接后端"}
      >
        <span
          className={cn(
            "size-1.5 rounded-full",
            backendUnreachable ? "bg-destructive" : "bg-success",
          )}
        />
        :{apiPort}
      </span>
    </header>
  );
}
