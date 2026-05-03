package com.endeavour;

import com.mojang.logging.LogUtils;
import com.mojang.serialization.MapCodec;
import net.neoforged.bus.api.IEventBus;
import net.neoforged.fml.common.Mod;
import net.neoforged.neoforge.common.world.BiomeModifier;
import net.neoforged.neoforge.registries.DeferredRegister;
import net.neoforged.neoforge.registries.NeoForgeRegistries;
import org.slf4j.Logger;

import java.util.function.Supplier;

@Mod(Endeavour.MODID)
public class Endeavour {
    public static final String MODID = "endeavour";
    public static final Logger LOGGER = LogUtils.getLogger();

    // DeferredRegister for our biome_modifier codecs. NeoForge expects custom
    // BiomeModifier implementations to register their MapCodec into this registry.
    public static final DeferredRegister<MapCodec<? extends BiomeModifier>> BIOME_MODIFIER_SERIALIZERS =
            DeferredRegister.create(NeoForgeRegistries.Keys.BIOME_MODIFIER_SERIALIZERS, MODID);

    // Register the codec under id `endeavour:scope_features` — this is what users put
    // in the JSON `"type"` field.
    public static final Supplier<MapCodec<ScopeFeaturesBiomeModifier>> SCOPE_FEATURES =
            BIOME_MODIFIER_SERIALIZERS.register("scope_features", () -> ScopeFeaturesBiomeModifier.CODEC);

    public Endeavour(IEventBus modEventBus) {
        BIOME_MODIFIER_SERIALIZERS.register(modEventBus);
        LOGGER.info("Endeavour mod loaded — registered biome_modifier type endeavour:scope_features");
    }
}
