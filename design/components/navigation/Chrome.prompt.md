The global ink bar. Two tiers: `tier="network"` for the directory's own tabs (Directory · Research · About); `tier="site"` for inside-a-site nav (The site · The story · The record), which also shows a site chip breadcrumb (`site` + mono `codename`) and a status `phase` pill.

```jsx
<Chrome tier="network" active="report" />
<Chrome tier="site" active="site" site="Lima" codename="BOSC" phase="Live" />
<Chrome tier="site" active="record" phase="Building · 58%"
  selector={selOpen && <SiteSwitcherPanel />} />
```

Notes
- A tab with `children` becomes a dropdown trigger instead of a direct link; pass `{ rule: true }` in the children array for a divider.
- `phase` doubles as the build-progress pill (`"Live"`, `"Building · 58%"`, `"Queued"`…) — pass `""` to hide it on network tier or a site with no phase yet.
- `selector` slots in a site-switcher panel (grouped by state/basin, etc.) that opens under the bar when the site chip is clicked — bring your own; Chrome only manages the open/closed toggle.
- Colors are the ink bar's own palette (not the bone/forest surface tokens) — this component is always dark, by doctrine.
- See `templates/watermark-platform/` for the full working nav (mega-menu "The site" tab, basin drawer, site selector) this was distilled from.
