# HANDOFF.md

Session-to-session continuity for Claude Code agents. Update this at the end of every session. **Read CLAUDE.md first** for project context.

## Current state

Repo just scaffolded. Design phase complete. Implementation has not started.

What exists:
- `CLAUDE.md` — cold-start context
- `design/design-doc.md` — full design
- `design/tier-map.xlsx` — source of truth for biomes/resources/tiers
- `design/mod-list.md` — active mods
- `design/density-function-research.md` — research notes on the toroidal climate gradient
- `design/open-questions.md` — pending decisions
- `datapack-worldgen/pack.mcmeta` — empty pack scaffold
- `datapack-rules/pack.mcmeta` — empty pack scaffold
- `mod/` — empty directory tree, no gradle scaffold yet
- `textures-source/` — placeholder for Jon's ore textures (pending Jon dropping them in)

What does NOT exist yet:
- Any density function JSON
- Any biome modifier JSON
- Any placed_feature JSON
- The mod's gradle setup
- Any Java code
- Any Patchouli book content

## Last decisions made

- Aeronautics is the LOGISTICS LAYER, not a tier gate.
- Tier ladder adopts Sandro's revised version: Vanilla → Create → Nether-via-prebuilt-portal → IE Steel → IE Petroleum → Create Nuclear → Aether.
- Custom ores DROPPED as progression. Repurposed as 8 Patchouli quest-key lore items.
- Mod scope shrunk to: book + advancements + lore items + portal-ignition-disable + recipe-disables.
- No modifications to Aeronautics recipes.

## Next action

Per the build queue in CLAUDE.md, step 1 is **prototyping the toroidal noise function in isolation**. This is the highest technical risk in the project. If it doesn't work, the whole climate-gradient design changes.

Approach is sketched in `design/density-function-research.md`. Build a minimal datapack that ONLY overrides `minecraft:overworld` noise settings with a candidate toroidal function. Test in a fresh world. Confirm climate visibly varies N/S/E/W with the expected wavelength. THEN proceed.

## Open questions blocking work

See `design/open-questions.md`. The blocking ones for next session:
- Q1 (climate wavelength) — defaults to 20k, but worth confirming before locking the noise function
- Q3 (distant-iron biomes) — need this list before writing biome modifiers
- Q5 (nether portal force-spawn distance) — need this before writing the portal placed_feature

## Notes on getting unstuck

If you can't make density function math work in pure datapack form, stop and discuss with Jon before pivoting to a mod-side solution. There may be other options (Lithostitched, biome-modifier-driven approach, accepting non-toroidal climate, etc.).

If you need to roll a seed for testing, use the jacobsjo map viewer:
https://map.jacobsjo.eu/?datapacks=modrinth:terralith,modrinth:continents,modrinth:william-wythers-overhauled-overworld-(datapack)

Add the Endeavour datapack URL once it has one.
