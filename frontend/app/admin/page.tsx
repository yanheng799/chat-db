"use client";

import { useEffect, useState, useCallback } from "react";
import { RefreshCw } from "lucide-react";
import {
  Tabs,
  Card,
  CardHeader,
  CardTitle,
  CardContent,
  Badge,
  Button,
  Select,
  DataTable,
  Table,
  THead,
  TBody,
  Tr,
  Th,
  Td,
  EmptyState,
  Skeleton,
} from "@/components/ui";
import { api } from "@/lib/api";

// ── Types ──────────────────────────────────────────

interface SyncStatus {
  latest: {
    sync_type: string;
    status: string;
    started_at: string;
    finished_at: string | null;
    tables_added: number;
    tables_removed: number;
    columns_changed: number;
    error_message?: string | null;
  } | null;
  status: string;
}

interface MappingItem {
  id?: string;
  table_name?: string;
  column_name?: string;
  value?: string;
  display?: string;
  code?: string;
  name?: string;
  short_name?: string;
  full_name?: string;
  target_table?: string;
  aliases?: string[];
}

// ── Page ───────────────────────────────────────────

const MAPPING_OPTIONS = [
  { value: "enum", label: "枚举别名" },
  { value: "region", label: "地区" },
  { value: "name", label: "名称简称" },
];

export default function AdminPage() {
  const [activeDsId, setActiveDsId] = useState<string>("");
  const [activeDsName, setActiveDsName] = useState<string>("");
  const [tab, setTab] = useState<string>("sync");

  // Sync
  const [sync, setSync] = useState<SyncStatus | null>(null);
  const [syncLoading, setSyncLoading] = useState(false);

  // Mappings
  const [mappingType, setMappingType] = useState("enum");
  const [mappings, setMappings] = useState<MappingItem[]>([]);
  const [mappingsLoading, setMappingsLoading] = useState(false);

  // Hotwords
  const [hotwords, setHotwords] = useState<Record<string, any> | any[]>({});
  const [hotwordsLoading, setHotwordsLoading] = useState(false);

  // Periods
  const [periods, setPeriods] = useState<Record<string, string[]>[]>([]);
  const [periodsLoading, setPeriodsLoading] = useState(false);

  // Audit
  const [audit, setAudit] = useState<Record<string, any>>({});
  const [auditLoading, setAuditLoading] = useState(false);

  // ── Load active datasource ────────────────────────
  useEffect(() => {
    (async () => {
      try {
        const dss = await api.get<any[]>("/api/datasources");
        const active = dss.find((d: any) => d.is_active);
        if (active) {
          setActiveDsId(active.id);
          setActiveDsName(active.name);
        }
      } catch {
        /* ignore */
      }
    })();
  }, []);

  // ── Card loaders ──────────────────────────────────
  const loadSync = useCallback(async () => {
    setSyncLoading(true);
    try {
      setSync(await api.get<SyncStatus>("/api/admin/sync/status"));
    } catch {
    }
    setSyncLoading(false);
  }, []);

  const loadMappings = useCallback(async () => {
    if (!activeDsId) return;
    setMappingsLoading(true);
    try {
      const data = await api.get<any>(
        `/api/admin/mappings/${mappingType}?data_source_id=${activeDsId}`,
      );
      setMappings(data.items || []);
    } catch {
      setMappings([]);
    }
    setMappingsLoading(false);
  }, [activeDsId, mappingType]);

  const loadHotwords = useCallback(async () => {
    setHotwordsLoading(true);
    try {
      const d = await api.get<any>("/api/admin/hotwords");
      setHotwords(d.items || []);
    } catch {
    }
    setHotwordsLoading(false);
  }, []);

  const loadPeriods = useCallback(async () => {
    setPeriodsLoading(true);
    try {
      const d = await api.get<any>("/api/admin/fixed-periods");
      setPeriods(d.items || []);
    } catch {
    }
    setPeriodsLoading(false);
  }, []);

  const loadAudit = useCallback(async () => {
    setAuditLoading(true);
    try {
      setAudit(await api.get<any>("/api/admin/audit-policy"));
    } catch {
    }
    setAuditLoading(false);
  }, []);

  // ── Load on mount / ds change ─────────────────────
  useEffect(() => {
    loadSync();
  }, [loadSync]);
  useEffect(() => {
    if (activeDsId) {
      loadMappings();
    }
  }, [activeDsId, mappingType, loadMappings]);
  useEffect(() => {
    loadHotwords();
    loadPeriods();
    loadAudit();
  }, [loadHotwords, loadPeriods, loadAudit]);

  // ── Derived: hotwords as a flat list ──────────────
  const hotwordList: { term: string; target_table?: string; target_column?: string; locked?: boolean }[] =
    Array.isArray(hotwords)
      ? hotwords.map((h: any) => ({
          term: h.term,
          target_table: h.target_table,
          target_column: h.target_column,
          locked: h.locked,
        }))
      : Object.entries(hotwords).map(([term, entry]: [string, any]) => ({
          term,
          target_table: entry?.target_table,
          target_column: entry?.target_column,
          locked: entry?.locked,
        }));

  // ── Render ────────────────────────────────────────
  return (
    <div className="flex-1 overflow-y-auto">
      <div className="max-w-5xl mx-auto px-7 py-6">
        <div className="flex items-center justify-between mb-5">
          <div>
            <h2 className="text-lg font-semibold text-foreground">管理控制台</h2>
            <p className="text-xs text-muted-foreground mt-0.5">
              {activeDsName ? `数据源：${activeDsName}` : "未激活数据源"}
            </p>
          </div>
        </div>

        <Tabs.Root value={tab} onValueChange={setTab}>
          <Tabs.List>
            <Tabs.Tab value="sync">同步状态</Tabs.Tab>
            <Tabs.Tab value="mappings">值映射</Tabs.Tab>
            <Tabs.Tab value="hotwords">热词</Tabs.Tab>
            <Tabs.Tab value="periods">日期周期</Tabs.Tab>
            <Tabs.Tab value="audit">审核策略</Tabs.Tab>
          </Tabs.List>

          {/* ── Sync ─────────────────────────────────── */}
          <Tabs.Panel value="sync">
            <Card>
              <CardHeader className="flex-row items-center justify-between">
                <CardTitle>同步状态</CardTitle>
                <Button variant="ghost" size="sm" onClick={loadSync}>
                  <RefreshCw className="size-3.5" />
                  刷新
                </Button>
              </CardHeader>
              <CardContent>
                {syncLoading ? (
                  <Skeleton className="h-32 w-full" />
                ) : !sync || sync.status === "no_sync_yet" ? (
                  <EmptyState title="暂无同步记录" />
                ) : sync.latest ? (
                  <dl className="text-sm space-y-2">
                    <DefRow label="状态">
                      <SyncStatusBadge s={sync.latest.status} />
                    </DefRow>
                    <DefRow label="类型">{sync.latest.sync_type}</DefRow>
                    <DefRow label="时间">
                      {sync.latest.started_at
                        ? new Date(sync.latest.started_at).toLocaleString("zh-CN")
                        : "—"}
                    </DefRow>
                    <DefRow label="新增表">
                      {String(sync.latest.tables_added ?? "—")}
                    </DefRow>
                    <DefRow label="列变更">
                      {String(sync.latest.columns_changed ?? "—")}
                    </DefRow>
                    {sync.latest.error_message ? (
                      <div className="text-xs text-destructive bg-destructive/5 border border-destructive/20 rounded-md px-3 py-2 font-mono break-all">
                        {sync.latest.error_message}
                      </div>
                    ) : null}
                  </dl>
                ) : null}
              </CardContent>
            </Card>
          </Tabs.Panel>

          {/* ── Mappings ─────────────────────────────── */}
          <Tabs.Panel value="mappings">
            <Card>
              <CardHeader className="flex-row items-center justify-between">
                <CardTitle>值映射</CardTitle>
                <Select
                  value={mappingType}
                  onChange={(e) => setMappingType(e.target.value)}
                  options={MAPPING_OPTIONS}
                  className="w-32"
                />
              </CardHeader>
              <CardContent>
                {!activeDsId ? (
                  <EmptyState title="请先激活数据源" />
                ) : mappingsLoading ? (
                  <Skeleton className="h-24 w-full" />
                ) : mappings.length === 0 ? (
                  <EmptyState title="暂无映射" />
                ) : (
                  <DataTable {...mappingTable(mappingType, mappings)} maxHeight="360px" />
                )}
              </CardContent>
            </Card>
          </Tabs.Panel>

          {/* ── Hotwords ─────────────────────────────── */}
          <Tabs.Panel value="hotwords">
            <Card>
              <CardHeader>
                <CardTitle>
                  热词词典
                  <span className="text-xs text-muted-foreground font-normal ml-2 tabular-nums">
                    {hotwordList.length}
                  </span>
                </CardTitle>
              </CardHeader>
              <CardContent>
                {hotwordsLoading ? (
                  <Skeleton className="h-24 w-full" />
                ) : hotwordList.length === 0 ? (
                  <EmptyState title="暂无热词" />
                ) : (
                  <Table>
                    <THead>
                      <Tr className="bg-muted/60 hover:bg-muted/60">
                        <Th>词</Th>
                        <Th>目标</Th>
                        <Th>状态</Th>
                      </Tr>
                    </THead>
                    <TBody>
                      {hotwordList.map((h, i) => (
                        <Tr key={i} className={i % 2 ? "bg-muted/30" : ""}>
                          <Td className="font-medium">{h.term}</Td>
                          <Td className="font-mono text-xs text-muted-foreground">
                            {h.target_table}.{h.target_column || "*"}
                          </Td>
                          <Td>
                            {h.locked ? <Badge variant="warning">锁定</Badge> : <span className="text-xs text-muted-foreground">—</span>}
                          </Td>
                        </Tr>
                      ))}
                    </TBody>
                  </Table>
                )}
              </CardContent>
            </Card>
          </Tabs.Panel>

          {/* ── Periods ──────────────────────────────── */}
          <Tabs.Panel value="periods">
            <Card>
              <CardHeader>
                <CardTitle>
                  固定日期周期
                  <span className="text-xs text-muted-foreground font-normal ml-2 tabular-nums">
                    {periods.length}
                  </span>
                </CardTitle>
              </CardHeader>
              <CardContent>
                {periodsLoading ? (
                  <Skeleton className="h-24 w-full" />
                ) : periods.length === 0 ? (
                  <EmptyState title="暂无周期" />
                ) : (
                  <DataTable
                    columns={["名称", "起始", "结束"]}
                    rows={periods.map((p: any) => [p.name, p.start, p.end])}
                    maxHeight="360px"
                  />
                )}
              </CardContent>
            </Card>
          </Tabs.Panel>

          {/* ── Audit ────────────────────────────────── */}
          <Tabs.Panel value="audit">
            <Card>
              <CardHeader>
                <CardTitle>审核策略</CardTitle>
              </CardHeader>
              <CardContent>
                {auditLoading ? (
                  <Skeleton className="h-24 w-full" />
                ) : Object.keys(audit).length === 0 ? (
                  <EmptyState title="未配置" />
                ) : (
                  <dl className="text-sm space-y-2">
                    <DefRow label="模式">
                      <Badge variant={audit.mode === "none" ? "success" : "warning"}>
                        {audit.mode === "none" ? "无审核" : audit.mode}
                      </Badge>
                    </DefRow>
                    <DefRow label="数据量阈值">
                      {String(audit.data_threshold ?? "—")}
                    </DefRow>
                    <DefRow label="复杂度阈值">
                      {String(audit.complexity_threshold ?? "—")}
                    </DefRow>
                    {audit.sensitive_tables?.length > 0 ? (
                      <DefRow label="敏感表">
                        {(audit.sensitive_tables as string[]).join(", ")}
                      </DefRow>
                    ) : null}
                  </dl>
                )}
              </CardContent>
            </Card>
          </Tabs.Panel>
        </Tabs.Root>
      </div>
    </div>
  );
}

// ── Helpers ─────────────────────────────────────────

function DefRow({ label, children }: { label: string; children: React.ReactNode }) {
  return (
    <div className="flex gap-3">
      <dt className="text-muted-foreground w-24 shrink-0">{label}</dt>
      <dd className="text-foreground flex-1 min-w-0">{children}</dd>
    </div>
  );
}

function SyncStatusBadge({ s }: { s: string }) {
  if (s === "success") return <Badge variant="success">成功</Badge>;
  if (s === "running") return <Badge variant="default">运行中</Badge>;
  if (s === "failed") return <Badge variant="destructive">失败</Badge>;
  return <Badge variant="outline">{s}</Badge>;
}

function mappingTable(type: string, items: MappingItem[]): {
  columns: string[];
  rows: unknown[][];
} {
  if (type === "region") {
    return {
      columns: ["代码", "名称"],
      rows: items.map((m) => [m.code ?? "", m.name ?? ""]),
    };
  }
  if (type === "name") {
    return {
      columns: ["简称", "全称"],
      rows: items.map((m) => [m.short_name ?? "", m.full_name ?? ""]),
    };
  }
  return {
    columns: ["表.列", "值", "显示"],
    rows: items.map((m) => [
      `${m.table_name}.${m.column_name}`,
      m.value ?? "",
      m.display ?? "",
    ]),
  };
}
