# Releases the 4x4 chunk grid forceloaded by southern_portal/check,
# then re-adds the 2x2 chunks meeting at (0, 30000) so the nether
# portal block state can be edited from anywhere via commands
# regardless of player position.

forceload remove -32 29968 31 30031
forceload add -16 29984 15 30015
