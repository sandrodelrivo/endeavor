# TODO

Roadmap from current state to a launchable Endeavour server. Grouped by the build queue in [CLAUDE.md](CLAUDE.md). Order matters where noted; within a phase, work usually parallelizes.

## Phase 0 - Unblock decisions

- [ ] Resolve **Q1** (climate `xz_scale`) - pick test values 0.00002 / 0.00003 / 0.00005 with default 0.00003.
- [ ] Resolve **Q3** (distant-iron biomes) - confirm Frozen Peaks / Glacial Chasm / Volcanic Crater / Caldera / Deep Frozen Ocean / Skylands + 5k-from-spawn rule with Jon and Sandro.
- [ ] Resolve **Q5** (nether portal force-spawn distance) - confirm 3k default.
- [ ] Fix the `pack.mcmeta` claim in [HANDOFF.md](HANDOFF.md) (files don't actually exist yet) and write real `pack.mcmeta` for both datapacks (`pack_format` 48 for 1.21.1).

## Phase 1 - Toroidal noise prototype (highest technical risk)

- [ ] Build a minimal datapack that ONLY overrides `data/minecraft/worldgen/noise_settings/overworld.json` with Approach A from [design/density-function-research.md](design/density-function-research.md): low-`xz_scale` `shifted_noise` for `temperature` and `vegetation`, mixed 70/30 with vanilla noise.
- [ ] Test in a fresh world at the three candidate `xz_scale` values. Confirm gradient is visible via F3 and walk/fly tests; rule out NaN / `shift_z` schema regressions.
- [ ] Verify load order with Terralith / Continents / WWOO - does the `zzz_` prefix actually win the override fight? If not, decide whether to live with that or pivot.
- [ ] **Decision gate:** if Approach A works, lock the chosen `xz_scale` and proceed. If it doesn't, surface to Jon before pivoting (mod-side periodic density function, accept non-toroidal, or static climate map).

## Phase 2 - `zzz_endeavour_worldgen` datapack

- [ ] Promote the noise prototype into the real worldgen datapack with a proper `pack.mcmeta`.
- [ ] Biome modifier JSONs for ore restriction:
  - [ ] Zinc → mesa family (Q2 default).
  - [ ] Big iron veins → Q3 distant biome list, with `>5k from spawn` predicate.
  - [ ] Uranium → extreme biomes (Frozen Peaks, Volcanic Crater family, etc.).
  - [ ] Vanilla iron, copper, coal, andesite → unchanged (verify nothing else overrides).
- [ ] `placed_feature` for forced ruined nether portal within Q5 distance of world spawn. Confirm placement in test seed.
- [ ] Waystone density bias overrides - JSONs that bias spawning toward settled biome tags, sparse in volcanic / deep ocean / far cold.
- [ ] Worldgen smoke test on jacobsjo map viewer once the datapack is published or accessible.

## Phase 3 - `zzz_endeavour_rules` datapack

- [ ] Sprint disable: `attribute base set @a generic.movement_speed` function on join + tick maintenance via function tag.
- [ ] Respawn point disable: `gamerule` setup + tick function that resets respawn to world spawn (and clears bed/anchor respawn). Confirm interaction with Corpse mod.
- [ ] Mob distance scaling function: scale `max_health`, `attack_damage`, `armor`, `movement_speed` linearly to 2x at 10k, soft-cap 3x at 15k. Apply on entity spawn function tag.
- [ ] Visual-tell loadouts: predicate-based equipment loadouts at the same distance bands (glowing eyes / particle / armor variants - vanilla-only mechanism).
- [ ] Tier-progression advancement tree (T0–T5): drives book chapter unlocks, elytra unlock at T5, waystone-build unlock mid-T3, dimension portal unlocks. Coordinate with Phase 5 (some advancements key off custom items).
- [ ] Elytra disable until T5 advancement: item-disable predicate or loot-table strip + advancement-gated unlock.
- [ ] Recipe disables for nether-portal crafting paths (datapack-side; ignition block goes in the mod).
- [ ] Triggered-only invasion fallback datapack - only if PureSuffering can't be configured for trigger-only (verify in Phase 6 first).

## Phase 4 - Companion mod scaffolding

- [ ] NeoGradle project skeleton for NeoForge 1.21.1, Mojang mappings, modid `endeavour`. Standard `mods.toml`, `build.gradle`, `gradle.properties`, `runs` block.
- [ ] Patchouli dependency wired (correct 1.21.1 NeoForge build).
- [ ] Item registry stubs for the 8 lore items with a creative tab.
- [ ] Datagen pipeline (recipes, item models, loot tables, lang) wired so we don't hand-write JSON.

## Phase 5 - Companion mod content

- [ ] Migrate existing textures from [textures-source/](textures-source/) into `mod/src/main/resources/assets/endeavour/textures/item/`.
- [ ] **Texture gap:** only sulfur / cryolite / aerolith textures exist. The other 5 lore items (abysmite, sculk-iron, pyrolith, mirage crystal iridescence, aetherbone) need textures from Jon before this phase ships.
- [ ] Wire each lore item's right-click handler to a one-shot Patchouli chapter unlock (advancement granted on use, advancement triggers Patchouli `entry_unlocked` predicate). Items consume on use.
- [ ] Loot-table injection: each lore item appears in the appropriate themed-biome dungeon / structure loot pool per the table in [design/design-doc.md](design/design-doc.md).
- [ ] Obsidian-frame ignition disable: NeoForge event handler intercepting portal-spawn events (verify the 1.21.1 API). Cancel ignition on player-built frames; allow worldgen-placed ruined portals.
- [ ] Patchouli book ("Reachfarer's Codex") scaffold: `book.json`, category structure, ~25–35 entry stubs with advancement-gating metadata.
- [ ] Patchouli book content pass: lore prose, recipe references, the 8 lore-item chapters, Aeronautics chapter (Q6 default = single book).

## Phase 6 - Integration / compat / polish

- [ ] Stand up a test server with the [hard] mods from [design/mod-list.md](design/mod-list.md) plus our two datapacks and the companion mod. Confirm Sable doesn't fight other mods.
- [ ] Configure PureSuffering for trigger-only mode; if impossible, ship the Phase 3 fallback datapack.
- [ ] Configure Waystones `warpRequirements` for distance-scaled resource cost; tie player-built teleporter unlock into the T3 advancement.
- [ ] Configure Homeostatic + Serene Seasons + Torches Burn Out values to match the design's danger curve.
- [ ] Configure Structurify spawn rules for waystone density and dungeon prevalence.
- [ ] Distance-scaled mob equipment / dungeon loot table audit - make sure dungeon chests genuinely feel "the world was rich" per principle 5.

## Phase 7 - World seeding

- [ ] Roll seeds against the locked stack until a small, resource-poor starter island near (0,0) is found per Q7. Document the chosen seed in [HANDOFF.md](HANDOFF.md) and a `design/seed.md`.

## Phase 8 - Ship

- [ ] Final playtest with 1–2 friends covering at least T0 → first horse, including death/respawn loop, waystone discovery, and a nether portal find.
- [ ] Server config bundle (`server.properties`, `ops.json` template, performance flags for Sodium / Lithium / Distant Horizons, world border if any).
- [ ] Update [README.md](README.md) and [HANDOFF.md](HANDOFF.md) to "ready to launch" state, with install instructions for the modpack + datapacks + companion mod.

## Risk flags

- **Texture gap.** 5 of 8 lore items have no textures yet. Phase 5 blocks on Jon producing them or a decision to ship with placeholders.
- **Sable compat is genuinely uncertain.** The mod-list flags it as intrusive. If Phase 6 step 1 finds a real conflict, that ripples back into the modlist itself, not just configs.
- **Toroidal noise.** Approach A in [design/density-function-research.md](design/density-function-research.md) is "noise that varies slowly," not true periodicity. If the prototype reveals visible wraparound problems at world scale, Phase 1's decision gate becomes a real branch point.
