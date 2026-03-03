import { useMemo, useState } from "react";

type UploadResponse = { document_id: string };
type QueryResponse = {
  answer: string;
  chunks_used?: Array<{ text: string; distance?: number }>;
};

export default function RagDemo() {
  const [file, setFile] = useState<File | null>(null);
  const [uploading, setUploading] = useState(false);
  const [documentId, setDocumentId] = useState<string | null>(null);
  const [uploadError, setUploadError] = useState<string | null>(null);

  const [question, setQuestion] = useState("");
  const [asking, setAsking] = useState(false);
  const [messages, setMessages] = useState<
    Array<{ role: "user" | "assistant"; content: string }>
  >([]);
  const [lastChunks, setLastChunks] = useState<QueryResponse["chunks_used"]>([]);

  const canAsk = useMemo(() => !!documentId && question.trim().length > 0, [documentId, question]);

  async function handleUpload() {
    if (!file) return;
    setUploading(true);
    setUploadError(null);

    try {
      const form = new FormData();
      form.append("file", file);

      const res = await fetch("/api/documents", {
        method: "POST",
        body: form,
      });

      if (!res.ok) {
        const text = await res.text();
        throw new Error(text || `Upload failed (${res.status})`);
      }

      const data = (await res.json()) as UploadResponse;
      setDocumentId(data.document_id);
    } catch (err: any) {
      setUploadError(err?.message ?? "Upload failed");
      setDocumentId(null);
    } finally {
      setUploading(false);
    }
  }

  async function handleAsk() {
    if (!documentId) return;
    const q = question.trim();
    if (!q) return;

    setAsking(true);
    setQuestion("");
    setMessages((prev) => [...prev, { role: "user", content: q }]);

    try {
      const res = await fetch("/api/query", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ document_id: documentId, question: q, top_k: 5 }),
      });

      if (!res.ok) {
        const text = await res.text();
        throw new Error(text || `Query failed (${res.status})`);
      }

      const data = (await res.json()) as QueryResponse;

      setMessages((prev) => [
        ...prev,
        { role: "assistant", content: data.answer ?? "(no answer)" },
      ]);
      setLastChunks(data.chunks_used ?? []);
    } catch (err: any) {
      setMessages((prev) => [
        ...prev,
        { role: "assistant", content: `Error: ${err?.message ?? "Query failed"}` },
      ]);
      setLastChunks([]);
    } finally {
      setAsking(false);
    }
  }

  return (
    <div className="min-h-screen p-6 flex justify-center">
      <div className="w-full max-w-3xl space-y-6">
        <div className="card bg-base-100 shadow">
          <div className="card-body space-y-3">
            <h2 className="card-title">RAG Demo</h2>

            <div className="flex flex-col gap-3 sm:flex-row sm:items-end">
              <div className="flex-1">
                <label className="label">
                  <span className="label-text">Upload a PDF</span>
                </label>
                <input
                  type="file"
                  accept="application/pdf"
                  className="file-input file-input-bordered w-full"
                  onChange={(e) => setFile(e.target.files?.[0] ?? null)}
                />
              </div>

              <button
                className="btn btn-primary"
                onClick={handleUpload}
                disabled={!file || uploading}
              >
                {uploading ? "Uploading..." : "Upload"}
              </button>
            </div>

            {uploadError && <div className="alert alert-error">{uploadError}</div>}

            <div className="text-sm opacity-80">
              {documentId ? (
                <div>
                  <span className="font-semibold">document_id:</span> {documentId}
                </div>
              ) : (
                <div>No document uploaded yet.</div>
              )}
            </div>
          </div>
        </div>

        <div className="card bg-base-100 shadow">
          <div className="card-body space-y-4">
            <h3 className="card-title">Chat</h3>

            <div className="border rounded-lg p-3 space-y-3 max-h-[360px] overflow-auto">
              {messages.length === 0 ? (
                <div className="opacity-60">Ask a question after uploading a PDF.</div>
              ) : (
                messages.map((m, idx) => (
                  <div key={idx} className="space-y-1">
                    <div className="text-xs uppercase opacity-60">{m.role}</div>
                    <div className="whitespace-pre-wrap">{m.content}</div>
                  </div>
                ))
              )}
            </div>

            <div className="flex gap-2">
              <input
                className="input input-bordered flex-1"
                placeholder={documentId ? "Ask something about the PDF..." : "Upload a PDF first"}
                value={question}
                onChange={(e) => setQuestion(e.target.value)}
                onKeyDown={(e) => {
                  if (e.key === "Enter") handleAsk();
                }}
                disabled={!documentId || asking}
              />
              <button className="btn btn-secondary" onClick={handleAsk} disabled={!canAsk || asking}>
                {asking ? "Asking..." : "Send"}
              </button>
            </div>
          </div>
        </div>

        <div className="card bg-base-100 shadow">
          <div className="card-body space-y-2">
            <h3 className="card-title">Top chunks used</h3>
            {(!lastChunks || lastChunks.length === 0) ? (
              <div className="opacity-60">No chunks yet.</div>
            ) : (
              <ul className="space-y-2">
                {lastChunks.map((c, i) => (
                  <li key={i} className="border rounded-lg p-3">
                    {c?.distance !== undefined && (
                      <div className="text-xs opacity-60">distance: {c.distance}</div>
                    )}
                    <div className="whitespace-pre-wrap">{c.text}</div>
                  </li>
                ))}
              </ul>
            )}
          </div>
        </div>
      </div>
    </div>
  );
}