# Endeavour worldgen - bootstrap that runs on world load and on /reload.
# Owns the endeavour_flags scoreboard and kicks off the forced-spawn
# structures (end-portal stronghold, southern nether portal, monument).

scoreboard objectives add endeavour_flags dummy

schedule function endeavour:stronghold/check 20t replace
schedule function endeavour:southern_portal/check 20t replace
schedule function endeavour:monument/check 20t replace
function endeavour:monument/init
