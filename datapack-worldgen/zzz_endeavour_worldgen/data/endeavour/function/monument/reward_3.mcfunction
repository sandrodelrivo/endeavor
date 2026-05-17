tellraw @a [{"text":"[ Monument ] ","color":"gold","bold":true},{"text":"The end portal will be lit for the next hour.","color":"white"}]

function endeavour:portals/light_end_portal

schedule function endeavour:portals/destroy_end_portal 3600s replace