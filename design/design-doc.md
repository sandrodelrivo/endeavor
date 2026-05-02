# Endeavour Server Design

A heavily-modded Minecraft 1.21.1 NeoForge server for ~6 friends. Cooperative. Lifespan target 3–6 months active.

## The premise

The world was rich. The world is dead. We are the only intelligent creatures left. Across the bones of a vanished civilization — ruined waystones at old crossroads, vast dungeons with no quest-givers to point the way — we rebuild. The world is large, hostile, and slow. Distance is the central design constraint, and every system reinforces it. Cooperation is not nudged; it is structurally required. A lone wolf can survive, but the team will always reach the next era first.

The factory grows. The map shrinks. We climb.

## Core principles

1. **The world is disconnected.** Strong, opinionated worldgen. Resources are biome-locked. Progression requires long-haul logistics across multiple distant biomes. No single base can cover the tech tree alone.
2. **The factory will grow.** Multi-block industrial complexity is the central engagement loop. Five tiers, each with a peak moment.
3. **The player is slow.** Sprint is removed. Every transport tier — horse, cart, boat, ship, dirigible, train — has a niche where it dominates. None is strictly best.
4. **The world is dangerous.** No respawn point. Death sends to world spawn. Mobs scale with distance from spawn, with visual tells. Adventuring far is a real expedition.
5. **The world was rich.** Adventuring rewards are real. Dungeons hold serious loot. The dead civilization left infrastructure (waystones) scattered across the world.
6. **The world is dead.** No villagers, no trades. Ruined villages exist as scenery and loot. Piglin brutes can stay; trading does not. The only intelligent agents are the players.
7. **Being alone is boring.** Discoverable waystones (dense in settled terrain, sparse in frontier) form a transit network with resource-gated teleport costs. Player-built teleporters appear mid-T3 and are expensive. The teleport economy is the buyback mechanism.

## Aeronautics is the logistics layer

The mod stack centers on Create + Aeronautics, but Aeronautics is not a tier gate. It's the parallel horizontal capability that connects the disconnected world. Steel-and-petroleum-and-uranium gate progression. Airships and dirigibles are how players bring those resources together across hostile geography.

Big iron veins live in distant biomes. Petroleum reservoirs live elsewhere. Uranium lives in extreme biomes. Players must build airborne logistics — and rail, and shipping — to connect them. That's the design.

## The world

- 20–30k blocks square. Soft border or no border (transport friction enforces effective borders).
- 2–4 large continents separated by medium oceans. Continents have wide, deep rivers permitting riverine logistics. Small islands sprinkled across oceans for interest.
- Spawn is center, on a deliberately resource-poor starter island. Capable of supporting a small port and not much else. Forces the early-game expedition outward.
- Worldgen mod stack: Terralith + Continents + WWOO. Tier-Map.xlsx defines biome categories.
- Climate gradient is toroidal: north is cold, south is warm, east is wet, west is dry. Loops with wavelength ~20k. Implemented by overriding `minecraft:overworld` noise settings.

## Tier ladder

Recipes stay near vanilla per their mods. The challenge is the world, not recipe tedium. Gates are biome access and coordinated production, never grind-tax intermediates.

| Tier | Era | Gate | Peak moment |
|------|-----|------|-------------|
| T0 | Stranded | Hand tools, the starter island | First boat off the starter island |
| T1 | Settler | Common biomes. Iron, copper, coal, andesite Create. | First horse, first water wheel |
| T2 | Brass Age | Zinc → brass. Mesa-family expedition. | First mechanical farm running unattended |
| T3 (entry) | Nether | Find a prebuilt ruined nether portal. Crafting disabled. | Crossing the threshold |
| T3 (steel) | Steel Age | IE Coke Oven + Blast Furnace. Big iron veins biome-locked to distant biomes. | First long-haul airship cargo run |
| T3 (petroleum) | Industrial | Crude oil reservoirs. | First petroleum pipeline online |
| T4 | Atomic | Uranium biome-locked to extreme biomes. | First reactor critical |
| T5 | Beyond | Aether dimension. Elytra unlocks. | Whatever the group decides |

The grind peak should land in late T3. After that, T4 → T5 is the victory lap.

## Movement and transport

### Player movement

- Sprint disabled. Walking only. Datapack: `attribute base set @a generic.movement_speed`.
- Elytra disabled until T5 advancement.
- Horses become real. Speed-bred horses are a genuine T1 priority.

### Transport tiers (parallel — none dominates)

| Mode | Throughput | Infrastructure | Range | Niche |
|------|-----------|----------------|-------|-------|
| Horse / cart | Low | Free | Short | Default early intra-region |
| River boat | Medium | Free (rivers) | Continental interior | Riverine logistics |
| Ocean ship | High | Port-to-port | Inter-continent | Bulk cargo across oceans |
| Dirigible | Low | Zero (just airports) | Anywhere | Expedition + reaching unreachable terrain |
| Train | Highest | Heavy (lay track) | Mature regions | Mature-economy backbone |

Geography dictates transport, not vice versa. A volcano forge in jagged terrain is dirigible territory; a river-fed gemstone grove is boat territory; a flat plains hub is rail territory.

## Death and respawn

- No respawn point. No beds, no respawn anchors. Death sends to world spawn.
- Corpse mod retains inventory at death location. Items are not lost; you have to get back to them.
- Buyback economy = waystone economy. Friends warp you back via the network for a real but bearable resource cost.

The threat is the trek and the second death from the mob you didn't see. Items are preserved. Progression isn't.

## Waystones

- Discoverable structures only at T1–T2. Ruined-civilization stone circles scattered across the world.
- Density biased toward settled terrain. ~5k average spacing in plains/rivers/old-road areas. Sparse in volcanic interiors, deep ocean, far cold.
- Activation cost: small resource to bring online once discovered.
- Per-warp cost scales with distance. Cheap intra-region, expensive inter-region, prohibitive frontier.
- Player-built teleporters appear mid-T3, expensive. Place a node at your distant base.
- Cheap teleport doesn't really exist until late T4.

Implementation via Waystones (BlayTheNinth) + custom `warpRequirements` config + datapack overrides for spawn density and biome bias.

## Mob progression

- Distance-scaled. `max_health`, `attack_damage`, `armor`, `movement_speed` scale with distance from spawn. Vanilla within 2–3k. Linear ramp to ~2x at 10k. Soft-cap ~3x past 15k. Datapack function tag on entity spawn.
- Visual tells mandatory. Tiered glowing-eye / particle / armor variants applied as predicate-based equipment loadouts.
- Tier-gated equipment scaling at the same distance bands.
- Dungeons override distance scaling with internal difficulty.

## Survival layer

- Seasons (Ecliptic Seasons) — 24 solar terms across 4 seasons. Accumulating snow on dirt/grass/leaves/rooftops in cold terms, regional rainfall by biome, foggy weather, biome color shifts. KubeJS bindings exposed.
- Thirst + temperature (Homeostatic) — drink water, wear appropriate clothing for biome. Wet-bulb globe temperature math, body temp regulation via armor insulation.
- Ecliptic→Homeostatic bridge — KubeJS script applies global temperature offset to Homeostatic based on current solar term. Without this, Homeostatic temperature stays seasonally flat.
- Torch burnout — configurable burn time, optional re-ignition with flint and steel.
- Better farming (Farmer's Delight) — meaningful engagement track for non-Create-pilled players.

## Adventure layer

- YUNG's Better Dungeons + Dungeons and Taverns extensions for dense, varied dungeons.
- Customized loot tables ensure dungeon chests are worth raiding.
- The world is littered with the dead civilization's last halls.

## Invasions

Manually triggered group ritual, not calendar-based. A group must be online and consenting. Clear in-game warning fires before activation. Themed wave attacks with elite mobs that can mine blocks.

Implementation via PureSuffering, configured for triggered-only mode. Custom datapack fallback if PureSuffering can't be configured to trigger-only.

## Custom companion mod

Small. Its job is what datapacks can't do.

- **Patchouli book** ("Reachfarer's Codex"): advancement-gated entries, lore, recipe references
- **Tier progression advancement tree**: drives book unlocks and waystone/elytra gating
- **Custom lore items** (8): Patchouli quest-key flavor items found in dungeons. Single-use right-click unlocks book chapters. Textures already exist.
- **Disable obsidian-frame ignition** (event handler, not pure datapack)
- **Recipe disables** for nether portal crafting paths

The mod does NOT add ores. It does NOT modify Aeronautics recipes. Scope is deliberately small.

## Custom lore items

Eight quest-key flavor items, found rarely in themed biomes' dungeons and structures. Right-click consumes, unlocks a Patchouli book chapter. No progression impact.

| Item | Theme | Found in | Unlocks chapter |
|------|-------|----------|-----------------|
| Sulfur Crystal | Fire/Volcanic | Volcanic biomes | The Forge-Walkers |
| Cryolite Fragment | Frost/Glacial | Cold-biome dungeons | The Cold Reach |
| Aerolith Shard | Sky/Lift | Skylands structures | They Built Wings |
| Abysmite Pearl | Sea/Pressure | Ocean monuments + underwater dungeons | Below the Waves |
| Sculk-Iron Splinter | Deep Dark | Ancient Cities | What the Sculk Took |
| Pyrolith Shard | Volcanic Crater | Volcanic Crater + Caldera (combine halves) | The Bellows of the World |
| Mirage Crystal Iridescence | Mirage Isles | Mirage Isles structures | Where Time Doubts Itself |
| Aetherbone Fragment | Skylands / pre-Aether | Skylands rare structures | Before the Aether |

## Datapacks we are writing

- **Sprint removal.** Sets `generic.movement_speed` to walking value on player join and tick.
- **Respawn point disable.** Removes bed/respawn anchor sleep/respawn behavior. Sets respawn to world spawn.
- **Elytra disable until T5.** Item-disable until quest completion grants the unlock advancement.
- **Mob distance scaling.** Scales stats by distance from spawn. Includes visual-tell loadout.
- **Tier progression advancement tree.** Drives all the gating: T1–T5 advancements that unlock recipes, waystone construction, elytra, dimension portals.
- **Biome resource locking.** NeoForge biome modifier JSONs that gate ore generation by biome tag.
- **Toroidal climate noise.** Override `minecraft:overworld` density functions for temperature and humidity.
- **Forced nether portal spawn.** Place at least one ruined portal within 3k blocks of world spawn.
- **Waystone density bias.** Spawn rate overrides biased toward settled biome tags.
- **Ritual-triggered invasion.** Fallback if PureSuffering can't be configured for trigger-only mode.

## Reference

Source-of-truth tables for biomes, resources, tier gates, lore items: `design/tier-map.xlsx`.

Live decisions still pending: `design/open-questions.md`.

Density function research: `design/density-function-research.md`.
