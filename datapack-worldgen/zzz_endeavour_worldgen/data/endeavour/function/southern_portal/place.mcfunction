# Place the southern portal (unlit variant). Called from poll.mcfunction
# once the forceloaded chunks have reached ticking level. Forceload
# stays on for another 30s so structure pieces have time to fully
# resolve before the chunks are trimmed back to the keep-loaded 2x2.

place template endeavour:southern_portal_unlit -8 1 29997
scoreboard players set $southern_portal_generated endeavour_flags 1
tellraw @a [{"text":"[Endeavour] southern portal placed at (-8, 1, 29997) after ","color":"gray"},{"score":{"name":"$southern_portal_polls","objective":"endeavour_flags"}},{"text":" chunk-readiness poll(s)"}]
schedule function endeavour:southern_portal/cleanup 30s replace
