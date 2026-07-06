#!/usr/bin/env node
// One-command interactive local stack for the FULL BOSC site, including its Cloudflare Pages
// Functions (/api/submit, /api/ask, /api/doc) — which `astro dev` never runs. The
// paid/destructive externals are mocked by default, so submit files no real issue and ask
// spends no tokens. Invoke via `mise run //frontend:dev:stack` — that puts the mise-managed
// wrangler (frontend/mise.toml [tools]) on PATH, which a bare `npm run dev:stack` would not.
//
// Pipeline:
//   1. ensure frontend/.dev.vars exists (generate a throwaway App key for JWT signing)
//   2. astro build with the dummy Turnstile site key so the widgets render (not the disabled
//      placeholder) — reads $BOSC_BUNDLE_DIR if set, else the committed sites/
//   3. seed the local R2 with the published documents so /api/doc serves real bytes
//      (scripts/seed-r2.mjs; skip with DEV_STACK_NO_SEED=1)
//   4. start the mock origin (scripts/dev-mocks.mjs)
//   5. wrangler pages dev — serves dist/ (pages_build_output_dir) + the Functions with local
//      KV + R2 (DOCS from wrangler.toml), auto-loading .dev.vars
// Ctrl-C (or wrangler dying) tears the whole stack down.

import { spawn } from "node:child_process";
import { generateKeyPairSync } from "node:crypto";
import { existsSync, readFileSync, writeFileSync } from "node:fs";
import { dirname, resolve } from "node:path";
import { fileURLToPath } from "node:url";

const FRONTEND = resolve(dirname(fileURLToPath(import.meta.url)), "..");
const DEV_VARS = resolve(FRONTEND, ".dev.vars");
const EXAMPLE = resolve(FRONTEND, ".dev.vars.example");
const MOCK_PORT = process.env.MOCK_PORT || "8799";
const SITE_PORT = process.env.SITE_PORT || "8788";
// Cloudflare's documented always-pass dummy Turnstile site key (pairs with the dummy secret).
const DUMMY_SITE_KEY = "1x00000000000000000000AA";

/** Create .dev.vars from the template on first run, filling in a throwaway PKCS#8 App key. */
function ensureDevVars() {
  if (existsSync(DEV_VARS)) {
    console.log("[dev-stack] using existing frontend/.dev.vars");
    return;
  }
  const { privateKey } = generateKeyPairSync("rsa", {
    modulusLength: 2048,
    privateKeyEncoding: { type: "pkcs8", format: "pem" },
    publicKeyEncoding: { type: "spki", format: "pem" },
  });
  // Collapse to one line — .dev.vars is single-line-per-key, and github.ts pemToDer strips
  // the markers + whitespace before decoding, so a newline-free PEM is fine.
  const oneLineKey = privateKey.replace(/\n/g, "");
  const body = readFileSync(EXAMPLE, "utf8").replace("__GENERATED_ON_FIRST_RUN__", oneLineKey);
  writeFileSync(DEV_VARS, body, { mode: 0o600 });
  console.log("[dev-stack] created frontend/.dev.vars (throwaway App key generated)");
}

/** Spawn a child inheriting stdio, in the frontend dir, with extra env. */
function run(label, command, args, env) {
  const child = spawn(command, args, {
    cwd: FRONTEND,
    stdio: "inherit",
    env: { ...process.env, ...env },
  });
  child.on("error", (e) => {
    console.error(`[dev-stack] ${label} failed to start: ${e.message}`);
    if (e.code === "ENOENT" && command === "wrangler")
      console.error(
        "[dev-stack] wrangler is a mise tool — run `mise run //frontend:dev:stack` so it's on PATH.",
      );
  });
  return child;
}

async function main() {
  ensureDevVars();

  console.log("[dev-stack] building the site (astro build, dummy Turnstile key)…");
  await new Promise((res, rej) => {
    const build = run("build", "npm", ["run", "build"], { PUBLIC_TURNSTILE_SITE_KEY: DUMMY_SITE_KEY });
    build.on("exit", (code) => (code === 0 ? res() : rej(new Error(`astro build failed (exit ${code})`))));
  });

  // Seed the local R2 so /api/doc serves real document bytes — the published set by default
  // (scripts/seed-r2.mjs writes via getPlatformProxy into the SAME store pages dev reads).
  // Pre-launch so the server sees it on boot; best-effort (needs a real bundle + `git lfs pull`
  // for bytes, else docs just 404). Skip with DEV_STACK_NO_SEED=1; seed more via seed-r2 directly.
  if (process.env.DEV_STACK_NO_SEED !== "1") {
    console.log("[dev-stack] seeding local R2 with the published documents…");
    await new Promise((res) => {
      const seed = run("seed-r2", "node", ["scripts/seed-r2.mjs"], {});
      seed.on("exit", () => res()); // non-fatal: a seed failure must not block the stack
    });
  }

  const mock = run("dev-mocks", "node", ["scripts/dev-mocks.mjs"], { MOCK_PORT });
  // wrangler comes from mise (frontend/mise.toml [tools]) — run this via
  // `mise run //frontend:dev:stack` so it's on PATH. No positional dir: wrangler serves
  // pages_build_output_dir ("dist") from wrangler.toml (matches docs/object-store.md); the
  // DOCS R2 binding comes from there too. KV namespaces bind to local simulators via --kv
  // (kept out of wrangler.toml so prod isn't affected).
  const wrangler = run(
    "wrangler",
    "wrangler",
    [
      "pages",
      "dev",
      "--port",
      SITE_PORT,
      "--kv",
      "RATE_LIMIT",
      "--kv",
      "ASK_RATE_LIMIT",
      "--kv",
      "SUBMISSION_CONTACT",
    ],
    {},
  );

  console.log(`[dev-stack] site → http://localhost:${SITE_PORT}  ·  mocks → http://localhost:${MOCK_PORT}`);
  console.log("[dev-stack] try /submit, /ask, and /api/doc/<rel> (published docs seeded). Ctrl-C to stop.");

  let stopping = false;
  const shutdown = (code) => {
    if (stopping) return;
    stopping = true;
    mock.kill("SIGTERM");
    wrangler.kill("SIGTERM");
    process.exit(code);
  };
  process.on("SIGINT", () => shutdown(0));
  process.on("SIGTERM", () => shutdown(0));
  wrangler.on("exit", () => shutdown(0)); // if the server dies, bring the mock down too
}

main().catch((e) => {
  console.error("[dev-stack]", e.message);
  process.exit(1);
});
