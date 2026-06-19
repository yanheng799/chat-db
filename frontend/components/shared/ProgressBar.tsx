"use client";

import { type ProgressStep } from "@/stores/chat";

const statusColors: Record<ProgressStep["status"], string> = {
  idle: "bg-muted",
  active: "bg-primary animate-pulse",
  done: "bg-green-500",
  error: "bg-red-500",
};

const statusDot = (status: ProgressStep["status"]) =>
  status === "done" ? "✓" : status === "error" ? "✕" : "";

interface ProgressBarProps {
  steps: ProgressStep[];
}

export function ProgressBar({ steps }: ProgressBarProps) {
  if (steps.length === 0) return null;

  return (
    <div className="flex items-center gap-1 px-2 py-1.5">
      {steps.map((step, i) => (
        <div key={step.label} className="flex items-center gap-1 flex-1 min-w-0">
          {/* Step Dot + Label */}
          <div className="flex items-center gap-1.5 flex-1 min-w-0">
            <span
              className={`inline-flex items-center justify-center w-3.5 h-3.5 rounded-full text-[10px] font-bold text-primary-foreground shrink-0 ${statusColors[step.status]}`}
            >
              {statusDot(step.status)}
            </span>
            <span
              className={`text-xs whitespace-nowrap truncate ${
                step.status === "active"
                  ? "text-primary font-medium"
                  : step.status === "done"
                    ? "text-green-400"
                    : step.status === "error"
                      ? "text-red-400"
                      : "text-muted-foreground"
              }`}
            >
              {step.label}
            </span>
          </div>
          {/* Connector line */}
          {i < steps.length - 1 && (
            <div
              className={`h-px flex-1 min-w-[8px] ${
                step.status === "done" ? "bg-green-500/40" : "bg-muted"
              }`}
            />
          )}
        </div>
      ))}
    </div>
  );
}
