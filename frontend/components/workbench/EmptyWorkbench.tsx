"use client";

import { Database } from "lucide-react";
import { Button } from "@/components/ui";

const EXAMPLES = [
  "昨天的订单总数",
  "上个月的营收",
  "北京地区的用户数",
  "订单最多的前10个商品",
];

interface EmptyWorkbenchProps {
  onExample: (text: string) => void;
  disabled?: boolean;
}

export function EmptyWorkbench({ onExample, disabled }: EmptyWorkbenchProps) {
  return (
    <div className="flex-1 overflow-y-auto min-w-0">
      <div className="max-w-5xl mx-auto px-6 py-6 h-full flex flex-col items-center justify-center text-center gap-5">
        <div className="size-12 rounded-xl bg-primary/10 text-primary grid place-items-center">
          <Database className="size-6" />
        </div>
        <div>
          <h2 className="text-lg font-semibold text-foreground">用自然语言查询你的数据库</h2>
          <p className="text-sm text-muted-foreground mt-1 max-w-md leading-relaxed">
            输入中文口语查询，系统自动理解意图、匹配字段、生成 SQL 并执行。
          </p>
        </div>
        <div className="flex flex-wrap gap-2 justify-center max-w-lg">
          {EXAMPLES.map((q) => (
            <Button
              key={q}
              variant="outline"
              size="sm"
              disabled={disabled}
              onClick={() => onExample(q)}
            >
              {q}
            </Button>
          ))}
        </div>
      </div>
    </div>
  );
}
