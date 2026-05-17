# Updates bossbar max and checks whether the current milestone has been reached.
# Bails early if all objectives are complete (idx >= objectives array length).

execute store result score $tmp_count endeavour_flags run data get storage endeavour:monument objectives
execute if score $monument_objective_idx endeavour_flags >= $tmp_count endeavour_flags run return 0

execute store result score $tmp_threshold endeavour_flags run data get storage endeavour:monument tmp.current.threshold
function endeavour:monument/set_bossbar_max with storage endeavour:monument tmp.current

execute if score $monument_progress endeavour_flags >= $tmp_threshold endeavour_flags run function endeavour:monument/milestone_reached
