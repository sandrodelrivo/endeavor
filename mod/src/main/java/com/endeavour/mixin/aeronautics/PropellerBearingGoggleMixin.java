package com.endeavour.mixin.aeronautics;

import com.endeavour.physics.GoggleTooltip;
import dev.eriksonn.aeronautics.content.blocks.propeller.bearing.propeller_bearing.PropellerBearingBlockEntity;
import net.minecraft.network.chat.Component;
import net.minecraft.world.level.block.entity.BlockEntity;
import org.spongepowered.asm.mixin.Mixin;
import org.spongepowered.asm.mixin.injection.At;
import org.spongepowered.asm.mixin.injection.Inject;
import org.spongepowered.asm.mixin.injection.callback.CallbackInfoReturnable;

import java.util.List;

@Mixin(PropellerBearingBlockEntity.class)
public abstract class PropellerBearingGoggleMixin {

    @Inject(method = "addToGoggleTooltip", at = @At("RETURN"), cancellable = true)
    private void endeavour$appendFrozenBladesModifier(List<Component> tooltip, boolean isPlayerSneaking,
                                                      CallbackInfoReturnable<Boolean> cir) {
        BlockEntity self = (BlockEntity) (Object) this;
        if (GoggleTooltip.append(tooltip, self.getLevel(), self.getBlockPos(), "Frozen Blades Modifier")) {
            cir.setReturnValue(true);
        }
    }
}
