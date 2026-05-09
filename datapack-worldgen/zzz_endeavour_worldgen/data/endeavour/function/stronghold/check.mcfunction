# Fires 20t after load. Bail if the spawn stronghold is already placed;
# otherwise forceload an 11x11 chunk grid around (0, -30000) and start
# polling for chunk readiness. /forceload add caps at 256 chunks per
# call, so 11x11 (121 chunks) fits with room to spare. The grid is
# larger than a stronghold's actual footprint so the structure has
# room to extend without crossing into unloaded chunks.

execute if score $stronghold_generated endeavour_flags matches 1.. run return 0

forceload add -80 -30080 95 -29905
schedule function endeavour:stronghold/poll 40t replace
