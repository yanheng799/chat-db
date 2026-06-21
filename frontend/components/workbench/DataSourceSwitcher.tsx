"use client";

import { useEffect } from "react";
import { Database, Check, ChevronDown } from "lucide-react";
import { cn } from "@/lib/utils";
import { Menu } from "@/components/ui";
import { useDataSourceStore } from "@/stores/datasources";
import { useToastStore } from "@/stores/toast";

export function DataSourceSwitcher() {
  const dataSources = useDataSourceStore((s) => s.dataSources);
  const loadDataSources = useDataSourceStore((s) => s.loadDataSources);
  const activate = useDataSourceStore((s) => s.activate);
  const showToast = useToastStore((s) => s.showToast);

  useEffect(() => {
    loadDataSources();
  }, [loadDataSources]);

  const active = dataSources.find((d) => d.is_active) ?? null;

  const handleActivate = async (id: string, name: string) => {
    try {
      await activate(id);
      showToast("success", `已切换到 ${name}`);
    } catch (e) {
      showToast("error", (e as Error).message || "切换失败");
    }
  };

  return (
    <Menu.Root>
      <Menu.Trigger
        className="h-8 px-2.5 gap-2 border border-input bg-background font-medium"
        aria-label="切换数据源"
      >
        <Database className="size-4 text-muted-foreground" />
        <span className={cn("max-w-40 truncate", active ? "text-foreground" : "text-muted-foreground")}>
          {active ? active.name : "选择数据源"}
        </span>
        <ChevronDown className="size-3.5 text-muted-foreground" />
      </Menu.Trigger>
      <Menu.Content>
        {dataSources.length === 0 ? (
          <div className="px-2 py-3 text-xs text-muted-foreground text-center">暂无数据源</div>
        ) : (
          dataSources.map((d) => (
            <Menu.Item key={d.id} onClick={() => handleActivate(d.id, d.name)}>
              <span className="flex-1 truncate">{d.name}</span>
              {d.is_active ? <Check className="size-3.5 text-primary" /> : null}
            </Menu.Item>
          ))
        )}
      </Menu.Content>
    </Menu.Root>
  );
}
