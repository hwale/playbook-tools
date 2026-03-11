import { useEffect, useRef, useMemo, useState } from "react";
import ReactMarkdown from "react-markdown";

type Playbook = { name: string; description: string | null };
type Step = { tool: string; input: Record<string, unknown> };
type Message = { role: "user" | "assistant"; content: string; steps?: Step[]; streaming?: boolean };

type UploadResponse = { document_id: string; chunks_indexed: number };
type AgentResponse = { answer: string; steps: Step[] };

const TOOL_ICON: Record<string, string> = {
  rag_retrieve: "🔍",
  duckduckgo_search: "🌐",
};

export default function App() {
  const [theme, setTheme] = useState<"synthwave" | "retro">("retro");

  useEffect(() => {
    document.documentElement.setAttribute("data-theme", theme);
  }, [theme]);

  // Playbooks
  const [playbooks, setPlaybooks] = useState<Playbook[]>([]);
  const [activePlaybook, setActivePlaybook] = useState<string>("");
  const [chatHistory, setChatHistory] = useState<Record<string, Message[]>>({});

  // Upload
  const [file, setFile] = useState<File | null>(null);
  const [uploading, setUploading] = useState(false);
  const [uploadError, setUploadError] = useState<string | null>(null);
  const [documentId, setDocumentId] = useState<string | null>(null);
  const [documentName, setDocumentName] = useState<string | null>(null);
  const [chunksIndexed, setChunksIndexed] = useState<number | null>(null);

  // Chat input
  const [question, setQuestion] = useState("");
  const [asking, setAsking] = useState(false);
  const [dragging, setDragging] = useState(false);

  const bottomRef = useRef<HTMLDivElement>(null);
  const messages = chatHistory[activePlaybook] ?? [];

  const canAsk = useMemo(
    () => !asking && question.trim().length > 0,
    [asking, question]
  );

  // Fetch playbooks on mount
  useEffect(() => {
    fetch("/api/agent/playbooks")
      .then((r) => r.json())
      .then((data: Playbook[]) => {
        setPlaybooks(data);
        if (data.length > 0) setActivePlaybook(data[0].name);
      })
      .catch(() => {/* backend may not be ready yet */});
  }, []);

  // Scroll to bottom on new messages
  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages, asking]);

  async function handleUpload() {
    if (!file) return;
    setUploading(true);
    setUploadError(null);
    try {
      const form = new FormData();
      form.append("file", file);
      const res = await fetch("/api/documents", { method: "POST", body: form });
      if (!res.ok) throw new Error((await res.text()) || `Upload failed (${res.status})`);
      const data = (await res.json()) as UploadResponse;
      setDocumentId(data.document_id);
      setDocumentName(file.name);
      setChunksIndexed(data.chunks_indexed);
      setFile(null);
    } catch (err: unknown) {
      setUploadError(err instanceof Error ? err.message : "Upload failed");
    } finally {
      setUploading(false);
    }
  }

  function clearDocument() {
    setDocumentId(null);
    setDocumentName(null);
    setChunksIndexed(null);
    setFile(null);
    setUploadError(null);
  }

  async function handleAsk() {
    const q = question.trim();
    if (!q || asking) return;

    // Capture active playbook now — user might switch mid-stream
    const playbook = activePlaybook;

    setAsking(true);
    setQuestion("");

    // Add user message, then an empty assistant placeholder
    setChatHistory((prev) => ({
      ...prev,
      [playbook]: [
        ...(prev[playbook] ?? []),
        { role: "user", content: q },
        { role: "assistant", content: "", steps: [], streaming: true },
      ],
    }));

    // Helper: update the last message in this playbook's history
    const updateLast = (patch: Partial<Message>) =>
      setChatHistory((prev) => {
        const msgs = prev[playbook] ?? [];
        const last = msgs[msgs.length - 1];
        if (!last || last.role !== "assistant") return prev;
        return { ...prev, [playbook]: [...msgs.slice(0, -1), { ...last, ...patch }] };
      });

    try {
      const res = await fetch("/api/agent/query/stream", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ question: q, playbook_name: playbook, document_id: documentId ?? undefined }),
      });
      if (!res.ok) throw new Error(`Request failed (${res.status})`);

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
          let event: { type: string; tool?: string; input?: Record<string, unknown>; content?: string; message?: string };
          try { event = JSON.parse(line.slice(6)); } catch { continue; }

          if (event.type === "tool_start") {
            setChatHistory((prev) => {
              const msgs = prev[playbook] ?? [];
              const last = msgs[msgs.length - 1];
              if (!last || last.role !== "assistant") return prev;
              return {
                ...prev,
                [playbook]: [
                  ...msgs.slice(0, -1),
                  { ...last, steps: [...(last.steps ?? []), { tool: event.tool!, input: event.input ?? {} }] },
                ],
              };
            });
          } else if (event.type === "token") {
            setChatHistory((prev) => {
              const msgs = prev[playbook] ?? [];
              const last = msgs[msgs.length - 1];
              if (!last || last.role !== "assistant") return prev;
              return { ...prev, [playbook]: [...msgs.slice(0, -1), { ...last, content: last.content + event.content! }] };
            });
          } else if (event.type === "error") {
            updateLast({ content: `Error: ${event.message}`, streaming: false });
          } else if (event.type === "done") {
            updateLast({ streaming: false });
          }
        }
      }
    } catch (err: unknown) {
      updateLast({ content: `Error: ${err instanceof Error ? err.message : "Request failed"}`, streaming: false });
    } finally {
      setAsking(false);
    }
  }

  return (
    <div className="min-h-screen flex flex-col">

      {/* Navbar */}
      <div className="navbar bg-base-200 border-b border-base-300 px-4">
        <div className="flex-1">
          <span className="text-lg font-bold tracking-tight">🎮 Playbook Tools</span>
        </div>
        <div className="flex-none flex items-center gap-2">
          {playbooks.length > 0 && (
            <select
              className="select select-ghost select-sm"
              value={activePlaybook}
              onChange={(e) => setActivePlaybook(e.target.value)}
            >
              {playbooks.map((p) => (
                <option key={p.name} value={p.name}>{p.name}</option>
              ))}
            </select>
          )}
          <button
            className="btn btn-ghost btn-sm btn-circle text-base"
            onClick={() => setTheme(t => t === "synthwave" ? "retro" : "synthwave")}
            title="Toggle theme"
          >
            {theme === "synthwave" ? "☀️" : "🌙"}
          </button>
        </div>
      </div>

      {/* Upload banner */}
      <div
        className={`border-b px-4 py-3 transition-all ${
          documentId
            ? "bg-base-200 border-base-300"
            : dragging
            ? "bg-primary/10 border-primary border-dashed"
            : "bg-base-200 border-base-300 border-dashed"
        }`}
        onDragOver={(e) => { e.preventDefault(); if (!documentId) setDragging(true); }}
        onDragLeave={() => setDragging(false)}
        onDrop={(e) => {
          e.preventDefault();
          setDragging(false);
          if (documentId) return;
          const dropped = e.dataTransfer.files[0];
          if (dropped) setFile(dropped);
        }}
      >
        {documentId ? (
          <div className="flex items-center gap-3 text-sm">
            <span className="text-success font-mono">✓ {documentName}</span>
            <span className="opacity-50">{chunksIndexed} chunks</span>
            <button className="btn btn-ghost btn-xs" onClick={clearDocument}>✕ clear</button>
          </div>
        ) : (
          <div className="flex flex-col items-center gap-2 py-1">
            <p className={`text-sm transition-colors ${dragging ? "text-primary font-medium" : "opacity-50"}`}>
              {dragging ? "Drop to select" : activePlaybook === "game-design"
                ? "📎 Drop your Game Design Document (PDF or .md) here, or use the picker below"
                : "📎 Drop a PDF or .md file here, or use the picker below"
              }
            </p>
            <div className="flex items-center gap-2">
              <input
                type="file"
                accept="application/pdf,.md"
                className="file-input file-input-bordered file-input-sm"
                onChange={(e) => setFile(e.target.files?.[0] ?? null)}
              />
              <button
                className="btn btn-primary btn-sm"
                onClick={handleUpload}
                disabled={!file || uploading}
              >
                {uploading ? <span className="loading loading-spinner loading-xs" /> : "Upload"}
              </button>
            </div>
            {file && !uploading && (
              <p className="text-xs opacity-60">Selected: {file.name}</p>
            )}
            {uploadError && (
              <p className="text-error text-xs">{uploadError}</p>
            )}
          </div>
        )}
      </div>

      {/* Chat area */}
      <div className="flex-1 overflow-y-auto px-4 py-6 space-y-4">
        {messages.length === 0 && (
          <div className="text-center opacity-40 text-sm mt-16">
            {documentId
              ? `Ask anything about your game. ${documentName} is loaded.`
              : "Ask anything — upload a GDD to ground answers in your game's systems."}
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
                {/* Each bubble in its own chat row so DaisyUI renders them separately */}
                {m.streaming && !m.content && !m.steps?.length && (
                  <div className="chat chat-start">
                    <div className="chat-bubble">
                      <span className="loading loading-dots loading-sm" />
                    </div>
                  </div>
                )}
                {m.steps && m.steps.length > 0 && (
                  <div className="chat chat-start">
                    <div className="chat-bubble bg-base-300 text-base-content space-y-1 text-xs font-mono opacity-70">
                      {m.steps.map((s, si) => (
                        <div key={si}>
                          {TOOL_ICON[s.tool] ?? "⚙️"} {s.tool}
                          {s.input.query != null && (
                            <span className="opacity-60"> — "{String(s.input.query)}"</span>
                          )}
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
        <div className="flex gap-2 max-w-3xl mx-auto">
          <input
            className="input input-bordered flex-1"
            placeholder={documentId ? `Ask about your game...` : "Ask anything..."}
            value={question}
            onChange={(e) => setQuestion(e.target.value)}
            onKeyDown={(e) => { if (e.key === "Enter" && canAsk) handleAsk(); }}
            disabled={asking}
          />
          <button className="btn btn-primary" onClick={handleAsk} disabled={!canAsk}>
            Send
          </button>
        </div>
      </div>

    </div>
  );
}
