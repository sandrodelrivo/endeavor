# `endeavour` companion mod

NeoForge 1.21.1 mod. Server-specific content for Endeavour.

## ⚠ Before scaffolding: verify Java is actually needed

KubeJS is now in the modlist. Several features originally planned for this Java mod may be KubeJS-feasible:

- **Custom lore items with right-click chapter unlocks** — KubeJS can register custom items with handlers
- **Obsidian-frame ignition cancel** — KubeJS event listener may suffice
- **Recipe disables** — KubeJS handles these natively
- **Advancement triggers** — KubeJS or pure datapack

**Investigate KubeJS feasibility before generating gradle scaffold.** If most or all features are KubeJS-feasible, this directory becomes textures + scripts only — no Java compilation step. If at least one feature genuinely requires Java (Patchouli `IComponent` extensions, deeper mixin work, etc.), keep the Java mod approach.

The rest of this README assumes the Java path. Adjust once the investigation is done.

## Scope

Small. The mod's job is what datapacks can't do.

- **Patchouli book** ("Reachfarer's Codex") — advancement-gated entries, lore, recipe references
- **Custom lore items** (8) — Patchouli quest-key flavor items found in dungeons. Single-use right-click unlocks book chapters
- **Disable obsidian-frame ignition** (event handler — pure datapack can't intercept this cleanly)
- **Recipe disables** for nether portal crafting paths

The mod does NOT add ores. The mod does NOT modify Aeronautics recipes.

## Structure (target — not yet built)

```
mod/
├── build.gradle
├── settings.gradle
├── gradle.properties
├── src/main/
│   ├── java/com/endeavour/
│   │   ├── Endeavour.java                ← @Mod entry point
│   │   ├── registry/
│   │   │   ├── ModItems.java             ← lore item DeferredRegister
│   │   │   ├── ModBlocks.java
│   │   │   └── ModCreativeTab.java
│   │   ├── item/
│   │   │   └── LoreUnlockItem.java       ← right-click unlocks Patchouli chapter
│   │   ├── event/
│   │   │   └── PortalIgnitionHandler.java ← cancels obsidian frame ignition
│   │   └── data/
│   │       └── (datagen if we use it)
│   └── resources/
│       ├── META-INF/
│       │   └── neoforge.mods.toml
│       ├── pack.mcmeta
│       ├── assets/endeavour/
│       │   ├── lang/
│       │   │   └── en_us.json
│       │   ├── models/item/
│       │   ├── textures/item/            ← migrated from textures-source/
│       │   └── patchouli_books/
│       │       └── reachfarers_codex/
│       │           ├── book.json
│       │           ├── en_us/
│       │           │   ├── categories/
│       │           │   ├── entries/
│       │           │   └── templates/
│       └── data/endeavour/
│           ├── advancement/
│           │   └── tier/                  ← T1–T5 advancement tree
│           └── recipe/
│               └── (recipe disables, e.g. flint_and_steel removal — actually not, see below)
```

## Dependencies

- Patchouli (1.21.1-93-NEOFORGE or later)
- NeoForge 1.21.1.x

## Recipe disables — important note

Don't blanket-disable flint and steel. It's used for many things. The "no nether portal ignition" rule is enforced by an event handler that cancels `PlayerInteractEvent` when the target is an obsidian frame in the right configuration.

For obsidian crafting itself, that's not a recipe — obsidian is created by water meeting lava. We can't disable that without breaking vanilla world generation. Options:
1. Allow obsidian creation but block ignition. Players can build the frame, just can't activate it.
2. Don't worry about it — players who go to the trouble of building an obsidian frame manually are doing the design legwork; only the find-a-prebuilt-portal mechanic is enforced for the *intended* path.

**Default:** option 1. Mostly a backstop. Decided.

## Status

Empty directory tree. Gradle scaffold not yet generated. See `HANDOFF.md` for the build queue.
