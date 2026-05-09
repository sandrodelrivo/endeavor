package com.endeavour.mixin.aeronautics;

import com.endeavour.physics.NorthernSink;
import com.llamalad7.mixinextras.injector.ModifyReturnValue;
import dev.eriksonn.aeronautics.content.blocks.propeller.bearing.propeller_bearing.PropellerBearingBlockEntity;
import dev.eriksonn.aeronautics.content.blocks.propeller.small.BasePropellerBlockEntity;
import dev.ryanhcode.sable.Sable;
import dev.ryanhcode.sable.api.block.propeller.BlockEntityPropeller;
import dev.ryanhcode.sable.sublevel.SubLevel;
import net.minecraft.core.BlockPos;
import net.minecraft.world.level.Level;
import org.joml.Vector3d;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.spongepowered.asm.mixin.Mixin;
import org.spongepowered.asm.mixin.Unique;
import org.spongepowered.asm.mixin.injection.At;

import java.util.concurrent.atomic.AtomicBoolean;
import java.util.concurrent.atomic.AtomicLong;

@Mixin({BasePropellerBlockEntity.class, PropellerBearingBlockEntity.class})
public abstract class PropellerThrustMixin implements BlockEntityPropeller {

    @Unique private static final Logger endeavour$LOGGER = LoggerFactory.getLogger("endeavour/aero-sink");
    @Unique private static final AtomicBoolean endeavour$WIRED_LOG = new AtomicBoolean(false);
    @Unique private static final AtomicLong endeavour$LAST_DEBUG_LOG = new AtomicLong(0L);

    @ModifyReturnValue(method = "getThrust()D", at = @At("RETURN"))
    private double endeavour$scaleThrust(double original) {
        Level level = this.getLevel();
        BlockPos pos = this.getBlockPos();
        if (level == null || pos == null) return original;
        SubLevel sub = Sable.HELPER.getContaining(level, pos);
        if (sub == null) return original;
        Vector3d worldPos = sub.logicalPose().position();
        double mul = NorthernSink.multiplier(worldPos.z);

        if (endeavour$WIRED_LOG.compareAndSet(false, true)) {
            endeavour$LOGGER.info("Propeller thrust mixin wired (first call at z={})",
                    String.format("%.1f", worldPos.z));
        }

        if (mul < 1.0 && NorthernSink.debugLog()) {
            long now = System.nanoTime();
            long last = endeavour$LAST_DEBUG_LOG.get();
            if (now - last > 1_000_000_000L && endeavour$LAST_DEBUG_LOG.compareAndSet(last, now)) {
                endeavour$LOGGER.info("Thrust falloff: prop@({}, {}) mul={} thrust {} -> {}",
                        String.format("%.1f", worldPos.x), String.format("%.1f", worldPos.z),
                        String.format("%.3f", mul),
                        String.format("%.2f", original),
                        String.format("%.2f", original * mul));
            }
        }

        return original * mul;
    }
}
