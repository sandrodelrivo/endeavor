# Monument bossbar init + objective data. Runs on every load/reload via load_worldgen.
# Errors on subsequent reloads ("already exists") are harmless.
#
# OBJECTIVES - edit this list to add or change tiers.
# Each entry: {threshold: <points>, reward: "<reward function name>"}
# The reward name resolves to endeavour:monument/<name>.

data modify storage endeavour:monument objectives set value [{threshold: 500, reward: "reward_0"}, {threshold: 1000, reward: "reward_1"}, {threshold: 10000, reward: "reward_2"}, {threshold: 100000, reward: "reward_3"}]

# Init idx to 0 if not yet set; add 0 is a no-op on existing scores.
scoreboard players add $monument_objective_idx endeavour_flags 0

bossbar add endeavour:monument {"text":"Monument Progress","color":"gold"}
bossbar set endeavour:monument visible true

schedule function endeavour:monument/tick 10t replace
