// Client-side logic for /account (profile + notification preferences).
// On load: verify session token → redirect to login if absent/expired.
// Fetches /api/account/profile + /api/account/notifications and populates the form.
// Handles PATCH on form submit for each section independently.

import { withBase } from "@watermark/core/base";

const PROFILE_URL = "/api/account/profile";
const NOTIF_URL = "/api/account/notifications";
// Use the Astro build-time base so redirects work regardless of deploy base path.
const LOGIN_PATH = withBase("/account/login");

function getToken(): string | null {
  const token = sessionStorage.getItem("watermark_id_token");
  if (!token) return null;
  try {
    const [, payloadB64] = token.split(".");
    const payload = JSON.parse(atob(payloadB64.replace(/-/g, "+").replace(/_/g, "/"))) as {
      exp?: unknown;
    };
    if (typeof payload.exp === "number" && payload.exp > Math.floor(Date.now() / 1000)) return token;
  } catch {
    // malformed
  }
  return null;
}

function bearer(token: string): Record<string, string> {
  return { Authorization: `Bearer ${token}`, "Content-Type": "application/json" };
}

function setText(id: string, value: string): void {
  const el = document.getElementById(id);
  if (el) el.textContent = value;
}

function setStatus(id: string, msg: string, kind: "ok" | "err" | "info"): void {
  const el = document.getElementById(id) as HTMLElement | null;
  if (!el) return;
  el.textContent = msg;
  el.dataset.kind = kind;
}

function setLoadError(id: string, msg: string): void {
  const el = document.getElementById(id) as HTMLElement | null;
  if (!el) return;
  el.textContent = msg;
  el.dataset.kind = "err";
}

async function loadProfile(token: string): Promise<void> {
  const res = await fetch(PROFILE_URL, { headers: bearer(token) }).catch(() => null);
  if (!res) {
    setLoadError("profile-loading", "Unable to load profile. Please try again.");
    return;
  }
  if (res.status === 401) {
    window.location.href = LOGIN_PATH;
    return;
  }
  if (!res.ok) {
    setLoadError("profile-loading", "Account profile is temporarily unavailable.");
    return;
  }
  const data = (await res.json()) as {
    display_name: string | null;
    email: string;
    role: string;
  };
  const nameInput = document.getElementById("profile-display-name") as HTMLInputElement | null;
  if (nameInput && data.display_name) nameInput.value = data.display_name;
  setText("profile-email", data.email);
  setText("profile-role", data.role);
  const loading = document.getElementById("profile-loading");
  const form = document.getElementById("profile-form-wrap");
  if (loading) loading.hidden = true;
  if (form) form.hidden = false;
}

async function loadNotifications(token: string): Promise<void> {
  const res = await fetch(NOTIF_URL, { headers: bearer(token) }).catch(() => null);
  if (!res) {
    setLoadError("notif-loading", "Unable to load notification preferences. Please try again.");
    return;
  }
  if (res.status === 401) {
    window.location.href = LOGIN_PATH;
    return;
  }
  if (!res.ok) {
    setLoadError("notif-loading", "Notification preferences are temporarily unavailable.");
    return;
  }
  const data = (await res.json()) as {
    sites: string[];
    categories: string[];
    frequency: string;
    email_verified: boolean;
  };

  for (const slug of data.sites) {
    const cb = document.getElementById(`notif-site-${slug}`) as HTMLInputElement | null;
    if (cb) cb.checked = true;
  }
  for (const cat of data.categories) {
    const cb = document.getElementById(`notif-cat-${cat}`) as HTMLInputElement | null;
    if (cb) cb.checked = true;
  }
  const freqEl = document.getElementById(`notif-freq-${data.frequency}`) as HTMLInputElement | null;
  if (freqEl) freqEl.checked = true;

  const emailNote = document.getElementById("notif-email-note");
  if (emailNote) {
    emailNote.textContent = data.email_verified
      ? "Your email is verified — you can receive notifications."
      : "Verify your email address to receive notifications.";
  }

  const loading = document.getElementById("notif-loading");
  const form = document.getElementById("notif-form-wrap");
  if (loading) loading.hidden = true;
  if (form) form.hidden = false;
}

async function init(): Promise<void> {
  const token = getToken();
  if (!token) {
    window.location.href = LOGIN_PATH;
    return;
  }

  await Promise.all([loadProfile(token), loadNotifications(token)]);

  // Profile form save
  const profileForm = document.getElementById("profile-form") as HTMLFormElement | null;
  if (profileForm) {
    profileForm.addEventListener("submit", async (e) => {
      e.preventDefault();
      const tok = getToken();
      if (!tok) {
        window.location.href = LOGIN_PATH;
        return;
      }
      const data = new FormData(profileForm);
      const payload: Record<string, string | null> = {
        display_name: (data.get("display_name") as string)?.trim() || null,
      };
      setStatus("profile-status", "Saving...", "info");
      const res = await fetch(PROFILE_URL, {
        method: "PATCH",
        headers: bearer(tok),
        body: JSON.stringify(payload),
      }).catch(() => null);
      if (!res) return setStatus("profile-status", "Network error — please try again.", "err");
      if (res.status === 401) {
        window.location.href = LOGIN_PATH;
        return;
      }
      if (res.ok) {
        setStatus("profile-status", "Saved.", "ok");
      } else {
        const out = (await res.json().catch(() => ({}))) as { error?: string };
        setStatus("profile-status", out.error ? `Error: ${out.error}` : "Failed to save.", "err");
      }
    });
  }

  // Notifications form save
  const notifForm = document.getElementById("notif-form") as HTMLFormElement | null;
  if (notifForm) {
    notifForm.addEventListener("submit", async (e) => {
      e.preventDefault();
      const tok = getToken();
      if (!tok) {
        window.location.href = LOGIN_PATH;
        return;
      }
      const data = new FormData(notifForm);
      const sites = data.getAll("sites") as string[];
      const categories = data.getAll("categories") as string[];
      const frequency = (data.get("frequency") as string) || "immediate";
      setStatus("notif-status", "Saving...", "info");
      const res = await fetch(NOTIF_URL, {
        method: "PATCH",
        headers: bearer(tok),
        body: JSON.stringify({ sites, categories, frequency }),
      }).catch(() => null);
      if (!res) return setStatus("notif-status", "Network error — please try again.", "err");
      if (res.status === 401) {
        window.location.href = LOGIN_PATH;
        return;
      }
      if (res.ok) {
        setStatus("notif-status", "Saved.", "ok");
      } else {
        const out = (await res.json().catch(() => ({}))) as { error?: string };
        setStatus("notif-status", out.error ? `Error: ${out.error}` : "Failed to save.", "err");
      }
    });
  }
}

void init();
