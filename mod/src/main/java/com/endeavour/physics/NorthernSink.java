package com.endeavour.physics;

import com.endeavour.config.EndeavourConfig;

public final class NorthernSink {
    private NorthernSink() {}

    public static double multiplier(double worldZ) {
        double safeZ = EndeavourConfig.NORTHERN_SINK_SAFE_Z.get();
        double full = EndeavourConfig.NORTHERN_SINK_FULL_EFFECT_DISTANCE.get();
        double distNorth = safeZ - worldZ;
        if (distNorth <= 0.0) return 1.0;
        double t = Math.min(distNorth / full, 1.0);
        return 1.0 - t;
    }

    public static boolean debugLog() {
        return EndeavourConfig.NORTHERN_SINK_DEBUG_LOG.get();
    }
}
