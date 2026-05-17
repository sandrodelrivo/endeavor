package com.endeavour.registry;

import com.endeavour.blockentity.TributeAltarBlockEntity;
import net.minecraft.core.registries.Registries;
import net.minecraft.world.level.block.entity.BlockEntityType;
import net.neoforged.neoforge.registries.DeferredRegister;

import java.util.function.Supplier;

import static com.endeavour.Endeavour.MODID;

public class EndeavourBlockEntities {

    public static final DeferredRegister<BlockEntityType<?>> BLOCK_ENTITIES =
            DeferredRegister.create(Registries.BLOCK_ENTITY_TYPE, MODID);

    public static final Supplier<BlockEntityType<TributeAltarBlockEntity>> TRIBUTE_ALTAR =
            BLOCK_ENTITIES.register("tribute_altar", () ->
                    BlockEntityType.Builder
                            .of(TributeAltarBlockEntity::new, EndeavourBlocks.TRIBUTE_ALTAR.get())
                            .build(null));
}
