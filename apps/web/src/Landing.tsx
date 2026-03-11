import { useEffect, useRef, useState } from "react";
import { useNavigate } from "react-router-dom";

type AuthMode = "login" | "register";

export default function Landing() {
  const navigate = useNavigate();
  const [mode, setMode] = useState<AuthMode>("login");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);
  const dialogRef = useRef<HTMLDialogElement>(null);

  // If already logged in, skip the landing page
  useEffect(() => {
    if (localStorage.getItem("access_token")) {
      navigate("/chat", { replace: true });
    }
  }, [navigate]);

  function openModal(m: AuthMode) {
    setMode(m);
    setError(null);
    setEmail("");
    setPassword("");
    dialogRef.current?.showModal();
  }

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    setLoading(true);
    setError(null);

    const endpoint = mode === "login" ? "/api/auth/login" : "/api/auth/register";

    try {
      const res = await fetch(endpoint, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ email, password }),
      });

      if (!res.ok) {
        const body = await res.json().catch(() => ({}));
        throw new Error(body.detail ?? `Request failed (${res.status})`);
      }

      const { access_token } = await res.json();
      localStorage.setItem("access_token", access_token);
      navigate("/chat", { replace: true });
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : "Something went wrong");
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="min-h-screen flex flex-col">
      {/* Hero */}
      <div className="hero flex-1">
        <div className="hero-content text-center flex-col gap-8 max-w-lg">
          <div>
            <div className="text-6xl mb-4">🎮</div>
            <h1 className="text-5xl font-bold tracking-tight">Playbook Tools</h1>
            <p className="mt-4 text-lg opacity-60">
              AI-powered game design assistant. Upload your GDD, ask anything.
            </p>
          </div>

          <div className="flex gap-3">
            <button
              className="btn btn-primary btn-lg"
              onClick={() => openModal("register")}
            >
              Get started
            </button>
            <button
              className="btn btn-ghost btn-lg"
              onClick={() => openModal("login")}
            >
              Log in
            </button>
          </div>

          <div className="grid grid-cols-3 gap-4 mt-4 text-sm opacity-50">
            <div>🔍 RAG search your GDD</div>
            <div>🌐 Web research built-in</div>
            <div>⚡ Streaming responses</div>
          </div>
        </div>
      </div>

      {/* Auth modal */}
      <dialog ref={dialogRef} className="modal">
        <div className="modal-box max-w-sm">
          <h3 className="font-bold text-lg mb-4">
            {mode === "login" ? "Welcome back" : "Create account"}
          </h3>

          <form onSubmit={handleSubmit} className="flex flex-col gap-3">
            <input
              type="email"
              placeholder="Email"
              className="input input-bordered w-full"
              value={email}
              onChange={(e) => setEmail(e.target.value)}
              required
              autoFocus
            />
            <input
              type="password"
              placeholder="Password (min 8 characters)"
              className="input input-bordered w-full"
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              required
              minLength={8}
            />

            {error && (
              <p className="text-error text-sm">{error}</p>
            )}

            <button
              type="submit"
              className="btn btn-primary w-full"
              disabled={loading}
            >
              {loading ? (
                <span className="loading loading-spinner loading-sm" />
              ) : mode === "login" ? "Log in" : "Create account"}
            </button>
          </form>

          <div className="divider text-xs opacity-40">or</div>

          <button
            className="btn btn-ghost btn-sm w-full"
            onClick={() => {
              setMode(m => m === "login" ? "register" : "login");
              setError(null);
            }}
          >
            {mode === "login" ? "Don't have an account? Sign up" : "Already have an account? Log in"}
          </button>
        </div>

        {/* Click outside to close */}
        <form method="dialog" className="modal-backdrop">
          <button>close</button>
        </form>
      </dialog>
    </div>
  );
}
