package com.endeavour;

import com.mojang.datafixers.util.Either;
import com.mojang.serialization.Codec;
import com.mojang.serialization.MapCodec;
import com.mojang.serialization.codecs.RecordCodecBuilder;
import net.minecraft.core.Holder;
import net.minecraft.core.HolderSet;
import net.minecraft.world.level.biome.Biome;
import net.minecraft.world.level.levelgen.GenerationStep.Decoration;
import net.minecraft.world.level.levelgen.placement.PlacedFeature;
import net.neoforged.neoforge.common.world.BiomeGenerationSettingsBuilder;
import net.neoforged.neoforge.common.world.BiomeModifier;
import net.neoforged.neoforge.common.world.ModifiableBiomeInfo;

import java.util.EnumSet;
import java.util.List;
import java.util.Set;

/**
 * Restricts a set of placed features to ONLY appear in biomes matching `scopeTo`.
 *
 * <p>Concretely: when the modifier fires (Phase.REMOVE) for a biome NOT in
 * {@code scopeTo}, every feature in {@code features} is stripped from the
 * specified {@code steps}. Biomes inside {@code scopeTo} are untouched, so the
 * feature continues to spawn there at whatever rate the original placement
 * declared.
 *
 * <p>Why this exists: stock NeoForge has {@code add_features} (Phase.ADD) and
 * {@code remove_features} (Phase.REMOVE). Combining them to "move feature from
 * biome group A to subset B" doesn't work because Phase.ADD always runs before
 * Phase.REMOVE — any add to a biome inside #is_overworld also gets stripped by
 * the subsequent remove targeting #is_overworld. The clone-and-add workaround
 * (create a new placed feature and add it to B) creates feature ordering cycles
 * across biome packs (e.g. Terralith's mantle_caves orders diamond variants
 * differently than vanilla, so introducing duplicates breaks the topological
 * sort).
 *
 * <p>This modifier sidesteps both. The placed_feature already exists in vanilla
 * biome JSONs. We just selectively strip it where it shouldn't be.
 *
 * <p>JSON shape:
 * <pre>{@code
 * {
 *   "type": "endeavour:scope_features",
 *   "scope_to": "#endeavour:volcanic_zone",
 *   "features": ["minecraft:ore_diamond", "minecraft:ore_diamond_buried", ...],
 *   "steps": "underground_ores"          // optional; defaults to all steps
 * }
 * }</pre>
 */
public record ScopeFeaturesBiomeModifier(
        HolderSet<Biome> scopeTo,
        HolderSet<PlacedFeature> features,
        Set<Decoration> steps
) implements BiomeModifier {

    public static final MapCodec<ScopeFeaturesBiomeModifier> CODEC = RecordCodecBuilder.mapCodec(builder -> builder.group(
            Biome.LIST_CODEC.fieldOf("scope_to").forGetter(ScopeFeaturesBiomeModifier::scopeTo),
            PlacedFeature.LIST_CODEC.fieldOf("features").forGetter(ScopeFeaturesBiomeModifier::features),
            // `steps` accepts either a single string or a list of strings; defaults to all decoration steps.
            Codec.<List<Decoration>, Decoration>either(Decoration.CODEC.listOf(), Decoration.CODEC)
                    .<Set<Decoration>>xmap(
                            either -> either.map(Set::copyOf, Set::of),
                            set -> set.size() == 1 ? Either.right(set.iterator().next()) : Either.left(List.copyOf(set))
                    )
                    .optionalFieldOf("steps", EnumSet.allOf(Decoration.class))
                    .forGetter(ScopeFeaturesBiomeModifier::steps)
    ).apply(builder, ScopeFeaturesBiomeModifier::new));

    @Override
    public void modify(Holder<Biome> biome, Phase phase, ModifiableBiomeInfo.BiomeInfo.Builder builder) {
        if (phase != Phase.REMOVE) return;
        // If this biome is in the protected scope, leave its features alone.
        if (this.scopeTo.contains(biome)) return;

        BiomeGenerationSettingsBuilder gen = builder.getGenerationSettings();
        for (Decoration step : this.steps) {
            gen.getFeatures(step).removeIf(this.features::contains);
        }
    }

    @Override
    public MapCodec<? extends BiomeModifier> codec() {
        return Endeavour.SCOPE_FEATURES.get();
    }
}
