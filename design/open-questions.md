# Open Questions

Live queue. Each entry has a default if no decision is made by the time we need it. Once decided, move to a "decided" section at the bottom or delete.

## Blocking next session

### Q1. Climate wavelength
What value of `xz_scale` produces the right gradient at our world size?
- **Default:** 0.00003 (one ~33k-period cycle, well-matched to a 25k world).
- **Action:** Test 0.00002, 0.00003, 0.00005 in the noise prototype and pick visually.

### Q3. Distant-iron biomes
Which biomes count as "distant" for big iron veins (T3 steel age expedition)?
- **Default:** Frozen Peaks, Glacial Chasm, Volcanic Crater, Caldera, Deep Frozen Ocean, Skylands biomes. Plus require >5k from world spawn.
- **Action:** Confirm with Jon and Sandro.

### Q5. Nether portal force-spawn distance
How close to world spawn must we guarantee at least one ruined portal?
- **Default:** Within 3k blocks. Datapack-enforced via placed_feature.
- **Action:** Confirm. Closer trivializes the mechanic; farther risks server-bricking.

## Other open questions

### Q2. Zinc restriction biomes
- **Default:** Mesa, Badlands, Wooded Badlands, Eroded Badlands, Bryce Canyon, Painted Mountains, Savanna Badlands. All mesa-family.
- **Status:** Defaults likely fine. Confirm before writing biome modifier.

### Q4. Custom lore items: include all 8?
- **Default:** All 8. Textures already exist. Pure flavor, low risk.
- **Status:** Likely fine.

### Q6. Aeronautics-specific Patchouli book chapter
- **Default:** Single book ("Reachfarer's Codex") with Aeronautics as a chapter inside.
- **Status:** Likely fine.

### Q7. Starter island
- **Default:** Hand-pick seed. Aim for a small island within a chunk or two of (0,0).
- **Status:** Locked. Defer until worldgen is locked, then roll seeds.

### Q8. WWOO biome treatment
- **Default:** Keep both Terralith and WWOO. Variety > size. Catch-all `wwoo:*` row in tier-map gets expanded once seed is rolled.
- **Status:** Locked.

### Q9. Uranium pick-2-of-4 vs all-4-required
- **Default:** Pick 2 of 4 for T4 entry; need all 4 for late T4 mega-projects (reactor scaling).
- **Status:** Likely fine.

### Q10. Aeronautics recipe modifications?
- **Default:** No modifications. Aeronautics stays vanilla-recipe per its mod.
- **Status:** Locked.

### Q11. Disable nether portal ignition: how?
- **Default:** KubeJS event listener on `BlockEvent.RightClick` checking for flint-and-steel against an obsidian frame in valid portal configuration. Fall back to Java event handler in companion mod if KubeJS doesn't expose the event cleanly.
- **Status:** Investigate KubeJS feasibility first.

### Q12. Companion mod: Java or KubeJS?
- **Default:** Investigate KubeJS feasibility for all listed mod features (lore items, ignition cancel, recipe disables, advancement triggers). If all feasible, drop Java path entirely - the "mod" becomes scripts + textures + Patchouli book data.
- **Status:** Open. Resolve before any gradle scaffolding.

### Q13. Ecliptic → Homeostatic temperature bridge
- **Default:** KubeJS script registers an Ecliptic season-change listener and applies a global temperature offset to Homeostatic via its API. Cold solar terms shift Homeostatic ambient temperature down; hot terms shift it up.
- **Status:** Need to verify both mods expose what's needed. Both list KubeJS support - should be straightforward.

## Decided

(empty for now - move locked items here as they get decided)
