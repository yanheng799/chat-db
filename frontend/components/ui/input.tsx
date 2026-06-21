import { forwardRef } from "react";
import { cva, type VariantProps } from "class-variance-authority";
import { cn } from "@/lib/utils";

const inputVariants = cva(
  "flex w-full px-3 bg-background border border-input rounded-md text-sm text-foreground placeholder:text-muted-foreground transition-[border-color,box-shadow] focus-visible:border-primary disabled:cursor-not-allowed disabled:opacity-50 aria-[invalid=true]:border-destructive",
  {
    variants: {
      size: {
        default: "h-9 py-2",
        sm: "h-8 text-xs",
      },
    },
    defaultVariants: { size: "default" },
  },
);

export interface InputProps
  extends Omit<React.InputHTMLAttributes<HTMLInputElement>, "size">,
    VariantProps<typeof inputVariants> {}

export const Input = forwardRef<HTMLInputElement, InputProps>(function Input(
  { className, size, ...props },
  ref,
) {
  return (
    <input
      ref={ref}
      data-slot="input"
      className={cn(inputVariants({ size, className }))}
      {...props}
    />
  );
});
