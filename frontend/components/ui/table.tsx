"use client";

import { useState } from "react";
import { cn } from "@/lib/utils";

export function Table({ className, ...props }: React.HTMLAttributes<HTMLTableElement>) {
  return (
    <table
      data-slot="table"
      className={cn("w-full caption-bottom border-collapse text-sm", className)}
      {...props}
    />
  );
}

export function THead({ className, ...props }: React.HTMLAttributes<HTMLTableSectionElement>) {
  return <thead data-slot="table-header" className={cn("[&_tr]:border-b", className)} {...props} />;
}

export function TBody({ className, ...props }: React.HTMLAttributes<HTMLTableSectionElement>) {
  return (
    <tbody data-slot="table-body" className={cn("[&_tr:last-child]:border-0", className)} {...props} />
  );
}

export function Tr({ className, ...props }: React.HTMLAttributes<HTMLTableRowElement>) {
  return (
    <tr
      data-slot="table-row"
      className={cn("border-b border-border transition-colors", className)}
      {...props}
    />
  );
}

export function Th({ className, ...props }: React.ThHTMLAttributes<HTMLTableCellElement>) {
  return (
    <th
      data-slot="table-header-cell"
      className={cn(
        "h-9 px-3 text-left align-middle text-xs font-semibold text-muted-foreground whitespace-nowrap",
        className,
      )}
      {...props}
    />
  );
}

export function Td({ className, ...props }: React.TdHTMLAttributes<HTMLTableCellElement>) {
  return (
    <td
      data-slot="table-cell"
      className={cn("px-3 py-1.5 align-middle text-sm text-foreground/90 whitespace-nowrap", className)}
      {...props}
    />
  );
}

// ── DataTable — the workbench hero ──────────────────────────────────────
// Ports the previous ResultTable behavior: render-cap, sticky header, zebra
// rows, NULL styling. Prevents jank on large result sets.

const INITIAL_ROW_CAP = 100;

export interface DataTableProps {
  columns: string[];
  rows: unknown[][];
  emptyLabel?: string;
  maxHeight?: string;
  /** Render all cells with monospace + tabular-nums (good for numeric data). */
  numeric?: boolean;
}

export function DataTable({
  columns,
  rows,
  emptyLabel = "无数据",
  maxHeight = "360px",
  numeric,
}: DataTableProps) {
  const [showAll, setShowAll] = useState(false);

  if (columns.length === 0) {
    return <div className="text-xs text-muted-foreground py-2">{emptyLabel}</div>;
  }

  const visible = showAll ? rows : rows.slice(0, INITIAL_ROW_CAP);
  const hidden = rows.length - visible.length;

  return (
    <div className="rounded-lg border border-border overflow-hidden">
      <div className="overflow-x-auto overflow-y-auto" style={{ maxHeight }}>
        <Table>
          <THead>
            <Tr className="bg-muted/60 hover:bg-muted/60">
              {columns.map((col) => (
                <Th key={col} className="sticky top-0 bg-muted">
                  {col}
                </Th>
              ))}
            </Tr>
          </THead>
          <TBody>
            {visible.map((row, ri) => (
              <Tr key={ri} className={ri % 2 ? "bg-muted/30" : ""}>
                {row.map((cell, ci) => (
                  <Td key={ci} className={numeric ? "font-mono tabular-nums" : ""}>
                    {cell === null || cell === undefined ? (
                      <span className="text-muted-foreground italic">NULL</span>
                    ) : typeof cell === "object" ? (
                      JSON.stringify(cell)
                    ) : (
                      String(cell)
                    )}
                  </Td>
                ))}
              </Tr>
            ))}
          </TBody>
        </Table>
      </div>
      {hidden > 0 ? (
        <button
          type="button"
          onClick={() => setShowAll(true)}
          className="w-full px-3 h-8 text-xs text-muted-foreground hover:text-foreground hover:bg-muted border-t border-border transition-colors"
        >
          显示其余 {hidden.toLocaleString()} 行（共 {rows.length.toLocaleString()} 行）
        </button>
      ) : null}
    </div>
  );
}
