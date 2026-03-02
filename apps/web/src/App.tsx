import { useEffect, useState } from "react";

type Health = { status: string };

export default function App() {
  const [health, setHealth] = useState<Health | null>(null);
  const [error, setError] = useState<string | null>(null);

  const apiBase = import.meta.env.VITE_API_BASE_URL ?? "/api";

  useEffect(() => {
    (async () => {
      try {
        const res = await fetch(`${apiBase}/health`);
        if (!res.ok) throw new Error(`HTTP ${res.status}`);
        const json = (await res.json()) as Health;
        setHealth(json);
      } catch (e) {
        setError(e instanceof Error ? e.message : String(e));
      }
    })();
  }, [apiBase]);

  return (
    <div className="min-h-screen flex items-center justify-center">
      <div className="card w-96 bg-base-100 shadow-xl">
        <div className="card-body">
          <h1 className="card-title">Playbook Tools</h1>

          <p className="text-sm opacity-70">
            API base: <span className="font-mono">{apiBase}</span>
          </p>

          {error ? (
            <div className="alert alert-error mt-4">
              <span>API error: {error}</span>
            </div>
          ) : health ? (
            <div className="alert alert-success mt-4">
              <span>API health: {health.status}</span>
            </div>
          ) : (
            <div className="mt-4 loading loading-spinner loading-md" />
          )}

          <div className="card-actions justify-end mt-4">
            <button
              className="btn btn-primary"
              onClick={() => window.location.reload()}
            >
              Refresh
            </button>
          </div>
        </div>
      </div>
    </div>
  );
}