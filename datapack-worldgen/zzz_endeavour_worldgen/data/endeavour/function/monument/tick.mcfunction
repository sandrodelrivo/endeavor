# Monument bossbar tick - runs every 10t (0.5 s), self-rescheduling.
# Item counting and scoreboard writes are handled by TributeAltarBlockEntity.

# Sync bossbar value from the Java-written progress score.
execute store result bossbar endeavour:monument value run scoreboard players get $monument_progress endeavour_flags

# Load current objective into tmp.current, then update bossbar max + check milestone.
execute store result storage endeavour:monument tmp.idx int 1 run scoreboard players get $monument_objective_idx endeavour_flags
function endeavour:monument/load_objective with storage endeavour:monument tmp

# Show bossbar only to players inside the monument region.
# dx/dz=71 covers [-35, 36) which includes x/z = 35 on both axes.
bossbar set endeavour:monument players @a[x=-35,y=0,z=-35,dx=71,dy=256,dz=71]

schedule function endeavour:monument/tick 10t replace
