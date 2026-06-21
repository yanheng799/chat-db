"use client";

import { Menu as MenuPrimitive } from "@base-ui/react/menu";
import { cn } from "@/lib/utils";

function MenuRoot(props: React.ComponentProps<typeof MenuPrimitive.Root>) {
  return <MenuPrimitive.Root {...props} />;
}

function MenuTrigger({ className, ...props }: React.ComponentProps<typeof MenuPrimitive.Trigger>) {
  return (
    <MenuPrimitive.Trigger
      data-slot="menu-trigger"
      className={cn(
        "inline-flex items-center justify-center rounded-md text-muted-foreground transition-colors hover:bg-accent hover:text-foreground focus-visible:outline-2 focus-visible:outline-[var(--ring)] focus-visible:outline-offset-2 cursor-pointer",
        className,
      )}
      {...props}
    />
  );
}

function MenuContent({ className, ...props }: React.HTMLAttributes<HTMLDivElement>) {
  return (
    <MenuPrimitive.Portal>
      <MenuPrimitive.Positioner align="end" sideOffset={4}>
        <MenuPrimitive.Popup
          data-slot="menu-content"
          className={cn(
            "z-50 min-w-40 bg-popover text-popover-foreground border border-border rounded-md shadow-md p-1 outline-none animate-in fade-in zoom-in-95",
            className,
          )}
          {...props}
        />
      </MenuPrimitive.Positioner>
    </MenuPrimitive.Portal>
  );
}

export interface MenuItemProps
  extends React.ComponentProps<typeof MenuPrimitive.Item> {
  variant?: "default" | "destructive";
}

function MenuItem({ className, variant = "default", ...props }: MenuItemProps) {
  return (
    <MenuPrimitive.Item
      data-slot="menu-item"
      className={cn(
        "relative flex items-center gap-2 h-8 px-2 rounded text-sm cursor-default outline-none transition-colors data-[highlighted]:bg-accent",
        variant === "destructive"
          ? "text-destructive data-[highlighted]:bg-destructive/10"
          : "text-foreground data-[highlighted]:text-accent-foreground",
        className,
      )}
      {...props}
    />
  );
}

function MenuSeparator(props: React.HTMLAttributes<HTMLDivElement>) {
  return (
    <div role="separator" className="my-1 h-px bg-border" {...props} />
  );
}

export const Menu = {
  Root: MenuRoot,
  Trigger: MenuTrigger,
  Content: MenuContent,
  Item: MenuItem,
  Separator: MenuSeparator,
};
