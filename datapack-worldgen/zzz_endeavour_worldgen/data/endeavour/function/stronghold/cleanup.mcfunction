# Releases the 11x11 chunk grid forceloaded by stronghold/check,
# then re-adds the 2x2 chunks meeting at (0, -30000) so the end portal
# block state can be edited from anywhere via commands regardless of
# player position.

forceload remove -80 -30080 95 -29905
forceload add -16 -30016 15 -29985
