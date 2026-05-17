# zzz_endeavour_worldgen

Production worldgen data pack for Endeavour. Loads after every other worldgen pack (the `zzz_` prefix is intentional - alphabetical pack-load order means our overrides win). Pack format 48 (Minecraft 1.21.1, NeoForge).

## Required runtime mods

This pack does not function without:

- [More Density Functions](https://modrinth.com/mod/more-density-functions) (`moredfs`) v2.2.1+ for `moredfs:x`, `moredfs:z`, `moredfs:sin`, `moredfs:power` used by the climate density functions.

Without `moredfs` the climate density functions silently parse to constant zero and the world generates as flat-temperate plains everywhere.

## Layout

```
zzz_endeavour_worldgen/
├── pack.mcmeta
├── README.md
└── data/
    ├── endeavour/
    │   ├── tags/worldgen/biome/        ← biome tag groups used by ore restrictions
    │   ├── worldgen/density_function/  ← named climate density functions (reusable)
    │   │   └── climate/
    │   │       ├── temperature.json
    │   │       └── vegetation.json
    │   └── neoforge/biome_modifier/    ← ore tier-locking via add/remove features
    └── minecraft/
        └── worldgen/
            ├── density_function/overworld/
            │   ├── far_waste_blend.json    ← elevated-wasteland mask at z=±25k
            │   └── far_waste_lift.json     ← Y-shift applied within the mask
            └── noise_settings/
                └── overworld.json          ← noise router, surface rules,
                                              climate-gated vein_toggle
```

## Climate

The overworld's `temperature` and `vegetation` are now string references to named density functions in `endeavour:climate/...`. Doing it this way (vs. inlining) lets `vein_toggle` and any future density function consume the same cached climate values without recomputation.

### Temperature - clamped linear ramp (`endeavour:climate/temperature`)

```
T(x, z) = clamp(z / 25000, -1, 1) + 0.2 · vanilla_temperature_noise
```

- `-z` (north) is cold, `+z` (south) is hot. Symmetric.
- `|z| < 3000`: green band, |T| < 0.12.
- `|z| ≈ 10000`: |T| ≈ 0.4, biomes go cold/warm.
- `|z| ≥ 25000`: |T| = 1.0 - clamp wall, permafrost / permadesert.
- Whole expression wrapped in `minecraft:flat_cache` (4×4 column cache).

### Vegetation - periodic sin (`endeavour:climate/vegetation`)

```
V(x, z) = sin(2π · x / VEG_PERIOD)^SIN_ORDER + 0.2 · vanilla_vegetation_noise
```

Current values in the file (preserved as-is from the prior iteration):
- the angular constant in the inner `mul` is `0.0001471975511966`
- the `moredfs:power` exponent is `1.0`

`+x` (east) is wet, `-x` (west) is dry. Adjustable per the design's tuning history.

### Far-waste terrain shaping

`minecraft:overworld/far_waste_blend` is a 0..1 mask that rises toward 1 as |z| approaches 30k, with a ramp from |z|=24k to |z|=30k blending in continentalness for shape. `minecraft:overworld/far_waste_lift` then multiplies that mask by a Y gradient (full strength at Y=52, fading to negative by Y=128) - the net effect is elevated wasteland plateaus at the climate walls. These two density functions are used inside `final_density` and `continents` of the noise router (see line numbers in `overworld.json`).

## Ore tier-locking

Every restricted ore has two biome_modifier files: a `remove_default` that scrubs the placed_feature from `#minecraft:is_overworld` (every step), and an `add_to_target` that re-places it under a curated biome tag. The numeric prefix on filenames is alphabetical-load-order grouping; remove always runs before add at the same step.

| # | Ore | Source | Target tag | Notes |
|---|-----|--------|------------|-------|
| 01 | diamond (4 placed_feature variants) | vanilla, terralith | `endeavour:volcanic_zone` | Vanilla "mine deep" replaced with "find a volcano." Terralith ships its own `minecraft:ore_diamond_medium` override; we remove and re-add it too. |
| 02 | emerald | vanilla | `endeavour:emerald_peaks` | Tightens vanilla mountain-only restriction further to terralith's `emerald_peaks` only. |
| 03 | redstone (2 variants) | vanilla | `endeavour:scarlet_mountains` | |
| 04 | lapis (2 variants) | vanilla | `endeavour:amethyst_zone` | |
| 05 | amethyst geode | vanilla | `endeavour:amethyst_zone` | Step is `underground_decoration`, not `underground_ores`. |
| 06 | zinc | create | `endeavour:mesa_family` | Critical T2 gate. |
| 07 | uranium | createnuclear | `endeavour:extreme_cold` | T4 atomic, north wastes. |
| 08 | thorium | create_new_age | `endeavour:extreme_hot` | T4 atomic, south wastes. Forces an expedition to *both* climate walls for full atomic capability. |
| 09 | oil reservoir | create: diesel | `endeavour:tier_2` | **Caveat:** C:D' uses a biome tag "oil_biomes" along with a config flag "DISABLE_NORMAL_OIL_CHUNKS"|

### Biome tags driving the locks

Membership lists are stored in `data/endeavour/tags/worldgen/biome/*.json`. Each tag uses `"replace": false` so it composes with other packs' definitions of the same tag name (none expected, but it's the safe default).

| Tag | Members | Source |
|-----|---------|--------|
| `mesa_family` | badlands × 3 (vanilla) + 4 terralith mesa biomes | xlsx Biomes sheet, terrain class = Mesa |
| `volcanic_zone` | terralith volcanic_crater, volcanic_peaks, caldera, thermal_caves, white_cliffs | xlsx, terrain class = Volcanic |
| `scarlet_mountains` | terralith:scarlet_mountains | only member |
| `emerald_peaks` | terralith:emerald_peaks | only member |
| `amethyst_zone` | terralith:amethyst_canyon, amethyst_rainforest | xlsx amethyst-themed biomes |
| `extreme_cold` | 7 vanilla + 7 terralith Very Cold / Extreme Cold biomes | xlsx, climate column `Very Cold` or `Extreme Cold` |
| `extreme_hot` | 4 vanilla + 8 terralith Hot Dry biomes | xlsx, climate column `Hot Dry` |

## Climate-gated `vein_toggle`

The 1.18+ ore vein system (the giant iron and copper veins that thread through chunks at Y∈[-60, 51]) isn't reachable by biome modifiers - it runs off `noise_router.vein_toggle` / `vein_ridged` / `vein_gap` density functions. To biome-lock it we have to modify the density function math directly.

Vanilla behavior: `vein_toggle` is a 3D noise that picks copper (positive sign) or iron (negative sign) at a given location, with magnitude gating whether a vein exists at all.

Our patched `vein_toggle`:

```
input = endeavour:climate/temperature
T < -0.3   → -|vanilla_vein_toggle|   (iron veins, cold zone)
T > +0.3   → +|vanilla_vein_toggle|   (copper veins, warm zone)
otherwise  → 0                        (no veins - green band is vein-free)
```

Outcome:
- Iron veins appear past `z ≈ -7500` (slightly inside the cool zone, well past the spawn safety band).
- Copper veins appear past `z ≈ +7500`.
- The temperate hemisphere around spawn has no big veins at all - players have to expedition for industrial-scale iron and copper.
- Past the climate walls (`|z| > 25000`, T = ±1 clamped), veins continue at full strength.

Magnitude is preserved (`|vanilla|` keeps the noise's original distribution), so vein density inside the active zones matches vanilla's intended tuning. Sign is forced so the same noise is reinterpreted as iron in the north / copper in the south rather than randomly mixed.

## Decisions still pending

These came up during the build but lacked an explicit call. Defaults left in place; revisit when ready.

- **`createnuclear:lead_ore`** - left at default (spawns everywhere). Probably wants a tier home but the xlsx didn't list lead.
- **`createnuclear:striated_ores_overworld`** - left at default. Likely contains additional CN-specific stone variants; inspect contents before deciding.
- **IE secondary ores** (`bauxite`, `lead`, `nickel`, `silver`) - left at default. Aluminum (bauxite) especially is mid-tier industrial; leaving it everywhere undermines the "expeditions for resources" story.
- **WWOO themed ores** (`ore_diamond_volcanic`, `ore_iron_windswept`, `ore_redstone_windswept`, `ore_gold_volcanic`, `ore_coal_windswept`) - these are already biome-themed at the WWOO level, not ours to restrict further. May reinforce or conflict with our locks; check in-game.
- **Aether ore family** - gated by dimension, no overworld leakage expected, no action taken.

## Testing

1. Generate a fresh world with this pack enabled (alongside `moredfs` and the modlist).
2. F3 climate readout at spawn should show `T ≈ 0, V ≈ 0` (± noise blur).
3. `/locatebiome terralith:volcanic_crater` - go check that diamonds spawn there and nowhere else.
4. Expedition north or south past `|z| ≈ 7500`, dig - iron / copper veins should start appearing. They should be entirely absent within `|z| < 5000`.
5. Past `|z| > 25000` - permafrost / permadesert plateaus, with iron / copper veins at full density.
6. Confirm uranium spawns only in extreme cold biomes, thorium only in extreme hot, and IE uranium does NOT spawn.
7. Check IP oil reservoirs - if they appear in temperate biomes, the IP-specific config edit is required.

## Sources of truth

- [design/tier-map.xlsx](../../design/tier-map.xlsx) - biome→tier and ore→tier assignments
- [design/journal.md](../../design/journal.md) - chronological log of worldgen design decisions
- The four mod jars whose feature IDs we depend on: `create-1.21.1-6.0.10.jar`, `createnuclear-1.3.2-beta.3-neoforge.jar`, `create-new-age-1.1.7c+neoforge-mc1.21.1.jar`, `createdieselgenerators-1.21.1-1.3.11.jar`
