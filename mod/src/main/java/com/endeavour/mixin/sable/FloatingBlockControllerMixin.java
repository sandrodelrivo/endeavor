package com.endeavour.mixin.sable;

import com.endeavour.physics.NorthernSink;
import com.llamalad7.mixinextras.injector.ModifyExpressionValue;
import dev.ryanhcode.sable.physics.floating_block.FloatingBlockController;
import dev.ryanhcode.sable.sublevel.ServerSubLevel;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.spongepowered.asm.mixin.Final;
import org.spongepowered.asm.mixin.Mixin;
import org.spongepowered.asm.mixin.Shadow;
import org.spongepowered.asm.mixin.Unique;
import org.spongepowered.asm.mixin.injection.At;

import java.util.concurrent.atomic.AtomicBoolean;

@Mixin(FloatingBlockController.class)
public abstract class FloatingBlockControllerMixin {

    @Unique private static final Logger endeavour$LOGGER = LoggerFactory.getLogger("endeavour/aero-sink");
    @Unique private static final AtomicBoolean endeavour$WIRED = new AtomicBoolean(false);

    @Shadow @Final private ServerSubLevel subLevel;

    @ModifyExpressionValue(
            method = "applyLift(Lorg/joml/Vector3d;Lorg/joml/Vector3d;Lorg/joml/Vector3d;D)V",
            at = @At(
                    value = "INVOKE",
                    target = "Ldev/ryanhcode/sable/physics/floating_block/FloatingBlockMaterial;liftStrength()D"
            )
    )
    private double endeavour$scaleLevititeLift(double original) {
        if (this.subLevel == null) return original;
        double worldZ = this.subLevel.logicalPose().position().z;
        double mul = NorthernSink.multiplier(worldZ);
        if (endeavour$WIRED.compareAndSet(false, true)) {
            endeavour$LOGGER.info("Levitite lift mixin wired (first call at z={}, mul={})",
                    String.format("%.1f", worldZ), String.format("%.3f", mul));
        }
        return original * mul;
    }
}
