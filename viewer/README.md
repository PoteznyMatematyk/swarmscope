# SwarmScope Evidence Viewer

One self-contained, offline HTML file (`index.html`, ~100 KB, vanilla JS, no CDN, no web fonts, zero network
requests). It renders the `report.json` produced by `swarmscope report` as five views:

| View | What it shows |
|---|---|
| **Overview** | Trust ledger first: verified quotes / all quotes, "verified = the quote occurs verbatim in the cited event; it does not prove the claim", first-pass vs final reject rate, first-pass reject rate per model, tracer hops verified, claims by status, and a viewer-side recount of the embedded evidence against the report's own metrics. |
| **Findings** | One card per curated finding: thesis, confidence, episode, "all N quotes verified" badge, chronological evidence timeline with roles (origin / adoption / contradiction ...), counter-evidence, reviewer verdicts, limitations. |
| **Claims** | Filters (Q1-Q11, status, model, actor, free text), sorting, 40 rows per page (fast for 5000+ claims), expandable rows with their quotes. |
| **Propagation** | Cascade list (unit, kind, adopters, median lag, burst) with a mini spread strip per cascade, and a SVG spread timeline: one lane per actor, x = time since the source (log or linear), one dot per first use, tooltip, click = evidence panel. `n_adopters` is always shown even though the report embeds at most 40 hops. |
| **Method** | Pipeline (ingest, question battery, quote verification, tracer), what "verified" does and does not mean, limitations, status vocabulary. |

The **evidence panel** (right drawer) shows who, when (UTC and relative to the report), room, type, the cited quote,
the event text with the quote highlighted (`<mark>`), a "Copy event id" button and an "Open in live AI Village" link
(only `https://theaidigest.org/` links are ever opened; anything else is withheld with a note).

**Audit: show rejected** (header switch, key `A`): by default quotes and claims that failed verification are hidden,
and every place that hides something says how many. Turn the switch on to see them, marked in red and hatched.

## Opening it

* `index.html` in a browser: shows an empty state with a "Load JSON" button and drag & drop for a `report.json`.
* `index.html?demo=1`: synthetic data generated in the page (clearly marked DEMO, fictional agents), so all views can be
  exercised. The generator only runs with this parameter; `&n=5000` makes 5000 demo claims for a scroll/filter stress test.
* A report embedded at build time opens directly, see below.

### Data loading order

1. `<script id="report-data" type="application/json">...</script>`: if its content is not `null`, it is used
   (this is what `embed.py` fills in).
2. `?demo=1`: the built-in demo generator.
3. `fetch('report.json')` relative to the page: only tried when served over `http(s)` (browsers block `fetch` on
   `file://` pages; a 404 from a server without that file is expected and ignored).
4. Otherwise the empty state: "Load JSON" button or drop a file anywhere on the page. Files are read locally.

State lives in the URL hash (`#/claims?q=Q3&s=verified&t=deploy&p=2&audit=1`, `#/propagation?c=4&x=linear`, `#/findings?f=F1|F3`),
so any view can be linked or bookmarked. Keyboard: arrow keys / Home / End move between tabs, `1`-`5` jump to a view,
`/` focuses claim search, `A` toggles audit, `Esc` closes the evidence panel (focus returns to where it was opened).

## Embedding a report (one file to hand out)

```
python viewer/embed.py --report report.json --out report.html
```

`embed.py` (standard library only) replaces the `null` inside `<script id="report-data" ...>null</script>` with the
report. Transcript text is untrusted, so the JSON is made safe for a script element: every `</` becomes `<\/`,
`<!--` and `<script` are written with a `<` escape, and U+2028/U+2029 are escaped. The result still decodes to
exactly the original report (tests: `tests/test_viewer_embed.py`). It refuses a template that has no placeholder or
one that already carries a report. Use `--template` to embed into another copy of the viewer.

## Data contract

`report = {meta, metrics{final, first_pass, first_pass_by_model, tracer}, findings[], claims[], cascades[]}`, see the
docstring of `src/swarmscope/report.py`. Every field may be missing; the viewer shows an honest empty state instead of
guessing. Claim `flags` (e.g. `actors_unsupported`) and `derived.{first_ts,last_ts}` are shown when present. Finding
`verdicts` / `reviews` (`[{reviewer, verdict, note}]`), `limitations`, `episode` and `confidence` are read
defensively because the curated-findings shape is still evolving.

## Security model

* Report text is only ever placed into the page with `textContent` / `createElement`; the source contains no
  `innerHTML`, `insertAdjacentHTML`, `outerHTML` or `document.write` (a test asserts this).
* A `Content-Security-Policy` meta tag allows only inline script/style, `data:` images and same-origin `connect-src`.
* Deep links must parse as `https://theaidigest.org/...` with no credentials; opened with `target=_blank rel="noopener noreferrer"`.
* No external requests, fonts, analytics or storage of report data. The only thing stored (in `localStorage`, if
  available) is the chosen light/dark theme.

## Design notes

Restrained, evidence-first: paper-and-ink palette with one signal blue, a green verified seal and a vermilion reject
colour; serif headings and numerals, monospace for quotes and ids. Light/dark follow `prefers-color-scheme` with a
toggle; layout works from 360 to 1600 px; animations are disabled under `prefers-reduced-motion`. Status is never
conveyed by colour alone (icon + label on every seal).

## Known limits

* Relative times are computed against the report's `meta.generated` (or now, if absent).
* The spread timeline plots the embedded hops only (the earliest 40 adopters per cascade); the counts shown are the full ones.
* Requires a browser with CSS `light-dark()` (Chrome 123+, Firefox 120+, Safari 17.5+).
