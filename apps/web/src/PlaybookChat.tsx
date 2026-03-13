import { useEffect, useRef, useMemo, useState, useCallback } from "react";
import { useNavigate } from "react-router-dom";
import ReactMarkdown from "react-markdown";

type Step = { tool: string; input: Record<string, unknown> };
type Message = {
  role: "user" | "assistant";
  content: string;
  steps?: Step[];
  streaming?: boolean;
  playbook?: string;   // which playbook the router selected for this response
};
type Session = {
  session_id: string;
  playbook_name: string | null;
  document_id: string | null;
  title: string | null;
  created_at: string;
};

const TOOL_ICON: Record<string, string> = { rag_retrieve: "🔍", duckduckgo_search: "🌐" };

function authHeader(): Record<string, string> {
  const token = localStorage.getItem("access_token");
  return token ? { Authorization: "Bearer " + token } : {};
}

function relativeTime(iso: string): string {
  const diff = Date.now() - new Date(iso).getTime();
  const days = Math.floor(diff / 86400000);
  if (days === 0) return "today";
  if (days === 1) return "1d";
  return days + "d";
}

export default function PlaybookChat() {
  const navigate = useNavigate();
  const [theme, setTheme] = useState<"light" | "dark">("light");
  useEffect(() => { document.documentElement.setAttribute("data-theme", theme); }, [theme]);

  const [sessions, setSessions] = useState<Session[]>([]);
  const [activeSessionId, setActiveSessionId] = useState<string | null>(null);
  const [messages, setMessages] = useState<Message[]>([]);

  const [file, setFile] = useState<File | null>(null);
  const [uploading, setUploading] = useState(false);
  const [uploadError, setUploadError] = useState<string | null>(null);
  const [documentId, setDocumentId] = useState<string | null>(null);
  const [documentName, setDocumentName] = useState<string | null>(null);
  const [chunksIndexed, setChunksIndexed] = useState<number | null>(null);
  const [dragging, setDragging] = useState(false);

  const [question, setQuestion] = useState("");
  const [asking, setAsking] = useState(false);
  const bottomRef = useRef<HTMLDivElement>(null);
  const fileInputRef = useRef<HTMLInputElement>(null);
  const canAsk = useMemo(() => !asking && question.trim().length > 0, [asking, question]);

  function logout() {
    localStorage.removeItem("access_token");
    navigate("/", { replace: true });
  }

  function clearDocument() {
    setDocumentId(null);
    setDocumentName(null);
    setChunksIndexed(null);
    setFile(null);
    setUploadError(null);
  }

  // Fetch all sessions (router picks the playbook per-query, so sessions aren't scoped to one playbook)
  const fetchSessions = useCallback(async () => {
    try {
      const res = await fetch("/api/chat/sessions", { headers: authHeader() });
      if (res.status === 401) { logout(); return; }
      if (!res.ok) return;
      setSessions(await res.json());
    } catch {}
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  // Load sessions on mount
  useEffect(() => {
    fetchSessions();
  }, [fetchSessions]);

  // Scroll to bottom when messages update
  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages, asking]);

  // Load a session from the sidebar into the chat area
  async function loadSession(session: Session) {
    setActiveSessionId(session.session_id);
    setMessages([]);
    if (session.document_id) {
      setDocumentId(session.document_id);
      setDocumentName("loaded from session");
      setChunksIndexed(null);
    } else {
      clearDocument();
    }
    try {
      const res = await fetch(
        "/api/chat/sessions/" + session.session_id + "/messages",
        { headers: authHeader() }
      );
      if (!res.ok) return;
      const data: { id: string; role: string; content: string }[] = await res.json();
      setMessages(data.map(m => ({ role: m.role as "user" | "assistant", content: m.content })));
    } catch {}
  }

  // Create a new DB session (called lazily on first message if no session exists).
  // playbook_name is omitted — the router will determine it from the query content.
  async function createSession(): Promise<string | null> {
    try {
      const res = await fetch("/api/chat/sessions", {
        method: "POST",
        headers: { "Content-Type": "application/json", ...authHeader() },
        body: JSON.stringify({ document_id: documentId ?? undefined }),
      });
      if (res.status === 401) { logout(); return null; }
      if (!res.ok) return null;
      const data: Session = await res.json();
      setSessions(prev => [data, ...prev]);
      setActiveSessionId(data.session_id);
      return data.session_id;
    } catch {
      return null;
    }
  }

  function newChat() {
    setActiveSessionId(null);
    setMessages([]);
    clearDocument();
  }

  // Accepts either the staged file or a freshly-dropped file directly.
  // Auto-fires on file select so users don't need a separate Upload button.
  async function handleUpload(target?: File) {
    const f = target ?? file;
    if (!f) return;
    setUploading(true);
    setUploadError(null);
    try {
      const form = new FormData();
      form.append("file", f);
      const res = await fetch("/api/documents", { method: "POST", headers: authHeader(), body: form });
      if (!res.ok) throw new Error((await res.text()) || "Upload failed (" + res.status + ")");
      const data = await res.json();
      setDocumentId(data.document_id);
      setDocumentName(f.name);
      setChunksIndexed(data.chunks_indexed);
      setFile(null);
    } catch (err: unknown) {
      setUploadError(err instanceof Error ? err.message : "Upload failed");
    } finally {
      setUploading(false);
    }
  }

  async function handleAsk() {
    const q = question.trim();
    if (!q || asking) return;
    setAsking(true);
    setQuestion("");

    // Lazily create session on first message
    let sessionId = activeSessionId;
    if (!sessionId) sessionId = await createSession();

    setMessages(prev => [
      ...prev,
      { role: "user", content: q },
      { role: "assistant", content: "", steps: [], streaming: true },
    ]);

    const updateLast = (patch: Partial<Message>) =>
      setMessages(prev => {
        const last = prev[prev.length - 1];
        if (!last || last.role !== "assistant") return prev;
        return [...prev.slice(0, -1), { ...last, ...patch }];
      });

    try {
      const res = await fetch("/api/agent/query/stream", {
        method: "POST",
        headers: { "Content-Type": "application/json", ...authHeader() },
        body: JSON.stringify({
          question: q,
          // playbook_name omitted → backend router picks the best playbook
          document_id: documentId ?? undefined,
          session_id: sessionId ?? undefined,
        }),
      });
      if (res.status === 401) { logout(); return; }
      if (!res.ok) throw new Error("Request failed (" + res.status + ")");

      const reader = res.body!.getReader();
      const decoder = new TextDecoder();
      let buffer = "";

      while (true) {
        const { done, value } = await reader.read();
        if (done) break;
        buffer += decoder.decode(value, { stream: true });
        const lines = buffer.split("\n");
        buffer = lines.pop() ?? "";

        for (const line of lines) {
          if (!line.startsWith("data: ")) continue;
          let event: { type: string; tool?: string; input?: Record<string, unknown>; content?: string; message?: string; playbook?: string };
          try { event = JSON.parse(line.slice(6)); } catch { continue; }

          if (event.type === "playbook_selected") {
            setMessages(prev => {
              const last = prev[prev.length - 1];
              if (!last || last.role !== "assistant") return prev;
              return [...prev.slice(0, -1), { ...last, playbook: event.playbook }];
            });
          } else if (event.type === "tool_start") {
            setMessages(prev => {
              const last = prev[prev.length - 1];
              if (!last || last.role !== "assistant") return prev;
              return [...prev.slice(0, -1), { ...last, steps: [...(last.steps ?? []), { tool: event.tool!, input: event.input ?? {} }] }];
            });
          } else if (event.type === "token") {
            setMessages(prev => {
              const last = prev[prev.length - 1];
              if (!last || last.role !== "assistant") return prev;
              return [...prev.slice(0, -1), { ...last, content: last.content + event.content! }];
            });
          } else if (event.type === "error") {
            updateLast({ content: "Error: " + event.message, streaming: false });
          } else if (event.type === "done") {
            updateLast({ streaming: false });
            // Refresh sidebar so new session title appears after first message
            fetchSessions();
          }
        }
      }
    } catch (err: unknown) {
      updateLast({ content: "Error: " + (err instanceof Error ? err.message : "Request failed"), streaming: false });
    } finally {
      setAsking(false);
    }
  }

  return (
    <div className="min-h-screen flex">

      {/* ── Sidebar ── */}
      <aside className="w-64 shrink-0 flex flex-col bg-base-200 border-r border-base-300 h-screen sticky top-0">
        <div className="px-4 py-3 border-b border-base-300">
          <span className="font-bold text-base tracking-tight">Playbook Tools</span>
        </div>

        <div className="px-3 py-2">
          <button className="btn btn-primary btn-sm w-full" onClick={newChat}>
            + New Chat
          </button>
        </div>

        <div className="flex-1 overflow-y-auto px-2 pb-4 space-y-0.5">
          {sessions.length === 0 && (
            <p className="text-xs opacity-40 text-center mt-6 px-2">No chats yet.</p>
          )}
          {sessions.map(s => (
            <button
              key={s.session_id}
              onClick={() => loadSession(s)}
              className={
                "w-full text-left px-3 py-2 rounded-lg text-sm transition-colors " +
                (s.session_id === activeSessionId
                  ? "bg-primary/20 text-primary font-medium"
                  : "hover:bg-base-300")
              }
            >
              <div className="truncate">{s.title ?? "New chat"}</div>
              <div className="text-xs opacity-40">{relativeTime(s.created_at)}</div>
            </button>
          ))}
        </div>

        <div className="border-t border-base-300 px-3 py-2 space-y-2">
          <div className="flex items-center justify-between">
            <button
              className="btn btn-ghost btn-xs"
              onClick={() => setTheme(t => t === "dark" ? "light" : "dark")}
              title="Toggle theme"
            >
              {theme === "dark" ? "🌙" : "☀️"}
            </button>
            <button className="btn btn-ghost btn-xs text-error" onClick={logout}>
              Log out
            </button>
          </div>
        </div>
      </aside>

      {/* ── Main area ── */}
      <div
        className="flex-1 flex flex-col min-h-screen relative"
        onDragOver={e => { e.preventDefault(); if (!documentId) setDragging(true); }}
        onDragLeave={e => { if (!e.currentTarget.contains(e.relatedTarget as Node)) setDragging(false); }}
        onDrop={e => {
          e.preventDefault(); setDragging(false);
          const f = e.dataTransfer.files[0];
          if (f) handleUpload(f);
        }}
      >

        {/* Drag-and-drop overlay — covers the whole chat area */}
        {dragging && (
          <div className="absolute inset-0 z-10 flex items-center justify-center bg-base-100/80 border-2 border-dashed border-primary rounded-lg pointer-events-none">
            <p className="text-primary font-semibold text-lg">Drop to attach</p>
          </div>
        )}

        {/* Chat area */}
        <div className="flex-1 overflow-y-auto px-4 py-6 space-y-4">
          {messages.length === 0 && (
            <div className="text-center opacity-40 text-sm mt-16">
              {documentId
                ? "Ask anything about your document. " + documentName + " is loaded."
                : "Ask anything — upload a document to ground answers in your source material."}
            </div>
          )}

          {messages.map((m, idx) => (
            <div key={idx}>
              {m.role === "user" ? (
                <div className="chat chat-end">
                  <div className="chat-bubble chat-bubble-primary">{m.content}</div>
                </div>
              ) : (
                <>
                  {m.streaming && !m.content && !m.steps?.length && (
                    <div className="chat chat-start">
                      <div className="chat-bubble"><span className="loading loading-dots loading-sm" /></div>
                    </div>
                  )}
                  {m.playbook && (
                    <div className="chat chat-start">
                      <div className="badge badge-outline badge-sm opacity-40 mb-1 ml-1">
                        {m.playbook}
                      </div>
                    </div>
                  )}
                  {m.steps && m.steps.length > 0 && (
                    <div className="chat chat-start">
                      <div className="chat-bubble bg-base-300 text-base-content space-y-1 text-xs font-mono opacity-70">
                        {m.steps.map((s, si) => (
                          <div key={si}>
                            {TOOL_ICON[s.tool] ?? "⚙️"} {s.tool}
                            {s.input.query != null && <span className="opacity-60"> — "{String(s.input.query)}"</span>}
                          </div>
                        ))}
                      </div>
                    </div>
                  )}
                  {m.content && (
                    <div className="chat chat-start">
                      <div className="chat-bubble prose prose-sm max-w-none">
                        <ReactMarkdown>{m.content}</ReactMarkdown>
                        {m.streaming && <span className="animate-pulse">▌</span>}
                      </div>
                    </div>
                  )}
                </>
              )}
            </div>
          ))}

          <div ref={bottomRef} />
        </div>

        {/* Input bar */}
        <div className="sticky bottom-0 bg-base-200 border-t border-base-300 px-4 py-3">
          <div className="flex flex-col gap-2 max-w-3xl mx-auto">

            {/* Attachment chip — shown when a file is staged or uploaded */}
            {(uploading || documentId || uploadError) && (
              <div className="flex items-center gap-2 px-1">
                {uploading && (
                  <div className="flex items-center gap-2 bg-base-300 rounded-lg px-3 py-1.5 text-sm">
                    <span className="loading loading-spinner loading-xs" />
                    <span className="opacity-60">Uploading…</span>
                  </div>
                )}
                {documentId && !uploading && (
                  <div className="flex items-center gap-2 bg-base-300 rounded-lg px-3 py-1.5 text-sm">
                    <span className="text-success">📄</span>
                    <span className="font-mono text-xs truncate max-w-48">{documentName}</span>
                    {chunksIndexed != null && (
                      <span className="opacity-40 text-xs">{chunksIndexed} chunks</span>
                    )}
                    <button
                      className="btn btn-ghost btn-xs btn-circle opacity-50 hover:opacity-100"
                      onClick={clearDocument}
                      title="Remove attachment"
                    >
                      ✕
                    </button>
                  </div>
                )}
                {uploadError && !uploading && (
                  <div className="flex items-center gap-2 bg-error/10 text-error rounded-lg px-3 py-1.5 text-sm">
                    <span>⚠️</span>
                    <span className="text-xs">{uploadError}</span>
                    <button className="btn btn-ghost btn-xs btn-circle" onClick={clearDocument}>✕</button>
                  </div>
                )}
              </div>
            )}

            {/* Text input row */}
            <div className="flex gap-2">
              {/* Hidden file input — triggered by the paperclip button */}
              <input
                ref={fileInputRef}
                type="file"
                accept="application/pdf,.md"
                className="hidden"
                onChange={e => {
                  const f = e.target.files?.[0];
                  if (f) { handleUpload(f); e.target.value = ""; }
                }}
              />
              <button
                className="btn btn-ghost btn-sm btn-circle self-end mb-0.5 opacity-60 hover:opacity-100"
                onClick={() => fileInputRef.current?.click()}
                disabled={uploading || !!documentId}
                title={documentId ? "Remove current file first" : "Attach a PDF or .md file"}
              >
                📎
              </button>
              <input
                className="input input-bordered flex-1"
                placeholder={documentId ? "Ask about " + documentName + "…" : "Ask anything… or attach a document with 📎"}
                value={question}
                onChange={e => setQuestion(e.target.value)}
                onKeyDown={e => { if (e.key === "Enter" && !e.shiftKey && canAsk) handleAsk(); }}
                disabled={asking}
              />
              <button className="btn btn-primary self-end" onClick={handleAsk} disabled={!canAsk}>
                Send
              </button>
            </div>

          </div>
        </div>

      </div>
    </div>
  );
}
