# Handoff: build the ore-tier-management tool

You are a fresh agent picking up a finished plumbing milestone. Worldgen ore-control infrastructure is now fully working in the modpack - your job is to build the management tool that lets us iterate on tier balance without hand-editing 50+ biome JSON files.

Read [CLAUDE.md](../CLAUDE.md) first for project context. Then the rest of this doc.

## Where we are (2026-05-03, verified working)

After many iterations, ore placement is now under our complete control. Mechanism:

1. **Hand-merged biome JSONs are the sole source of truth.** Every overworld biome (vanilla + Terralith + WWOO) has its full biome JSON committed in `datapack-worldgen/zzz_endeavour_worldgen/data/`. Each JSON's `features` array lists exactly what spawns in that biome at each generation step. Whatever's in the list, spawns. Whatever's not, doesn't.

2. **All ore-injecting mod biome_modifiers are neutralized.** Each mod that injected ores via `data/<modid>/neoforge/biome_modifier/<name>.json` (Create, Create Nuclear, Create New Age, Immersive Engineering, Create: Diesel) has its biome_modifier file shadowed in our datapack at the same path with `{"type": "neoforge:none"}`. NeoForge's documented "datapack overrides mod files at same path" pattern. 15 such overrides are in place (all `data/<modid>/neoforge/biome_modifier/*.json` in our pack).

3. **Ore Veines+ has been removed from the modpack.** It was the dominant cause of ore chaos for many sessions - its own runtime ore-placement system ignored our biome_modifier overrides and painted ores everywhere via its config. Removing the jar entirely was the unblock. Do NOT suggest re-adding it.

4. **Verified end-to-end.** In Gen25 Worldgen Testing, spawning at (0, 0) in a forest biome shows only vanilla T1 ores (iron, copper, coal, gold, etc.) - no zinc, no uranium, no thorium, no IE bauxite/lead/nickel/silver, no Aether ores, no magnetite. All ore injection now flows through biome JSONs only.

## What you're building

A Python CLI tool that regenerates biome JSON `features` arrays from declarative inputs, so we can iterate on tier balance by editing config files instead of editing JSON by hand.

### Inputs (tool reads)

- **[design/tier-map.xlsx](tier-map.xlsx)** - already exists. Sheet "Biomes" has columns: `Biome ID`, `Source` (Vanilla / Terralith / WWOO), `Climate`, `Terrain Class`, `Tier` (T1/T2/T4/TX/TURN OFF), `Rarity`, `Notes`. ~146 rows.
- **`config/tier_templates.yaml`** - new file you author. Defines, per tier, the feature list per generation step. Example:
  ```yaml
  tiers:
    T1:
      underground_ores:
        - minecraft:ore_dirt
        - minecraft:ore_gravel
        # base stones
        - minecraft:ore_coal_upper
        - minecraft:ore_coal_lower
        - minecraft:ore_iron_upper
        - minecraft:ore_iron_middle
        - minecraft:ore_iron_small
        - minecraft:ore_copper
    T2:
      underground_ores:
        "@inherit": T1
        "@add":
          - minecraft:ore_gold
    T4:
      underground_ores:
        "@inherit": T1     # T4 wastes are barren plus their special ore via biome_overrides
  ```
- **`config/biome_overrides.yaml`** - new file you author. Per-biome additions/removals on top of the tier template. Example:
  ```yaml
  # Vanilla biome IDs
  badlands:
    underground_ores:
      "@add":
        - minecraft:ore_gold_extra   # badlands have extra gold in vanilla; preserve

  # Terralith biome IDs
  terralith:volcanic_crater:
    underground_ores:
      "@add":
        - minecraft:ore_diamond
        - minecraft:ore_diamond_buried
        - minecraft:ore_diamond_large
        - minecraft:ore_diamond_medium
  terralith:emerald_peaks:
    underground_ores:
      "@add":
        - minecraft:ore_emerald
  terralith:amethyst_canyon:
    underground_ores:
      "@add":
        - minecraft:ore_lapis
        - minecraft:ore_lapis_buried
    underground_decoration:
      "@add":
        - minecraft:amethyst_geode
  terralith:scarlet_mountains:
    underground_ores:
      "@add":
        - minecraft:ore_redstone
        - minecraft:ore_redstone_lower

  # Tag-based bulk overrides (apply to all biomes in a tag)
  "#endeavour:mesa_family":
    underground_ores:
      "@add":
        - create:zinc_ore
  "#endeavour:extreme_cold":
    underground_ores:
      "@add":
        - createnuclear:uranium_ore
  "#endeavour:extreme_hot":
    underground_ores:
      "@add":
        - create_new_age:thorium_ore
  ```

### Outputs (tool writes)

For every biome listed in tier-map.xlsx, regenerate its biome JSON's `features` array from `tier_templates[tier] + biome_overrides[biome]`. Preserve all other fields in the JSON unchanged (climate parameters, weight, mob spawns, surface rules - the tool only touches the `features` array).

Three biome JSON locations to write:
- `datapack-worldgen/zzz_endeavour_worldgen/data/minecraft/worldgen/biome/<biome>.json` (vanilla biomes, Source = Vanilla)
- `datapack-worldgen/zzz_endeavour_worldgen/data/terralith/worldgen/biome/<biome>.json` (Source = Terralith - note Terralith uses subfolders for cave biomes: `cave/mantle_caves.json`, etc.)
- `datapack-worldgen/zzz_endeavour_worldgen/data/wythers/worldgen/biome/<biome>.json` (Source = WWOO)

### Constraints

- **First run must be a no-op.** When the tool starts, the existing biome JSONs are the working state. Author `tier_templates.yaml` and `biome_overrides.yaml` so that running the tool the first time reproduces those existing JSONs byte-for-byte (or feature-list-equivalent - the order matters for FeatureSorter, see below). This proves the regen pipeline before we start tweaking. The way to do this: run the tool in a "extract" mode first that reads the existing biome JSONs and dumps the feature lists; use that to seed the YAML.

- **Feature ordering matters.** Minecraft's FeatureSorter does a topological sort across all biomes' feature lists. If two biomes have features [X, Y] and [Y, X] respectively, the chunk generator throws `Feature order cycle found` and refuses to generate. When emitting features, preserve a single global ordering - typically the order in tier_templates, with biome_overrides' `@add` entries appended at the end. Don't let per-biome overrides reorder features that appear in multiple biomes.

- **Don't touch other files in the datapack.** Climate density functions (`data/minecraft/worldgen/noise_settings/overworld.json`, `data/minecraft/worldgen/density_function/overworld/far_waste_*.json`), tags (`data/endeavour/tags/worldgen/biome/*.json`), and the 15 mod biome_modifier overrides are all already configured correctly. The tool only edits the `features` array of biome JSONs.

- **Validate output.** After writing, the tool should run a sanity check: every biome JSON parses, every placed_feature ID referenced in `features` exists somewhere (vanilla, modded, or in our endeavour clones). Catch typos before the user has to bisect a worldgen failure.

### Suggested file layout

```
endeavour/
├── tools/ore-tier-manager/        ← new directory
│   ├── apply.py                   ← main CLI: reads YAML, writes biome JSONs
│   ├── extract.py                 ← one-shot: reads existing biome JSONs, dumps initial YAML
│   ├── validate.py                ← post-write sanity checks
│   ├── config/
│   │   ├── tier_templates.yaml
│   │   └── biome_overrides.yaml
│   ├── README.md                  ← how to use
│   └── pyproject.toml             ← deps: openpyxl, pyyaml
```

A flat Python script is fine; no need for a UI. The user explicitly does NOT want a web app - declarative YAML inputs they can edit and re-run is the desired iteration loop.

### Tier mappings to encode (the design intent)

Per [tier-map.xlsx](tier-map.xlsx) and the design discussions:

- **T1** biomes get the standard vanilla T1 ore set (iron, copper, coal, gold).
- **T2** biomes get T1 + sometimes extras (e.g., mesa biomes get zinc).
- **T4** biomes (extreme cold + extreme hot wastes) get T1 + their atomic ore (uranium north, thorium south).
- **Special biomes** get specific ores via `biome_overrides`:
  - `terralith:volcanic_crater`, `volcanic_peaks`, `caldera`, `cave/thermal_caves`, `white_cliffs` → diamond (4 variants)
  - `terralith:emerald_peaks` → emerald
  - `terralith:scarlet_mountains` → redstone (2 variants)
  - `terralith:amethyst_canyon`, `amethyst_rainforest` → lapis (2 variants) + amethyst_geode
- **Mesa family** (vanilla badlands + Terralith bryce_canyon, painted_mountains, savanna_badlands, white_mesa, eroded_badlands, wooded_badlands) → zinc.
- **Extreme cold** (vanilla snowy_*, ice_spikes, frozen_*, deep_frozen_ocean, snowy_slopes, frozen_peaks + Terralith glacial_chasm, ice_marsh, siberian_*, snowy_*, frozen_cliffs) → uranium (Create Nuclear).
- **Extreme hot** (Hot Dry climate biomes - vanilla desert + badlands family, Terralith desert_*, painted_mountains, lush_desert, red_oasis, sandstone_valley) → thorium (Create New Age).

The `#endeavour:mesa_family`, `#endeavour:extreme_cold`, `#endeavour:extreme_hot`, `#endeavour:volcanic_zone`, `#endeavour:scarlet_mountains`, `#endeavour:emerald_peaks`, `#endeavour:amethyst_zone`, `#endeavour:tier_1`, `#endeavour:tier_2`, `#endeavour:tier_4` tags ALREADY EXIST at `datapack-worldgen/zzz_endeavour_worldgen/data/endeavour/tags/worldgen/biome/`. The tool can READ these to expand tag-based override keys (`"#endeavour:mesa_family":` in YAML) into individual biome IDs.

### What about Immersive Engineering's secondary ores?

`immersiveengineering:bauxite` (aluminum), `:lead`, `:nickel`, `:silver`, `:deep_nickel` are currently disabled via `neoforge:none` overrides - they don't spawn anywhere. The user has not yet decided their tier home. Leave them disabled by default in `tier_templates.yaml` (don't add to any tier). Add a note in the YAML comments that these are pending design decisions. When the user decides, they edit the YAML and rerun.

`createnuclear:lead_ore` is similar - disabled, pending decision (since IE also has lead, may not need both).

`create:striated_ores_overworld` is decorative stone variants (limestone, scoria, etc.). Currently disabled via `neoforge:none`. The user may want to include these in tier_1 so they spawn everywhere as decorative variation - or not. Default: leave disabled, document in comments.

## What success looks like

1. Tool runs end-to-end on a fresh checkout. Reads xlsx + YAML, writes biome JSONs.
2. First run with empty biome_overrides reproduces current state (no diff in biome JSONs).
3. Edit `biome_overrides.yaml` to add a new ore to a tag - rerun - verify only the affected biome JSONs changed.
4. User repacks zip, drops into a fresh world, ores spawn correctly per the new YAML.

## Things to know that aren't obvious

- **Ore Veines+ is removed**, do not reintroduce it. All ore tuning happens via `count` placement modifiers inside the placed_feature JSONs (vanilla pattern), or by adjusting which biomes reference which placed_feature (this tool's job).
- **Climate is locked.** Don't suggest changes to `noise_settings/overworld.json` or the `far_waste_*` density functions. Those work and are out of scope.
- **The `endeavour` namespace** is reserved for our datapack-side custom content (tags, density functions). The companion mod with `endeavour` modid is planned but NOT YET BUILT - `mod/` directory has stale gradle scaffolding from an abandoned attempt. You can ignore it. Don't suggest building the mod for this work.
- **The user is patient with multi-iteration debugging but has been burned by hallucinated docs**. Verify any claim about Minecraft data formats against either: (a) the misode/mcmeta repo (`https://github.com/misode/mcmeta` branches `1.21.1-data` and `1.21.1-summary`), (b) actual mod jar contents at `C:\Users\jonat\AppData\Roaming\ModrinthApp\profiles\Aetherian Skies\mods\`, or (c) the existing biome JSONs in our datapack. Don't trust wikis or AI-summarized docs without primary-source confirmation.
- **The `design/` folder has the source-of-truth docs**: design-doc.md (vision), tier-map.xlsx (biome+ore tier assignments), journal.md (chronological log of decisions and what we tried), open-questions.md (live decision queue), mod-list.md, density-function-research.md.

Good luck. The hard plumbing is done. This is a clean tooling job on a known-working substrate.
