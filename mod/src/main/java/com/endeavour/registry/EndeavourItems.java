package com.endeavour.registry;

import net.minecraft.world.item.BlockItem;
import net.neoforged.neoforge.registries.DeferredItem;
import net.neoforged.neoforge.registries.DeferredRegister;

import static com.endeavour.Endeavour.MODID;

public class EndeavourItems {

    public static final DeferredRegister.Items ITEMS = DeferredRegister.createItems(MODID);

    public static final DeferredItem<BlockItem> TRIBUTE_ALTAR =
            ITEMS.registerSimpleBlockItem(EndeavourBlocks.TRIBUTE_ALTAR);
}
