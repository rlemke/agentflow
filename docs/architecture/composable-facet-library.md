# A composable facet library for LLM-authored workflows (design)

The blueprint for Facetwork's next step: turn a *pile of facets that grew organically for
humans* into a **deliberately-designed, complete, orthogonal, discoverable, distributed
library of primitives** — so Claude can satisfy a complex natural-language request by
*composing* it, remember how (the catalog + authoring summary), and reuse it without
replaying the refinement. OSM is the worked case; the model generalizes to any domain.

Pairs with: [Claude workflow catalog](claude-workflow-catalog.md) (the memory of solved
requests), [extending with new handlers](extending-with-new-handlers.md) (the growth path),
[`use` resolution](catalog-use-resolution.md) (libraries are pinned, not loose files),
[`agent-spec/tools-pattern.agent-spec.yaml`](../../agent-spec/tools-pattern.agent-spec.yaml)
(the handler/tools/cache contract), and the AI-authorship thesis (`docs/thesis/ai-authorship.md`).

## 1. The shift, and the moat

Facetwork started as "humans write workflows in a DSL." The value now is a different shape:

- **A vast library of reusable functionality** (facets/events) — the *primitives*.
- **Claude composes** a workflow that satisfies an NL request from those primitives.
- **The catalog remembers** how the request was satisfied — an immutable, parameterized,
  reviewed workflow with an **authoring summary** of intent.
- **The fleet executes** it, distributed (per-region `foreach` fan-out, lock-free).

The moat is the third point. The expensive part of an NL request is the **refinement** —
turning *"map the interstate freeways in California"* into a precise spec (`highway=motorway`
∧ `ref` starts "I "; which facets; which params). Running is cheap by comparison. The catalog
+ summary make that refinement a **one-time cost per request-family**; the library makes the
spec *expressible* by composition. Library and memory reinforce each other: the memory shows
which compositions recur → which primitives to harden and add.

## 2. Where we are — and the gap

The osm package has ~99 workflows and many facets, but it grew *organically for humans*, so
it is **not** a composable library. Symptoms observed in practice:

- **Holes** — several `extract_*` functions were declared but never written. `extract_amenities`,
  `extract_places_with_population`, `extract_parks`, and `extract_buildings` are now implemented
  (joining `extract_roads`); `extract_routes` (relation stitching) and `extract_pois` (aggregate
  shape) remain.
- **Inconsistent contracts** — `FilterByOSMTag` filters a PBF; `FilterGeoJSONByOSMType` filters
  GeoJSON; `CacheRegion` yields the *full* region PBF, not category extracts.
- **No semantic discovery** — Claude must already know "fast food" → `amenity=fast_food`. There
  is no queryable index of facet capabilities or the domain's tag vocabulary.
- **Not designed for repeated composition** — a single business search filtered the full 1.2 GB
  California PBF (~54 min) because nothing was designed to be re-composed cheaply.

Closing this gap is the work this document specifies.

## 3. Design principles

1. **Orthogonal** — one facet, one operation. No facet should do "extract *and* filter *and*
   render"; those are three composable steps.
2. **Complete** — no declared-but-unimplemented facets. A facet in the library *works*.
3. **Uniform contracts** — primitives in a layer share an I/O convention (below), so any output
   feeds any compatible input. This is what makes composition predictable for an LLM.
4. **Single-region leaf, fan-out at the workflow** — leaf facets take ONE region; multi-region is
   `andThen foreach` at the workflow, so the fleet parallelises (the established preference).
5. **Cheap to re-compose** — operate on cached *category* extracts (or PostGIS), never re-scan the
   full region PBF per query. Cache + idempotency are first-class.
6. **Discoverable** — every facet carries machine-readable purpose, typed params, effects, and a
   rough cost, and the domain ships a **vocabulary** (the tag ontology) Claude can query.
7. **Distributed by construction** — composition is over steps the lock-free fleet schedules.

## 4. The primitive taxonomy (layered)

A request decomposes through layers; each layer has one contract. (✓ = exists, ◐ = partial/
inconsistent, ✗ = to build.)

The layering is corroborated by the open-source OSM ecosystem (see §4.1): the verbs below are
exactly the ones that recur across osmium, Overpass, the routing engines, the geocoders, and the
geometry kernels. The status column names a representative tool establishing each as a primitive.

| Layer | Role | Contract | Status — and the OSS tools that establish it |
|---|---|---|---|
| **Source** | region/file → queryable handle | `region → handle` | `CacheRegion` ✓; **per-category warm extracts** ✓ (`CombinedScan`/`ExtractCategory`, cached single pass); PostGIS source ◐; `Merge`/`Sort`/`ConvertFormat`/`ApplyChanges` ✗ (osmium, osmosis) |
| **Clip** | spatial subset of a region | `handle + bbox/polygon → handle` | `ClipByBBox`/`ClipByPolygon` ✓ (`osm.Clip`, osmium-extract → clipped `OSMCache`; osmconvert `-b`, ogr2ogr, Overpass bbox) |
| **Extract** | one category → GeoJSON | `handle + category → GeoJSON` | roads/amenities/places/parks/buildings ✓; uniform cached `ExtractCategory` ✓; routes/pois ✗ (osmium tags-filter) |
| **Filter** | narrow a GeoJSON by predicate | `GeoJSON + predicate → GeoJSON` | tag-exact ✓; tag-**prefix** ✓; **contains/regex** ✓; by-element-type ✓; radius ✓; `CompleteWays`/recurse ✗ (PBF-only — N/A at GeoJSON level) (osmfilter, Overpass has-kv / recurse) |
| **Transform / Analyze** | combine, reduce | `GeoJSON(s) → GeoJSON / scalar` | per-class stats ◐; `MergeLayers` / `Summarize` (subsumes `Count`) / `Dissolve` ✓ (`osm.Transform`, shapely); generic `Count` folded into `Summarize` (turf, shapely, PostGIS) |
| **Spatial** | relate geometries — the universal verb | `GeoJSON(s) → GeoJSON / scalar` | `WithinDistance`/`BeyondDistance`/`Nearest`/`SpatialJoin`/`Buffer` ✓ (`osm.Spatial`, shapely STRtree over a local AEQD projection); `Intersect`/`Union`, `Centroid`, `Simplify` ✗ (Overpass around/area, turf, PostGIS `ST_*`, routing isochrone) |
| **Routing** | answer over the road network | `points + profile → route / matrix / area` | **all ✗** — `Route`, `Matrix`, `Nearest`, `MapMatch`, `Isochrone`, `Trip` (OSRM, Valhalla, GraphHopper, pgRouting) |
| **Geocoding** | name/address ↔ coordinate | `query → coords` / `coords → address` | `ResolveRegion` ◐; `Geocode` / `ReverseGeocode` ✓ (`osm.geocode`, Nominatim HTTP — forward + reverse) (Photon, Pelias) |
| **Render / Tiles** | produce a viewable artifact | `GeoJSON(s) → artifact` | `RenderMap` ✓, `RenderLayers` ✓, `RenderStyledMap` ✓; `BuildVectorTiles` (→ MBTiles) ✗ (Mapnik, tippecanoe, OpenMapTiles) |

The biggest capability gaps, in priority order: the **Spatial** family (`WithinDistance`/`Nearest`/
`SpatialJoin`) — the single most universal verb across the ecosystem and the unlock for "food
deserts" or "schools without a pharmacy within 1 mile". The distance core of this family —
`WithinDistance`, its complement `BeyondDistance`, and `Nearest` — is now **shipped** (`osm.Spatial`,
see §9 item 2); `SpatialJoin`/`Buffer`/`Intersect` remain. **`Clip`** (cheap sub-region queries) is
also **shipped** (`osm.Clip`, §9 item 2). Then the two self-contained service families that turn our
extracts into answers, **Routing** and **Geocoding**; and **vector tiles** for scalable visualization.

### 4.1 Grounded in the OSS ecosystem

This taxonomy isn't invented — it's the distillation of what the mature open-source OSM programs
already do. Surveying them, the same handful of operations recur, and they fall cleanly onto the
layers above:

| Tool family | Programs | Operations they expose |
|---|---|---|
| Process / convert | [osmium-tool](https://osmcode.org/osmium-tool/manual.html), Osmosis, osmconvert/osmfilter, GDAL/ogr2ogr | [extract (bbox/polygon)](https://docs.osmcode.org/osmium/latest/osmium-extract.html), [tags-filter](https://docs.osmcode.org/osmium/latest/osmium-tags-filter.html), merge, sort, convert, apply diffs |
| Spatial query | [Overpass API / QL](https://wiki.openstreetmap.org/wiki/Overpass_API/Overpass_QL) | tag filter (has-kv), bbox, [`area`](https://dev.overpass-api.de/overpass-doc/en/full_data/area.html), `around` (radius), `recurse` (members/parents) |
| Routing | [OSRM](https://project-osrm.org/docs/v5.5.1/api/), Valhalla, GraphHopper, pgRouting ([overview](https://gis-ops.com/open-source-routing-engines-and-algorithms-an-overview/)) | route, table/matrix, nearest, map-match, isochrone, trip (TSP) |
| Geocoding | [Nominatim](https://github.com/osm-search/Nominatim), Photon, Pelias | forward geocode, reverse geocode, lookup |
| Render / tiles | Mapnik, [tippecanoe](https://github.com/mapbox/tippecanoe), [OpenMapTiles](https://openmaptiles.org/docs/generate/custom-vector-from-shapefile-geojson/) | GeoJSON→raster, GeoJSON→vector tiles (MBTiles), style, serve |
| Persist | [osm2pgsql](https://osm2pgsql.org/), imposm3 | import to PostGIS, schema mapping, keep-updated |
| Geometry kernel | GEOS, shapely, turf.js, PostGIS `ST_*` | buffer, centroid, simplify, area/length, within/contains, intersect/union, nearest |

The signal: a *small, stable* set of verbs underlies the whole ecosystem, and operations ranked by
how many independent tools implement them are the highest-value primitives. **Spatial
within-distance / nearest** appears in Overpass (`around`), every routing engine (as table /
isochrone), turf, and PostGIS — it is the universal verb, and our largest gap. **Clip by
bbox/polygon** appears in osmium, osmconvert, ogr2ogr, and Overpass. That cross-tool recurrence is
what justifies promoting these to first-class facets, and the survey adds three coherent service
families the original taxonomy didn't enumerate: Routing, Geocoding, and Tiles.

## 5. Contract conventions (the calling convention)

- **GeoJSON-path I/O.** Extract/Filter/Transform pass GeoJSON *file paths* (cache-backed), so
  steps chain and the runtime persists artifacts. Render consumes paths.
- **Tags preserved.** Filters and transforms keep OSM properties (`name`, `ref`, `amenity`, …) so
  downstream steps can filter further. (This is why the prefix filter could follow an extract.)
- **Typed schemas.** Every result is an FFL schema (`RoadFeatures`, `OSMFilteredFeatures`,
  `MapResult`, …) with `output_path` + `feature_count`, so the composer reasons about shapes.
- **One region per leaf; `foreach` to fan out.** A multi-region request is a `CollectX` workflow
  that `foreach`-es and a renderer that consumes the aggregated layers (the `FindBusinessMap`
  shape) — the runtime schedules the regions across servers.
- **Idempotent + cached.** Re-running a step with the same inputs hits the cache; primitives
  operate on cached category extracts, not the full PBF.

## 6. The discovery & semantics layer

NL → facet must be *reliable*, not guesswork. Two pieces:

1. **A capability index** — for every facet: a one-line purpose, its typed params + returns, its
   layer, effects (`@pure`/`@external`), and a rough cost. Derivable from the cataloged library
   FFL (doc comments + signatures) + effect annotations. Exposed so Claude can ask "what can
   operate on a roads GeoJSON?" or "what extracts amenities?" — the facet-level analogue of
   `fw_catalog_search` (which today finds *workflows*).
2. **A domain vocabulary (ontology)** — the tag values the domain understands: `amenity` values
   (fast_food, cafe, pharmacy, bank…), `shop` values, `highway` values, etc., with synonyms. This
   is what lets "find a pharmacy" map to `amenity=pharmacy` deterministically, and tells the
   composer whether "business type" keys on `amenity` or `shop`.

Together these turn "compose a workflow" from pattern-matching on memorised tags into a
*lookup-then-compose*.

## 7. Worked decomposition

*"Show the food deserts in California"* (areas far from a supermarket) decomposes onto the target
library as:

```
foreach region in [California]:
    cache  = Source.Cache(region)
    shops  = Extract(cache, category="supermarket")      # shop=supermarket
    pop    = Extract(cache, category="population_places") # place=*
    far    = SpatialBeyondDistance(pop, shops, "1mi")     # population points > 1mi from any shop
    yield layers += [far]
RenderLayers(layers)
```

It needs exactly two primitives: complete category extraction (shipped, item 1) + a **spatial
within/beyond-distance** transform. As of item 2 both exist, so the decomposition is now
*expressible* — shipped as the parameterized `osm.Spatial.workflows.PlacesBeyondReach`
(`Cache → ExtractCategory(amenities) → Filter(tag=value) → ExtractCategory(population) →
BeyondDistance → RenderMap`), of which "food deserts" is the `shop=supermarket` instance and
"healthcare deserts" the `amenity=hospital` instance. The interstate example we shipped earlier
(`Source.Cache → Extract(roads,motorway) → Filter(ref prefix "I ") → Render`) already fit the
model — it just exposed that `Extract(roads)` and the prefix filter had to be built first.

## 8. Memory + reuse (the flywheel)

- **Reuse-first.** Before authoring, match the request against the catalog by intent (the
  authoring summary). A match → fill the typed params → run, reusing the refined spec.
- **Parameterize for families.** One workflow should cover a request *family* (`FindBusinessMap`:
  name + type + regions → thousands of requests), not a single phrasing.
- **Grow from solved requests.** When composition hits a missing primitive, the run preflight
  names the gap → `scripts/scaffold-handler` scaffolds it → review → it *joins the library*. The
  library's growth is driven by real demand, and the catalog records which compositions recur,
  pointing at which primitives to harden next.

## 9. Roadmap (prioritized)

1. **Extraction complete + uniform + cheap** — ✅ *shipped*. Holes filled (amenities, places,
   parks, buildings, roads); the uniform cached `ExtractCategory` facade warms the cheap point
   categories in one cached single pass (heartbeat-safe on full-state PBFs), so a business query
   is seconds-then-instant instead of a 54-minute full-PBF filter. Proven end-to-end:
   `FindBusinessMapCheap` on California rendered **12,189 `fast_food` outlets**
   (`CacheRegion → ExtractCategory(amenities) → FilterGeoJSONByOSMType → RenderMap`), and the
   warm cache makes subsequent business queries on the region an instant lookup. The run also
   surfaced a real distributed-systems lesson: a multi-minute single pass must heartbeat (or
   register `timeout_ms=0`) or the task lease expires and it retries forever. The first warm was
   then made ~29× faster by pushing a C-level `KeyFilter` (union of the plugins' interest keys)
   into osmium for node-only scans — benchmarking showed the node-location index wasn't the cost,
   the per-element Python callback over ~99%-untagged nodes was (264 MB region: 347s → 12s, counts
   unchanged), extrapolating California's warm from ~26 min to ~1 min. Remaining: `routes`/`pois`.
2. **`Clip` + the `Spatial` family** — the distance core is ✅ *shipped*: `osm.Spatial` now exposes
   `WithinDistance` (keep subject features within *d* of any reference — Overpass `around` /
   PostGIS `ST_DWithin`), `BeyondDistance` (its complement — the "food desert" primitive), and
   `Nearest` (annotate each subject with its nearest reference distance — KNN / turf nearestPoint).
   Contract is uniform with the Filter layer (subject GeoJSON path + reference GeoJSON path +
   distance → GeoJSON path, tags preserved); distances are metric in a local azimuthal-equidistant
   projection centered on the reference centroid, indexed with a shapely `STRtree` (O(log n) per
   subject feature, subject streamed). Proven by deterministic unit tests against geodesic ground
   truth (within/beyond partition the subject exactly; nearest orders by distance; unit conversion;
   empty-reference edge), then **proven end-to-end on the live fleet**: the parameterized
   `osm.Spatial.workflows.PlacesBeyondReach` ran on California (PBF cache hit + a ~1.5-min
   `amenities` warm pass) as `CacheRegion → ExtractCategory(amenities) →
   FilterGeoJSONByOSMType(amenity=hospital) → ExtractCategory(population) → BeyondDistance(10 mi) →
   RenderMap`. It filtered **142 hospitals** (from 278,795 amenity features), related **4,992
   populated places** against them via the STRtree in ~1 s, and found **3,223 places (≈65%) beyond
   10 mi of the nearest hospital** — the rendered map (bounds spanning the whole state) flags exactly
   the rural places one expects (Buttonwillow, Desert Center). "Food deserts" is the same workflow
   with `tag_key="shop", tag_value="supermarket"` (verified live: 2,224 supermarkets → 4,075/4,992
   places beyond 1 mi).
   **`Clip` is also ✅ shipped**: `osm.Clip` exposes `ClipByBBox` / `ClipByPolygon`, wired to the
   `osmium extract` tool (`pbf-clips` cache_type with SHA-validity sidecars) and returning a new
   `OSMCache` over the clipped PBF — which composes with `ExtractCategory`/Spatial for free because
   every extractor reads `cache.path`. The blocking clip runs under a heartbeat pump so the lease
   survives a multi-minute extract. Proven live (`osm.Clip.workflows.ClipAndExtract`): clipping
   California (**1,311 MB**) to a Bay-Area bbox produced a **162 MB** PBF (**8× smaller**), then
   `ExtractCategory(amenities)` ran on the *clip* (77,377 features) — the "cheap sub-region query"
   that makes continental-scale spatial work tractable. (The live run also surfaced + fixed a latent
   bug in the previously-untested `pbf_clip` tool: `osmium extract` needs an explicit
   `--output-format pbf` because the staging filename hides the extension.)
   **`SpatialJoin` and `Buffer` complete the Spatial family** (also `osm.Spatial`): `SpatialJoin`
   attaches a reference layer's properties onto each subject feature by a topological predicate
   (`intersects`/`within`/`contains` — the point-in-polygon join, projection-invariant so it queries
   the WGS84 STRtree directly), with `how="inner"`/`"left"`; `Buffer` expands each feature by a
   distance into polygons (metric AEQD project → `buffer` → reproject) for service-area coverage.
   Both proven on real California data and **cross-validated** against `BeyondDistance`: buffering the
   142 hospitals by 10 mi and joining the 4,992 places `within` the coverage found **1,768 covered**;
   1,768 + 3,223 (beyond) = 4,991 of 4,992 — two independent implementations agreeing to a single
   boundary point. **Item 2's relational core is done**; only the set-ops `Intersect`/`Union` (and
   `Centroid`/`Simplify`) remain, deferred until a target query needs them.
3. **The missing filters/transforms** — ✅ *shipped*. The Filter layer gains `FilterGeoJSONByTagContains`
   (substring, case-insensitive by default) and `FilterGeoJSONByTagRegex` (`re.search`) in `osm.Filters`,
   completing the exact/prefix/contains/regex match family. A new `osm.Transform` namespace adds the
   generic combine/reduce verbs: `MergeLayers` (concatenate GeoJSON layers — the foreach-fanout
   aggregator), `Summarize` (count, optionally grouped by a tag, with count/sum/avg/min/max over a
   measure — subsumes the listed `Count`; writes a JSON breakdown), and `Dissolve` (union each group's
   geometries — PostGIS `ST_Union … GROUP BY` / turf dissolve). `CompleteWays`/recurse is **N/A** at the
   GeoJSON level (features are already complete; it's a PBF-only concept, available via `FilterByOSMType`'s
   `include_dependencies`). Proven on real California data, internally cross-consistent: `Summarize` of
   278,795 amenities → 448 categories in ~1 s (restaurant 21,170 + cafe 7,165); the regex filter
   `amenity ~ /^(cafe|restaurant)$/` returns exactly 28,335 = 21,170 + 7,165; `MergeLayers` of that with
   the 1,556 `name⊃"Starbucks"` matches = exactly 29,891; `Dissolve` of the 142 hospital-coverage circles
   → one MultiPolygon. Remaining (deferred): the Spatial set-ops `Intersect`/`Union`.
4. **The service families** — in progress. **`Geocoding` ✅ shipped**: `osm.geocode.Geocode`
   (forward — the facet was declared but had no handler) and the new `osm.geocode.ReverseGeocode`,
   both backed by a Nominatim HTTP client (`_osm_tools/geocode.py`) with a configurable endpoint
   (`AFL_NOMINATIM_URL` — point at a self-hosted instance for volume), a required User-Agent, and a
   polite ~1 req/s throttle for the public instance; results are the typed `GeoCoordinate`, cached on
   a synthetic key, and an unresolved query fails explicitly. Proven live against public Nominatim:
   "Golden Gate Bridge" → (37.820, −122.479), Google HQ → "Google Building 41", a clean
   forward→reverse round-trip, and reverse of Eiffel-Tower coords → "Avenue Gustave Eiffel, Paris".
   **`Routing` core was already present** (`osm.Routing.{API,OSRM}.Route` / `MultiStopRoute` /
   `Isochrone`, plus GraphHopper/Valhalla graph builders) — the genuine gaps are the `Matrix` /
   `Nearest` / `MapMatch` verbs (need a running OSRM/engine) and a `Trip` facet. **`BuildVectorTiles`**
   remains a thin facet wrapper over the complete `_osm_tools/vector_tiles_build.py` (tippecanoe), to
   be added once tippecanoe is available in the target environment.
5. **Build the discovery layer** — the capability index + the OSM tag vocabulary, exposed to the
   composer (an MCP `fw_capabilities`-style surface).
6. **Reuse-first catalog matching** — search-by-intent before authoring; aggressive parameterization.
7. **Effect + cost annotations** — so the composer chooses efficient compositions.

Each item is additive — it extends the typed/validated/distributed substrate, never relaxes it
— consistent with the thesis's design position. The end state: a complex OSM NL request is
*looked up or composed* from an orthogonal, discoverable primitive set, **remembered** as a
parameterized workflow, and **executed across the fleet** — and the library compounds with every
request it learns to satisfy.
