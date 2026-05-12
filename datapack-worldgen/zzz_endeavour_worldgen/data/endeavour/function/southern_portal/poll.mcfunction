# Poll until the forceloaded chunks at (0, 30000) reach ticking level,
# then run the place. /place fails silently when chunks aren't ticking,
# and a fresh forceload doesn't finish loading instantly on a heavily-
# modded cold start.
#
# Sample five points across the structure footprint. If any sample is
# unloaded, reschedule self in 2s. Cap at 300 polls (10 minutes).

execute if score $southern_portal_generated endeavour_flags matches 1.. run return 0

scoreboard players add $southern_portal_polls endeavour_flags 1

scoreboard players set $southern_portal_chunks_ready endeavour_flags 1
execute unless loaded 0 60 30000 run scoreboard players set $southern_portal_chunks_ready endeavour_flags 0
execute unless loaded 16 60 30000 run scoreboard players set $southern_portal_chunks_ready endeavour_flags 0
execute unless loaded -16 60 30000 run scoreboard players set $southern_portal_chunks_ready endeavour_flags 0
execute unless loaded 0 60 29984 run scoreboard players set $southern_portal_chunks_ready endeavour_flags 0
execute unless loaded 0 60 30015 run scoreboard players set $southern_portal_chunks_ready endeavour_flags 0

# Chunks ready: place and stop polling.
execute if score $southern_portal_chunks_ready endeavour_flags matches 1 run function endeavour:southern_portal/place
execute if score $southern_portal_chunks_ready endeavour_flags matches 1 run return 0

# Not ready, attempt cap reached: give up and release forceload.
execute if score $southern_portal_polls endeavour_flags matches 300.. run tellraw @a [{"text":"[Endeavour] gave up waiting for chunks at (0, 30000) after ","color":"red"},{"score":{"name":"$southern_portal_polls","objective":"endeavour_flags"}},{"text":" polls; manual /place required"}]
execute if score $southern_portal_polls endeavour_flags matches 300.. run scoreboard players set $southern_portal_generated endeavour_flags 1
execute if score $southern_portal_polls endeavour_flags matches 300.. run schedule function endeavour:southern_portal/cleanup 30s replace
execute if score $southern_portal_polls endeavour_flags matches 300.. run return 0

# Not ready, keep polling.
schedule function endeavour:southern_portal/poll 40t replace
