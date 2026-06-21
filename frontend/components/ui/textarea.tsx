"use client";

import { forwardRef, type TextareaHTMLAttributes } from "react";
import { cn } from "@/lib/utils";

export interface TextareaProps extends TextareaHTMLAttributes<HTMLTextAreaElement> {
  /** Auto-grow the height up to `maxRows` lines as the user types. */
  autosize?: boolean;
  maxRows?: number;
}

export const Textarea = forwardRef<HTMLTextAreaElement, TextareaProps>(
  function Textarea({ className, autosize = false, maxRows = 6, onInput, ...props }, ref) {
    return (
      <textarea
        ref={ref}
        data-slot="textarea"
        onInput={(e) => {
          if (autosize) {
            const el = e.currentTarget;
            el.style.height = "auto";
            const lineHeight = parseFloat(getComputedStyle(el).lineHeight) || 20;
            el.style.height = `${Math.min(el.scrollHeight, lineHeight * maxRows)}px`;
          }
          onInput?.(e);
        }}
        className={cn(
          "w-full px-3 py-2 bg-background border border-input rounded-md text-sm text-foreground placeholder:text-muted-foreground transition-[border-color] focus-visible:border-primary disabled:cursor-not-allowed disabled:opacity-50 resize-none",
          className,
        )}
        {...props}
      />
    );
  },
);
