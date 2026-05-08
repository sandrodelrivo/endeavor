// disable_curing_and_beds.js
// Goes in: kubejs/server_scripts/

function notifyPlayer(event, message) {
  const name = event.player.name.string
  const json = JSON.stringify({
    text: message,
    color: 'red'
  })

  console.info(`[KubeJS notify test] Sending message to ${name}: ${message}`)

  // Use runCommand, not runCommandSilent, while testing.
  // If the command fails, this is more likely to show feedback somewhere.
  event.server.runCommand(`tellraw ${name} ${json}`)
}

// ------------------------------------------------------------
// 1. Disable zombie villager curing
// ------------------------------------------------------------
// This cancels right-clicking a zombie villager with a golden apple.
// KubeJS's entityInteracted event fires when a player right-clicks an entity,
// and it is cancellable.

ItemEvents.entityInteracted('minecraft:golden_apple', event => {
  if (event.target.type !== 'minecraft:zombie_villager') return
  notifyPlayer(event, 'Zombie villager curing is disabled.')
  event.cancel()
})


// ------------------------------------------------------------
// 2. Disable beds setting player spawn
// ------------------------------------------------------------
// This cancels right-clicking beds.
// Cancelling the bed interaction prevents the normal bed behavior.

const BEDS = [
  'minecraft:white_bed',
  'minecraft:orange_bed',
  'minecraft:magenta_bed',
  'minecraft:light_blue_bed',
  'minecraft:yellow_bed',
  'minecraft:lime_bed',
  'minecraft:pink_bed',
  'minecraft:gray_bed',
  'minecraft:light_gray_bed',
  'minecraft:cyan_bed',
  'minecraft:purple_bed',
  'minecraft:blue_bed',
  'minecraft:brown_bed',
  'minecraft:green_bed',
  'minecraft:red_bed',
  'minecraft:black_bed',
  'aether:skyroot_bed',
  'minecraft:respawn_anchor'
]

BlockEvents.rightClicked(event => {
  // Prevent double messages from main hand/offhand processing
  if (event.hand === 'OFF_HAND') return

  if (!BEDS.includes(event.block.id)) return
  notifyPlayer(event, 'Beds and respawn anchors are disabled.')
  event.cancel()
})