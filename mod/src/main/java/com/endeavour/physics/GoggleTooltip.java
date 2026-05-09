package com.endeavour.physics;

import dev.ryanhcode.sable.Sable;
import dev.ryanhcode.sable.sublevel.SubLevel;
import net.minecraft.ChatFormatting;
import net.minecraft.core.BlockPos;
import net.minecraft.network.chat.Component;
import net.minecraft.world.level.Level;
import org.joml.Vector3d;

import java.util.List;

public final class GoggleTooltip {
    private GoggleTooltip() {}

    public static boolean append(List<Component> tooltip, Level level, BlockPos pos, String label) {
        if (level == null || pos == null) return false;
        SubLevel sub = Sable.HELPER.getContaining(level, pos);
        Vector3d worldPos = sub != null ? sub.logicalPose().position() : new Vector3d(pos.getX(), pos.getY(), pos.getZ());
        double mul = NorthernSink.multiplier(worldPos.z);
        double reductionPercent = (1.0 - mul) * 100.0;

        ChatFormatting valueColor;
        String stateLabel;
        if (reductionPercent < 1.0) {
            valueColor = ChatFormatting.GREEN;
            stateLabel = "stable";
        } else if (reductionPercent < 30.0) {
            valueColor = ChatFormatting.YELLOW;
            stateLabel = String.format("-%.0f%%", reductionPercent);
        } else if (reductionPercent < 75.0) {
            valueColor = ChatFormatting.GOLD;
            stateLabel = String.format("-%.0f%%", reductionPercent);
        } else if (reductionPercent < 100.0) {
            valueColor = ChatFormatting.RED;
            stateLabel = String.format("-%.0f%%", reductionPercent);
        } else {
            valueColor = ChatFormatting.DARK_RED;
            stateLabel = "frozen";
        }

        tooltip.add(Component.literal(""));
        tooltip.add(Component.literal(" ")
                .append(Component.literal(label + ": ").withStyle(ChatFormatting.GRAY))
                .append(Component.literal(stateLabel).withStyle(valueColor)));
        return true;
    }
}
