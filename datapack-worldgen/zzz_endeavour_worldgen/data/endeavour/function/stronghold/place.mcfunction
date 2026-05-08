# Place the spawn stronghold and flip the flag. Forceload stays on for
# another 30s so the structure pieces have time to fully resolve before
# the chunks are released.

place structure minecraft:stronghold 0 60 -30000
scoreboard players set $stronghold_generated endeavour_flags 1
schedule function endeavour:stronghold/cleanup 30s replace
