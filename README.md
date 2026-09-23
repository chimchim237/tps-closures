# Proposed TPS School Closures

An interactive map of the 17 Tulsa Public Schools campuses named for closure in the
Superintendent's *Proposal to Address Budget Deficit* (board presentation, 21 September 2026),
plotted against median household income by census tract or ZIP code, with every other
district site shown for contrast and the four "other building changes" from the same slide.

Static site: one HTML page, one script, one stylesheet, three GeoJSON files, and a vendored
copy of MapLibre GL JS. No build step. Any static host serves it (GitHub Pages included).

## Run it locally

The page fetches its data with `fetch()`, so it needs to be served over HTTP rather than
opened as a `file://` URL.

```sh
python3 -m http.server 8000
# then open http://localhost:8000/
```

## Where each figure lives

Contributors will most often want to edit the data, not the code.

| File | What it holds | Source |
|---|---|---|
| `data/schools.geojson` | All 85 campuses: name, address, ZIP, tract GEOID, level, status (`closure` / `change` / `open`), closure number, feeder pattern (`feeder`, plus `feeder_proposed` / `feeder_note` where the proposal moves a school), consolidation group (`group`, `group_students`, `group_families`), welcoming sites (`welcoming`, `welcoming_note`, and the reverse `receives_from`), and the per-site rows shown on cards (enrollment, occupancy, staffing, bond, building) | Slides 27–46 of the board presentation; TPS *Our Schools* pages (feeder headings); TPS *Directory of Schools 2026–27*; U.S. Census Geocoder; Tulsa World, 21 Sep 2026 |
| `data/tracts.geojson` | 208 Tulsa County tracts + 5 Osage County tracts that reach into west Tulsa: median household income, margin of error, population, poverty rate, reliability flag | ACS 2024 5-year, tables B19013 / B01003 / B17020 via the Census API; Census cartographic boundaries (500k, 2022) |
| `data/zips.geojson` | 38 ZIP Code Tabulation Areas: median household income, MOE, population, reliability flag | ACS 2024 5-year as republished by IncomeByZipCode.com; 2010 ZCTA boundaries |

`tools/add_feeders_groups.py` holds the feeder membership, group and welcoming-site tables
in one place and rewrites those properties; edit it and rerun rather than editing 85 features.
The feeder building-use figures (slide 46) live in `FEEDERS` at the top of `assets/app.js`.

To add or correct a card row, edit the feature's properties in `schools.geojson`. Empty rows
are simply omitted from the card. To add a school, add a Point feature with at least `id`,
`name`, `address`, `zip`, `tract_geoid`, `level` and `status`; `number` is required only for
closures and drives the pin label and the sidebar order.

Notes on the data:

- Coordinates come from the U.S. Census Geocoder (`Public_AR_Current`), one address at a time,
  with one exception recorded in `coord_source`: the 3100 block of W Edison St has no address
  range in Census TIGER, so the Central campus uses the published Wikipedia coordinate.
- Tract assignment is point-in-polygon. Greenwood Leadership Academy, Central and S.O.A.R.
  fall in Osage County — west Tulsa north of the river is across the county line — which is
  why five Osage tracts are included.
- The `reliability` flag is `small` (population under 500), `wide` (MOE above 25% of the
  estimate for tracts, 17% for ZIPs) or `ok`. Flagged areas draw with a dashed outline.
- ZIP 74117 has no published median (population 52) and draws in the no-data color.

## How the map is drawn

`assets/app.js` loads the three GeoJSON files, then:

- uses CARTO's Positron (light) or Dark Matter (dark) vector basemap, choosing by the
  viewer's color scheme and switching live when it changes;
- inserts the income shading and outlines *before the basemap's first symbol layer*, so
  street and place names render above the shading;
- draws remaining sites and building-change sites as circle layers, and the 17 numbered
  closure pins as DOM markers (keyboard-reachable, no glyph dependency);
- on selection, draws dashed links from a closing site to its welcoming sites (or into a
  welcoming site from the closures it takes) and rings the welcoming sites;
- the "Highlight" select, and the group / feeder rows in the sidebar, fade every school outside
  the chosen consolidation group or feeder pattern (feature-state `dim`; faded sites are inert);
- reads every color from the CSS tokens in `assets/style.css`, so restyling the page restyles
  the map.

Add `?style=blank` to the URL to run without the basemap (used by the tests).

## Deploying as a subfolder of another site

The page uses only relative paths, so it can live at any URL — `example.org/tps-closures/`
works with no changes. Two things matter on the host:

- `.mjs` files must be served with a JavaScript MIME type; the included `.htaccess` sets
  this for Apache / cPanel. Without it, browsers refuse to load the MapLibre module.
- The same `.htaccess` makes `index.html`, `assets/*`, and `data/*` revalidate on every visit
  (`Cache-Control: no-cache`, served as cheap 304s) while the vendored MapLibre modules and
  images cache for a week. Without that, a browser that visited before a deploy can pair the new
  page with a week-old script.
- The page fetches its data, so it must be served over HTTP, never opened from `file://`.

On cPanel, the simplest route is **Git Version Control → Create → Clone a Repository** with
this repo's public URL and a repository path of `public_html/tps-closures`. cPanel then
serves it at `/tps-closures/` and "Update from Remote" pulls new commits. The site's own
private repository never needs to reference this one.

## Social preview

`og-image.png` (2400×1260) is the Open Graph / Twitter card image referenced from `index.html`.
`tools/make_og_image.py` regenerates it from the page itself in headless Chromium; rerun it after
changing the closure list or the header figures.

## Tests

`tests/test_map.py` drives the real page in headless Chromium with Playwright and exercises
hover, click, keyboard, every toggle, the tract/ZIP switch, zoom and pan, phone width and
dark mode, welcoming links and group / feeder highlights — 101 checks. It runs offline against `?style=blank`.

```sh
pip install playwright && playwright install chromium
python3 tests/test_map.py
```

## Sources

- Tulsa Public Schools, *Superintendent's Proposal to Address Budget Deficit*, board presentation, 21 September 2026 (slide 27; slides 7–49 for groups, welcoming sites, headcounts, feeder shifts, building use, criteria and budget figures).
- Tulsa Public Schools, *Directory of Schools 2026–2027* (addresses).
- Tulsa Public Schools, *Our Schools* pages, tulsaschools.org/enrollment/our-schools, feeder-pattern headings, read 22 September 2026 (feeder membership for all 85 sites).
- U.S. Census Bureau Geocoder, `Public_AR_Current` benchmark (coordinates).
- U.S. Census Bureau, American Community Survey 2024 5-year estimates, tables B19013, B01003, B17020, via `api.census.gov` (tract income, population, poverty).
- U.S. Census Bureau, cartographic boundary files, 500k, 2022 vintage, via the Bureau's `citysdk` repository (tract boundaries).
- IncomeByZipCode.com, ACS 2024 5-year republication (ZIP income); 2010 ZCTA boundaries via OpenDataDE (ZIP boundaries).
- Tulsa World, "18 schools listed in draft TPS closure, repurposing proposal," 21 September 2026 (feeder patterns, enrollment, occupancy, staffing, bond history).
- Tulsa Flyer, "What you need to know about the proposed $12 million cuts at Tulsa Public Schools," 18 September 2026 (process and dates).
- Base map © OpenStreetMap contributors, © CARTO. Rendered with MapLibre GL JS (BSD-3-Clause, vendored in `vendor/`).

## License

Code: MIT (see `LICENSE`). Data files are compiled from the public sources above and are
released under CC BY 4.0; please cite the original sources when reusing the figures.
