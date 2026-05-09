# Poll until the forceloaded chunks at (0, -30000) reach ticking level,
# then run the place. /place fails silently when chunks aren't ticking,
# and a fresh forceload of 400 chunks doesn't finish loading in 30s on
# a heavily-modded cold start.
#
# Sample five points across the structure footprint (a stronghold can
# extend ~64 blocks from origin in any direction). If any sample is
# unloaded, reschedule self in 2s. Cap at 300 polls (10 minutes).

execute if score $stronghold_generated endeavour_flags matches 1.. run return 0

scoreboard players add $stronghold_polls endeavour_flags 1

scoreboard players set $stronghold_chunks_ready endeavour_flags 1
execute unless loaded 0 60 -30000 run scoreboard players set $stronghold_chunks_ready endeavour_flags 0
execute unless loaded 64 60 -30000 run scoreboard players set $stronghold_chunks_ready endeavour_flags 0
execute unless loaded -64 60 -30000 run scoreboard players set $stronghold_chunks_ready endeavour_flags 0
execute unless loaded 0 60 -29936 run scoreboard players set $stronghold_chunks_ready endeavour_flags 0
execute unless loaded 0 60 -30064 run scoreboard players set $stronghold_chunks_ready endeavour_flags 0

# Chunks ready: place and stop polling.
execute if score $stronghold_chunks_ready endeavour_flags matches 1 run function endeavour:stronghold/place
execute if score $stronghold_chunks_ready endeavour_flags matches 1 run return 0

# Not ready, attempt cap reached: give up and release forceload.
execute if score $stronghold_polls endeavour_flags matches 300.. run tellraw @a [{"text":"[Endeavour] gave up waiting for chunks at (0, -30000) after ","color":"red"},{"score":{"name":"$stronghold_polls","objective":"endeavour_flags"}},{"text":" polls; manual /place required"}]
execute if score $stronghold_polls endeavour_flags matches 300.. run scoreboard players set $stronghold_generated endeavour_flags 1
execute if score $stronghold_polls endeavour_flags matches 300.. run schedule function endeavour:stronghold/cleanup 30s replace
execute if score $stronghold_polls endeavour_flags matches 300.. run return 0

# Not ready, keep polling.
schedule function endeavour:stronghold/poll 40t replace
