# Place the spawn stronghold. Called from poll.mcfunction once the
# forceloaded chunks have reached ticking level. Forceload stays on for
# another 30s so structure pieces have time to fully resolve before
# the chunks are released.

place structure minecraft:stronghold 0 60 -30000
scoreboard players set $stronghold_generated endeavour_flags 1
tellraw @a [{"text":"[Endeavour] spawn stronghold placed at (0, 60, -30000) after ","color":"gray"},{"score":{"name":"$stronghold_polls","objective":"endeavour_flags"}},{"text":" chunk-readiness poll(s)"}]
schedule function endeavour:stronghold/cleanup 30s replace
