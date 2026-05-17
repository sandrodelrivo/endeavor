package com.endeavour.blockentity;

import com.endeavour.block.TributeAltarBlock;
import com.endeavour.registry.EndeavourBlockEntities;
import net.minecraft.core.BlockPos;
import net.minecraft.core.HolderLookup;
import net.minecraft.core.NonNullList;
import net.minecraft.nbt.CompoundTag;
import net.minecraft.server.level.ServerLevel;
import net.minecraft.world.ContainerHelper;
import net.minecraft.world.entity.player.Player;
import net.minecraft.world.item.Item;
import net.minecraft.world.item.ItemStack;
import net.minecraft.world.item.Items;
import net.minecraft.world.level.Level;
import net.minecraft.world.level.block.entity.BlockEntity;
import net.minecraft.world.level.block.state.BlockState;
import net.minecraft.world.scores.Objective;
import net.minecraft.world.scores.ScoreHolder;
import net.minecraft.world.scores.Scoreboard;
import net.minecraft.world.Container;

import java.util.Map;

public class TributeAltarBlockEntity extends BlockEntity implements Container {

    private static final int SIZE = 27;
    private static final String SCOREBOARD_OBJ = "endeavour_flags";
    private static final String SCORE_HOLDER   = "$monument_progress";

    // Items accepted by the altar and their point values per item.
    public static final Map<Item, Integer> POINT_VALUES = Map.of(
        Items.COAL,       1,
        Items.IRON_INGOT, 2,
        Items.GOLD_INGOT, 3,
        Items.DIAMOND,    4
    );

    private NonNullList<ItemStack> items = NonNullList.withSize(SIZE, ItemStack.EMPTY);

    public TributeAltarBlockEntity(BlockPos pos, BlockState state) {
        super(EndeavourBlockEntities.TRIBUTE_ALTAR.get(), pos, state);
    }

    private static final int ZONE_MIN = -35;
    private static final int ZONE_MAX =  35;

    private static boolean inMonumentZone(BlockPos pos) {
        return pos.getX() >= ZONE_MIN && pos.getX() <= ZONE_MAX
            && pos.getZ() >= ZONE_MIN && pos.getZ() <= ZONE_MAX;
    }

    // Called every game tick; throttled to once per 10t (0.5 s).
    public static void serverTick(Level level, BlockPos pos, BlockState state, TributeAltarBlockEntity be) {
        if (level.getGameTime() % 10 != 0) return;

        boolean inZone = inMonumentZone(pos);
        boolean wasActive = state.getValue(TributeAltarBlock.ACTIVE);

        // Sync blockstate when zone membership changes.
        if (wasActive != inZone) {
            level.setBlock(pos, state.setValue(TributeAltarBlock.ACTIVE, inZone), 3);
            return;
        }

        if (!inZone) return;

        int total = 0;
        for (int i = 0; i < SIZE; i++) {
            ItemStack stack = be.items.get(i);
            if (!stack.isEmpty()) {
                total += POINT_VALUES.getOrDefault(stack.getItem(), 0) * stack.getCount();
                be.items.set(i, ItemStack.EMPTY);
            }
        }
        if (total == 0) return;

        be.setChanged();

        Scoreboard board = ((ServerLevel) level).getScoreboard();
        Objective obj = board.getObjective(SCOREBOARD_OBJ);
        if (obj == null) return;

        var access = board.getOrCreatePlayerScore(ScoreHolder.forNameOnly(SCORE_HOLDER), obj);
        access.set(access.get() + total);
    }

    // --- Container ----------------------------------------------------------

    @Override public boolean canPlaceItem(int slot, ItemStack stack)  { return POINT_VALUES.containsKey(stack.getItem()); }
    @Override public int  getContainerSize()                          { return SIZE; }
    @Override public boolean isEmpty()                                { return items.stream().allMatch(ItemStack::isEmpty); }
    @Override public ItemStack getItem(int slot)                      { return items.get(slot); }
    @Override public ItemStack removeItem(int slot, int amount)       { return ContainerHelper.removeItem(items, slot, amount); }
    @Override public ItemStack removeItemNoUpdate(int slot)           { return ContainerHelper.takeItem(items, slot); }
    @Override public void setItem(int slot, ItemStack stack)          { items.set(slot, stack); setChanged(); }
    @Override public boolean stillValid(Player player)                { return true; }
    @Override public void clearContent()                              { items.clear(); setChanged(); }

    // --- NBT ----------------------------------------------------------------

    @Override
    protected void saveAdditional(CompoundTag tag, HolderLookup.Provider registries) {
        super.saveAdditional(tag, registries);
        ContainerHelper.saveAllItems(tag, items, registries);
    }

    @Override
    protected void loadAdditional(CompoundTag tag, HolderLookup.Provider registries) {
        super.loadAdditional(tag, registries);
        items = NonNullList.withSize(SIZE, ItemStack.EMPTY);
        ContainerHelper.loadAllItems(tag, items, registries);
    }
}
