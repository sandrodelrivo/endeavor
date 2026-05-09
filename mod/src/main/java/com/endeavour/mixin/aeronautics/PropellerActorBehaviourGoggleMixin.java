package com.endeavour.mixin.aeronautics;

import com.endeavour.physics.GoggleTooltip;
import com.simibubi.create.foundation.blockEntity.behaviour.BlockEntityBehaviour;
import dev.eriksonn.aeronautics.content.blocks.propeller.behaviour.PropellerActorBehaviour;
import net.minecraft.network.chat.Component;
import org.spongepowered.asm.mixin.Mixin;
import org.spongepowered.asm.mixin.injection.At;
import org.spongepowered.asm.mixin.injection.Inject;
import org.spongepowered.asm.mixin.injection.callback.CallbackInfoReturnable;

import java.util.List;

@Mixin(PropellerActorBehaviour.class)
public abstract class PropellerActorBehaviourGoggleMixin extends BlockEntityBehaviour {

    private PropellerActorBehaviourGoggleMixin() {
        super(null);
        throw new AssertionError();
    }

    @Inject(method = "addToGoggleTooltip", at = @At("RETURN"), cancellable = true)
    private void endeavour$appendFrozenBladesModifier(List<Component> tooltip, boolean isPlayerSneaking,
                                                      CallbackInfoReturnable<Boolean> cir) {
        if (this.blockEntity == null) return;
        if (GoggleTooltip.append(tooltip, this.blockEntity.getLevel(), this.blockEntity.getBlockPos(),
                "Frozen Blades Modifier")) {
            cir.setReturnValue(true);
        }
    }
}
