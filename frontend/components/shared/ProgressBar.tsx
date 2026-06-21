"use client";

import { type ProgressStep } from "@/stores/chat";

const statusColors: Record<ProgressStep["status"], string> = {
  idle: "bg-muted",
  active: "bg-primary animate-pulse",
  done: "bg-success",
  error: "bg-destructive",
};

const labelColors: Record<ProgressStep["status"], string> = {
  idle: "text-muted-foreground",
  active: "text-primary font-medium",
  done: "text-success",
  error: "text-destructive",
};

const statusGlyph = (status: ProgressStep["status"]) =>
  status === "done" ? "✓" : status === "error" ? "✕" : "";

interface ProgressBarProps {
  steps: ProgressStep[];
}

export function ProgressBar({ steps }: ProgressBarProps) {
  if (steps.length === 0) return null;

  return (
    <div
      role="status"
      aria-live="polite"
      aria-label="查询进度"
      className="flex items-center gap-1"
    >
      {steps.map((step, i) => (
        <div key={step.label} className="flex items-center gap-1 flex-1 min-w-0">
          {/* Step Dot + Label */}
          <div className="flex items-center gap-1.5 flex-1 min-w-0">
            <span
              className={`inline-flex items-center justify-center size-3.5 rounded-full text-[10px] font-bold text-primary-foreground shrink-0 ${statusColors[step.status]}`}
            >
              {statusGlyph(step.status)}
            </span>
            <span className={`text-xs whitespace-nowrap truncate ${labelColors[step.status]}`}>
              {step.label}
            </span>
          </div>
          {/* Connector line */}
          {i < steps.length - 1 && (
            <div
              className={`h-px flex-1 min-w-[8px] ${step.status === "done" ? "bg-success/40" : "bg-border"}`}
            />
          )}
        </div>
      ))}
    </div>
  );
}
