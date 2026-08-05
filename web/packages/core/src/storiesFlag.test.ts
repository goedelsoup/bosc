// The Stories UI flag, and the routes it now governs (#1894, epic #1884 phase 10).
//
// `stories: false` has been the state in `deploy/features.yaml` since #1090, and the four authoring
// routes built on every selectable site regardless — sixteen pages whose whole content was
// "Reader-authored stories are coming soon." Nothing linked them, because there is nothing to link
// to yet. The honest shape of a dark feature is a route that doesn't exist and appears the day the
// flag flips, which is what `storyToolPaths` is.
import { afterEach, describe, expect, it, vi } from "vitest";
import { selectableSitePaths } from "./sites";
import { storiesUiEnabled, storyToolPaths } from "./storiesFlag";

afterEach(() => {
  vi.unstubAllEnvs();
});

/** The build-time shape of a deploy with Stories on: both Cognito keys plus the kill switch. */
function enableStories(): void {
  vi.stubEnv("PUBLIC_COGNITO_DOMAIN", "auth.example.org");
  vi.stubEnv("PUBLIC_COGNITO_CLIENT_ID", "abc123");
  vi.stubEnv("PUBLIC_STORIES_ENABLED", "true");
}

describe("storiesUiEnabled", () => {
  it("needs the kill switch AND both Cognito keys — a half-provisioned deploy stays dark", () => {
    enableStories();
    expect(storiesUiEnabled()).toBe(true);
    vi.stubEnv("PUBLIC_STORIES_ENABLED", "false");
    expect(storiesUiEnabled()).toBe(false);
    enableStories();
    vi.stubEnv("PUBLIC_COGNITO_CLIENT_ID", "");
    expect(storiesUiEnabled()).toBe(false);
  });
});

describe("storyToolPaths (#1894)", () => {
  it("emits every selectable site when the feature is on", () => {
    enableStories();
    expect(storyToolPaths()).toEqual(selectableSitePaths());
    expect(storyToolPaths().length).toBeGreaterThan(1);
  });

  it("emits nothing in a production build with the feature dark", () => {
    vi.stubEnv("DEV", false);
    vi.stubEnv("PUBLIC_STORIES_ENABLED", "false");
    expect(storyToolPaths()).toEqual([]);
  });

  it("still emits in dev with the feature dark — the placeholder's ?preview is how the islands get looked at", () => {
    vi.stubEnv("DEV", true);
    vi.stubEnv("PUBLIC_STORIES_ENABLED", "false");
    expect(storyToolPaths()).toEqual(selectableSitePaths());
  });

  it("emits in a production build once the flag flips, without touching this file", () => {
    // The whole point of gating on the flag rather than deleting the routes: turning Stories on is a
    // `deploy/features.yaml` edit plus `pulumi up`, and the pages come back with it.
    vi.stubEnv("DEV", false);
    enableStories();
    expect(storyToolPaths()).toEqual(selectableSitePaths());
  });
});
