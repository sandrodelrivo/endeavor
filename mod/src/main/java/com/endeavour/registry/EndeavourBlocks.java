package com.endeavour.registry;

import com.endeavour.block.TributeAltarBlock;
import net.minecraft.world.level.block.SoundType;
import net.minecraft.world.level.block.state.BlockBehaviour;
import net.neoforged.neoforge.registries.DeferredBlock;
import net.neoforged.neoforge.registries.DeferredRegister;

import static com.endeavour.Endeavour.MODID;

public class EndeavourBlocks {

    public static final DeferredRegister.Blocks BLOCKS = DeferredRegister.createBlocks(MODID);

    public static final DeferredBlock<TributeAltarBlock> TRIBUTE_ALTAR =
            BLOCKS.register("tribute_altar", () -> new TributeAltarBlock(
                    BlockBehaviour.Properties.of()
                            .strength(3.5f, 6.0f)
                            .sound(SoundType.STONE)
                            .requiresCorrectToolForDrops()
                            .lightLevel(state -> state.getValue(TributeAltarBlock.ACTIVE) ? 9 : 0)
            ));
}
