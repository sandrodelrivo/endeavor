# ore-tier-manager

The tool is the **sole** source of truth for ore distribution. It strips
catalog-listed ores from biome JSONs and re-injects them via NeoForge
biome_modifier files generated from `config/biome_overrides.yaml`.

## Setup

Python 3.11+. One dep:

```
pip install pyyaml
```

(Or `pip install -e .` from this directory.)

## Layout

```
tools/ore-tier-manager/
  common.py
  extract.py                  # one-shot bootstrap (biome JSONs -> YAML)
  apply.py                    # main: YAML -> stripped biome JSONs + biome_modifiers
  validate.py                 # post-apply sanity checks
  gui.py                      # Tk editor
  config/
    ore_catalog.yaml          # placed_feature IDs the tool treats as ores
    biome_overrides.yaml      # tag -> ore lists
```

## Daily use

```
python apply.py             # strip + write biome_modifiers
python apply.py --dry-run   # report changes; no writes
python apply.py --diff      # per-biome ore-strip diff + biome_modifier list
python validate.py
python gui.py
```

## How it works

There are three pieces of state:

1. **`config/ore_catalog.yaml`** - the explicit list of placed_feature IDs
   the tool considers ores. Anything not in this file is "terrain /
   structure / decoration / vegetation" and the tool never touches it.

2. **`config/biome_overrides.yaml`** - tag -> ore lists. Keys are
   `#endeavour:<tag>`. Each entry says which ores the tool injects into
   biomes carrying that tag. Per-biome exceptions don't exist: if one
   biome needs an ore none of its tag-mates do, put the biome in a
   singleton tag.

3. **`data/endeavour/tags/worldgen/biome/*.json`** - biome -> tag
   membership. Edit through the GUI's right pane.

`apply.py` does two things every run:

- **Strips** every catalog feature from every tagged biome's JSON
  `features` array. Untagged biomes are left alone.
- **Writes** `data/endeavour/neoforge/biome_modifier/<tag>__<step>.json`
  files using NeoForge's `add_features` mechanism. Each carries the
  ore list for one (tag, step) combination. The biome_modifier
  directory is fully tool-managed: stale files are deleted on every
  run.

At world load, NeoForge applies the biome_modifiers, layering ores back
onto biomes that match each tag's `#endeavour:<tag>` selector. Net
runtime state: biome JSON terrain features (in original order) +
ores from tag-matching biome_modifiers.

## Resolution: ores partition across tags (no double-count)

The tool guarantees each ore appears in **at most one** tag's
biome_modifier per biome. Otherwise NeoForge's `add_features` would
stack duplicates and multi-spawn at runtime.

Bootstrap algorithm (`extract.py`):
1. Seed modded ores from existing endeavour biome_modifiers (zinc to
   `mesa_family`, uranium/oil to `extreme_cold`, etc.).
2. Process tags in order of biome-set size (largest first). For each
   tag, claim every catalog ore present in any of its biomes that
   isn't already covered by a previously-processed tag. Ores assigned
   in step 1 are already covered for their biomes.

Tier tags (~38-53 biomes each) thus claim the bulk of vanilla ores.
Smaller cross-cutting tags (`mesa_family`, `extreme_cold`, etc.) end
up carrying just their tag-specific ores.

UNION semantics across each tag means some biomes may gain ores they
didn't previously have (e.g. tier_4 biomes that lacked emerald_ore now
get it because the tag claims emerald_ore once for all members). Use
`apply.py --diff` to inspect; correct in the GUI by removing ores from
overly-broad tags or splitting a tag.

## Untagged biomes

A biome that's in zero endeavour tags is left untouched by `apply.py`:
its JSON is not stripped, no biome_modifier targets it, and Terralith's
default ores remain. Add it to a tag in the GUI to bring it under tool
management.

Currently untagged: `minecraft:deep_dark`, `terralith:alpha_islands`,
`terralith:alpha_islands_winter`, `terralith:ancient_sands`,
`terralith:mirage_isles`, `terralith:skylands_*` (4 variants),
`terralith:warped_mesa`.

## What it edits, what it leaves alone

**Edits:**

- `config/biome_overrides.yaml` (via the GUI or hand)
- `data/endeavour/tags/worldgen/biome/*.json` (membership, via GUI)
- The `features` array of every tagged biome JSON (strips catalog ores)
- `data/endeavour/neoforge/biome_modifier/*.json` (fully tool-managed)

**Doesn't touch:**

- `design/tier-map.xlsx`. Pure documentation.
- `config/ore_catalog.yaml`. Edit by hand to add a new ore the tool
  should manage.
- Climate density functions
  (`data/minecraft/worldgen/noise_settings/overworld.json`,
  `density_function/overworld/far_waste_*.json`).
- The 15 `neoforge:none` mod biome_modifier shadows under
  `data/<modid>/neoforge/biome_modifier/`. These remain inert
  permanently; the tool generates its replacements.
- Untagged biomes' JSONs.
- The companion mod scaffolding under `mod/`.

## GUI

`python gui.py` opens a three-pane Tk window:

- **Left:** every endeavour tag. Add / delete tags.
- **Middle:** ores in the selected tag at the chosen generation step.
  Multi-select removal with Ctrl/Shift. Non-catalog entries are flagged
  `[NOT IN CATALOG]` (apply.py drops them silently otherwise).
- **Right:** biomes that belong to the selected tag. Add a biome by
  picking from the list (annotated with each biome's other tags).

The "+ Add ore(s)" picker is multi-select and groups the catalog by
namespace (vanilla / create / immersiveengineering / etc.). "Select
all visible" + filter combo lets you assign 50 ores in three clicks.
A custom-ID textbox at the bottom takes one ore-ID per line, but unless
you also add the ID to `ore_catalog.yaml`, apply.py will drop it.

The Generation step dropdown changes which step the middle pane
edits. Most ores live at `underground_ores`. Use `local_modifications`
for amethyst/emerald geodes; `fluid_springs` is also possible (IP
reservoir was historically there before mods moved it).

## Catalog

`config/ore_catalog.yaml` lists every placed_feature ID the tool treats
as an ore. The bootstrap catalog covers vanilla, WWOO biome-locked
variants, Create / Create Nuclear / Create New Age / Immersive
Engineering / Immersive Petroleum. Edit it to:

- Add a new modded ore the tool should manage. Save → reload the GUI →
  the ore appears in the picker.
- Remove an ore from tool management (the tool stops stripping it from
  biome JSONs; current biome_modifiers stop including it on next apply).

Categorization is for human readability; the tool reads it as a flat
union.

## Bootstrap (one-time)

```
python extract.py            # writes config/biome_overrides.yaml
python apply.py --diff       # review the migration; biome JSONs lose ores
python validate.py
```

The bootstrap migrates from the old "ores embedded in biome JSONs +
06_*-10_* biome_modifiers" architecture to the catalog-driven one. It:

- Writes `biome_overrides.yaml` capturing current ore distribution
  partitioned across tags.
- Strips catalog ores from biome JSONs.
- Replaces the legacy `06_*-10_*` biome_modifiers with
  `<tag>__<step>.json` files.

Inspect the biome-JSON diffs in `git status` before committing. The
migration is destructive: biomes lose their old per-biome ore lists,
gain ores common to their tag-mates. Tweak in the GUI as needed.

## Validation

`validate.py` checks:

- Every biome JSON parses; no biome has more than 11 generation steps.
- No tagged biome's JSON still contains a catalog ore (apply drift).
- Every feature in `biome_overrides.yaml` is in the catalog (anything
  else gets silently dropped at apply time).
- No biome-id keys in `biome_overrides.yaml` (legacy from pre-catalog
  architecture; the catalog-driven tool ignores them).
- Tag JSONs reference only on-disk biomes.
- No orphan endeavour biome_modifier files (besides legacy `06_*-10_*`,
  which `apply.py` will replace).
- Cross-biome FeatureSorter ordering cycles (warning only; the existing
  Terralith data has some).
