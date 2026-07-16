// Client-side logic for /account/admin — user search + role/site assignment.
// Gate: verifies session token; redirects to login if absent/expired or if caller
// is not `admin` or `site-admin`.
//
// Admin view: search all users by email → edit groups + adminSites.
// Site-admin view: same, but the API only returns users in the caller's site scope.

import { withBase } from "@watermark/core/base";

const LOGIN_PATH = withBase("/account/login");
const USERS_URL = withBase("/api/admin/users");
const AUDIT_URL = withBase("/api/admin/audit");
const userGroupsUrl = (sub: string) => withBase(`/api/admin/users/${encodeURIComponent(sub)}/groups`);
const userAdminSitesUrl = (sub: string) =>
  withBase(`/api/admin/users/${encodeURIComponent(sub)}/admin-sites`);
const userEarlyAccessUrl = (sub: string) =>
  withBase(`/api/admin/users/${encodeURIComponent(sub)}/early-access`);

const MANAGED_GROUPS = ["admin", "site-admin", "standard"];

interface AdminUser {
  sub: string;
  email: string;
  groups: string[];
  adminSites: string[];
}

interface AuditEntry {
  actor: string;
  target: string;
  action: string;
  before: string[];
  after: string[];
  at: string;
}

function b64urlDecode(s: string): string {
  const base64 = s.replace(/-/g, "+").replace(/_/g, "/");
  const rem = base64.length % 4;
  return atob(rem ? base64 + "=".repeat(4 - rem) : base64);
}

function getToken(): string | null {
  const token = sessionStorage.getItem("watermark_id_token");
  if (!token) return null;
  try {
    const [, payloadB64] = token.split(".");
    const payload = JSON.parse(b64urlDecode(payloadB64)) as { exp?: unknown };
    if (typeof payload.exp === "number" && payload.exp > Math.floor(Date.now() / 1000)) return token;
  } catch {
    // malformed
  }
  return null;
}

function getRole(token: string): string {
  try {
    const [, b64] = token.split(".");
    const p = JSON.parse(b64urlDecode(b64)) as {
      "cognito:groups"?: string[];
    };
    const groups = p["cognito:groups"] ?? [];
    if (groups.includes("admin")) return "admin";
    if (groups.includes("site-admin")) return "site-admin";
  } catch {
    // ignore
  }
  return "standard";
}

function bearer(token: string): Record<string, string> {
  return { Authorization: `Bearer ${token}`, "Content-Type": "application/json" };
}

function escapeHtml(s: string): string {
  return s.replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;").replace(/"/g, "&quot;");
}

function setStatus(msg: string, kind: "ok" | "err" | "info"): void {
  const el = document.getElementById("search-status");
  if (!el) return;
  el.textContent = msg;
  el.dataset.kind = kind;
}

function renderAuditTrail(entries: AuditEntry[]): string {
  if (!entries.length) return "<p class='audit-row'>No audit records found.</p>";
  return entries
    .map(
      (e) =>
        `<div class="audit-row">${escapeHtml(e.at)} — ${escapeHtml(e.actor)} set ${escapeHtml(e.action)} on ${escapeHtml(e.target)}: [${escapeHtml(e.before.join(", "))}] → [${escapeHtml(e.after.join(", "))}]</div>`,
    )
    .join("");
}

async function loadAuditTrail(token: string, sub: string, container: Element): Promise<void> {
  try {
    const res = await fetch(`${AUDIT_URL}?sub=${encodeURIComponent(sub)}`, {
      headers: bearer(token),
    });
    if (!res.ok) return;
    const entries = (await res.json()) as AuditEntry[];
    const div = container.querySelector(".audit-trail-body");
    if (div) div.innerHTML = renderAuditTrail(entries);
  } catch {
    // best-effort
  }
}

function renderUserCard(user: AdminUser, callerRole: string): string {
  const groupsChecks = MANAGED_GROUPS.map(
    (g) =>
      `<label class="check-label">
        <input type="checkbox" name="group" value="${escapeHtml(g)}"
          ${user.groups.includes(g) ? "checked" : ""}
          ${callerRole === "site-admin" ? "disabled" : ""}>
        ${escapeHtml(g)}
      </label>`,
  ).join("");

  const sitesInput = `<input type="text" name="admin-sites" value="${escapeHtml(user.adminSites.join(", "))}"
      placeholder="comma-separated slugs" style="width:100%">`;

  const groupsSection =
    callerRole === "admin"
      ? `<h3>Groups</h3>
        <div class="check-grid">${groupsChecks}</div>
        <button type="button" class="btn btn--sm save-groups-btn" data-sub="${escapeHtml(user.sub)}">Save groups</button>
        <p class="save-status save-groups-status form-status" role="status" aria-live="polite"></p>`
      : `<h3>Groups</h3><p class="account-note">${escapeHtml(user.groups.join(", ") || "(none)")}</p>`;

  const hasEarlyAccess = user.groups.includes("early-access");
  const earlyAccessSection = `<div class="early-access-row">
    ${hasEarlyAccess ? `<span class="badge badge--ea">early access</span>` : ""}
    <button type="button" class="btn btn--sm ea-toggle-btn" data-sub="${escapeHtml(user.sub)}" data-has="${hasEarlyAccess ? "1" : "0"}">
      ${hasEarlyAccess ? "Revoke early access" : "Grant early access"}
    </button>
    <p class="save-status ea-status form-status" role="status" aria-live="polite"></p>
  </div>`;

  return `<div class="user-card" id="user-card-${escapeHtml(user.sub)}">
    <div class="user-card-meta">${escapeHtml(user.email)} &mdash; sub: <code>${escapeHtml(user.sub)}</code></div>
    ${groupsSection}
    <h3>Early access</h3>
    ${earlyAccessSection}
    <h3>Admin sites</h3>
    ${sitesInput}
    <button type="button" class="btn btn--sm save-sites-btn" data-sub="${escapeHtml(user.sub)}">Save sites</button>
    <p class="save-status save-sites-status form-status" role="status" aria-live="polite"></p>
    <div class="audit-trail">
      <h4>Audit trail</h4>
      <div class="audit-trail-body"><em>Loading…</em></div>
    </div>
  </div>`;
}

function attachCardHandlers(card: Element, token: string): void {
  const sub = (card as HTMLElement).id.replace("user-card-", "");

  const saveGroupsBtn = card.querySelector(".save-groups-btn");
  if (saveGroupsBtn) {
    saveGroupsBtn.addEventListener("click", async () => {
      const groups = Array.from(card.querySelectorAll<HTMLInputElement>('input[name="group"]:checked')).map(
        (el) => el.value,
      );
      const status = card.querySelector(".save-groups-status");
      if (status) {
        status.textContent = "Saving…";
        (status as HTMLElement).dataset.kind = "info";
      }
      try {
        const res = await fetch(userGroupsUrl(sub), {
          method: "POST",
          headers: bearer(token),
          body: JSON.stringify({ groups }),
        });
        const msg = res.ok ? "Saved." : `Error: ${((await res.json()) as { error: string }).error}`;
        if (status) {
          status.textContent = msg;
          (status as HTMLElement).dataset.kind = res.ok ? "ok" : "err";
        }
        if (res.ok) await loadAuditTrail(token, sub, card);
      } catch {
        if (status) {
          status.textContent = "Network error.";
          (status as HTMLElement).dataset.kind = "err";
        }
      }
    });
  }

  const saveSitesBtn = card.querySelector(".save-sites-btn");
  if (saveSitesBtn) {
    saveSitesBtn.addEventListener("click", async () => {
      const input = card.querySelector<HTMLInputElement>('input[name="admin-sites"]');
      const sites = (input?.value ?? "")
        .split(",")
        .map((s) => s.trim())
        .filter(Boolean);
      const status = card.querySelector(".save-sites-status");
      if (status) {
        status.textContent = "Saving…";
        (status as HTMLElement).dataset.kind = "info";
      }
      try {
        const res = await fetch(userAdminSitesUrl(sub), {
          method: "POST",
          headers: bearer(token),
          body: JSON.stringify({ sites }),
        });
        const msg = res.ok ? "Saved." : `Error: ${((await res.json()) as { error: string }).error}`;
        if (status) {
          status.textContent = msg;
          (status as HTMLElement).dataset.kind = res.ok ? "ok" : "err";
        }
        if (res.ok) await loadAuditTrail(token, sub, card);
      } catch {
        if (status) {
          status.textContent = "Network error.";
          (status as HTMLElement).dataset.kind = "err";
        }
      }
    });
  }

  const eaToggleBtn = card.querySelector<HTMLButtonElement>(".ea-toggle-btn");
  if (eaToggleBtn) {
    eaToggleBtn.addEventListener("click", async () => {
      const hasEa = eaToggleBtn.dataset.has === "1";
      const status = card.querySelector(".ea-status");
      if (status) {
        status.textContent = "Saving…";
        (status as HTMLElement).dataset.kind = "info";
      }
      try {
        const res = await fetch(userEarlyAccessUrl(sub), {
          method: hasEa ? "DELETE" : "PUT",
          headers: bearer(token),
        });
        if (res.ok) {
          const nowHas = !hasEa;
          eaToggleBtn.dataset.has = nowHas ? "1" : "0";
          eaToggleBtn.textContent = nowHas ? "Revoke early access" : "Grant early access";
          const badge = card.querySelector(".badge--ea");
          if (nowHas && !badge) {
            eaToggleBtn.insertAdjacentHTML(
              "beforebegin",
              `<span class="badge badge--ea">early access</span>`,
            );
          } else if (!nowHas && badge) {
            badge.remove();
          }
          if (status) {
            status.textContent = nowHas ? "Granted." : "Revoked.";
            (status as HTMLElement).dataset.kind = "ok";
          }
          await loadAuditTrail(token, sub, card);
        } else {
          const msg = `Error: ${((await res.json()) as { error: string }).error}`;
          if (status) {
            status.textContent = msg;
            (status as HTMLElement).dataset.kind = "err";
          }
        }
      } catch {
        if (status) {
          status.textContent = "Network error.";
          (status as HTMLElement).dataset.kind = "err";
        }
      }
    });
  }

  void loadAuditTrail(token, sub, card);
}

async function handleSearch(token: string, q: string, callerRole: string): Promise<void> {
  setStatus("Searching…", "info");
  const resultsEl = document.getElementById("user-results");
  if (resultsEl) resultsEl.innerHTML = "";

  try {
    const res = await fetch(`${USERS_URL}?q=${encodeURIComponent(q)}`, { headers: bearer(token) });
    if (res.status === 401) {
      window.location.href = LOGIN_PATH;
      return;
    }
    if (res.status === 403) {
      setStatus("Access denied.", "err");
      return;
    }
    if (!res.ok) {
      setStatus("Search failed.", "err");
      return;
    }

    const users = (await res.json()) as AdminUser[];
    if (!users.length) {
      setStatus("No users found.", "info");
      return;
    }

    setStatus(`${users.length} user${users.length === 1 ? "" : "s"} found.`, "ok");
    if (!resultsEl) return;
    resultsEl.innerHTML = users.map((u) => renderUserCard(u, callerRole)).join("");
    resultsEl.querySelectorAll(".user-card").forEach((card) => {
      attachCardHandlers(card, token);
    });
  } catch {
    setStatus("Network error.", "err");
  }
}

async function init(): Promise<void> {
  const token = getToken();
  if (!token) {
    window.location.href = `${LOGIN_PATH}?next=${encodeURIComponent(window.location.pathname)}`;
    return;
  }

  const role = getRole(token);
  const gateMsg = document.getElementById("admin-gate-msg");
  const panel = document.getElementById("admin-panel");

  if (role !== "admin" && role !== "site-admin") {
    if (gateMsg) gateMsg.textContent = "You do not have access to this page.";
    return;
  }

  if (gateMsg) gateMsg.hidden = true;
  if (panel) panel.hidden = false;

  const form = document.getElementById("user-search-form");
  form?.addEventListener("submit", (e) => {
    e.preventDefault();
    const q = (document.getElementById("admin-email-q") as HTMLInputElement)?.value ?? "";
    void handleSearch(token, q, role);
  });
}

void init();
