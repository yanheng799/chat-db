"use client";

import { Switch as SwitchPrimitive } from "@base-ui/react/switch";
import { cn } from "@/lib/utils";

export interface SwitchProps
  extends Omit<React.ComponentProps<typeof SwitchPrimitive.Root>, "defaultChecked"> {
  size?: "sm" | "default";
}

export function Switch({ className, size = "default", ...props }: SwitchProps) {
  return (
    <SwitchPrimitive.Root
      data-slot="switch"
      className={cn(
        "group/switch inline-flex shrink-0 items-center rounded-full bg-input transition-colors data-[checked]:bg-primary focus-visible:outline-2 focus-visible:outline-[var(--ring)] focus-visible:outline-offset-2",
        size === "sm" ? "h-4 w-7" : "h-5 w-9",
        className,
      )}
      {...props}
    >
      <SwitchPrimitive.Thumb
        className={cn(
          "pointer-events-none block rounded-full bg-background shadow ring-0 transition-transform",
          size === "sm"
            ? "size-3 ml-0.5 group-data-[checked]/switch:translate-x-3"
            : "size-4 ml-0.5 group-data-[checked]/switch:translate-x-4",
        )}
      />
    </SwitchPrimitive.Root>
  );
}
