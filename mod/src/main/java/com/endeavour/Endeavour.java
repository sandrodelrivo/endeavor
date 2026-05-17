package com.endeavour;

import com.endeavour.config.EndeavourConfig;
import com.endeavour.registry.EndeavourBlockEntities;
import com.endeavour.registry.EndeavourBlocks;
import com.endeavour.registry.EndeavourItems;
import com.mojang.logging.LogUtils;
import com.mojang.serialization.MapCodec;
import net.neoforged.bus.api.IEventBus;
import net.neoforged.fml.ModContainer;
import net.neoforged.fml.common.Mod;
import net.neoforged.fml.config.ModConfig;
import net.neoforged.neoforge.common.world.BiomeModifier;
import net.neoforged.neoforge.registries.DeferredRegister;
import net.neoforged.neoforge.registries.NeoForgeRegistries;
import org.slf4j.Logger;

import java.util.function.Supplier;

@Mod(Endeavour.MODID)
public class Endeavour {
    public static final String MODID = "endeavour";
    public static final Logger LOGGER = LogUtils.getLogger();

    public static final DeferredRegister<MapCodec<? extends BiomeModifier>> BIOME_MODIFIER_SERIALIZERS =
            DeferredRegister.create(NeoForgeRegistries.Keys.BIOME_MODIFIER_SERIALIZERS, MODID);

    public static final Supplier<MapCodec<ScopeFeaturesBiomeModifier>> SCOPE_FEATURES =
            BIOME_MODIFIER_SERIALIZERS.register("scope_features", () -> ScopeFeaturesBiomeModifier.CODEC);

    public Endeavour(IEventBus modEventBus, ModContainer modContainer) {
        BIOME_MODIFIER_SERIALIZERS.register(modEventBus);
        EndeavourBlocks.BLOCKS.register(modEventBus);
        EndeavourItems.ITEMS.register(modEventBus);
        EndeavourBlockEntities.BLOCK_ENTITIES.register(modEventBus);
        modContainer.registerConfig(ModConfig.Type.COMMON, EndeavourConfig.SPEC);
        LOGGER.info("Endeavour mod loaded");
    }
}
