"use client";
/* eslint-disable react-hooks/set-state-in-effect -- form state is intentionally reset when the dialog opens / `initial` changes */

import { useState, useEffect, useRef, useId, useCallback } from "react";
import { X } from "lucide-react";
import { Dialog, Button, Input, Textarea, Select, Field } from "@/components/ui";

interface FormData {
  name: string;
  engine: string;
  host: string;
  port: string;
  username: string;
  password: string;
  database: string;
  schema_whitelist: string;
}

interface FieldError {
  field: string;
  message: string;
}

interface DataSourceFormProps {
  open: boolean;
  /** If provided, edit mode */
  initial?: {
    name: string;
    engine: string;
    host: string;
    port: number;
    username: string;
    database: string;
    schema_whitelist?: Record<string, string>[] | null;
  } | null;
  onSave: (data: Record<string, unknown>) => Promise<void>;
  onClose: () => void;
}

const EMPTY_FORM: FormData = {
  name: "",
  engine: "postgresql",
  host: "",
  port: "5432",
  username: "",
  password: "",
  database: "",
  schema_whitelist: "",
};

const ENGINE_OPTIONS = [
  { value: "postgresql", label: "PostgreSQL" },
  { value: "mysql", label: "MySQL" },
];

export function DataSourceForm({ open, initial, onSave, onClose }: DataSourceFormProps) {
  const [form, setForm] = useState<FormData>(EMPTY_FORM);
  const [errors, setErrors] = useState<FieldError[]>([]);
  const [saving, setSaving] = useState(false);
  const [showPassword, setShowPassword] = useState(false);
  const [dirty, setDirty] = useState(false);

  const titleId = useId();
  const nameInputRef = useRef<HTMLInputElement>(null);

  const isEdit = !!initial;

  useEffect(() => {
    if (!open) return;
    if (initial) {
      setForm({
        name: initial.name,
        engine: initial.engine,
        host: initial.host,
        port: String(initial.port),
        username: initial.username,
        password: "", // don't backfill password
        database: initial.database,
        schema_whitelist: initial.schema_whitelist
          ? JSON.stringify(initial.schema_whitelist, null, 2)
          : "",
      });
    } else {
      setForm(EMPTY_FORM);
    }
    setErrors([]);
    setSaving(false);
    setShowPassword(false);
    setDirty(false);
  }, [open, initial]);

  // Close handler that warns about unsaved edits (Esc / backdrop handled by base-ui Dialog)
  const requestClose = useCallback(() => {
    if (saving) return;
    if (dirty && !window.confirm("有未保存的更改，确定要关闭吗？")) return;
    onClose();
  }, [dirty, saving, onClose]);

  if (!open) return null;

  const validate = (): FieldError[] => {
    const errs: FieldError[] = [];
    if (!form.name.trim()) errs.push({ field: "name", message: "名称不能为空" });
    if (!["postgresql", "mysql"].includes(form.engine))
      errs.push({ field: "engine", message: "引擎必须是 postgresql 或 mysql" });
    if (!form.host.trim()) errs.push({ field: "host", message: "主机不能为空" });
    const port = Number(form.port);
    if (!Number.isInteger(port) || port < 1 || port > 65535)
      errs.push({ field: "port", message: "端口范围 1–65535" });
    if (!form.username.trim()) errs.push({ field: "username", message: "用户名不能为空" });
    if (!isEdit && !form.password.trim())
      errs.push({ field: "password", message: "密码不能为空" });
    if (!form.database.trim()) errs.push({ field: "database", message: "数据库名不能为空" });
    if (form.schema_whitelist.trim()) {
      try {
        JSON.parse(form.schema_whitelist);
      } catch {
        errs.push({ field: "schema_whitelist", message: "Schema 白名单需为有效 JSON" });
      }
    }
    return errs;
  };

  const errFor = (field: string) => errors.find((e) => e.field === field);

  const handleSave = async () => {
    const errs = validate();
    if (errs.length > 0) {
      setErrors(errs);
      const firstField = errs[0].field;
      if (firstField !== "_form") {
        window.setTimeout(() => {
          (
            document.querySelector(`[name="${firstField}"]`) as HTMLElement | null
          )?.focus();
        }, 0);
      }
      return;
    }
    setSaving(true);
    setErrors([]);
    try {
      const data: Record<string, unknown> = {
        name: form.name.trim(),
        engine: form.engine,
        host: form.host.trim(),
        port: Number(form.port),
        username: form.username.trim(),
        password: form.password,
        database: form.database.trim(),
      };
      if (form.schema_whitelist.trim()) {
        data.schema_whitelist = JSON.parse(form.schema_whitelist);
      }
      await onSave(data);
      setDirty(false);
      onClose();
    } catch (e: unknown) {
      const msg = (e as Error).message || "保存失败";
      setErrors([{ field: "_form", message: msg }]);
    } finally {
      setSaving(false);
    }
  };

  const set =
    (field: keyof FormData) =>
    (
      e: React.ChangeEvent<
        HTMLInputElement | HTMLSelectElement | HTMLTextAreaElement
      >,
    ) => {
      setForm((f) => ({ ...f, [field]: e.target.value }));
      setErrors((prev) => prev.filter((err) => err.field !== field && err.field !== "_form"));
      setDirty(true);
    };

  return (
    <Dialog.Root
      open={open}
      onOpenChange={(o) => {
        if (!o) requestClose();
      }}
    >
      <Dialog.Content side="right">
        {/* Header */}
        <div className="px-6 py-5 border-b border-border flex items-center justify-between shrink-0">
          <Dialog.Title id={titleId} className="text-base font-semibold text-foreground">
            {isEdit ? "编辑数据源" : "新建数据源"}
          </Dialog.Title>
          <Dialog.Close
            aria-label="关闭"
            className="text-muted-foreground hover:text-foreground transition-colors"
          >
            <X className="size-5" />
          </Dialog.Close>
        </div>

        {/* Body */}
        <div className="flex-1 overflow-y-auto px-6 py-5 space-y-4">
          {errFor("_form") ? (
            <div
              role="alert"
              className="px-3 py-2.5 rounded-lg bg-destructive/10 border border-destructive/30 text-sm text-destructive"
            >
              {errFor("_form")!.message}
            </div>
          ) : null}

          <Field label="名称" required error={errFor("name")?.message}>
            <Input
              ref={nameInputRef}
              name="name"
              autoComplete="off"
              value={form.name}
              onChange={set("name")}
              placeholder="例如：生产数据库"
            />
          </Field>

          <Field label="引擎" required error={errFor("engine")?.message}>
            <Select
              name="engine"
              autoComplete="off"
              value={form.engine}
              onChange={set("engine")}
              options={ENGINE_OPTIONS}
            />
          </Field>

          <div className="flex gap-3">
            <div className="flex-1">
              <Field label="主机" required error={errFor("host")?.message}>
                <Input
                  name="host"
                  autoComplete="off"
                  value={form.host}
                  onChange={set("host")}
                  placeholder="localhost"
                />
              </Field>
            </div>
            <div className="w-[120px]">
              <Field label="端口" required error={errFor("port")?.message}>
                <Input
                  type="number"
                  name="port"
                  inputMode="numeric"
                  autoComplete="off"
                  value={form.port}
                  onChange={set("port")}
                />
              </Field>
            </div>
          </div>

          <div className="flex gap-3">
            <div className="flex-1">
              <Field label="用户名" required error={errFor("username")?.message}>
                <Input
                  name="username"
                  autoComplete="username"
                  value={form.username}
                  onChange={set("username")}
                />
              </Field>
            </div>
            <div className="flex-1">
              <Field
                label="密码"
                required={!isEdit}
                error={errFor("password")?.message}
              >
                <div className="relative">
                  <Input
                    type={showPassword ? "text" : "password"}
                    name="password"
                    autoComplete={isEdit ? "current-password" : "new-password"}
                    value={form.password}
                    onChange={set("password")}
                    placeholder={isEdit ? "留空不修改" : ""}
                    className="pr-14"
                  />
                  <button
                    type="button"
                    onClick={() => setShowPassword((v) => !v)}
                    className="absolute right-2 top-1/2 -translate-y-1/2 text-xs text-muted-foreground hover:text-foreground"
                  >
                    {showPassword ? "隐藏" : "显示"}
                  </button>
                </div>
              </Field>
            </div>
          </div>

          <Field label="数据库" required error={errFor("database")?.message}>
            <Input
              name="database"
              autoComplete="off"
              value={form.database}
              onChange={set("database")}
              placeholder="例如：chat_db"
            />
          </Field>

          <Field
            label="Schema 白名单 (JSON)"
            error={errFor("schema_whitelist")?.message}
            hint="可选，限制同步范围"
          >
            <Textarea
              name="schema_whitelist"
              autoComplete="off"
              value={form.schema_whitelist}
              onChange={set("schema_whitelist")}
              placeholder='[{"schema": "public", "tables": ["orders"]}]'
              rows={4}
              className="font-mono text-xs"
            />
          </Field>
        </div>

        {/* Footer */}
        <div className="px-6 py-4 border-t border-border flex justify-end gap-3 bg-background shrink-0">
          <Button variant="outline" onClick={requestClose} disabled={saving}>
            取消
          </Button>
          <Button onClick={handleSave} disabled={saving}>
            {saving ? "保存中…" : "保存"}
          </Button>
        </div>
      </Dialog.Content>
    </Dialog.Root>
  );
}
