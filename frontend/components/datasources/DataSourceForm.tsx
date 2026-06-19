"use client";

import { useState, useEffect } from "react";

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

export function DataSourceForm({
  open,
  initial,
  onSave,
  onClose,
}: DataSourceFormProps) {
  const [form, setForm] = useState<FormData>(EMPTY_FORM);
  const [errors, setErrors] = useState<FieldError[]>([]);
  const [saving, setSaving] = useState(false);
  const [showPassword, setShowPassword] = useState(false);

  useEffect(() => {
    if (open) {
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
    }
  }, [open, initial]);

  if (!open) return null;

  const isEdit = !!initial;

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
    if (!isEdit && !form.password.trim()) errs.push({ field: "password", message: "密码不能为空" });
    if (!form.database.trim()) errs.push({ field: "database", message: "数据库名不能为空" });
    // Validate schema_whitelist JSON if provided
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
      onClose();
    } catch (e: unknown) {
      const msg = (e as Error).message || "保存失败";
      setErrors([{ field: "_form", message: msg }]);
    } finally {
      setSaving(false);
    }
  };

  const set = (field: keyof FormData) => (e: React.ChangeEvent<HTMLInputElement | HTMLSelectElement | HTMLTextAreaElement>) => {
    setForm((f) => ({ ...f, [field]: e.target.value }));
    setErrors((prev) => prev.filter((err) => err.field !== field && err.field !== "_form"));
  };

  return (
    <div className="fixed inset-0 z-40 flex justify-end">
      {/* Backdrop */}
      <div className="absolute inset-0 bg-black/60" onClick={onClose} />

      {/* Slide-over panel */}
      <div className="relative z-10 w-[480px] max-w-[92vw] bg-background border-l border-border h-full overflow-y-auto shadow-2xl animate-in slide-in-from-right">
        {/* Header */}
        <div className="px-6 py-5 border-b border-border flex items-center justify-between sticky top-0 bg-background z-10">
          <h2 className="text-base font-semibold text-foreground">
            {isEdit ? "编辑数据源" : "新建数据源"}
          </h2>
          <button
            onClick={onClose}
            className="text-muted-foreground hover:text-foreground transition-colors text-lg leading-none"
            aria-label="关闭"
          >
            ✕
          </button>
        </div>

        {/* Form body */}
        <div className="px-6 py-5 space-y-4">
          {/* Global form error */}
          {errFor("_form") && (
            <div className="px-3 py-2.5 rounded-lg bg-destructive/10 border border-destructive/30 text-sm text-red-400">
              {errFor("_form")!.message}
            </div>
          )}

          {/* Name */}
          <Field label="名称" required error={errFor("name")?.message}>
            <input
              type="text"
              value={form.name}
              onChange={set("name")}
              placeholder="例如：生产数据库"
              className={inputClass}
            />
          </Field>

          {/* Engine */}
          <Field label="引擎" required error={errFor("engine")?.message}>
            <select value={form.engine} onChange={set("engine")} className={inputClass}>
              <option value="postgresql">PostgreSQL</option>
              <option value="mysql">MySQL</option>
            </select>
          </Field>

          {/* Host + Port */}
          <div className="flex gap-3">
            <div className="flex-1">
              <Field label="主机" required error={errFor("host")?.message}>
                <input
                  type="text"
                  value={form.host}
                  onChange={set("host")}
                  placeholder="localhost"
                  className={inputClass}
                />
              </Field>
            </div>
            <div className="w-[120px]">
              <Field label="端口" required error={errFor("port")?.message}>
                <input
                  type="number"
                  value={form.port}
                  onChange={set("port")}
                  className={inputClass}
                />
              </Field>
            </div>
          </div>

          {/* Username + Password */}
          <div className="flex gap-3">
            <div className="flex-1">
              <Field label="用户名" required error={errFor("username")?.message}>
                <input
                  type="text"
                  value={form.username}
                  onChange={set("username")}
                  className={inputClass}
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
                  <input
                    type={showPassword ? "text" : "password"}
                    value={form.password}
                    onChange={set("password")}
                    placeholder={isEdit ? "留空不修改" : ""}
                    className={inputClass + " pr-16"}
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

          {/* Database */}
          <Field label="数据库" required error={errFor("database")?.message}>
            <input
              type="text"
              value={form.database}
              onChange={set("database")}
              placeholder="例如：chat_db"
              className={inputClass}
            />
          </Field>

          {/* Schema whitelist */}
          <Field label="Schema 白名单 (JSON)" error={errFor("schema_whitelist")?.message}>
            <textarea
              value={form.schema_whitelist}
              onChange={set("schema_whitelist")}
              placeholder='[{"schema": "public", "tables": ["orders"]}]'
              rows={4}
              className={inputClass + " font-mono text-xs"}
            />
          </Field>
        </div>

        {/* Footer */}
        <div className="px-6 py-4 border-t border-border sticky bottom-0 bg-background flex justify-end gap-3">
          <button
            onClick={onClose}
            disabled={saving}
            className="px-4 py-2 rounded-lg text-sm font-medium border border-border text-foreground hover:bg-secondary transition-colors"
          >
            取消
          </button>
          <button
            onClick={handleSave}
            disabled={saving}
            className="px-5 py-2 rounded-lg text-sm font-semibold bg-primary text-primary-foreground hover:brightness-110 transition-all disabled:opacity-50"
          >
            {saving ? "保存中…" : "保存"}
          </button>
        </div>
      </div>
    </div>
  );
}

// ── Small inline field wrapper ────────────────────────

function Field({
  label,
  required,
  error,
  children,
}: {
  label: string;
  required?: boolean;
  error?: string;
  children: React.ReactNode;
}) {
  return (
    <label className="block">
      <span className="text-xs font-medium text-foreground/80 mb-1.5 block">
        {label}
        {required && <span className="text-red-400 ml-0.5">*</span>}
      </span>
      {children}
      {error && (
        <span className="text-xs text-red-400 mt-1 block">{error}</span>
      )}
    </label>
  );
}

const inputClass =
  "w-full px-3 py-2.5 bg-secondary border border-border rounded-lg text-sm text-foreground placeholder:text-muted-foreground outline-none transition-colors focus:border-primary disabled:opacity-50";
