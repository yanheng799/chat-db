import { ChevronDown } from "lucide-react";
import { cn } from "@/lib/utils";

export interface SelectOption {
  value: string;
  label: string;
}

export interface SelectProps
  extends Omit<React.SelectHTMLAttributes<HTMLSelectElement>, "size"> {
  options: SelectOption[];
}

/** Styled native <select>. Low-risk + accessible; honors `color-scheme: light`. */
export function Select({ className, options, ...props }: SelectProps) {
  return (
    <div className="relative">
      <select
        data-slot="select"
        className={cn(
          "w-full h-9 pl-3 pr-8 bg-background border border-input rounded-md text-sm text-foreground transition-[border-color] focus-visible:border-primary disabled:cursor-not-allowed disabled:opacity-50 appearance-none cursor-pointer",
          className,
        )}
        {...props}
      >
        {options.map((o) => (
          <option key={o.value} value={o.value}>
            {o.label}
          </option>
        ))}
      </select>
      <ChevronDown
        aria-hidden="true"
        className="pointer-events-none absolute right-2.5 top-1/2 -translate-y-1/2 size-4 text-muted-foreground"
      />
    </div>
  );
}
