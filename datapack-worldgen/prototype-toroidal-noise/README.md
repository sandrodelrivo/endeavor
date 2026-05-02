# prototype-toroidal-noise

Throwaway prototype for the toroidal climate gradient. Overrides only `temperature` and `vegetation` inside the vanilla overworld noise router. Now uses [More Density Functions (`moredfs`)](https://modrinth.com/mod/more-density-functions) primitives because pure 1.21.1 vanilla has no density function that reads world X or Z position.

## What it is

A minimal Minecraft 1.21.1 NeoForge data pack:

```
prototype-toroidal-noise/
├── pack.mcmeta                             pack_format 48 (1.21.1)
└── data/minecraft/worldgen/noise_settings/
    └── overworld.json                      vanilla file with two fields modified
```

Requires the `moredfs` mod loaded. Without it, `moredfs:sin` / `moredfs:x` / `moredfs:z` are unknown types and worldgen fails to load.

The override is full-file replacement. The non-modified fields (continents, erosion, depth, ridges, surface_rule, etc.) are byte-for-byte vanilla 1.21.1 from [misode/mcmeta @ 1.21.1-data](https://github.com/misode/mcmeta/tree/1.21.1-data).

## What changed

The two density functions inside `noise_router` are now strict directional sinusoids:

```
temperature(x, z) = +1 · sin(2π · z / PERIOD)
vegetation (x, z) = +1 · sin(2π · x / PERIOD)
```

PERIOD is currently **`2000`** blocks (TEMPORARY — small for visualization testing on Xaero's map; production target is closer to 60000). Orientation: `-z` (north) is cold, `+z` (south) is hot, `-x` (west) is dry, `+x` (east) is wet — matches the design doc convention.

Sample values at `PERIOD = 2000`:

| Position | temperature | vegetation | meaning |
|----------|------------:|-----------:|---------|
| (0, 0) | 0 | 0 | spawn — temperate, mid-humidity |
| (0, +500) | **+1 (max)** | 0 | far south — hot |
| (0, -500) | **-1 (min)** | 0 | far north — cold |
| (0, +1000) | 0 | 0 | half period — back to temperate |
| (0, +2000) | 0 | 0 | full period |
| (+500, 0) | 0 | **+1 (max)** | far east — wet |
| (-500, 0) | 0 | **-1 (min)** | far west — dry |
| (+1000, 0) | 0 | 0 | half period — back to mid-humidity |

JSON shape (temperature; vegetation is identical with `moredfs:z` swapped for `moredfs:x`):

```jsonc
{
  "type": "minecraft:flat_cache",                 // 4×4 column cache — matches vanilla pattern
  "argument": {                                   //   for `continents` and other 2D climate fns.
    "type": "minecraft:mul",                      //   No precision loss because biome selection
    "argument1": 1.0,                             //   already samples at 4-block resolution.
    "argument2": {                                // SIGN  — outer mul arg1; -1.0 flips orientation
      "type": "moredfs:sin",
      "argument": {
        "type": "minecraft:mul",
        "argument1": 0.0031415926535898,          // 2π / PERIOD where PERIOD = 2000
        "argument2": { "type": "moredfs:z" }      // axis: z for temperature, x for vegetation
      }
    }
  }
}
```

## Knobs to tune

All edits go in `data/minecraft/worldgen/noise_settings/overworld.json`.

| Knob | Where | Default | Effect |
|------|-------|---------|--------|
| `PERIOD` | The `0.00314…` constant in `argument2.argument.argument1` of both `temperature` and `vegetation`. Replace with `2π / new_period`. Examples: 500 → `0.01256637`, 2000 → `0.00314159`, 30000 → `0.00020944`, 60000 → `0.00010472`. | `2000` (constant `0.00314159`) | Larger PERIOD → wider bands. Both axes can use different PERIODs. Below ~500 you start hitting biome-blending chaos. |
| `SIGN` | `argument1` of the `mul` inside `flat_cache.argument` of each field. | `+1.0` | Set to `-1.0` to flip which direction is hot/cold (or wet/dry). Per-axis. |
| Amplitude | Multiply `SIGN` by a magnitude (e.g., `1.5` instead of `1.0`). | `1.0` | Reaches more extreme biome temperature values. Vanilla biome climate parameters extend past ±1, so amplitudes up to ~1.5 unlock more-extreme biomes (frozen peaks, deserts) at the band edges. |

## Adding biome diversity within bands (optional)

The current formula gives clean stripes — every block at the same z gets identical temperature. That makes the test verifiable but the resulting world will have unnaturally regular biome boundaries.

To re-introduce vanilla per-block noise variation within a band, wrap each field as `add(mul(GRADIENT_WEIGHT, sin_term), mul(NOISE_WEIGHT, vanilla_shifted_noise))`. Try `0.7 / 0.3`. Skipped for the prototype so the gradient is the only thing visible.

## Test plan

1. Drop `moredfs` (1.21.1 NeoForge build) into the modpack.
2. Drop this datapack into the world's `datapacks/` folder, or use `/datapack enable` after world creation.
3. Generate a fresh world. Spawn at (0, 0). Walk +z; temperature should drop monotonically. Walk -z; temperature should rise. Same with x for humidity.
4. Use F3 + a biome-finder mod to verify climate values at the sample positions in the table above.

(map.jacobsjo.eu only evaluates vanilla density functions in JS — `moredfs:*` types render as no-ops there, so it's not the right testing surface for this prototype.)

## Sources

- [Minecraft Wiki — Pack format](https://minecraft.wiki/w/Pack_format) — pack_format 48 for 1.21.1
- [Minecraft Wiki — Density function](https://minecraft.wiki/w/Density_function) — vanilla type schemas; confirms no X/Z position primitive in 1.21.1 vanilla
- [misode/mcmeta `1.21.1-data` — overworld.json](https://github.com/misode/mcmeta/blob/1.21.1-data/data/minecraft/worldgen/noise_settings/overworld.json) — vanilla baseline used directly
- [More Density Functions wiki — full type list](https://github.com/klinbee/More-Density-Functions/wiki) — `moredfs:x`, `moredfs:z`, `moredfs:sin`, etc.
- [Modrinth — More Density Functions versions](https://modrinth.com/mod/more-density-functions/versions) — `[NeoForge 1.21.1]` build available (v2.2.1)
