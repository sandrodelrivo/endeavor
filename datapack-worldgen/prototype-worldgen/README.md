# prototype-toroidal-noise

Working prototype of the climate gradient. Overrides only `temperature` and `vegetation` inside the vanilla overworld noise router. Requires the [More Density Functions (`moredfs`)](https://modrinth.com/mod/more-density-functions) library mod for the position and trig primitives - pure 1.21.1 vanilla has no density function that reads world X or Z.

## What it is

A minimal Minecraft 1.21.1 NeoForge data pack:

```
prototype-toroidal-noise/
├── pack.mcmeta                             pack_format 48 (1.21.1)
└── data/minecraft/worldgen/noise_settings/
    └── overworld.json                      vanilla file with two fields modified
```

The override is full-file replacement. The non-modified fields (continents, erosion, depth, ridges, surface_rule, etc.) are byte-for-byte vanilla 1.21.1 from [misode/mcmeta @ 1.21.1-data](https://github.com/misode/mcmeta/tree/1.21.1-data).

## What changed

The two density functions inside `noise_router` are now:

```
temperature(x, z) = clamp(z / 25000, -1, 1)            + 0.2 · vanilla_temperature_noise
vegetation (x, z) = sin( 2π · x / 6000 ) ^ 7           + 0.2 · vanilla_vegetation_noise
```

Both wrapped in `minecraft:flat_cache` (matches vanilla's pattern for `continents` - caches per 4×4 column, no precision loss for biome selection).

### Temperature is a clamped linear ramp (permafrost / permadesert vibe)

| z position | T value | meaning |
|-----------:|--------:|---------|
| 0 | 0 | spawn - temperate |
| ±3,000 | ±0.12 | edge of green band - temperate biomes still dominate |
| ±10,000 | ±0.4 | mostly cold / mostly warm biomes |
| ±25,000 | ±1.0 | clamp wall - permafrost ice / permadesert sand |
| beyond ±25,000 | ±1.0 | infinite extreme - same as the wall |

`-z` (north) is cold, `+z` (south) is hot. Symmetric - both sides hit walls at 25k.

### Vegetation is a 7th-power sinusoid (mid-humidity dominates, narrow extreme bands)

`sin^7(x)` is near 0 for most of its domain - only briefly spikes to ±1 near the sin peaks. So most of the world has moderate humidity (where biome variety lives) with narrow bands of extreme wet (jungle / swamp) and extreme dry (badlands-flavor) every half-period.

| x position | V value | meaning |
|-----------:|--------:|---------|
| 0 | 0 | spawn - mid-humidity |
| ±750 | ~±0.1 | still mostly mid |
| ±1500 | ±1.0 | narrow extreme peak |
| ±3000 | 0 | half period - back to mid |
| ±4500 | ∓1.0 | next extreme peak (sign-flipped) |
| ±6000 | 0 | full period |

Half-period 3k. `+x` (east) at the first peak is wet, `-x` (west) is dry. Pattern repeats every 6k.

### Noise blur

Both axes have `0.2 · vanilla_shifted_noise` added. The vanilla `minecraft:temperature` and `minecraft:vegetation` noises sampled at vanilla `xz_scale=0.25` are biome-scale Gaussian-ish wobble. Output magnitude typically ±0.2, occasionally a touch higher. This blurs the otherwise-rectangular band edges so the climate transitions feel natural instead of laser-cut.

## JSON shape (temperature)

```jsonc
{
  "type": "minecraft:flat_cache",
  "argument": {
    "type": "minecraft:add",
    "argument1": {                                    // gradient term: clamped linear
      "type": "minecraft:clamp",
      "input": {
        "type": "minecraft:mul",
        "argument1": 0.00004,                         // C = 1 / PERMA_DIST  (PERMA_DIST=25000)
        "argument2": { "type": "moredfs:z" }
      },
      "min": -1.0,
      "max":  1.0
    },
    "argument2": {                                    // blur term: 0.2 × vanilla noise
      "type": "minecraft:mul",
      "argument1": 0.2,                               // NOISE_BLUR magnitude
      "argument2": {
        "type": "minecraft:shifted_noise",
        "noise": "minecraft:temperature",
        "shift_x": "minecraft:shift_x",
        "shift_y": 0.0,
        "shift_z": "minecraft:shift_z",
        "xz_scale": 0.25,
        "y_scale":  0.0
      }
    }
  }
}
```

## JSON shape (vegetation)

```jsonc
{
  "type": "minecraft:flat_cache",
  "argument": {
    "type": "minecraft:add",
    "argument1": {                                    // gradient term: sin^7(2π · x / VEG_PERIOD)
      "type": "moredfs:power",
      "base": {
        "type": "moredfs:sin",
        "argument": {
          "type": "minecraft:mul",
          "argument1": 0.0010471975511966,            // 2π / VEG_PERIOD  (VEG_PERIOD=6000)
          "argument2": { "type": "moredfs:x" }
        }
      },
      "exponent": 7.0                                 // SIN_ORDER. Must stay odd to preserve sign.
    },
    "argument2": { /* same blur term shape, with noise=minecraft:vegetation */ }
  }
}
```

## Knobs to tune

| Knob | Default | Where to find it | Effect |
|------|---------|------------------|--------|
| `PERMA_DIST` (T wall distance) | `25000` | `temperature.argument.argument1.input.argument1` - the `0.00004` constant. Set to `1 / new_distance`. | Smaller → walls closer to spawn. |
| `VEG_PERIOD` (V full period) | `6000` | `vegetation.argument.argument1.base.argument.argument1` - the `0.001047…` constant. Set to `2π / new_period`. | Smaller → tighter wet/dry bands. |
| `SIN_ORDER` (V shaping) | `7` | `vegetation.argument.argument1.exponent`. **Must be odd** to preserve sign of negative half-cycles. | Higher → narrower extreme peaks, wider mid zones. |
| `NOISE_BLUR` | `0.2` | The `0.2` constant in `argument2.argument1` of both `temperature` and `vegetation`. | Higher → more wobble, fuzzier band boundaries. |

## How to test

1. NeoForge 1.21.1 instance with `more-density-functions` (v2.2.1+) loaded.
2. Drop this datapack into `world/datapacks/` or use `/datapack enable`.
3. Generate fresh chunks. Confirm via F3 climate readout:
   - At spawn (0, 0): T ≈ 0, V ≈ 0 (± noise blur).
   - Walking +z: T trends up linearly to +1 by z=25000.
   - Walking -z: T trends down linearly to -1 by z=-25000.
   - Walking +x or -x: V cycles 0 → ±1 → 0 every 3000 blocks.

map.jacobsjo.eu doesn't evaluate `moredfs:*` types (it's a vanilla-only JS reimplementation). Test in-game or via Chunky pre-render.

## Sources

- [Minecraft Wiki - Pack format](https://minecraft.wiki/w/Pack_format) - pack_format 48 for 1.21.1
- [Minecraft Wiki - Density function](https://minecraft.wiki/w/Density_function) - vanilla `clamp`, `flat_cache`, `mul`, `add`, `shifted_noise` schemas
- [misode/mcmeta `1.21.1-data` - overworld.json](https://github.com/misode/mcmeta/blob/1.21.1-data/data/minecraft/worldgen/noise_settings/overworld.json) - vanilla baseline used directly
- [misode/mcmeta `1.21.1-data` - overworld/continents.json](https://github.com/misode/mcmeta/blob/1.21.1-data/data/minecraft/worldgen/density_function/overworld/continents.json) - vanilla `flat_cache` pattern reference
- [More Density Functions wiki - full type list](https://github.com/klinbee/More-Density-Functions/wiki) - `moredfs:x`, `moredfs:z`, `moredfs:sin`, `moredfs:power`
