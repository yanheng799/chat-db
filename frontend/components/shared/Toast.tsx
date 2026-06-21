"use client";

import { X } from "lucide-react";
import { useToastStore } from "@/stores/toast";

const typeStyles: Record<string, string> = {
  success: "border-success/40 bg-success/10 text-success",
  error: "border-destructive/40 bg-destructive/10 text-destructive",
  info: "border-info/40 bg-info/10 text-info",
};

export function ToastContainer() {
  const toasts = useToastStore((s) => s.toasts);
  const dismiss = useToastStore((s) => s.dismissToast);

  if (toasts.length === 0) return null;

  return (
    <div
      role="status"
      aria-live="polite"
      className="fixed bottom-6 right-6 z-[60] flex flex-col gap-2 max-w-sm"
    >
      {toasts.map((t) => (
        <div
          key={t.id}
          className={`relative pl-4 pr-9 py-3 rounded-lg border text-sm shadow-md cursor-pointer transition-colors animate-in slide-in-from-right ${
            typeStyles[t.type] || typeStyles.info
          }`}
          onClick={() => dismiss(t.id)}
        >
          {t.message}
          <button
            type="button"
            aria-label="关闭通知"
            onClick={(e) => {
              e.stopPropagation();
              dismiss(t.id);
            }}
            className="absolute right-2 top-1/2 -translate-y-1/2 size-6 rounded grid place-items-center opacity-70 hover:opacity-100"
          >
            <X className="size-3.5" />
          </button>
        </div>
      ))}
    </div>
  );
}
