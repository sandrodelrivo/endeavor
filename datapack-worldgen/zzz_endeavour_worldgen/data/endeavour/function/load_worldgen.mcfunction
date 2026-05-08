# Endeavour worldgen — bootstrap that runs on world load and on /reload.
# Owns the endeavour_flags scoreboard and kicks off the stronghold force-spawn.

scoreboard objectives add endeavour_flags dummy

schedule function endeavour:stronghold/check 20t replace
