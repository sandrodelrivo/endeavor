# ore-tier-manager

Regenerate the `features` array of every overworld biome JSON in
`datapack-worldgen/zzz_endeavour_worldgen/` from declarative YAML.

This is the iteration loop for tier-balance work. Edit the YAML, run
`apply.py`, repack the datapack zip, drop into a fresh world. No
hand-editing 50+ biome JSON files.

## Setup

Python 3.11+. Two deps:

```
pip install openpyxl pyyaml
```

(Or `pip install -e .` from this directory.)

## Layout

```
tools/ore-tier-manager/
  common.py                 # shared lib (YAML schema, resolution, tag expansion)
  extract.py                # one-shot bootstrap: biome JSONs -> seed YAML
  apply.py                  # main: YAML -> biome JSONs
  validate.py               # post-apply sanity checks
  config/
    tier_templates.yaml     # per-tier baseline feature lists
    biome_overrides.yaml    # per-biome and per-tag deltas
```

## Daily use

```
python apply.py             # write biome JSONs
python apply.py --dry-run   # report changes; no writes
python apply.py --diff      # per-biome additions/removals
python validate.py          # check the result
python gui.py               # Tk GUI for editing tiers, tags, ore + biome assignments
```

## GUI

`python gui.py` opens a three-pane Tk window:

- **Left:** tiers (from `tier_templates.yaml` and the xlsx) + tags
  (from `data/endeavour/tags/worldgen/biome/*.json`). Buttons to add or
  delete tiers and tags.
- **Middle:** features assigned to the selected tier/tag at the chosen
  generation step (default: `underground_ores`). Picker dialog supports
  filter + custom-ID typing for adding mod ores not yet in any biome.
- **Right:** biomes assigned to the selected tier (xlsx column) or
  selected tag (tag JSON). Adding a biome to a tier replaces its prior
  tier; biomes can be in multiple tags.

The "Generation step" dropdown at the top changes which step the middle
pane edits - useful for adding fluid_springs reservoirs, vegetal
features, etc.

Save writes all four backing stores (both YAMLs, the tag JSONs, the
xlsx). Apply runs `apply.py --diff` and shows the resulting biome-JSON
changes in a popup. Nothing touches the biome JSONs until you press
Apply, so you can save iteratively and review before committing the
worldgen change.

Caveats:
- Editing the xlsx via openpyxl preserves data + cell types but may
  rewrite some formatting metadata. Diff before committing.
- Adding a biome to a tier when the biome wasn't in the xlsx appends a
  new row with namespace-derived `Source` and a blank climate/terrain.
  Fill those in manually if you care about the source-of-truth value.
- Saving rewrites the YAMLs from the in-memory model. Header comments
  are preserved; per-step inline comments you may have hand-added are
  not (use `git diff` to spot what's gone).

## What it edits, what it leaves alone

**Edits:** the `features` array of every biome JSON listed in
`design/tier-map.xlsx` (Biomes sheet) plus any biome whose ID appears in
`biome_overrides.yaml`. Other JSON fields (climate, mob spawns, surface
rules, original key order, indent) are preserved.

**Doesn't touch:**

- Climate density functions
  (`data/minecraft/worldgen/noise_settings/overworld.json`,
  `density_function/overworld/far_waste_*.json`).
- The `endeavour` tag JSONs at
  `data/endeavour/tags/worldgen/biome/`. These are READ by the tool to
  expand `#endeavour:foo` keys but never rewritten.
- The 15 `neoforge:none` mod biome_modifier shadows under
  `data/<modid>/neoforge/biome_modifier/` (Create, Create Nuclear,
  Create New Age, IE, IP). These neutralize mod-injected ore placement
  and are configured correctly already.
- The 5 active endeavour biome_modifiers
  (`06_add_zinc_ore_to_mesa_family.json` etc.) that currently inject
  zinc/uranium/thorium/oil via tags. See [Migration path](#migration-path)
  below if you want to fold these into biome JSONs instead.
- The companion mod (`mod/`) - stale gradle scaffolding from an
  abandoned attempt; out of scope.

## YAML schema

### Generation steps

Use vanilla 1.21.1 step names as keys inside each biome/tier block.
Order matches `GenerationStep.Decoration`:

```
raw_generation, lakes, local_modifications, underground_structures,
surface_structures, strongholds, underground_ores, underground_decoration,
fluid_springs, vegetal_decoration, top_layer_modification
```

### Ops

A step block is either a bare list (= full `@set`) or a dict with
`@`-prefixed ops:

| Op | Meaning |
|----|---------|
| `@inherit: <tier>` | (tier_templates only) start from another tier's resolved list |
| `@set: [...]` | replace whatever was inherited |
| `@add: [...]` | append features (deduped against current list) |
| `@remove: [...]` | drop features by ID |

Resolution order per (biome, step):

1. `tier_templates[biome.tier][step]` (with `@inherit` recursively flattened)
2. Tag-based overrides from `biome_overrides.yaml` (keys starting `#`)
3. Biome-id overrides from `biome_overrides.yaml` (keys with `:` not `#`)

Tag overrides apply BEFORE biome-id overrides, so a specific biome can
remove a tag-injected feature.

### Tag keys

Only `#endeavour:<tag>` is supported. The tool reads
`data/endeavour/tags/worldgen/biome/<tag>.json` and applies the override
to every biome listed there.

Pre-existing tags you can target:

- `#endeavour:tier_1`, `#endeavour:tier_2`, `#endeavour:tier_4`
- `#endeavour:mesa_family` - vanilla badlands family + Terralith bryce_canyon, painted_mountains, savanna_badlands, white_mesa
- `#endeavour:extreme_cold` - vanilla snowy/frozen + Terralith glacial_chasm, ice_marsh, siberian_*
- `#endeavour:extreme_hot` - vanilla desert/badlands + Terralith desert_*
- `#endeavour:volcanic_zone`, `#endeavour:scarlet_mountains`,
  `#endeavour:emerald_peaks`, `#endeavour:amethyst_zone`

### Per-biome ordering

Within a step, features are emitted in this order:

1. Features that were already in the existing biome JSON, in their
   original order. (Preserves ordering across runs even if YAML edits
   reorder things.)
2. Net-new features, in the order they appear after resolution.

This avoids creating cross-biome ordering conflicts that would crash
worldgen with FeatureSorter's "Feature order cycle found".

### Odd cases

- `terralith:fractured_savanna` ships with 10 generation-step entries
  instead of 11. The tool preserves that shape - it doesn't lengthen
  the array.
- The xlsx has some Terralith cave biomes listed without the `cave/`
  prefix (`terralith:andesite_caves` rather than
  `terralith:cave/andesite_caves`). The tool normalizes against on-disk
  paths, so the right biome gets touched regardless.
- 3 Terralith biomes have JSON but aren't in the xlsx
  (`alpha_islands`, `alpha_islands_winter`, `ancient_sands`). Their
  YAML entries carry full `@set` lists since there's no tier template
  to apply.

## Bootstrap (one-time)

```
python extract.py            # writes config/{tier_templates,biome_overrides}.yaml
python apply.py --dry-run    # should report 0 changes
python validate.py           # should report OK
```

The seed YAML factors per-(tier, step) intersections into
`tier_templates.yaml` and emits each biome's diff into
`biome_overrides.yaml`. With pure intersection across 38 T1 biomes,
templates start sparse - most content lives in `biome_overrides.yaml`.
Refactor as you find shared subsets.

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

1. Add the equivalent tag override to `biome_overrides.yaml`:
   ```yaml
   "#endeavour:mesa_family":
     underground_ores:
       "@add":
         - create:zinc_ore
   ```
2. Run `python apply.py`. Confirm the biome JSONs gained the ore.
3. Replace the biome_modifier file with a `neoforge:none` shadow:
   ```json
   {"type": "neoforge:none"}
   ```
4. Repack the zip, test in a fresh world. The ore should still spawn
   (now from the biome JSON) and should NOT spawn anywhere outside the
   tag (now that the tag-wide injector is disabled).

The tool deliberately doesn't automate step 3 - those files are owned
by other concerns (e.g. `09_add_oil_to_extreme_cold` puts a fluid
reservoir, not an ore feature, and may want a different home).

## Pending ore decisions

These ores are currently disabled (no biome references them). Their
tier home is undecided - add them to the appropriate template or
tag-based override when you're ready:

- `immersiveengineering:bauxite` (aluminum)
- `immersiveengineering:lead`
- `immersiveengineering:nickel`
- `immersiveengineering:silver`
- `immersiveengineering:deep_nickel`
- `createnuclear:lead_ore` (IE has lead too - decide which one ships)
- `create:striated_ores_overworld` (decorative limestone/scoria
  variants - may want T1-everywhere or stay disabled)

## Validation

`validate.py` checks:

- Every emitted biome JSON parses.
- No biome has more than 11 generation steps.
- Every feature ID has a `namespace:path` form.
- Reports unfamiliar namespaces (likely typos) - whitelisted ones are
  `minecraft, terralith, wythers, create, createnuclear, create_new_age,
  immersiveengineering, immersivepetroleum, endeavour, aether,
  deep_aether, lithosphere`.
- Warns (does not fail) on cross-biome FeatureSorter ordering cycles.
  Vanilla 1.21.1's FeatureSorter empirically tolerates some cycles
  that the existing Terralith data ships with; the tool's per-biome
  ordering preservation prevents NEW cycles from edits.

`validate.py` does not check that every referenced placed_feature
exists in a mod jar. Terralith may load as a datapack rather than a
mod, and we don't scan those archives. Treat the unfamiliar-namespace
warning as the practical typo guard.
