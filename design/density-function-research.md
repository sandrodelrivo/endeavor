# Density Function Research — Toroidal Climate Gradient

## The goal

Make the world have directional climate. North is cold, south is warm. East is wet, west is dry. Loops toroidally so there are no hard edges.

This is not a vanilla Minecraft feature. Vanilla `temperature` and `humidity` are 2D Perlin-style noise — random and isotropic. We override them with functions that are mostly directional gradient, with some noise mixed in so biome boundaries aren't perfect horizontal stripes.

## Where this lives in worldgen

In 1.21.1, the overworld noise router lives at:

```
data/minecraft/worldgen/noise_settings/overworld.json
```

Inside that file, the `noise_router` object has fields including `temperature`, `vegetation` (humidity), `continents`, `erosion`, `weirdness`, `depth`, etc. Each is a density function.

We override `temperature` and `vegetation` with our toroidal versions. We leave `continents`, `erosion`, `weirdness`, `depth` alone — those handle continent shapes, mountain placement, and extreme-biome rarity. Toroidal climate composes on top.

## The math

We want temperature to vary along Z axis (north/south) and humidity along X axis (east/west). Both should loop.

Periodic functions: Minecraft density functions don't have a native `cos` or `sin` primitive. We have these arithmetic primitives in 1.21.1:

- `add`, `mul`, `min`, `max`, `abs`, `clamp`, `square`, `cube`
- `noise`, `shifted_noise`, `flat_cache`, `cache_2d`, `cache_once`, `interpolated`
- `blend_alpha`, `blend_offset`, `blend_density`
- `range_choice` (constant in a range, otherwise another function)
- `spline` (1D piecewise function)

No trig. We approximate periodicity two ways:

### Approach A: tuned shifted_noise

The simplest approach: replace `temperature` with a `shifted_noise` whose `shift_x` is set to 0 and `shift_z` is large, so the noise effectively only varies in Z. Then mix with smaller-amplitude isotropic noise for variation.

Pseudo-structure:
```json
{
  "type": "minecraft:add",
  "argument1": {
    "type": "minecraft:mul",
    "argument1": 0.7,
    "argument2": {
      "type": "minecraft:shifted_noise",
      "noise": "minecraft:temperature",
      "xz_scale": 0.0001,
      "y_scale": 0,
      "shift_x": 0,
      "shift_y": 0,
      "shift_z": 0
    }
  },
  "argument2": {
    "type": "minecraft:mul",
    "argument1": 0.3,
    "argument2": "<vanilla temperature noise>"
  }
}
```

The `xz_scale` of 0.0001 makes the noise vary very slowly across the world — at our scale of 25k, one full noise cycle is ~10k blocks. This isn't strictly periodic but at our world size it visually reads as "north is cold, south is warm" because the player only experiences part of one cycle.

**Problem with A:** noise is not actually periodic. It's just slow. At a world border 30k away from spawn, "north" and "extra-far north" may both be at high temperature because the noise peaked. Acceptable trade-off if we accept some randomness in the gradient.

### Approach B: spline-based sawtooth

The `spline` density function takes a 1D input and maps it through piecewise-linear segments. We can construct a triangle wave (sawtooth-like) by using world Z as input mapped through a spline that goes 0 → 1 → 0 → -1 → 0 over its range.

But splines need a finite domain — they don't loop. To get a true loop, we'd need to apply modulo first, and there's no `mod` primitive.

**Approach B is harder than A and produces sharper transitions.** Defer.

### Approach C: pre-baked noise via shifted_noise scaling

We can scale a single noise sample to create something approximately periodic at our world scale. The trick: pick `xz_scale` very carefully. If `xz_scale = 0.0002`, one full noise oscillation is ~5k blocks. At a 25k world that's ~5 oscillations. Not a clean N-S gradient — just a banded climate.

This is *worse* than A.

## Recommendation: start with Approach A

Pure `shifted_noise` with very low `xz_scale`. Mix 70% gradient + 30% small-scale noise for biome variety. Tune `xz_scale` until at our world size, the player experiences ~one cycle from spawn to world edge.

For a 25k world (so 50k diameter), and we want ~one cycle: `xz_scale ≈ 1/50000 = 0.00002`. Test values: 0.00002, 0.00003, 0.00005.

## Test plan

Before integrating into the full datapack:

1. Make a minimal datapack that ONLY overrides `data/minecraft/worldgen/noise_settings/overworld.json`.
2. In that override, replace the `temperature` and `vegetation` density functions with tuned `shifted_noise` candidates.
3. Generate a fresh world.
4. Use the F3 debug screen or a biome-finder mod to confirm: is "north" colder than "south"? Is the gradient visible?
5. Iterate on `xz_scale` until the gradient is visible but biomes still mix.

## Things to verify

- That overriding the overworld noise settings doesn't break Terralith, Continents, or WWOO. They may also override these files. Test the load order.
- That setting `xz_scale` very low doesn't produce numerical issues (NaN, infinite, etc.).
- That the `shift_z` parameter works the way we expect in 1.21.1 — the schema has changed across versions.

## Fallback if it doesn't work

If pure-datapack toroidal climate proves infeasible:

1. Accept non-toroidal climate. World feels more "random." Still works for the design.
2. Write a small NeoForge mod that injects a custom density function with real periodic behavior. More work but gives us proper sin/cos.
3. Use the climate gradient at world generation time only, via a one-shot script that writes a static climate-map file that the world reads. Hacky.

Discuss with Jon before pivoting.

## References

- 1.21.1 density function format: https://minecraft.wiki/w/Density_function
- Misode generator (always check version selector is 1.21.1): https://misode.github.io/worldgen/density-function/
- Test in jacobsjo viewer once datapack is in a public modrinth project: https://map.jacobsjo.eu/

## Open questions on this specifically

- What `xz_scale` produces a pleasing gradient at 25k world size?
- Does Terralith's or WWOO's noise settings override survive ours, or vice versa?
- Should the climate amplitude be 70/30 (gradient/noise), 60/40, or something else?
