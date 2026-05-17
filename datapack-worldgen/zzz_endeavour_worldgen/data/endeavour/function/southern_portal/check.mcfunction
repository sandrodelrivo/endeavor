# Fires 20t after load. Bail if the southern portal is already placed;
# otherwise forceload a 4x4 chunk grid around (0, 30000) and start
# polling for chunk readiness. The structure is 17x16x6 placed at
# (-8, 1, 29997), so it only occupies a 2x2 chunk footprint - 4x4 is
# plenty of safety margin for piece resolution.

execute if score $southern_portal_generated endeavour_flags matches 1.. run return 0

forceload add -32 29968 31 30031
schedule function endeavour:southern_portal/poll 40t replace
