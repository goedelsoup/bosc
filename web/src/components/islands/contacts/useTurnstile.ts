/**
 * A minimal Cloudflare Turnstile hook for the public contacts islands. When a site key is present it
 * loads the Turnstile script once and explicitly renders a widget into `ref`, surfacing the solved
 * token. When no site key is configured it is inert and returns an empty token — matching the server,
 * which only enforces verification when `TURNSTILE_SECRET` is set (so the feature works dark).
 */
import { useEffect, useRef, useState } from "react";

interface TurnstileApi {
  render: (
    el: HTMLElement,
    opts: { sitekey: string; callback: (token: string) => void; "expired-callback"?: () => void },
  ) => string;
  reset: (id?: string) => void;
}
declare global {
  interface Window {
    turnstile?: TurnstileApi;
  }
}

const SCRIPT_SRC = "https://challenges.cloudflare.com/turnstile/v0/api.js";
let scriptPromise: Promise<void> | null = null;

function loadScript(): Promise<void> {
  if (typeof document === "undefined") return Promise.resolve();
  if (window.turnstile) return Promise.resolve();
  if (!scriptPromise) {
    scriptPromise = new Promise<void>((resolve) => {
      const s = document.createElement("script");
      s.src = SCRIPT_SRC;
      s.async = true;
      s.onload = () => resolve();
      document.head.appendChild(s);
    });
  }
  return scriptPromise;
}

/** Returns a ref to mount the widget on, the current token (`""` until solved / when disabled), and a reset. */
export function useTurnstile(siteKey?: string): {
  ref: (el: HTMLDivElement | null) => void;
  token: string;
  reset: () => void;
} {
  const [token, setToken] = useState("");
  const widgetId = useRef<string | undefined>(undefined);
  const elRef = useRef<HTMLDivElement | null>(null);

  useEffect(() => {
    if (!siteKey || !elRef.current) return;
    let cancelled = false;
    loadScript().then(() => {
      if (cancelled || !elRef.current || !window.turnstile) return;
      widgetId.current = window.turnstile.render(elRef.current, {
        sitekey: siteKey,
        callback: (t) => setToken(t),
        "expired-callback": () => setToken(""),
      });
    });
    return () => {
      cancelled = true;
    };
  }, [siteKey]);

  return {
    ref: (el) => {
      elRef.current = el;
    },
    token,
    reset: () => {
      setToken("");
      if (window.turnstile) window.turnstile.reset(widgetId.current);
    },
  };
}
