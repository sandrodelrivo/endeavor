# Fires 20t after load. Bail if the spawn stronghold is already placed;
# otherwise forceload the 20x20 chunk grid around (0, -30000) and schedule
# the actual /place 30s later (gives the chunkloader time to settle).

execute if score $stronghold_generated endeavour_flags matches 1.. run return 0

forceload add -160 -30160 159 -29841
schedule function endeavour:stronghold/place 30s replace
