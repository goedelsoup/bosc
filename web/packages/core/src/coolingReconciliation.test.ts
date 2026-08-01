import { describe, expect, it } from "vitest";
import { hasFeed, loadFeed, manifestOrNull } from "./bundle";
import {
  buildCoolingReconciliation,
  COOLING_RECONCILIATION_FEED,
  RECONCILE_OUTCOME_META,
} from "./coolingReconciliation";
import type { CoolingReconciliation } from "./feeds";
import { SITES } from "./sites";

// Runs against the committed per-site bundles (`web/sites/<slug>/`) — the same fixtures the
// study suites read, so these assertions pin real shipped data, not synthetic rows.

const bundled = SITES.map((s) => s.slug).filter((slug) => manifestOrNull(slug) !== null);

describe("cooling-reconciliation — the site's own claim-vs-record account", () => {
  it("urbana ships its committed outcome (the #1805 acceptance)", () => {
    const feed = buildCoolingReconciliation("urbana");
    expect(feed).not.toBeNull();
    expect(feed?.site).toBe("urbana");
    expect(feed?.candidates).toHaveLength(1);
    const row = feed!.candidates[0];
    expect(row.outcome).toBe("gap");
    expect(row.claim_source).toBe("reference"); // an operator claim, not an instrument
    expect(row.claimed_archetype).toBe("closed_loop_dry");
    expect(row.account.predicted_makeup?.value).toBe(0); // predicted ~0 MGD
    expect(row.lead?.records_sought.length).toBeGreaterThan(0);
    // The discipline travels as data — a renderer must have caveats to show.
    expect(feed!.caveats.length).toBeGreaterThan(0);
  });

  it("a site outside the cohort carries no feed (lima) — never an empty shell", () => {
    expect(hasFeed(COOLING_RECONCILIATION_FEED, "lima")).toBe(false);
    expect(buildCoolingReconciliation("lima")).toBeNull();
  });

  it("the Intel positive control never ships in ANY committed bundle", () => {
    // The acceptance's hard rule: the calibration vector is not site data. Swept over every
    // committed bundle — including new-albany, whose slug the control row carries.
    let shippedRows = 0;
    for (const slug of bundled) {
      if (!hasFeed(COOLING_RECONCILIATION_FEED, slug)) continue;
      const feed = loadFeed<CoolingReconciliation>(COOLING_RECONCILIATION_FEED, slug);
      for (const row of feed.candidates) {
        shippedRows += 1;
        expect(row.is_control, `${slug}: a control row shipped`).toBe(false);
        expect(row.site, `${slug}: another site's account shipped`).toBe(slug);
        expect(RECONCILE_OUTCOME_META[row.outcome]).toBeDefined();
      }
    }
    expect(shippedRows).toBeGreaterThan(0); // the sweep saw the cohort, not a vacuous pass
  });

  it("new-albany ships Intel's real record — route_blind, with the refusal legible", () => {
    // The B6 (#1686) row. The site's bundle carries a LIVE row alongside the excluded control:
    // an openly-evaporative claim that still cannot be reconciled, because the campus buys its
    // water and discharges to a sewer. Everything a renderer needs to say so must be present.
    const feed = buildCoolingReconciliation("new-albany");
    expect(feed).not.toBeNull();
    expect(feed?.candidates).toHaveLength(1);
    const row = feed!.candidates[0];
    expect(row.is_control).toBe(false);
    expect(row.outcome).toBe("route_blind");
    expect(row.claimed_archetype).toBe("evaporative_tower"); // the claim is WET, and openly so
    expect(RECONCILE_OUTCOME_META.route_blind.label).toBeTruthy();

    // The prediction is refused, totally and with a reason — never a substituted zero.
    expect(row.account.predicted_makeup ?? null).toBeNull();
    expect(row.account.predicted_consumptive ?? null).toBeNull();
    expect(row.account.predicted_blowdown ?? null).toBeNull();
    expect(row.account.prediction_refused).toBeTruthy();

    // The route says which side(s) the instruments cannot reach, and carries its citation.
    expect(row.account.route?.supply).toBe("municipal");
    expect(row.account.route?.discharge).toBe("sanitary_sewer");
    expect(row.account.route?.citation).toBeTruthy();

    // The registry's real figure is on its own slot — never mistaken for the cooling account.
    expect(row.account.nonprocess_makeup?.value).toBeGreaterThan(0);
    expect(row.account.documented_makeup ?? null).toBeNull();
    expect(row.account.documented_blowdown ?? null).toBeNull();

    // The ask is re-aimed at the holder that actually meters the campus.
    expect(row.lead?.holder).toMatch(/City/i);
  });
});
