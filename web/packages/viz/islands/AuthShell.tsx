/**
 * AuthShell — account chip in the global topbar (Epic #919 A5).
 *
 * Reads the ID token from sessionStorage on mount (client-only; renders nothing
 * on SSR). Shows "Sign in" when logged out and an avatar chip when logged in.
 * On logout: clears sessionStorage, calls /api/account/logout (clears the
 * HttpOnly refresh cookie), then redirects to the Cognito /logout endpoint.
 *
 * Config is injected as props from Header.astro using PUBLIC_* build-time env vars.
 */
import { useEffect, useState } from "react";
import { type AuthUser, clearIdToken, clearPkceVerifier, currentUser } from "@watermark/viz/auth";

interface Props {
  /** Cognito Hosted UI domain — PUBLIC_COGNITO_DOMAIN. */
  cognitoDomain: string;
  /** Cognito app client ID — PUBLIC_COGNITO_CLIENT_ID. */
  clientId: string;
  /** Base URL path to /account/login (base-aware). */
  loginHref: string;
  /** Base URL path to /account/logout (base-aware). */
  logoutHref: string;
}

export default function AuthShell({
  cognitoDomain: _cognitoDomain,
  clientId: _clientId,
  loginHref,
  logoutHref,
}: Props): JSX.Element | null {
  const [user, setUser] = useState<AuthUser | null>(null);
  const [ready, setReady] = useState(false);

  useEffect(() => {
    setUser(currentUser());
    setReady(true);
  }, []);

  // Nothing on SSR or while hydrating — avoids a flash of wrong state.
  if (!ready) return null;

  if (!user) {
    return (
      <a className="account-chip account-chip--out" href={loginHref} aria-label="Sign in">
        <svg
          viewBox="0 0 24 24"
          width="15"
          height="15"
          fill="none"
          stroke="currentColor"
          strokeWidth={1.7}
          strokeLinecap="round"
          strokeLinejoin="round"
          aria-hidden="true"
        >
          <circle cx="12" cy="8" r="3.6" />
          <path d="M5.5 20 a6.5 6.5 0 0 1 13 0" />
        </svg>
        <span className="account-chip-label">Sign in</span>
      </a>
    );
  }

  const initial = user.email.charAt(0).toUpperCase();

  async function handleSignOut(e: React.MouseEvent): Promise<void> {
    e.preventDefault();
    clearIdToken();
    clearPkceVerifier();
    try {
      await fetch("/api/account/logout", { method: "POST" });
    } catch {
      // proceed regardless
    }
    // Redirect to /account/logout which will end the Cognito Hosted UI session.
    window.location.href = logoutHref;
  }

  return (
    <span className="account-chip account-chip--in">
      <span
        className="account-chip-avatar"
        role="img"
        title={user.email}
        aria-label={`Signed in as ${user.email}`}
      >
        {initial}
      </span>
      {user.role !== "standard" && (
        <span className="account-chip-role">{user.role === "admin" ? "admin" : "site-admin"}</span>
      )}
      <button
        className="account-chip-signout"
        onClick={(e) => void handleSignOut(e)}
        type="button"
        aria-label="Sign out"
        title="Sign out"
      >
        out
      </button>
    </span>
  );
}
