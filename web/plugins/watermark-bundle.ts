/**
 * Vite plugin that runs `watermark export` for each configured site before the
 * Astro SSG build starts, encoding the data-tier → build dependency
 * machine-readably instead of relying on a separate CI step.
 *
 * Skip conditions (checked in order):
 *   1. WATERMARK_SKIP_EXPORT=1 in the environment
 *   2. options.skip === true
 *   3. watch mode (dev server) — unless WATERMARK_EXPORT_IN_DEV=1
 *
 * Dev mode (configureServer): watches the data dirs and re-exports on change
 * (300 ms debounce), then sends a full-reload to connected clients. Opt-in via
 * WATERMARK_EXPORT_IN_DEV=1 for the initial export on startup.
 *
 * handleHotUpdate: suppresses HMR for files inside data/site/bundles/ so the
 * plugin's own writes don't trigger an infinite reload loop.
 *
 * #1019/#1021 forward-compat seam: supply `buildArgs` to swap the CLI args
 * when `bosc catalog run` ships without touching plugin code. `cmd` is the
 * resolved base command (from `opts.cmd`) passed for reference; return only
 * the args to append after the binary's base args:
 *   buildArgs: (_cmd, slug) => ["catalog", "run", `watermark-export-${slug}`]
 */

import { spawnSync } from "node:child_process";
import * as path from "node:path";
import { fileURLToPath } from "node:url";
import type { Plugin, ViteDevServer, HmrContext } from "vite";

export interface WatermarkCommand {
  args: string[];
  label?: string;
  sites?: "all" | string[];
}

export interface WatermarkBundleOptions {
  sites?: string[];
  cmd?: string[];
  extraCommands?: WatermarkCommand[];
  skip?: boolean;
  cwd?: string;
  buildArgs?: (cmd: string[], slug: string) => string[];
}

const DEFAULT_SITES = ["lima", "urbana", "fort-wayne"];
const DEFAULT_CMD = ["uv", "run", "watermark"];

const DATA_WATCH_DIRS = [
  "data/extracted",
  "data/site",
  "data/hypotheses",
  "data/scenarios",
  "data/reference",
];

const _pluginDir = path.dirname(fileURLToPath(import.meta.url));

function repoRoot(pluginDir: string): string {
  return path.resolve(pluginDir, "../..");
}

function runExport(
  cmd: string[],
  args: string[],
  cwd: string,
  label: string,
): boolean {
  const [bin, ...binArgs] = cmd;
  const result = spawnSync(bin, [...binArgs, ...args], {
    cwd,
    stdio: "inherit",
    env: process.env,
  });
  if (result.error) {
    console.error(`[watermark-bundle] ${label} could not be spawned: ${result.error.message}`);
    return false;
  }
  if (result.status !== 0) {
    console.error(`[watermark-bundle] ${label} failed (exit ${result.status ?? "signal"})`);
    return false;
  }
  return true;
}

export function watermarkBundle(opts: WatermarkBundleOptions = {}): Plugin {
  const sites = opts.sites ?? DEFAULT_SITES;
  const cmd = opts.cmd ?? DEFAULT_CMD;
  const cwd = opts.cwd ?? repoRoot(_pluginDir);
  const buildArgs =
    opts.buildArgs ??
    ((_c: string[], slug: string) => ["--site", slug, "export"]);

  let debounceTimer: ReturnType<typeof setTimeout> | null = null;

  function shouldSkip(isWatch: boolean): boolean {
    if (process.env.WATERMARK_SKIP_EXPORT === "1") return true;
    if (process.env.VITEST) return true; // vitest loads Vite plugins but must not shell out
    if (opts.skip) return true;
    if (isWatch && process.env.WATERMARK_EXPORT_IN_DEV !== "1") return true;
    return false;
  }

  function exportAll(): void {
    for (const slug of sites) {
      const args = buildArgs(cmd, slug);
      const ok = runExport(cmd, args, cwd, `--site ${slug} export`);
      if (!ok) throw new Error(`[watermark-bundle] export failed for site "${slug}"`);
    }
    for (const extra of opts.extraCommands ?? []) {
      const targets =
        extra.sites === "all"
          ? sites
          : extra.sites != null
            ? extra.sites
            : [null];
      for (const slug of targets) {
        const prefix = slug != null ? ["--site", slug] : [];
        const ok = runExport(
          cmd,
          [...prefix, ...extra.args],
          cwd,
          extra.label ?? extra.args.join(" "),
        );
        if (!ok)
          throw new Error(
            `[watermark-bundle] extra command failed: ${extra.label ?? extra.args.join(" ")}`,
          );
      }
    }
  }

  return {
    name: "watermark-bundle",

    buildStart() {
      const isWatch = (this as { meta?: { watchMode?: boolean } }).meta?.watchMode ?? false;
      if (shouldSkip(isWatch)) {
        console.log("[watermark-bundle] skipped (WATERMARK_SKIP_EXPORT or watch mode)");
        return;
      }
      exportAll();
    },

    configureServer(server: ViteDevServer) {
      const bundlesDir = path.join(cwd, "data", "site", "bundles");
      const watchDirs = DATA_WATCH_DIRS.map((d) => path.join(cwd, d));

      function onChange(filePath: string) {
        if (filePath.startsWith(bundlesDir + path.sep)) return;
        if (debounceTimer != null) clearTimeout(debounceTimer);
        debounceTimer = setTimeout(() => {
          debounceTimer = null;
          console.log("[watermark-bundle] data changed — re-exporting...");
          try {
            exportAll();
            server.ws.send({ type: "full-reload" });
          } catch {
            // logged inside exportAll
          }
        }, 300);
      }

      for (const dir of watchDirs) {
        server.watcher.add(dir);
      }
      server.watcher.on("change", onChange);
      server.watcher.on("add", onChange);
      server.watcher.on("unlink", onChange);

      if (process.env.WATERMARK_EXPORT_IN_DEV === "1") {
        console.log("[watermark-bundle] dev: running initial export...");
        try {
          exportAll();
        } catch {
          // logged inside exportAll
        }
      }

      return () => {
        if (debounceTimer != null) {
          clearTimeout(debounceTimer);
          debounceTimer = null;
        }
        server.watcher.off("change", onChange);
        server.watcher.off("add", onChange);
        server.watcher.off("unlink", onChange);
      };
    },

    handleHotUpdate({ file }: HmrContext) {
      const bundlesDir = path.join(cwd, "data", "site", "bundles");
      if (file.startsWith(bundlesDir + path.sep)) {
        return [];
      }
      return undefined;
    },
  };
}
