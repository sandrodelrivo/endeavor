package com.endeavour.config;

import net.neoforged.neoforge.common.ModConfigSpec;

public final class EndeavourConfig {
    private static final ModConfigSpec.Builder BUILDER = new ModConfigSpec.Builder();

    public static final ModConfigSpec.DoubleValue NORTHERN_SINK_SAFE_Z;
    public static final ModConfigSpec.DoubleValue NORTHERN_SINK_FULL_EFFECT_DISTANCE;
    public static final ModConfigSpec.BooleanValue NORTHERN_SINK_DEBUG_LOG;

    public static final ModConfigSpec SPEC;

    static {
        BUILDER.push("northernSink");

        NORTHERN_SINK_SAFE_Z = BUILDER
                .comment(
                        "Z coordinate at which lift and thrust falloff begins.",
                        "Falloff applies for any airship with z below this value (further north).",
                        "Default: -100"
                )
                .defineInRange("safeZ", -100.0, -1.0E9, 1.0E9);

        NORTHERN_SINK_FULL_EFFECT_DISTANCE = BUILDER
                .comment(
                        "Distance in blocks past safeZ over which lift and thrust drop linearly to zero.",
                        "At z = safeZ - fullEffectDistance, multiplier is 0 (airship cannot fly).",
                        "Default: 1000"
                )
                .defineInRange("fullEffectDistance", 1000.0, 1.0, 1.0E9);

        NORTHERN_SINK_DEBUG_LOG = BUILDER
                .comment(
                        "If true, log balloon positions and lift/thrust scaling once per second when in the falloff zone.",
                        "Default: false"
                )
                .define("debugLog", false);

        BUILDER.pop();

        SPEC = BUILDER.build();
    }

    private EndeavourConfig() {}
}
