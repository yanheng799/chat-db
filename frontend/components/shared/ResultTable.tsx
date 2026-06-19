"use client";

interface ResultTableProps {
  columns: string[];
  rows: unknown[][];
}

export function ResultTable({ columns, rows }: ResultTableProps) {
  if (columns.length === 0) {
    return (
      <div className="text-xs text-muted-foreground py-2">(空结果)</div>
    );
  }

  return (
    <div className="border border-border rounded-xl overflow-hidden">
      {/* Stats bar */}
      <div className="px-3 py-1.5 bg-secondary/50 border-b border-border flex items-center gap-4">
        <span className="text-[11px] text-muted-foreground">
          {columns.length} 列 × {rows.length} 行
        </span>
      </div>
      {/* Table with horizontal scroll */}
      <div className="overflow-x-auto max-h-[360px] overflow-y-auto">
        <table className="w-full text-xs">
          <thead>
            <tr className="bg-amber-500/10 border-b border-border">
              {columns.map((col) => (
                <th
                  key={col}
                  className="px-3 py-2 text-left font-semibold text-amber-100 whitespace-nowrap sticky top-0 bg-amber-500/15"
                >
                  {col}
                </th>
              ))}
            </tr>
          </thead>
          <tbody>
            {rows.map((row, ri) => (
              <tr
                key={ri}
                className={`border-b border-border/40 ${
                  ri % 2 === 0 ? "bg-transparent" : "bg-secondary/20"
                }`}
              >
                {row.map((cell, ci) => (
                  <td
                    key={ci}
                    className="px-3 py-1.5 text-foreground/80 whitespace-nowrap"
                  >
                    {cell === null ? (
                      <span className="text-muted-foreground italic">NULL</span>
                    ) : typeof cell === "object" ? (
                      JSON.stringify(cell)
                    ) : (
                      String(cell)
                    )}
                  </td>
                ))}
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}
