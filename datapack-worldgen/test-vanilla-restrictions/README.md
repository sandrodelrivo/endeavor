# test-vanilla-restrictions

Smoke test of the NeoForge biome_modifier add+remove pattern in a clean environment.

## Purpose

Determine whether `neoforge:remove_features` and `neoforge:add_features` actually work in this NeoForge build, isolated from any third-party complications (Ore Veines+, Terralith, Create, etc.).

## What it does

Four ore families, each with a `remove_features` (scrub from all overworld) + `add_features` (re-place in one specific vanilla biome) pair. Vanilla ores only, vanilla biomes only.

| Ore family | Removed from | Re-added to |
|---|---|---|
| `minecraft:ore_diamond` (×4 variants) | `#minecraft:is_overworld` | `minecraft:badlands` |
| `minecraft:ore_lapis` (×2 variants) | `#minecraft:is_overworld` | `minecraft:jungle` |
| `minecraft:ore_redstone` (×2 variants) | `#minecraft:is_overworld` | `minecraft:taiga` |
| `minecraft:amethyst_geode` | `#minecraft:is_overworld` | `minecraft:swamp` |

Pack ID: `test-vanilla-restrictions`. Namespace inside: `test`.

## Test setup

1. Spin up a clean vanilla NeoForge 1.21.1 instance - **NO other mods**. Not even moredfs, not Ore Veines+, not Terralith.
2. Drop this pack's zip into the world's `datapacks/` folder before world creation, OR use the world creation screen's data pack picker.
3. Create a new world - default seed is fine.
4. Test by digging in each target biome.

## What the result tells us

**Phase ordering note:** NeoForge runs biome_modifiers in phase order - ADD phase first, then REMOVE phase. Our remove targets `#minecraft:is_overworld` which **includes** the add target biome (e.g., `minecraft:badlands` is in the overworld tag). So the remove will strip the ore even from where we just added it. Per stock-modifier semantics, the most likely outcome of this exact pattern is **no ores anywhere**, not "ores only in target."

That's still useful diagnostic. The four possible outcomes:

| Observation | Diagnosis |
|---|---|
| No diamonds, lapis, redstone, or geodes anywhere | `remove_features` works. The phase-ordering theory is correct; add+remove on overlapping sets nets to remove. We need a different approach to scope-to-biome (custom modifier or non-overlapping biome lists). |
| Ores exist in target biomes only (e.g., diamond only in badlands) | `remove_features` works AND the phase ordering is forgiving enough that add applies after remove. The v1/v2 design was correct and the user's observation that ores still spawned was caused by something else (Ore Veines+ very likely). |
| Ores exist everywhere unchanged | Either `remove_features` doesn't fire at all, or NeoForge doesn't load datapack biome_modifiers in this environment. Same diagnostic value as before. |
| Ores in target biomes AND elsewhere | `remove_features` is partial / not finding all biomes / silently skipping something. |

## Verification mechanics

For each ore, navigate to a chunk in **both** the target biome and a non-target biome:

- **Diamond:** `/locate biome minecraft:badlands` → tp there, dig at y=-30 to y=0. Then tp to a non-badlands biome at the same y range.
- **Lapis:** `/locate biome minecraft:jungle` vs anywhere else, y=-32 to y=32.
- **Redstone:** `/locate biome minecraft:taiga` vs anywhere else, y=-64 to y=0.
- **Amethyst geode:** `/locate biome minecraft:swamp` vs anywhere else. Geodes are larger and clustered - often visible at the surface or via cave openings; can also `/locate structure` if there's a corresponding structure tag, otherwise fly underground from y=0 down.

## What this pack deliberately does NOT include

- Climate functions (no moredfs requirement)
- Far-waste density functions
- Any Endeavour-namespace tags (so it works without our worldgen pack loaded)
- Any modded ores (Create / CN / IE)
- Any biome_filter overrides via Ore Veines+ (this pack is meant to run withOUT that mod)

The point is to isolate one variable at a time: does `neoforge:remove_features` work when nothing else is in the way.
