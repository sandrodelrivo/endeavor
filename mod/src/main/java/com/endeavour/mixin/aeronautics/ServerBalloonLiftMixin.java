package com.endeavour.mixin.aeronautics;

import com.endeavour.physics.NorthernSink;
import com.llamalad7.mixinextras.injector.ModifyExpressionValue;
import dev.eriksonn.aeronautics.content.blocks.hot_air.balloon.Balloon;
import dev.eriksonn.aeronautics.content.blocks.hot_air.balloon.ServerBalloon;
import dev.ryanhcode.sable.Sable;
import dev.ryanhcode.sable.sublevel.SubLevel;
import org.joml.Vector3d;
import org.objectweb.asm.Opcodes;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.spongepowered.asm.mixin.Mixin;
import org.spongepowered.asm.mixin.Unique;
import org.spongepowered.asm.mixin.injection.At;

import java.util.concurrent.atomic.AtomicBoolean;
import java.util.concurrent.atomic.AtomicLong;

@Mixin(ServerBalloon.class)
public abstract class ServerBalloonLiftMixin extends Balloon {

    @Unique private static final Logger endeavour$LOGGER = LoggerFactory.getLogger("endeavour/aero-sink");
    @Unique private static final AtomicBoolean endeavour$WIRED_LOG = new AtomicBoolean(false);
    @Unique private static final AtomicLong endeavour$LAST_DEBUG_LOG = new AtomicLong(0L);

    private ServerBalloonLiftMixin() {
        super(null, null, null, null, null);
        throw new AssertionError();
    }

    @ModifyExpressionValue(
            method = "applyForces(D)V",
            at = @At(
                    value = "FIELD",
                    target = "Ldev/eriksonn/aeronautics/content/blocks/hot_air/balloon/ServerBalloon;totalLift:D",
                    opcode = Opcodes.GETFIELD
            )
    )
    private double endeavour$scaleLift(double original) {
        if (this.level == null || this.controllerPos == null) return original;
        SubLevel sub = Sable.HELPER.getContaining(this.level, this.controllerPos);
        if (sub == null) return original;
        Vector3d worldPos = sub.logicalPose().position();
        double mul = NorthernSink.multiplier(worldPos.z);

        if (endeavour$WIRED_LOG.compareAndSet(false, true)) {
            endeavour$LOGGER.info("ServerBalloon lift mixin wired (first tick at z={})",
                    String.format("%.1f", worldPos.z));
        }

        if (mul < 1.0 && NorthernSink.debugLog()) {
            long now = System.nanoTime();
            long last = endeavour$LAST_DEBUG_LOG.get();
            if (now - last > 1_000_000_000L && endeavour$LAST_DEBUG_LOG.compareAndSet(last, now)) {
                endeavour$LOGGER.info("Lift falloff: balloon@({}, {}) mul={} lift {} -> {}",
                        String.format("%.1f", worldPos.x), String.format("%.1f", worldPos.z),
                        String.format("%.3f", mul),
                        String.format("%.2f", original),
                        String.format("%.2f", original * mul));
            }
        }

        return original * mul;
    }
}
