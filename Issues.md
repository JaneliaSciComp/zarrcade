# Code Review — Open Issues

Audit of the Zarrcade SPA + CLI + npm packaging work as of branch
`t3-improvements`. Items are grouped by category, then severity. Each
entry names the file(s) and a concrete fix.

---

## Critical

### XSS via column values in `titleTemplate`
- `web/src/components/ImageCard.tsx:106`, `web/src/components/ImageDetail.tsx:65`
- `getTitle()` in `web/src/utils/csv.ts` substitutes raw CSV cell values into
  `display.titleTemplate` and the result is rendered with
  `dangerouslySetInnerHTML`. A column value containing `<script>` (or
  `onerror="..."` inside an `<img>`) executes in the user's session.
- **Impact:** Any party who can supply data — a CSV on S3 today, but more
  importantly *any* CSV a user opens via `?config=` — can run JS in the
  user's browser. Token theft, phishing, drive-by anything.
- **Fix:** HTML-encode each substituted value *before* it goes into the
  template (replace `<`, `>`, `&`, `"`, `'`), OR run the final string
  through DOMPurify with a tight whitelist (only `<font>`, `<b>`, `<i>`,
  `<span>` styling tags). The template itself is author-controlled and
  can keep raw markup; only the substituted values need escaping.

### XSS via `?config=<url>` + arbitrary HTML in branding slots
- `web/src/components/Footer.tsx:15`, plus any future `headerCenter`/etc.
- `branding.footer.{left,right}.html` is rendered as-is via
  `dangerouslySetInnerHTML`. We documented the trust model as
  "configs are author-controlled," but the SPA also accepts a config
  via the `?config=<url>` query param, so anyone can craft a URL that
  loads an attacker-hosted config and inject arbitrary HTML/JS into
  the page.
- **Impact:** Same as above — phishing-grade XSS via a single link.
- **Fix:** Either (a) sanitize HTML slot contents through DOMPurify
  before injection, or (b) only honor HTML slots when the config came
  from a same-origin source (i.e. not `?config=`-loaded). (a) is the
  simpler and more durable choice.

### Path traversal in `zarrcade-dev`
- `web/bin/zarrcade-dev.mjs`
- The middleware accepts any URL under the `/ext/` prefix and resolves
  it via `path.join(userDir, url.slice(1))`. A request to
  `/ext/../package.json` (or `/ext/../../../etc/passwd`) escapes
  `userDir` because `path.join` normalizes the `..` segments.
- **Impact:** During local dev, any file readable by the dev user can be
  served over the bound port — which we default to `0.0.0.0`. On a
  shared workstation this is reachable from the network.
- **Fix:** After `path.join`, call `path.resolve()` and verify the
  result starts with `path.resolve(userDir) + path.sep` (or `===
  userDir`); otherwise 403. Also consider defaulting the dev host to
  `127.0.0.1` and requiring opt-in for `0.0.0.0`.

---

## High

### Theme tracking stops following the OS after first paint
- `web/src/hooks/useTheme.ts:36-39`
- The `useEffect` that applies the theme to `<html>` also writes to
  `localStorage` unconditionally. So the first render persists the
  initial value, and the system-preference listener at lines 47-49
  then treats the auto-persisted value as a "manual choice" and
  refuses to follow subsequent OS theme changes.
- **Fix:** Only call `localStorage.setItem` from `setTheme`/
  `toggleTheme` (i.e. on explicit user action), not in the
  apply-to-document effect. Apply via `setAttribute` and store
  separately.

### O(n²) `allData.indexOf(row)` in gallery and table render
- `web/src/components/Gallery.tsx:28`, `web/src/components/TableView.tsx:44`
- For each visible row we walk `allData` to find the global index. With
  `pageSize: 50` and a 10k-row dataset that's ~500k array scans per
  render. The page hangs perceptibly at scale.
- **Fix:** Build a `Map<ImageRow, number>` once (or thread the global
  index through `paginatedData` as a `{row, index}` pair) and read in
  O(1).

### Table rows are not keyboard-accessible
- `web/src/components/TableView.tsx:47`
- `<tr onClick=...>` has no `role`, no `tabIndex`, no `onKeyDown`.
  Keyboard-only and screen-reader users cannot open a detail view from
  the table.
- **Fix:** Add `role="button" tabIndex={0}` to the `<tr>` and handle
  Enter/Space in `onKeyDown`. Or render the first cell as an actual
  `<a>` to the same URL the detail navigation produces; that's the
  most universally accessible option.

### Settings menu skips keyboard nav between items
- `web/src/components/SettingsMenu.tsx`
- Uses `role="menu"` + `role="menuitem"` but only handles Escape. The
  ARIA pattern for a menu requires arrow-key navigation between items
  and focus management on open. Currently you must tab through every
  item, and on small viewports the trigger button can be missed
  entirely.
- **Fix:** Either implement the menu pattern properly (arrow keys,
  Home/End, focus-trap while open, focus restoration on close) or
  downgrade the roles to a plain disclosure (`role` removed,
  `aria-expanded` only) and document it as a list of links/buttons.

---

## Medium

### `vite.config.ts` bakes `base: './'`
- `web/vite.config.ts:7`
- Resolved on `t3-improvements`: `'./'` is the right default — it makes
  the SPA portable across mount points without per-deployment config.
  Annotated the file with a comment explaining why.
- **Follow-up on `npm-library`:** `zarrcade-build` should only override
  `base` when `ZARRCADE_BASE` is explicitly set, not when it falls back
  to the env-var default. Otherwise the build CLI silently substitutes
  `/` for the intentional `'./'`.

### `useData` body-shape heuristic rejects valid edge cases
- `web/src/hooks/useData.ts`
- Rejects bodies that start with `<`, `{`, or `[`. CSVs whose first
  cell legitimately starts with `<` (e.g. a column whose first column
  header literally contains the character) fail to load with a
  misleading "not CSV" error. Rare but possible.
- **Fix:** Sniff the `Content-Type` header first; only fall back to
  the prefix sniff if the server reports `text/csv` or unknown.

### No row virtualization
- `web/src/components/Gallery.tsx`, `web/src/components/TableView.tsx`
- All rows for the current page are rendered, which is fine. But
  `pageSize` is configurable and some sites have used 100+. Combined
  with the convention-thumbnail intersection observer per card, large
  pages cause noticeable jank.
- **Fix:** Out of scope today, but flag for the next perf pass. Either
  cap `pageSize` at ~100, or virtualize.

### Image `alt` text is the (HTML) title
- `web/src/components/ImageCard.tsx`, `web/src/components/ImageDetail.tsx`
- `alt` receives the result of `getTitle()`, which may contain HTML
  tags from `titleTemplate`. Screen readers read raw text including
  the tags.
- **Fix:** Strip tags (or use a plain-text variant of the title) for
  `alt`. Cheap to do once in `getTitle()` and expose as
  `getPlainTitle()`.

### `?config=<url>` accepts any origin without warning
- `web/src/config.ts:102-112`
- Anyone can construct a URL like `…/?config=https://evil.example/x.json`
  that the SPA will fetch and apply. Combined with the HTML-slot XSS
  above, this is the actual attack surface.
- **Fix:** When the config URL's origin differs from the page origin,
  warn the user (one-time interstitial: "This page wants to load
  configuration from <origin>. Proceed?") or restrict to an
  allowlist provided via meta tag.

---

## Low

### `convert_to_v2.py` is one-off and not in this repo
- Lives in `zarrcade-sites/dyebioavailability/data/`. We've explicitly
  said we won't maintain it as a Zarrcade feature, but the README and
  CLAUDE.md should make clear the canonical conversion path is "drop
  the legacy YAML and write a `zarrcade.json` by hand."

### `web/public/config.json` ships with `dataUrl: ""`
- Useful as a Welcome-screen affordance, but the new
  `zarrcade-build` flow copies the consumer's `zarrcade.json` to
  `dist/`. Both files end up in `dist/`. The config-load order means
  `zarrcade.json` wins, but the dead `config.json` is unused bytes.
- **Fix:** `zarrcade-build` should delete the default `config.json`
  from dist after the Vite build completes.

### No `<title>` / `<meta>` synced to config.title
- `web/index.html` ships with a static `<title>Zarrcade</title>`.
  Browser tabs and OG previews don't reflect the site title.
- **Fix:** Update `document.title = config.title` after load. Optionally
  inject OG/Twitter meta tags from `config.title` + a configurable
  description field.

### Download metadata always exports all columns
- `web/src/utils/csv.ts:downloadCsv` respects `hideColumns`, which
  hides the path/thumbnail/MIP columns from the download too. That's
  arguably correct, but if a user actually wants the path column for
  scripting they have to round-trip via the dev tools.
- **Fix:** Add a "Download metadata (all columns)" variant, or make the
  download skip `hideColumns` since the download is for offline
  analysis, not card display.

### Footer text/HTML can't pull from config-level fields
- The footer slots accept raw HTML/text only. A common pattern would
  be `{title}` substitution into a copyright line. Not blocking, just
  ergonomic.

---

## Missing features (not bugs, but worth tracking)

- **Column sorting in table view.** Designed but not implemented; the
  `?sort=Column&sortDir=asc` URL contract was sketched. ~30 LOC.
- **Saved views.** Persist filter/search/sort combinations in
  `localStorage`; menu item to switch between them.
- **CSS/theme override hook.** L2 of the extensibility brainstorm —
  consumers want to add their own stylesheet via
  `branding.theme.stylesheet`. Currently sites can only override
  via the bg-color knobs.
- **Pre-loaded filter from URL params.** The URL state currently
  supports `?detail` and `?view`; query params for individual filters
  (`?species=Mouse`) are listed in the README but not actually
  honored on load by `useFilters`.
- **`branding.menuItems` is text-only.** Cannot reference a local
  asset (would be nice for "Download our paper PDF").

---

## Suggested triage order

1. **Critical XSS pair + path traversal** — patch within the next session.
2. **Theme persistence bug** — small, user-visible.
3. **O(n²) indexOf + table keyboard access** — affects every gallery render
   and every assistive-tech user.
4. **`vite.config.ts` base + `?config` origin warning** — coherence cleanup
   before any external publishing.
5. Everything else — backlog.
