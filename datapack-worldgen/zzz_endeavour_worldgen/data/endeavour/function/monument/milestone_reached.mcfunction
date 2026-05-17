# Fires when $monument_progress reaches the current tier's threshold.
# Dispatches the reward function by name, then advances to the next tier.

function endeavour:monument/run_reward with storage endeavour:monument tmp.current
scoreboard players add $monument_objective_idx endeavour_flags 1
scoreboard players set $monument_progress endeavour_flags 0