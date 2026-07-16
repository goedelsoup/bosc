import { describe, expect, it } from "vitest";
import { type DonateLinks, donateEnabled, hasRecurringTiers } from "./donate";

// Both gates take an injectable links arg so they're testable without touching
// import.meta.env. The Donate section ships dark: it appears once *any* link is present,
// and each tier then gates on its own link (individually disable-able).
const all: DonateLinks = {
  follower: "https://buy.stripe.com/follower",
  contributor: "https://buy.stripe.com/contributor",
  sustainer: "https://buy.stripe.com/sustainer",
  oneTime: "https://buy.stripe.com/once",
};

describe("donateEnabled", () => {
  it("is true when every link is set", () => {
    expect(donateEnabled(all)).toBe(true);
  });

  it("is false when no links are set", () => {
    expect(donateEnabled({})).toBe(false);
  });

  it.each([
    "follower",
    "contributor",
    "sustainer",
  ] as const)("is true when only the %s tier is set", (only) => {
    expect(donateEnabled({ [only]: all[only] })).toBe(true);
  });

  it("is true when only the one-time link is set", () => {
    expect(donateEnabled({ oneTime: all.oneTime })).toBe(true);
  });

  it("treats an empty-string link as unset", () => {
    expect(donateEnabled({ follower: "", contributor: "", sustainer: "", oneTime: "" })).toBe(false);
  });
});

describe("hasRecurringTiers", () => {
  it("is true when at least one recurring tier is set", () => {
    expect(hasRecurringTiers({ sustainer: all.sustainer })).toBe(true);
  });

  it("is false for a one-time-only setup (so the tier grid stays hidden)", () => {
    expect(hasRecurringTiers({ oneTime: all.oneTime })).toBe(false);
  });

  it("is false when no links are set", () => {
    expect(hasRecurringTiers({})).toBe(false);
  });
});
