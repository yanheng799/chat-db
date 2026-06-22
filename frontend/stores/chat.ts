import { create } from "zustand";
import { api } from "@/lib/api";
import { useAdminStore } from "@/stores/admin";

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

// Inactivity cap on a single SSE query: abort only if the stream stays
// silent longer than this. The backend streams a `status` event per pipeline
// phase (semantic → normalize → generate → sql → security → execute), so a
// healthy long-running query keeps resetting this timer; it only fires when
// the connection is truly stuck. Tune via NEXT_PUBLIC_SSE_IDLE_TIMEOUT_MS
// (milliseconds).
const SSE_IDLE_TIMEOUT_MS = Number(process.env.NEXT_PUBLIC_SSE_IDLE_TIMEOUT_MS) || 120_000;

// Maps a streamed pipeline phase to its progress-step index.
// Intermediate phases (normalize, generate) update the status message
// without advancing the progress bar — the bar steps only when a
// meaningful milestone is reached.
const PHASE_STEP: Record<string, number> = {
  semantic: 0,   // 语义匹配完成 → step 0 done, step 1 active
  normalize: 0,  // still in preparation, status text only
  generate: 1,   // SQL 生成中 → step 1 active
  sql: 1,        // SQL + security done → step 1 done, step 2 active
  security: 2,   // security done → step 2 done, step 3 active
  execute: 3,    // execution done → step 3 done
};

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
  /** Fetch the list of known sessions from the backend */
  loadConversations: () => Promise<void>;
  /** Start a brand-new session */
  createSession: () => Promise<void>;
  /** Delete a session (local + remote) */
  deleteConversation: (sid: string) => Promise<void>;
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
  //
  // SSE transport: a plain `fetch` + manual `ReadableStream` reader.
  //
  // We deliberately do NOT use @microsoft/fetch-event-source here. That
  // library auto-reconnects whenever the stream closes (onclose does not
  // throw by default), which for a *POST* SSE endpoint means silently
  // re-POSTing the same query — exactly the "duplicate message" bug we hit:
  // the first POST would drop after the `starting` event (transient network
  // blip / fragile done·abort race), the library reconnected, re-POSTed, and
  // the backend's dedup guard returned 409. Manual reading gives full
  // control: a closed stream just exits the loop. No reconnect, ever.

  sendQuery: async (text: string) => {
    const state = get();
    console.warn("[sendQuery] called", { text, queryState: state.queryState });
    if (state.queryState === "running") return;

    // Cancel any in-flight request
    state._abortController?.abort();

    const ctrl = new AbortController();
    // Inactivity timer: reset on every SSE event. Aborts only when the stream
    // is silent past the threshold (truly stuck) — a healthy long-running
    // query keeps emitting phase events and stays alive.
    let idleTimer: ReturnType<typeof setTimeout> | null = null;
    let abortedByTimeout = false;
    let streamDone = false;  // set true when `done` event arrives
    const resetIdleTimer = () => {
      if (idleTimer) clearTimeout(idleTimer);
      idleTimer = setTimeout(() => {
        abortedByTimeout = true;
        ctrl.abort();
      }, SSE_IDLE_TIMEOUT_MS);
    };
    const clearIdleTimer = () => {
      if (idleTimer) {
        clearTimeout(idleTimer);
        idleTimer = null;
      }
    };
    resetIdleTimer();

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

    // Mark a phase's step done and the next one active.
    const markStepDone = (idx: number) =>
      set((s) => ({
        progressSteps: s.progressSteps.map((step, i) => {
          if (i === idx) return { ...step, status: "done" as const };
          if (i === idx + 1) return { ...step, status: "active" as const };
          return step;
        }),
      }));

    // Dispatch one parsed SSE payload to the UI. Extracted from the old
    // fetchEventSource `onmessage` — behavior unchanged.
    const handleEvent = (data: Record<string, unknown>) => {
      const eventType = data.type as string;
      switch (eventType) {
        case "status": {
          const msg = data.message as string;
          const phase = data.phase as string | undefined;
          set((s) => ({
            messages: s.messages.map((m) => {
              if (m.id !== sysMsg.id) return m;
              // If result already arrived, keep it as-is + add summary
              if (m.content === "result") return { ...m, summary: msg };
              return { ...m, content: msg };
            }),
          }));
          // Phase-driven progress: set the step for this phase.
          if (phase && phase in PHASE_STEP) markStepDone(PHASE_STEP[phase]);
          break;
        }
        case "result": {
          const resultData = data.data as Record<string, unknown> | undefined;
          const columns = resultData?.columns as string[] | undefined;
          const rows = resultData?.rows as unknown[][] | undefined;
          const sql = data.sql as string | undefined;
          set((s) => ({
            messages: s.messages.map((m) =>
              m.id === sysMsg.id
                ? { ...m, content: "result", sql, columns, rows }
                : m
            ),
          }));
          markStepDone(3); // execute done
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
          const items = (data.items as NonNullable<Message["confirmItems"]>) || [];
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
          streamDone = true;
          set({
            queryState: "idle",
            _abortController: null,
            progressSteps: get().progressSteps.map((step) => ({
              ...step,
              status: "done" as const,
            })),
          });
          // Auto-name and persist the new session in the sidebar
          const cur = get();
          if (!cur.conversations.some((c) => c.id === cur.sessionId)) {
            cur.addConversation({
              id: cur.sessionId!,
              title: text.slice(0, 24),
              time: new Date().toLocaleTimeString("zh-CN", { hour: "2-digit", minute: "2-digit" }),
            });
          }
          break;
        }
      }
    };

    try {
      const resp = await fetch(`${api.base}/api/query`, {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          "X-Session-Id": state.sessionId || "",
        },
        body: JSON.stringify({
          text,
          data_source_id: useAdminStore.getState().activeDataSourceId || undefined,
        }),
        signal: ctrl.signal,
      });

      resetIdleTimer();

      if (!resp.ok) {
        // 409 = backend dedup. With manual streaming there is no
        // auto-reconnect, so this is now only a defensive net — drop it
        // silently; the original in-flight query owns this sysMsg.
        if (resp.status === 409) {
          set({ queryState: "idle", _abortController: null });
          return;
        }
        const errBody = await resp.text().catch(() => "");
        throw new Error(errBody || `HTTP ${resp.status}`);
      }

      // If backend created a new session for us, capture its ID
      const sid = resp.headers.get("X-Session-Id");
      if (sid && !get().sessionId) {
        set({ sessionId: sid });
      }

      if (!resp.body) {
        throw new Error("empty SSE response body");
      }

      // Read the SSE stream manually. CRITICAL: no reconnect loop — a closed
      // stream simply exits. SSE events are separated by a blank line (\n\n);
      // each event's payload is on a `data:` line. Backend keepalive comments
      // (`: keepalive`) carry no payload and are skipped.
      const reader = resp.body.getReader();
      const decoder = new TextDecoder();
      let buffer = "";

      while (!streamDone) {
        const { done, value } = await reader.read();
        if (done) break;  // server closed the stream
        resetIdleTimer();
        buffer += decoder.decode(value, { stream: true });

        let sep: number;
        while ((sep = buffer.indexOf("\n\n")) !== -1) {
          const raw = buffer.slice(0, sep);
          buffer = buffer.slice(sep + 2);
          const dataLine = raw.split("\n").find((l) => l.startsWith("data:"));
          if (!dataLine) continue;  // keepalive comment / blank
          let data: Record<string, unknown>;
          try {
            data = JSON.parse(dataLine.slice(5).trimStart());
          } catch {
            continue;
          }
          handleEvent(data);
          if (streamDone) break;
        }
      }
      // Release the reader so the underlying connection is reclaimed promptly
      // (we may have broken out on the `done` event before the server's
      // stream-end reached us).
      reader.cancel().catch(() => {});
    } catch (err: unknown) {
      const aborted = err instanceof Error && err.name === "AbortError";

      if (streamDone) {
        // `done` event already processed — normal completion.
        set({ queryState: "idle", _abortController: null });
        return;
      }
      if (abortedByTimeout) {
        // Idle timer fired — the stream went silent past the threshold.
        set((s) => ({
          queryState: "idle",
          _abortController: null,
          messages: s.messages.map((m) =>
            m.id === sysMsg.id ? { ...m, content: "❌ 查询超时（长时间无响应，已断开）" } : m
          ),
          progressSteps: s.progressSteps.map((step) =>
            step.status === "active" ? { ...step, status: "error" as const } : step
          ),
        }));
        return;
      }
      if (aborted) {
        // User cancelled (or session switch aborted the in-flight stream).
        set({ queryState: "idle", _abortController: null });
        return;
      }
      // Genuine transport error (network drop, non-2xx, parse). Show once;
      // never auto-retry — the user can resend explicitly.
      const message = err instanceof Error ? `❌ ${err.message}` : `❌ ${String(err)}`;
      set((s) => ({
        queryState: "idle",
        _abortController: null,
        messages: s.messages.map((m) =>
          m.id === sysMsg.id ? { ...m, content: message } : m
        ),
      }));
    } finally {
      clearIdleTimer();
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
      type BackendTurn = { user: string; assistant: string; sql?: string };
      const data = await api.get<{ turns?: BackendTurn[] }>(`/api/conversations/${sid}`);
      const turns = data.turns || [];
      const msgs: Message[] = [];
      for (const t of turns) {
        msgs.push({
          id: crypto.randomUUID(),
          role: "user",
          content: t.user,
          timestamp: Date.now(),
        });
        // Reconstruct system message: if SQL was stored, render as result
        const hasResult = !!t.sql;
        msgs.push({
          id: crypto.randomUUID(),
          role: "system",
          content: hasResult ? "result" : t.assistant,
          sql: t.sql,
          summary: hasResult ? t.assistant : undefined,
          timestamp: Date.now(),
        });
      }
      set({ messages: msgs });
    } catch (e) {
      console.error("switchSession failed:", e);
    }
  },

  // ── loadConversations ───────────────────────────────

  loadConversations: async () => {
    try {
      const data = await api.get<{ sessions: { session_id: string; title: string }[] }>("/api/conversations");
      const existing = get().conversations;
      const seen = new Set(existing.map((c) => c.id));
      const merged = [...existing];
      for (const s of (data.sessions || [])) {
        if (!seen.has(s.session_id)) {
          merged.push({
            id: s.session_id,
            title: s.title || s.session_id.slice(0, 8) + "…",
            time: "",
          });
        }
      }
      set({ conversations: merged });
    } catch {
      // silently fail
    }
  },

  // ── deleteConversation ───────────────────────────────

  deleteConversation: async (sid: string) => {
    get()._abortController?.abort();
    try {
      await api.delete(`/api/conversations/${sid}`);
    } catch (e) {
      console.error("deleteConversation failed:", e);
      return; // don't remove from local list if server delete failed
    }
    set((s) => ({
      conversations: s.conversations.filter((c) => c.id !== sid),
      ...(s.sessionId === sid ? { sessionId: null, messages: [] } : {}),
    }));
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
