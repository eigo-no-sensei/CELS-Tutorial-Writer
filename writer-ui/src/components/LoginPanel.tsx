import { FormEvent, useState } from "react";

interface Props {
  busy: boolean;
  error: string | null;
  onLogin: (username: string, password: string) => Promise<void>;
}

export function LoginPanel({ busy, error, onLogin }: Props) {
  const [username, setUsername] = useState("");
  const [password, setPassword] = useState("");

  async function submit(event: FormEvent) {
    event.preventDefault();
    if (!username.trim() || !password) return;
    try {
      await onLogin(username.trim(), password);
    } finally {
      // Password is transient UI state only; clear it whether login succeeds or fails.
      setPassword("");
    }
  }

  return (
    <form className="login-panel" onSubmit={submit}>
      <div>
        <strong>GEL session</strong>
        <span className="subtle">Required only for authoritative New/Revision source forms.</span>
      </div>
      <label>
        Username
        <input autoComplete="username" value={username} onChange={(event) => setUsername(event.target.value)} disabled={busy} />
      </label>
      <label>
        Password
        <input type="password" autoComplete="current-password" value={password} onChange={(event) => setPassword(event.target.value)} disabled={busy} />
      </label>
      <button type="submit" disabled={busy || !username.trim() || !password}>{busy ? "Signing in…" : "Log in"}</button>
      {error && <div className="error-banner">{error}</div>}
      <small>Credentials and session cookies are not persisted by Tutorial Writer.</small>
    </form>
  );
}
