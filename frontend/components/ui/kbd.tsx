import { cn } from "@/lib/utils";

export function Kbd({ className, ...props }: React.HTMLAttributes<HTMLElement>) {
  return (
    <kbd
      data-slot="kbd"
      className={cn(
        "inline-flex items-center justify-center min-w-5 h-5 px-1 rounded border border-border bg-secondary text-[10px] font-medium text-muted-foreground font-mono",
        className,
      )}
      {...props}
    />
  );
}
