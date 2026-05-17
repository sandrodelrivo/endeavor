# Macro: copies objectives[idx] into tmp.current, then hands off to process_objective.
# Called via: function endeavour:monument/load_objective with storage endeavour:monument tmp
$data modify storage endeavour:monument tmp.current set from storage endeavour:monument objectives[$(idx)]
function endeavour:monument/process_objective
