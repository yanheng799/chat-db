import { create } from "zustand";
import { fetchEventSource } from "@microsoft/fetch-event-source";
import { api } from "@/lib/api";

// ── Types ──────────────────────────────────────────────

export interface Message {
  id: string;
  role: "user" | "system";
  content: string;
  timestamp: number;
  /** Rich payload from result event */
  sql?: string;
  columns?: string[];
  rows?: unknown[][];
  queryId?: string;
  /** need_confirm items */
  confirmItems?: { field?: string; reason?: string; value?: string }[];
  /** Summary text (shown below result) */
  summary?: string;
}

export interface Conversation {
  id: string;
  title: string;
  time: string;
}

export interface ProgressStep {
  label: string;
  status: "idle" | "active" | "done" | "error";
}

const DEFAULT_STEPS: ProgressStep[] = [
  { label: "语义匹配", status: "idle" },
  { label: "SQL 生成", status: "idle" },
  { label: "安全校验", status: "idle" },
  { label: "执行", status: "idle" },
];

// ── Store ──────────────────────────────────────────────

interface ChatState {
  sessionId: string | null;
  conversations: Conversation[];
  messages: Message[];
  queryState: "idle" | "running" | "await_confirm";
  progressSteps: ProgressStep[];
  backendUnreachable: boolean;
  _abortController: AbortController | null;

  setSessionId: (id: string) => void;
  addConversation: (conv: Conversation) => void;
  updateConversationTitle: (title: string) => void;
  addMessage: (msg: Message) => void;
  updateMessage: (id: string, content: string) => void;
  setQueryState: (state: "idle" | "running" | "await_confirm") => void;
  setBackendUnreachable: (v: boolean) => void;
  /** Send a natural-language query via SSE */
  sendQuery: (text: string) => Promise<void>;
  /** Cancel the in-flight SSE connection */
  cancelQuery: () => void;
  /** Switch to a different session, loading history */
  switchSession: (sid: string) => Promise<void>;
  /** Start a brand-new session */
  createSession: () => Promise<void>;
  /** Confirm an await_confirm query */
  confirmQuery: (msgId: string) => Promise<void>;
  /** Cancel an await_confirm query */
  cancelConfirm: (msgId: string) => void;
}

export const useChatStore = create<ChatState>((set, get) => ({
  sessionId: null,
  conversations: [],
  messages: [],
  queryState: "idle",
  progressSteps: DEFAULT_STEPS.map((s) => ({ ...s })),
  backendUnreachable: false,
  _abortController: null,

  setSessionId: (id) => set({ sessionId: id }),

  addConversation: (conv) =>
    set((s) => ({ conversations: [conv, ...s.conversations] })),

  updateConversationTitle: (title) =>
    set((s) => {
      if (s.conversations.length === 0) return s;
      const updated = [...s.conversations];
      if (updated[0].title === "新建会话") {
        updated[0] = { ...updated[0], title: title.slice(0, 24) };
      }
      return { conversations: updated };
    }),

  addMessage: (msg) => set((s) => ({ messages: [...s.messages, msg] })),

  updateMessage: (id, content) =>
    set((s) => ({
      messages: s.messages.map((m) => (m.id === id ? { ...m, content } : m)),
    })),

  setQueryState: (queryState) => set({ queryState }),
  setBackendUnreachable: (v) => set({ backendUnreachable: v }),

  // ── sendQuery ──────────────────────────────────────

  sendQuery: async (text: string) => {
    const state = get();
    if (state.queryState === "running") return;

    // Cancel any in-flight request
    state._abortController?.abort();

    const ctrl = new AbortController();
    const timeout = setTimeout(() => ctrl.abort(), 60000);

    const userMsg: Message = {
      id: crypto.randomUUID(),
      role: "user",
      content: text,
      timestamp: Date.now(),
    };
    const sysMsg: Message = {
      id: crypto.randomUUID(),
      role: "system",
      content: "思考中…",
      timestamp: Date.now(),
    };

    set({
      queryState: "running",
      _abortController: ctrl,
      progressSteps: DEFAULT_STEPS.map((s, i) => ({
        ...s,
        status: i === 0 ? "active" : "idle",
      })),
      messages: [...state.messages, userMsg, sysMsg],
    });

    let stepIndex = 0;

    const advanceProgress = () => {
      if (stepIndex < 4) {
        set((s) => ({
          progressSteps: s.progressSteps.map((step, i) => {
            if (i === stepIndex) return { ...step, status: "done" as const };
            if (i === stepIndex + 1) return { ...step, status: "active" as const };
            return step;
          }),
        }));
        stepIndex++;
      }
    };

    try {
      await fetchEventSource(`${api.base}/api/query`, {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          "X-Session-Id": state.sessionId || "",
        },
        body: JSON.stringify({ text }),
        signal: ctrl.signal,
        async onopen(response) {
          if (!response.ok) {
            const body = await response.text();
            throw new Error(body || `HTTP ${response.status}`);
          }
        },
        onmessage(event) {
          let data: Record<string, unknown>;
          try {
            data = JSON.parse(event.data);
          } catch {
            return;
          }
          const eventType = data.type as string;

          switch (eventType) {
            case "status": {
              const msg = data.message as string;
              set((s) => ({
                messages: s.messages.map((m) => {
                  if (m.id !== sysMsg.id) return m;
                  // If result already arrived, keep it as-is + add summary
                  if (m.content === "result") return { ...m, summary: msg };
                  return { ...m, content: msg };
                }),
              }));
              // Trigger-based progress: each status event advances one step
              advanceProgress();
              break;
            }
            case "result": {
              const resultData = data.data as Record<string, unknown> | undefined;
              const columns = resultData?.columns as string[] | undefined;
              const rows = resultData?.rows as unknown[][] | undefined;
              const sql = data.sql as string | undefined;
              console.log("[SSE] result event:", { sql, columns, rows, hasData: !!resultData });
              set((s) => ({
                messages: s.messages.map((m) =>
                  m.id === sysMsg.id
                    ? { ...m, content: "result", sql, columns, rows }
                    : m
                ),
              }));
              // result → step4 done (trigger-based)
              advanceProgress();
              break;
            }
            case "error": {
              const detail = (data.detail as string) || "未知错误";
              set((s) => ({
                messages: s.messages.map((m) =>
                  m.id === sysMsg.id
                    ? { ...m, content: `❌ ${detail}` }
                    : m
                ),
                progressSteps: s.progressSteps.map((step) =>
                  step.status === "active" ? { ...step, status: "error" as const } : step
                ),
                queryState: "idle",
              }));
              break;
            }
            case "need_confirm": {
              const items = (data.items as any[]) || [];
              const confirmSql = (data.sql as string) || undefined;
              const informational = data.informational === true;
              set((s) => ({
                messages: s.messages.map((m) => {
                  if (m.id !== sysMsg.id) return m;
                  // If result already arrived, don't override — just add notes
                  if (m.content === "result" || informational) {
                    return { ...m, confirmItems: items };
                  }
                  // No result yet — show confirm card
                  return { ...m, content: "confirm", confirmItems: items, sql: confirmSql };
                }),
                // Only block on non-informational confirm
                queryState: informational ? s.queryState : "await_confirm",
              }));
              break;
            }
            case "done": {
              set((s) => ({
                queryState: "idle",
                _abortController: null,
                progressSteps: s.progressSteps.map((step) => ({
                  ...step,
                  status: "done" as const,
                })),
              }));
              break;
            }
          }
        },
        onerror(err) {
          clearTimeout(timeout);
          set((s) => ({
            queryState: "idle",
            _abortController: null,
            messages: s.messages.map((m) =>
              m.id === sysMsg.id
                ? { ...m, content: `❌ 连接中断: ${String(err)}` }
                : m
            ),
            progressSteps: s.progressSteps.map((step) =>
              step.status === "active" ? { ...step, status: "error" as const } : step
            ),
          }));
          // Don't throw → stops retry
          throw err;
        },
      });
    } catch (err: unknown) {
      clearTimeout(timeout);
      const message =
        err instanceof Error
          ? err.name === "AbortError"
            ? undefined // user cancelled — no update
            : `❌ ${err.message}`
          : `❌ ${String(err)}`;
      if (message) {
        set((s) => ({
          queryState: "idle",
          _abortController: null,
          messages: s.messages.map((m) =>
            m.id === sysMsg.id ? { ...m, content: message } : m
          ),
        }));
      } else {
        set({ queryState: "idle", _abortController: null });
      }
    }
  },

  // ── cancelQuery ─────────────────────────────────────

  cancelQuery: () => {
    const { _abortController } = get();
    if (_abortController) {
      _abortController.abort();
      set({ queryState: "idle", _abortController: null });
    }
  },

  // ── confirmQuery ───────────────────────────────────

  confirmQuery: async (msgId: string) => {
    set({ queryState: "running" });
    try {
      await api.post("/api/query/placeholder/confirm", { confirmed: true });
      set((s) => ({
        messages: s.messages.map((m) =>
          m.id === msgId ? { ...m, content: "已确认，继续处理中…", confirmItems: undefined } : m
        ),
      }));
    } catch {
      set({ queryState: "await_confirm" });
    }
  },

  // ── cancelConfirm ──────────────────────────────────

  cancelConfirm: (msgId: string) => {
    set((s) => ({
      queryState: "idle",
      messages: s.messages.map((m) =>
        m.id === msgId ? { ...m, content: "已取消查询", confirmItems: undefined } : m
      ),
    }));
  },

  // ── switchSession ───────────────────────────────────

  switchSession: async (sid: string) => {
    // Abort any in-flight query
    get()._abortController?.abort();

    set({ sessionId: sid, messages: [], queryState: "idle", _abortController: null });
    try {
      const data = await api.get<{
        turns?: { role: string; content: string }[];
      }>(`/api/conversations/${sid}`);
      const turns = data.turns || [];
      const msgs: Message[] = turns.map((t) => ({
        id: crypto.randomUUID(),
        role: t.role === "user" ? "user" : "system",
        content: t.content,
        timestamp: Date.now(),
      }));
      set({ messages: msgs });
    } catch {
      // session may not exist yet — stay on empty
    }
  },

  // ── createSession ───────────────────────────────────

  createSession: async () => {
    get()._abortController?.abort();
    try {
      const data = await api.post<{ session_id: string }>("/api/session");
      const sid = data.session_id;
      const conv: Conversation = {
        id: sid,
        title: "新建会话",
        time: new Date().toLocaleTimeString("zh-CN", {
          hour: "2-digit",
          minute: "2-digit",
        }),
      };
      set({
        sessionId: sid,
        messages: [],
        queryState: "idle",
        _abortController: null,
      });
      set((s) => ({ conversations: [conv, ...s.conversations] }));
    } catch {
      // silently fail — user can still query
    }
  },
}));
