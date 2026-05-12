# Fires 20t after load. Bail if the monument is already placed.
# The monument footprint (x in [-35, 34], z in [-33, 33]) sits inside
# the worldspawn spawn-chunk forceload, so we don't add any forceload
# of our own — just wait for those chunks to reach ticking level, which
# is required for `positioned over world_surface` to resolve.

execute if score $monument_generated endeavour_flags matches 1.. run return 0

schedule function endeavour:monument/poll 40t replace
