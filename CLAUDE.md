# CLAUDE.md

You are working on **Endeavour**, a heavily-modded Minecraft 1.21.1 NeoForge server for ~6 friends. This file is the cold-start context. Read it fully before any other work.

## Working with Jon

Jon's preferences live in his Claude system prompt and are critical. The short version for agents who don't have them:

- **Boil the ocean.** Do the whole thing, do it right, do it with tests, do it with documentation. Never offer to "table this for later." Never ship a workaround when the real fix exists. Time/fatigue/complexity are not excuses. The standard isn't "good enough" - it's "holy shit, that's done."
- **Search before building.** Test before shipping.
- **Be challenged, challenge back.** Jon is sharp. He'll push back on hallucinations. You should push back on his bad calls. No sycophancy. No "you're absolutely right." No "that's not X, that's Y." No em-dashes. No LLM-slop phrases.
- **Python conventions.** `.venv`, `requirements.txt`, README.md, gitignored `.env`, ruff for linting, pylance hints, Google-style docstrings, pyproject.toml.
- **Apologize only when actually wrong** - don't fold under pressure if Jon challenges something you're confident about. Be dead certain he's right before you concede.
- **Source-of-truth documents describe what IS, not what CHANGED.** Git is the changelog. No "v2 changes" sections in living docs. No version markers in filenames if avoidable.

If anything in this file conflicts with the running design discussion, the design discussion wins - but ask first if it's a meaningful conflict.

## What this project is

Heavily-modded Minecraft 1.21.1 NeoForge server. Six friends. Cooperative. Lifespan target 3–6 months. The world is **disconnected, dangerous, and dead.** Players cooperate to rebuild civilization in a world where a prior age left ruins, dungeons, and infrastructure but no people.

The vibe: *Frostpunk-meets-Factorio-in-Minecraft.*

## Core design principles (locked)

These are non-negotiable. Everything else serves them.

1. **The world is disconnected.** Strong, opinionated worldgen. Resources are biome-locked. Progression *requires* long-haul logistics across multiple distant biomes. No single base can cover the tech tree alone.
2. **The factory will grow.** Multi-block industrial complexity is the central engagement loop. Five tiers of technology, each with a peak moment.
3. **The player is slow.** Sprint is removed (walking speed only). Every transport tier - horse, cart, boat, ship, dirigible, train - has a niche where it dominates. None is strictly best.
4. **The world is dangerous.** No respawn point. Death sends you to world spawn. Mobs scale with distance from spawn (visual tells required). Adventuring far is a real expedition.
5. **The world was rich.** Adventuring rewards are real and substantial. Dungeons hold serious loot. The dead civilization left infrastructure (waystones) scattered across the world.
6. **The world is dead.** No villagers, no trades. Ruined villages exist as scenery and loot. Piglin brutes can stay; trading does not. The only intelligent agents are the players.
7. **Being alone is boring.** Discoverable waystones (dense in settled terrain, sparse in frontier) form a transit network with resource-gated teleport costs. Player-built teleporters appear mid-T3 and are expensive.

## Aeronautics is the LOGISTICS LAYER, not a tier

Originally framed as "the core mod." That framing was wrong and is corrected. Aeronautics is **how the disconnected world connects** - the parallel horizontal capability that runs alongside vertical tier progression. Steel-and-diesel-and-uranium gate progression. Airships and dirigibles are how you bring those resources together across hostile geography.

Big iron veins in distant biomes + diesel reservoirs in different biomes + uranium in extreme biomes ⇒ players must build airborne logistics to connect them. That's the design.

## Tier ladder (locked)

| Tier | Era | Gate | Source |
|------|-----|------|--------|
| T0 | Stranded | Get off starter island | Vanilla |
| T1 | Settler | Common biomes, basic Create | Vanilla + Create |
| T2 | Brass Age | Zinc → brass. Mesa expedition. | Create + biome-lock zinc |
| T3 entry | Nether | **Find a prebuilt ruined portal.** Crafting disabled. | Vanilla + datapack |
| T3 (steel) | Steel Age | IE Coke Oven + Blast Furnace. Big iron veins biome-locked to distant biomes. | Immersive Engineering |
| T3 (diesel) | Industrial | Crude oil reservoirs. | Create: Diesel |
| T4 | Atomic | Uranium. Biome-locked to extreme biomes. | Create Nuclear / IE |
| T5 | Beyond | Aether dimension. Elytra unlocks. | Aether + Deep Aether |

See `design/tier-map.xlsx` for the full source-of-truth tables.

## Mod list

The active modlist is in `design/mod-list.md`. Hard-core anchors:

- **Create + Sable + Create: Aeronautics** (NeoForge 1.21.1)
- **Immersive Engineering + Create Diesel + Crafts and Additions**
- **Create Nuclear + Create New Age**
- **The Aether + Deep Aether + Aether's Delight**
- **Terralith + Continents + WWOO** (worldgen)
- **Waystones (BlayTheNinth)** + **Corpse**
- **Serene Seasons + Homeostatic** (seasons + thirst/temperature)
- **Torches Burn Out**
- **Simple Voice Chat**
- **PureSuffering** (configurable invasions)
- **Sodium + Lithium + Distant Horizons** (performance)
- **Patchouli** (companion mod's data-driven guidebook)
- **KubeJS + Create KubeJS + Ponder for KubeJS** (scripting layer - see note below)

### KubeJS changes the build calculus

KubeJS is in the modlist. This means:
- Custom items with right-click handlers may not need a Java mod - KubeJS can register them.
- Event handlers (block ignition, player events, etc.) may be KubeJS scripts, not Java.
- The Ecliptic Seasons → Homeostatic temperature bridge is a KubeJS script.
- Recipe modifications, advancement triggers, and small mechanics live in KubeJS.

**Before scaffolding the Java companion mod, verify which features actually need Java vs. which are KubeJS-feasible.** If most features are KubeJS, the companion mod may collapse to "datapacks + scripts + textures" with no Java compilation step. The mod README still describes a Java mod approach as a fallback. Investigate before committing either direction.

## What we are building

Three deliverables in this repo:

### 1. `datapack-worldgen/` - `zzz_endeavour_worldgen`
The worldgen + ore distribution + biome restriction layer. **Pure data files.** No Java.
- Toroidal climate density functions (overrides `minecraft:overworld` noise settings)
- Biome modifier JSONs for ore restriction (zinc → mesa family, big iron veins → distant biomes, uranium → extreme biomes)
- Placed_features for forced-spawn nether portals near world spawn
- Loaded last in pack order (`zzz_` prefix is intentional)

### 2. `datapack-rules/` - `zzz_endeavour_rules`
Pure-rules layer for things that don't need worldgen. **Pure data files.**
- Sprint disable (set `generic.movement_speed` to walking)
- Respawn point disable
- Elytra disable until T5 advancement
- Mob distance scaling + visual tells
- Disable nether portal crafting paths

### 3. `mod/` - `endeavour` companion mod (NeoForge 1.21.1)
The mod is small. Its job is the things datapacks can't do:
- **Patchouli book** ("Reachfarer's Codex"): advancement-gated entries, lore, recipe references
- **Tier progression advancement tree**: drives book unlocks and waystone/elytra gating
- **Custom lore items** (8 of them): Patchouli quest-key flavor items found in dungeons. Single-use right-click unlocks book chapters. Textures already exist in `textures-source/`.
- **Disable obsidian-frame ignition** (event handler, not pure datapack)
- **Recipe disables** for nether portal crafting paths

The mod does NOT add ores. It does NOT modify Aeronautics recipes. Scope is deliberately small.

## Build queue (do these in order)

The handoff hits this point. Next steps:

1. **Prototype the toroidal noise function** in isolation. 1.21.1 density functions don't have a native `cos`. We approximate with tuned `shifted_noise` plus arithmetic. **This is the highest-risk technical piece - prove it works before building the full worldgen pack.** See `design/density-function-research.md` for the approach.
2. **Lock open questions in `design/tier-map.xlsx` (Open Questions sheet).** Climate wavelength, distant-iron biome list, nether portal force-spawn distance, etc. Don't build worldgen until these are decided.
3. **Write the worldgen datapack.** Climate density functions, biome modifiers for ore restriction, placed_features for forced-spawn portals.
4. **Write the rules datapack.** Sprint, respawn, elytra, mob scaling. These are well-understood and small.
5. **Write the companion mod skeleton.** NeoGradle + Mojang mappings setup. Basic blocks/items registry. Patchouli book scaffolding.
6. **Mod compatibility test pass.** Stand up a test server with the hard-core mods. Sable is intrusive - confirm no fights.
7. **Patchouli book content.** Lore writing. ~25–35 entries, advancement-gated.
8. **Texture migration.** Move Jon's textures from `textures-source/` to mod resource paths.
9. **Seed rolling.** Once worldgen is locked, roll seeds against the mod stack until we find a small-island spawn with good continent layout.

## What's open vs. locked

`design/open-questions.md` has the live list of decisions still pending.
`design/tier-map.xlsx` "Open Questions" sheet has the spreadsheet version of the same.

## Where things live

```
endeavour/
├── CLAUDE.md                      ← this file
├── HANDOFF.md                     ← session-to-session continuity
├── README.md                      ← human-facing repo intro
├── design/
│   ├── design-doc.md              ← the full design document
│   ├── tier-map.xlsx              ← source of truth for biomes/resources/tiers
│   ├── mod-list.md                ← active mods
│   ├── density-function-research.md  ← toroidal noise research notes
│   └── open-questions.md          ← live decision queue
├── datapack-worldgen/             ← zzz_endeavour_worldgen (pure data)
├── datapack-rules/                ← zzz_endeavour_rules (pure data)
├── mod/                           ← endeavour NeoForge mod
│   └── src/main/...
└── textures-source/               ← Jon's hand-made ore textures, pre-migration
```

## Build outputs

Two build steps produce the artifacts the modpack consumes:

- **Datapack zips**: run `python tools/rezip_datapacks.py` (stdlib only, no deps) to rebuild `datapack-rules/zzz_endeavour_rules.zip` and `datapack-worldgen/zzz_endeavour_worldgen.zip` from their source directories. Always use this script for these zips - Windows-native zip tools (Compress-Archive, .NET ZipFile, Send to compressed folder) write backslashes in entry paths, which silently break the pack on Linux servers.
- **Mod jar**: run `./gradlew jar` from `mod/`. First run after a clone needs `./gradlew setupCompileLibs` to pull aero/sable/create classes from the local Modrinth profile (path overridable via `-Pendeavour.modpack.mods.dir=<path>`). Output at `mod/build/libs/endeavour-<version>.jar`.

## A note on tone

This project is for fun. The friends are smart, the design is opinionated, and the standard is high. Don't be precious. Don't be cautious past the point of usefulness. If you find a bad call in the design, say so. If a mod combination is going to crash, say so. If you don't know something, say "I don't know" and search.

The work is the play.
