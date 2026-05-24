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

| Layer | Role | Contract | OSM today → target |
|---|---|---|---|
| **Source** | get a region's data into a cheap-to-query form | `region → handle` | `CacheRegion` ✓ (full PBF) → also emit **per-category extracts** ✗ / PostGIS source ◐ |
| **Extract** | pull one category of features as GeoJSON | `handle + category → GeoJSON(path)` | roads ✓; amenities/places/parks/buildings ✓ (holes now filled); routes/pois ✗ (relation/aggregate shapes); uniform `Extract(category)` facade ✗ |
| **Filter** | narrow a GeoJSON by predicate | `GeoJSON + predicate → GeoJSON` | tag-exact ✓; tag-**prefix** ✓ (added); **contains/regex** ✗; radius ✓; **bbox/polygon (sub-region)** ✗ |
| **Transform / Analyze** | combine, reduce, relate | `GeoJSON(s) → GeoJSON / scalar` | per-class stats ◐ (roads only); **merge layers** ✗; **count/summarize (generic)** ✗; **spatial join / within-distance / nearest** ✗; dedupe ✗ |
| **Render** | produce a viewable artifact | `GeoJSON(s) → MapResult` | `RenderMap` ✓, `RenderLayers` ✓, `RenderStyledMap` ✓ |

The biggest capability gaps are **complete category extraction**, **richer filters
(contains/regex, spatial)**, and **spatial analysis (join / distance / nearest)** — the last is
what unlocks genuinely complex requests like "food deserts" or "schools without a pharmacy within
1 mile".

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

It needs exactly the missing primitives: complete category extraction + a **spatial
within/beyond-distance** transform. The interstate example we shipped
(`Source.Cache → Extract(roads,motorway) → Filter(ref prefix "I ") → Render`) already fits the
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

1. **Make extraction complete + uniform + cheap** — *holes mostly filled* (amenities, places,
   parks, buildings, roads implemented; routes/pois remain). Still open: have `Source.Cache`
   emit per-category extracts (or back the source with PostGIS) so filters/transforms run in
   seconds, not 54 minutes — completeness is done, **cheapness** is the next half.
2. **Add the missing filters/transforms** — contains/regex tag filter, bbox/polygon sub-region,
   layer merge, generic count/summarize, and the **spatial join / within-distance / nearest**
   family (the unlock for complex requests).
3. **Build the discovery layer** — the capability index + the OSM tag vocabulary, exposed to the
   composer (an MCP `fw_capabilities`-style surface).
4. **Reuse-first catalog matching** — search-by-intent before authoring; aggressive parameterization.
5. **Effect + cost annotations** — so the composer chooses efficient compositions.

Each item is additive — it extends the typed/validated/distributed substrate, never relaxes it
— consistent with the thesis's design position. The end state: a complex OSM NL request is
*looked up or composed* from an orthogonal, discoverable primitive set, **remembered** as a
parameterized workflow, and **executed across the fleet** — and the library compounds with every
request it learns to satisfy.
