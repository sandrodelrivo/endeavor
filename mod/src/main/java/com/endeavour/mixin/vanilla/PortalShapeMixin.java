package com.endeavour.mixin.vanilla;

import net.minecraft.core.BlockPos;
import net.minecraft.core.Direction;
import net.minecraft.world.level.LevelAccessor;
import net.minecraft.world.level.portal.PortalShape;
import org.spongepowered.asm.mixin.Mixin;
import org.spongepowered.asm.mixin.injection.At;
import org.spongepowered.asm.mixin.injection.Inject;
import org.spongepowered.asm.mixin.injection.callback.CallbackInfoReturnable;

import java.util.Optional;

// Players cannot create their own nether portals. The only way into the nether
// is through a prebuilt portal placed by worldgen near spawn (see the worldgen
// datapack's placed_features). Returning Optional.empty() here makes
// BaseFireBlock.onPlace skip portal creation for any fire source - flint and
// steel, fire charge, lightning (including lightning rod farms), or anything
// else that drops a fire block into an obsidian frame.
//
// Ruined portals from vanilla generate unlit and stay that way under this
// rule; the forced-spawn portals are the intended T3 entry path.
@Mixin(PortalShape.class)
public abstract class PortalShapeMixin {

    @Inject(
            method = "findEmptyPortalShape(Lnet/minecraft/world/level/LevelAccessor;Lnet/minecraft/core/BlockPos;Lnet/minecraft/core/Direction$Axis;)Ljava/util/Optional;",
            at = @At("HEAD"),
            cancellable = true
    )
    private static void endeavour$blockPlayerPortalCreation(
            LevelAccessor level,
            BlockPos pos,
            Direction.Axis axis,
            CallbackInfoReturnable<Optional<PortalShape>> cir
    ) {
        cir.setReturnValue(Optional.empty());
    }
}
