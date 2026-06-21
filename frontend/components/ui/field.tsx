import { cn } from "@/lib/utils";

export interface FieldProps {
  label?: string;
  required?: boolean;
  error?: string;
  hint?: string;
  children: React.ReactNode;
  className?: string;
}

/**
 * Label + control + error/hint wrapper. When `label` is provided the whole
 * thing is wrapped in a <label> so clicking the label text focuses the
 * control (single hit target). Pass exactly one form control as children.
 */
export function Field({ label, required, error, hint, children, className }: FieldProps) {
  const note = error ? (
    <span role="alert" className="text-xs text-destructive mt-1.5 block">
      {error}
    </span>
  ) : hint ? (
    <span className="text-xs text-muted-foreground mt-1.5 block">{hint}</span>
  ) : null;

  if (!label) {
    return (
      <div className={className}>
        {children}
        {note}
      </div>
    );
  }

  return (
    <label className={cn("block", className)}>
      <span className="text-xs font-medium text-foreground/80 mb-1.5 block">
        {label}
        {required ? <span className="text-destructive ml-0.5">*</span> : null}
      </span>
      {children}
      {note}
    </label>
  );
}
