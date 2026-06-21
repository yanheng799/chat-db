"use client";

import { useState } from "react";
import { ChevronDown } from "lucide-react";
import { cn } from "@/lib/utils";
import { Collapsible } from "@/components/ui";
import { ProgressBar } from "@/components/shared/ProgressBar";
import { useChatStore } from "@/stores/chat";

export function TraceStrip() {
  const progressSteps = useChatStore((s) => s.progressSteps);
  const queryState = useChatStore((s) => s.queryState);
  const [open, setOpen] = useState(true);

  const anyActive =
    queryState !== "idle" || progressSteps.some((s) => s.status !== "idle");
  if (!anyActive) return null;

  return (
    <Collapsible.Root
      open={open}
      onOpenChange={setOpen}
      className="shrink-0 border-b border-border bg-secondary/30"
    >
      <Collapsible.Trigger className="w-full flex items-center gap-1.5 px-6 py-1.5 text-xs text-muted-foreground hover:text-foreground transition-colors">
        <ChevronDown className={cn("size-3.5 transition-transform", open ? "" : "-rotate-90")} />
        查询过程
      </Collapsible.Trigger>
      <Collapsible.Panel className="px-6 pb-2">
        <ProgressBar steps={progressSteps} />
      </Collapsible.Panel>
    </Collapsible.Root>
  );
}
