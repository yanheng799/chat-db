"use client";

import { Tooltip as TooltipPrimitive } from "@base-ui/react/tooltip";

export interface TooltipProps {
  children: React.ReactElement;
  content: React.ReactNode;
  side?: "top" | "right" | "bottom" | "left";
  sideOffset?: number;
}

/** Attaches a tooltip to a single trigger element via base-ui's `render` prop. */
export function Tooltip({ children, content, side = "top", sideOffset = 6 }: TooltipProps) {
  return (
    <TooltipPrimitive.Provider delay={300}>
      <TooltipPrimitive.Root>
        <TooltipPrimitive.Trigger render={children} />
        <TooltipPrimitive.Portal>
          <TooltipPrimitive.Positioner side={side} sideOffset={sideOffset}>
            <TooltipPrimitive.Popup className="z-50 max-w-xs rounded-md bg-foreground text-background px-2 py-1 text-xs shadow-md leading-tight">
              {content}
            </TooltipPrimitive.Popup>
          </TooltipPrimitive.Positioner>
        </TooltipPrimitive.Portal>
      </TooltipPrimitive.Root>
    </TooltipPrimitive.Provider>
  );
}
