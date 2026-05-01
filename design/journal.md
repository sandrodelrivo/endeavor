# Worldgen Journal

Chronological log of worldgen experiments, dead ends, and decisions made along the way. The design doc describes what *is*; this describes what we *tried* and *learned*. Newest entries on top.

---

## 2026-05-01 — Climate function rev 2: clamped linear T + sin⁷ V + noise blur

### Why

The first working sin/sin prototype produced bands that were directionally correct but uncomfortably stark:

- Pure first-order sin spends *more* time near the extremes than near zero (it slows down as it approaches each peak), so the world ended up dominated by ±1 climate values — narrow temperate band, vast snowy/desert regions on either side.
- Band edges were visibly laser-cut — biomes changed in straight lines because the gradient had no high-frequency wobble.

### Decision

Pulled apart the two axes; they want different shapes:

- **Temperature → clamped linear ramp.** Talked with Sandro; we lean into the extremes for temp specifically. The "permafrost wall to the north, permadesert wall to the south" feel is on-theme for Endeavour. Function: `T = clamp(z / 25000, -1, 1)`. Green band at |z|<3k (T<0.12), mostly cold by 10k (T≈-0.4), permafrost at 25k+. Symmetric on the south side.
- **Vegetation → sin⁷.** Raising sin to an odd integer power keeps periodicity and sign but redistributes time-spent — sin⁷(x) is near 0 for most of its domain, with brief sharp peaks at ±1 near sin's natural peaks. Half-period 3k. Result: most of the world has moderate humidity (where biome variety lives), with narrow bands of wet (jungle/swamp) and dry (badlands-flavor) every 6k.
- **Noise blur on both.** Added `0.2 · vanilla_shifted_noise(temperature_or_vegetation_noise, xz_scale=0.25)` to each. Vanilla biome-scale Perlin gives ~±0.2 wobble on top of the deterministic gradient. Smooths the band edges without changing the macro shape.

`SIN_ORDER` placeholder: must stay odd to preserve negative-half-cycle sign. Default 7. If we want sharper peaks, 9 or 11; if we want closer-to-vanilla sin shape, 3.

### Open questions kicked down the road

- Does `permafrost extends infinitely past 25k` interact badly with anything? Practical answer: the world border / transport friction caps exploration well before that's a problem. Worth noting in the design doc that the world is intentionally bounded by climate even without a hard border.
- Vegetation's 6k full period vs. temperature's 50k effective span (the linear ramp covers ±25k before clamping) is a deliberate asymmetry: temperature is a global gradient, humidity is local variety. Confirm this still feels right at PERIOD = 60000 (production scale).

---

## 2026-05-01 — Performance / lag triage

### Symptom

Slideshow FPS in a fresh world with the full modpack. Chunks generated but framerate didn't recover after loading completed.

### What fixed it

- **8GB client heap** (default 2GB was the floor we were hitting).
- **Distant Horizons off.** This was the dominant cost. With DH disabled, post-load FPS climbed to 55–60 on a 1660 Super.

### Notes for later

DH stays in the modlist as `[opt]`; it's clearly playable-but-expensive. Future work: figure out the right DH render distance for our target hardware before re-enabling. Probably needs a per-user config rather than a server-wide default.

---

## 2026-05-01 — `flat_cache` wrapping the climate functions

### Why

Climate functions are 2D (depend only on x, z). Without a cache marker, the noise router would call `moredfs:sin(moredfs:z)` once per (x, y, z) sample — and the router samples each column at multiple Y values for aquifer / surface / decoration purposes. That's 16–100× redundant evaluation.

### What

Wrapped both `temperature` and `vegetation` in `minecraft:flat_cache` (4×4 column resolution, evaluated once at Y=0 per column). Matches vanilla's pattern for `continents` — checked the vanilla `data/minecraft/worldgen/density_function/overworld/continents.json`, which is also `flat_cache(shifted_noise(...))`.

### Why not `cache_2d`?

`cache_2d` is per-block horizontal resolution — too fine for biome selection, which already samples climate at 4×4 cells. `flat_cache`'s 4×4 cache aligns with biome resolution, so there's zero precision loss for our use.

### Why not nest both like vanilla `shift_x` does?

Vanilla's `shift_x` is `flat_cache(cache_2d(shift_a(...)))`. The double wrapping helps when an inner function has expensive intermediate state worth caching at finer resolution than the outer wrapper. Our chain (`mul → sin → mul → moredfs:z`) is cheap enough per call that the inner cache wouldn't pay for itself.

---

## 2026-05-01 — Pivot to `more-density-functions` library mod

### The pure-datapack dead end

Spent a chunk of time trying to build the toroidal climate in pure datapack form. It cannot be done in 1.21.1 vanilla. Confirmed:

- No density function returns world X or Z. Only `y_clamped_gradient` reads a world coordinate (Y).
- `shifted_noise` *samples* a 3D noise at a position-derived input, but the output is the noise's value, not the position.
- `spline` takes a density function as input — but with no `world_x` or `world_z` primitive to feed it, you can't construct a periodic-in-position function.

The original design doc's "Approach A" — low-`xz_scale` shifted_noise — produces 2D-isotropic slow climate, not strict directional bands. It looks like "slowly varying noise everywhere," not "north cold, south hot." The doc anticipated this as a fallback option ("Write a small NeoForge mod that injects a custom density function with real periodic behavior"). We took the option.

### `xz_scale` math gotcha

The original placeholder `xz_scale = 0.00003` produced a uniformly temperate world — bug, not by-design. Why: each Minecraft noise has `firstOctave` defining its dominant period (`minecraft:temperature` has `firstOctave: -10` → period 1024 in noise input space). The world-space period of one full noise cycle is `noise_period / xz_scale`. So `xz_scale = 0.00003` gave a period of 34M blocks — we were sampling 0.07% of one cycle across the world.

Correct math: `xz_scale = noise_period / desired_world_period`. For one cycle in 25k blocks: temperature `xz_scale ≈ 0.041`, vegetation `xz_scale ≈ 0.010` (different because the two noises have different `firstOctave`).

This whole branch became moot once we switched to `moredfs:sin(moredfs:z)`, which doesn't depend on noise period at all. But noting it because the same trap applies if anyone tries to do periodic climate via shifted_noise tricks again.

### The fix

Added [More Density Functions](https://modrinth.com/mod/more-density-functions) (modid `moredfs`) by klinbee, NeoForge build 2.2.1 for 1.21.1. Adds:

- `moredfs:x`, `moredfs:y`, `moredfs:z` — return world coordinates as density-function values.
- `moredfs:sin`, `moredfs:cos`, `moredfs:tan` (and arc/hyperbolic versions) — trig in radians.
- `moredfs:mod`, `moredfs:floor_mod` — wrap-around math.
- `moredfs:power`, `moredfs:sqrt`, `moredfs:cbrt` — powers and roots.
- `moredfs:x_clamped_gradient`, `moredfs:z_clamped_gradient` — directional ramps.

Listed `[hard]` in `design/mod-list.md` under Worldgen.

### Trade-off accepted

map.jacobsjo.eu cannot evaluate `moredfs:*` types — it's a JavaScript reimplementation of vanilla worldgen, has no way to execute the mod's Java. Loading the .jar into the page is silently ignored; unknown types stub to `0`. Diagnostic: if the entire map renders as plains/birch (T=0, V=0 everywhere), the viewer is no-opping our functions.

Testing therefore requires a real Minecraft instance. Slower iteration cycle. Worth it.

---

## 2026-05-01 — Initial sin prototype: orientation + period validation

First working version using `moredfs:sin(moredfs:z)`. Found in playtest:

- **Orientation flipped.** Prototype shipped with `SIGN = -1.0`, which made `+z` (south) cold and `-z` (north) hot — opposite of design doc convention. Fix: `SIGN = +1.0`. Single-character patch.
- **Math worked the first time.** F3 readout at z=15000 showed `T=-1.0, V=0`, ice spikes generating; at z=-15000, `T=+1.0, V=0`. After sign flip: `T=+1` at +z (south = hot), `T=-1` at -z (north = cold). Matches design doc.
- **Period 60000 → 2000 for visualization testing.** With production-scale 60000 the bands are wider than a typical Chunky pre-render area and don't show up in Xaero's map view. Dropped to 2000 (extremes at ±500) to verify the band pattern visually. To restore production scale: replace `0.00314…` with `0.000104…` (= 2π / 60000).

---

## How to use this journal

When making a non-trivial worldgen decision, add an entry here with: the symptom or question, what we tried, what worked, what we ruled out, and the resulting decision. Keep entries dated. Don't edit old entries to "correct" history — add a new entry that supersedes the old one and reference it. The point is a record of the design's evolution, not a snapshot of the current state.

The current state lives in [design-doc.md](design-doc.md), [mod-list.md](mod-list.md), [tier-map.xlsx](tier-map.xlsx), and the actual data/code in `datapack-worldgen/`, `datapack-rules/`, `mod/`. This journal explains *why* those look the way they do.
