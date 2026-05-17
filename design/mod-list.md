# Mod List

Minecraft 1.21.1, NeoForge. Active modlist below.

Markers:
- `*` - worldgen-changing mod
- `[hard]` - load-bearing for the design; removing breaks core mechanics
- `[opt]` - optional / aesthetic / QoL
- `[lib]` - library, required by other mods

## Core gameplay

| Mod | Role | Notes |
|-----|------|-------|
| Create | Foundation [hard] | Andesite/brass/steam progression |
| Sable | Physics library [hard] | Required by Aeronautics. Intrusive - confirm compatibility per addon |
| Create: Aeronautics | Logistics layer [hard] | The mod the server is named for |
| Aeronautics Camera Sync | Aeronautics camera follow [opt] | Aeronautics addon |
| Exposure | Custom camera exposure [opt] | |
| Create: Steam 'n' Rails | Rail variety [hard] | NeoForge port |
| Create: Crafts and Additions | IE compatibility [hard] | Bridges Create and IE |
| Create Deco | Decorative [opt] | |
| Create Horse Power | Horse-powered kinetics [opt] | Fits T1 horse-priority design |
| Create Slice and Dice | Cutting machines [opt] | Farmer's Delight integration |
| Create Waystones Recipes | Waystone-Create integration [opt] | Recipes for waystone parts |

## Industrial progression

| Mod | Role | Notes |
|-----|------|-------|
| Immersive Engineering | Steel [hard] | T3 gate |
| Create: Diesel | Crude oil + refining [hard] | T3 gate |
| Create Nuclear | Reactors [hard] | T4 gate |
| Create New Age | Advanced electrical [opt] | |

## Dimension content

| Mod | Role | Notes |
|-----|------|-------|
| The Aether | T5 dimension [hard] | Endgame |
| Aether Addon: Emissivity | Aether visuals [opt] | |
| Aether Addon: Enhanced Extinguishing | Aether QoL [opt] | |
| Aether's Delight | Aether food [opt] | Farmer's Delight integration |
| Deep Aether | Aether expansion [hard] | T5 content depth |

## Worldgen

| Mod | Role | Notes |
|-----|------|-------|
| Terralith * | Biome variety [hard] | KIND OF. Technically the mod is not in the pack. Its data has been ripped and integrated into the custom zzz_endeavour_worldgen datapack so we can modify ore spawns in biomes. |
| Continents * | Continental landmass shape [hard] | |
| William Wythers' Overhauled Overworld * | Additional biome variety [hard] | KIND OF. Technically the mod is not in the pack. Its data has been ripped and integrated into the custom zzz_endeavour_worldgen datapack so we can modify ore spawns in biomes. |
| Distant Horizons | Render-distance extension [opt] | Performance critical for our world size |
| Structurify | Structure spawn control [hard] | |
| More Density Functions | Adds `moredfs:x`, `moredfs:z`, `moredfs:sin`, `moredfs:cos`, `moredfs:mod`, etc. [hard] | Required for the toroidal climate density functions; vanilla 1.21.1 has no primitive that reads world X or Z. |
| Noisium (Forked) | Worldgen perf [lib] | |

## Travel and survival

| Mod | Role | Notes |
|-----|------|-------|
| Waystones | Discoverable + buildable waystones [hard] | Configurable warpRequirements |
| Ecliptic Seasons | Seasons [hard] | |
| Homeostatic | Thirst + temperature [hard] | |
| Torches Burn Out | Torch burnout [hard] | |
| Better Days | Day-length config [opt] | |
| Farmer's Delight | Better food/cooking [hard] | |
| Farmer's Knives | Farmer's Delight tools [opt] | |
| More Delight | More Farmer's Delight content [opt] | |

## Adventure

| Mod | Role | Notes |
|-----|------|-------|
| YUNG's Better Dungeons | Dungeon variety [hard] | |
| Dungeons and Taverns (Base + extensions) | Structure overhaul [hard] | Ancient City, Desert Temple, Jungle Temple, Nether Fortress, Ocean Monument, Stronghold, Swamp Hut, Woodland Mansion |
| YUNG's API | Required for YUNG mods [lib] | |
| Undead Nights - Zombie Horde Nights | Configurable invasions [hard] | Configure for trigger-only |

## Communication and aesthetic

| Mod | Role | Notes |
|-----|------|-------|
| Simple Voice Chat | Proximity voice [hard] | |
| Fresh Animations (via EMF/ETF) | Mob animation polish [opt] | |
| EMF/ETF | Fresh Animations runtime [lib] | |
| Xaero's Minimap | Minimap [opt] | |
| Xaero's World Map | Full map [opt] | |
| Xaero Zoomout | World map zoom [opt] | |
| Xaero's Minimap & World Map - Waystones Compatibility | Map-waystone integration [opt] | |

## Performance and infrastructure

| Mod | Role | Notes |
|-----|------|-------|
| Sodium | Render perf [hard] | |
| Lithium | Server tick perf [hard] | |
| Architectury API | Multi-loader API [lib] | |
| Balm | Helper library [lib] | Required by Waystones |
| GlitchCore | Required by some structures [lib] | |
| Gabou's Libs | Helper library [lib] | |
| YetAnotherConfigLib | Config UI [lib] | |
| Kotlin for Forge | Kotlin runtime [lib] | |
| Jade | Block info HUD [opt] | |
| JEI | Recipe lookup [hard] | |
| KubeJS | JS Integration | |
| KubeJS Create | Create JS Integration | |
| Ponder of KubeJS | Custom Ponder Scenes | |

## Companion mod (we are writing this)

| Mod | Role | Notes |
|-----|------|-------|
| endeavour | Server-specific content [hard] | Patchouli book, advancements, lore items, ignition rules |
| Patchouli | Data-driven guidebook [hard] | Required by `endeavour` |
| Patchouli Library | Inventory quick-access for Patchouli books [opt] | QoL addon - adds inventory buttons to open installed Patchouli books |
