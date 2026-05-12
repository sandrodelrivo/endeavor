# Poll until the spawn chunks covering the monument footprint reach
# ticking level, then run the place. `positioned over world_surface`
# needs loaded chunks to resolve the heightmap.
#
# Footprint: 70x67 from (-35, -33) to (34, 33). Sample the center and
# four corners. Cap at 300 polls (10 minutes).

execute if score $monument_generated endeavour_flags matches 1.. run return 0

scoreboard players add $monument_polls endeavour_flags 1

scoreboard players set $monument_chunks_ready endeavour_flags 1
execute unless loaded 0 60 0 run scoreboard players set $monument_chunks_ready endeavour_flags 0
execute unless loaded -35 60 -33 run scoreboard players set $monument_chunks_ready endeavour_flags 0
execute unless loaded 34 60 -33 run scoreboard players set $monument_chunks_ready endeavour_flags 0
execute unless loaded -35 60 33 run scoreboard players set $monument_chunks_ready endeavour_flags 0
execute unless loaded 34 60 33 run scoreboard players set $monument_chunks_ready endeavour_flags 0

# Chunks ready: place and stop polling.
execute if score $monument_chunks_ready endeavour_flags matches 1 run function endeavour:monument/place
execute if score $monument_chunks_ready endeavour_flags matches 1 run return 0

# Not ready, attempt cap reached: give up. No forceload of our own to
# release, so just mark generated and warn.
execute if score $monument_polls endeavour_flags matches 300.. run tellraw @a [{"text":"[Endeavour] gave up waiting for spawn chunks before placing monument after ","color":"red"},{"score":{"name":"$monument_polls","objective":"endeavour_flags"}},{"text":" polls; manual /place required"}]
execute if score $monument_polls endeavour_flags matches 300.. run scoreboard players set $monument_generated endeavour_flags 1
execute if score $monument_polls endeavour_flags matches 300.. run return 0

# Not ready, keep polling.
schedule function endeavour:monument/poll 40t replace
