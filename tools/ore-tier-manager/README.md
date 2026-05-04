# ore-tier-manager

Regenerate the `features` array of every overworld biome JSON in
`datapack-worldgen/zzz_endeavour_worldgen/` from one declarative file:
`config/biome_overrides.yaml`.

Architecture is tag-only. There's no separate "tier" concept; tiers are
just tags whose biome lists happen to be (by convention) mutually
exclusive. Edit the YAML or use the GUI, run `apply.py`, repack the
datapack zip, drop into a fresh world.

## Setup

Python 3.11+. One dep:

```
pip install pyyaml
```

(Or `pip install -e .` from this directory.)

## Layout

```
tools/ore-tier-manager/
  common.py                 # shared lib (resolution, tag loading, JSON formatting)
  extract.py                # one-shot bootstrap: biome JSONs -> seed YAML
  apply.py                  # main: YAML -> biome JSONs
  validate.py               # post-apply sanity checks
  gui.py                    # Tk editor for the YAML + tag JSONs
  config/
    biome_overrides.yaml    # tag and biome-id ore lists
```

## Daily use

```
python apply.py             # write biome JSONs
python apply.py --dry-run   # report changes; no writes
python apply.py --diff      # per-biome additions/removals
python validate.py          # check the result
python gui.py               # Tk editor for tags, ores, biome assignments
```

## Resolution model

Every overworld biome JSON's `features` array is computed from
`biome_overrides.yaml` like this:

```
features = []
for tag in sorted(tags this biome belongs to):           # alphabetical
    apply biome_overrides["#endeavour:" + tag] to features
apply biome_overrides[biome_id] to features              # biome-id last
```

A biome's tag membership is read from the tag JSON files at
`data/endeavour/tags/worldgen/biome/*.json`. A biome can be in zero,
one, or many tags. Resolution is union semantics; multiple tags
compose additively.

### Per-step ops

A step block in `biome_overrides.yaml` is either a bare list (= `@set`)
or a dict with `@`-prefixed ops:

| Op | Meaning |
|----|---------|
| `@set: [...]` | replace whatever was inherited from earlier tags |
| `@add: [...]` | append features (deduped against current list) |
| `@remove: [...]` | drop features by ID |

Tag entries should almost always use `@add`. Bare lists or `@set` on a
tag entry will silently wipe contributions from any tag that comes
earlier in the alphabet, which is rarely what you want.

`@set` is fine on biome-id entries, where it lets a single biome
overrule its tag-derived baseline entirely.

### Generation steps

Use vanilla 1.21.1 step names as keys inside each step block. Order
matches `GenerationStep.Decoration`:

```
raw_generation, lakes, local_modifications, underground_structures,
surface_structures, strongholds, underground_ores, underground_decoration,
fluid_springs, vegetal_decoration, top_layer_modification
```

### Per-biome ordering

Within a step, features are emitted in this order:

1. Features that were already in the existing biome JSON, in their
   original order. Preserves inter-run stability and avoids
   FeatureSorter cycles where none existed.
2. Net-new features, in the order they appear after resolution.

## What it edits, what it leaves alone

**Edits:**

- `config/biome_overrides.yaml` (via the GUI or hand)
- The `features` array of every biome JSON
- The endeavour tag JSONs at `data/endeavour/tags/worldgen/biome/`
  (membership, when you assign biomes via the GUI)

**Doesn't touch:**

- `design/tier-map.xlsx`. Pure documentation; the tool neither reads
  nor writes it. Keep it in sync manually if you care about the
  human-facing tier overview.
- Climate density functions
  (`data/minecraft/worldgen/noise_settings/overworld.json`,
  `density_function/overworld/far_waste_*.json`).
- The 15 `neoforge:none` mod biome_modifier shadows
  (Create, Create Nuclear, Create New Age, IE, IP).
- The 5 active endeavour biome_modifiers
  (`06_add_zinc_ore_to_mesa_family.json` etc.) that currently inject
  zinc/uranium/thorium/oil via tags. See [Migration path](#migration-path)
  to fold these into biome JSONs instead.
- The companion mod scaffolding under `mod/`.

## GUI

`python gui.py` opens a three-pane Tk window:

- **Left:** every endeavour tag (`tier_1`, `tier_2`, `tier_4`,
  `mesa_family`, `extreme_cold`, ...). Add a new tag or delete an
  existing one.
- **Middle:** features that the selected tag adds at the chosen
  generation step (default: `underground_ores`). Picker dialog supports
  filter + custom-ID typing for adding mod ores not yet in any biome.
- **Right:** biomes that belong to the selected tag. Add/remove biome
  membership; the picker labels each candidate biome with its other
  tag memberships so you can see what you're combining.

The "Generation step" dropdown at the top changes which step the
middle pane edits. Use `fluid_springs` for IP reservoirs,
`local_modifications` for amethyst geodes, etc.

Save writes both the YAML and the tag JSONs. Apply runs `apply.py
--diff` and shows the resulting biome-JSON changes in a popup; nothing
touches the biome JSONs until you press Apply.

## Bootstrap (one-time)

```
python extract.py            # writes config/biome_overrides.yaml
python apply.py --dry-run    # should report 0 changes
python validate.py           # should report OK
```

The seed YAML factors per-tag feature intersections (for `tier_1`,
`tier_2`, `tier_4`) into `#endeavour:tier_X` entries and emits each
biome's diff against its tags' union as a biome-id key. Cross-cutting
tags like `mesa_family` start empty rules-wise; their biome lists are
unchanged.

`extract.py` refuses to overwrite existing YAML unless given `--force`.

## Migration path: folding endeavour biome_modifiers into biome JSONs

The currently-active endeavour biome_modifiers
(`06_add_zinc_ore_to_mesa_family.json`,
`07_add_uranium_ore_to_extreme_cold.json`,
`08_add_thorium_ore_to_extreme_hot.json`,
`09_add_oil_to_extreme_cold.json`,
`10_add_oil_to_extreme_hot.json`) inject modded ores via biome tags.
These work, but route ore distribution through two systems
(biome_modifier + biome JSON) instead of one.

To consolidate everything into biome JSONs:

1. In the GUI, select the corresponding tag (e.g. `mesa_family`),
   set the step dropdown to `underground_ores`, and add the
   ore (e.g. `create:zinc_ore`). For oil add it under `fluid_springs`.
2. Save and Apply. Confirm the biome JSONs gained the ore via the
   diff popup.
3. Replace the biome_modifier file with a `neoforge:none` shadow:
   ```json
   {"type": "neoforge:none"}
   ```
4. Repack the zip, test in a fresh world. The ore should still spawn
   (now from the biome JSON) and should NOT spawn anywhere outside
   the tag.

## Pending ore decisions

These ores are currently disabled (no biome references them). Their
tag home is undecided; add them to the appropriate tag entry when
you're ready:

- `immersiveengineering:bauxite` (aluminum)
- `immersiveengineering:lead`
- `immersiveengineering:nickel`
- `immersiveengineering:silver`
- `immersiveengineering:deep_nickel`
- `createnuclear:lead_ore` (IE has lead too; pick one)
- `create:striated_ores_overworld` (decorative limestone/scoria
  variants; could go on a universal tag if you want them everywhere)

## Validation

`validate.py` checks:

- Every biome JSON parses.
- No biome has more than 11 generation steps.
- Every feature ID has a `namespace:path` form.
- Reports unfamiliar namespaces (likely typos). Whitelisted ones are
  `minecraft, terralith, wythers, create, createnuclear, create_new_age,
  immersiveengineering, immersivepetroleum, endeavour, aether,
  deep_aether, lithosphere`.
- Warns (does not fail) on cross-biome FeatureSorter ordering cycles.
  Vanilla 1.21.1 tolerates the cycles that the existing Terralith data
  ships with; per-biome ordering preservation prevents new cycles.
- Warns when tag JSONs reference biome IDs that don't exist on disk
  (likely stale entries with wrong cave/ paths).
