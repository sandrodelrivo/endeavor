package com.endeavour.mixin.vanilla;

import net.minecraft.world.InteractionResult;
import net.minecraft.world.item.EnderEyeItem;
import net.minecraft.world.item.context.UseOnContext;
import net.minecraft.world.level.block.Blocks;
import org.spongepowered.asm.mixin.Mixin;
import org.spongepowered.asm.mixin.injection.At;
import org.spongepowered.asm.mixin.injection.Inject;
import org.spongepowered.asm.mixin.injection.callback.CallbackInfoReturnable;

// Players cannot activate the end portal. Mirrors the nether portal lockout in
// PortalShapeMixin: right-clicking an end portal frame with an eye of ender is
// short-circuited to FAIL, so the frame's eye state never flips and the portal
// can never complete.
//
// We only cancel when the targeted block is an end portal frame. Returning FAIL
// unconditionally would break the eye-throw stronghold-finder behavior, since
// useOn returning PASS is what lets Item#use fire on non-frame blocks.
@Mixin(EnderEyeItem.class)
public abstract class EnderEyeItemMixin {

    @Inject(
            method = "useOn(Lnet/minecraft/world/item/context/UseOnContext;)Lnet/minecraft/world/InteractionResult;",
            at = @At("HEAD"),
            cancellable = true
    )
    private void endeavour$blockPlayerEyePlacement(
            UseOnContext context,
            CallbackInfoReturnable<InteractionResult> cir
    ) {
        if (context.getLevel().getBlockState(context.getClickedPos()).is(Blocks.END_PORTAL_FRAME)) {
            cir.setReturnValue(InteractionResult.FAIL);
        }
    }
}
