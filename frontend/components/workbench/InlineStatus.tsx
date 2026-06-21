"use client";

import { Info } from "lucide-react";
import { cn } from "@/lib/utils";
import { Spinner } from "@/components/ui";

interface InlineStatusProps {
  text: string;
  spinner?: boolean;
  variant?: "info" | "muted";
}

export function InlineStatus({ text, spinner, variant = "info" }: InlineStatusProps) {
  return (
    <div
      className={cn(
        "flex items-center gap-2 text-sm",
        variant === "muted" ? "text-muted-foreground" : "text-foreground",
      )}
    >
      {spinner ? (
        <Spinner className="size-4" />
      ) : (
        <Info className="size-4 text-muted-foreground" />
      )}
      {text}
    </div>
  );
}
