# Place the monument. Uses `positioned over world_surface` to find the
# surface y at (-35, -33), then offsets y by -12 to bury the bottom
# 12 blocks of the structure underground.

execute positioned -35 0 -33 positioned over world_surface positioned ~ ~-22 ~ run place template endeavour:monument
scoreboard players set $monument_generated endeavour_flags 1
tellraw @a [{"text":"[Endeavour] monument placed at world-surface near (-35, ?, -33) after ","color":"gray"},{"score":{"name":"$monument_polls","objective":"endeavour_flags"}},{"text":" chunk-readiness poll(s)"}]
