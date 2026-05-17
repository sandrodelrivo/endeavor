/**
 * Three.js 3-D structure viewer - textured rendering using the Minecraft atlas.
 *
 * Exported API:
 *   renderStructure(data)  - data = {size, blocks:[{pos,type}]}
 *   clearViewer()
 *   resetCamera()
 */

import * as THREE from "three";
import { OrbitControls } from "three/addons/controls/OrbitControls.js";

const canvas      = document.getElementById("three-canvas");
const viewerPanel = document.getElementById("viewer-panel");

// ── Renderer / scene / camera / controls ──────────────────
const renderer = new THREE.WebGLRenderer({ canvas, antialias: true });
renderer.setPixelRatio(Math.min(window.devicePixelRatio, 2));
renderer.setClearColor(0x111114);

const scene  = new THREE.Scene();
const camera = new THREE.PerspectiveCamera(55, 1, 0.1, 4000);

const controls = new OrbitControls(camera, canvas);
controls.enableDamping = true;
controls.dampingFactor = 0.08;

// Lighting
scene.add(new THREE.AmbientLight(0xffffff, 0.6));
const sun = new THREE.DirectionalLight(0xffffff, 0.9);
sun.position.set(1, 2, 1.5);
scene.add(sun);

let gridHelper = null;

// ── Resize ─────────────────────────────────────────────────
const ro = new ResizeObserver(resizeRenderer);
ro.observe(viewerPanel);

function resizeRenderer() {
  const w = viewerPanel.clientWidth;
  const h = Math.max(1, viewerPanel.clientHeight - 36);
  renderer.setSize(w, h, false);
  camera.aspect = w / h;
  camera.updateProjectionMatrix();
}
resizeRenderer();

// ── Render loop ────────────────────────────────────────────
(function animate() {
  requestAnimationFrame(animate);
  controls.update();
  renderer.render(scene, camera);
})();

// ── Atlas state ────────────────────────────────────────────
let _atlasTexture   = null;   // THREE.Texture
let _uvmap          = null;   // {texture_id: [u0,v0,u1,v1]}
let _blockTextures  = null;   // {block_name: texture_id}  from model chain resolution

async function ensureAtlas() {
  if (_atlasTexture && _uvmap && _blockTextures) return;

  const [uvmap, blockTextures, tex] = await Promise.all([
    fetch("/api/assets/uvmap.json").then(r => r.json()),
    fetch("/api/assets/block_textures.json").then(r => r.json()),
    new Promise((resolve, reject) => {
      const loader = new THREE.TextureLoader();
      loader.load(
        "/api/assets/atlas.png",
        t => { t.magFilter = THREE.NearestFilter; t.minFilter = THREE.NearestFilter; resolve(t); },
        undefined,
        reject
      );
    }),
  ]);

  _uvmap         = uvmap;
  _blockTextures = blockTextures;
  _atlasTexture  = tex;
}

// ── Block → texture name ───────────────────────────────────
// Resolution order:
//  1. Hard overrides for entity-rendered blocks (chests, campfires, etc.)
//  2. _blockTextures map - resolved from Minecraft block state + model JSONs
//  3. Exact atlas lookup by "block/{name}"
//  4. Hash-based fallback color

// Only blocks that need a texture the model chain won't find (entity renders,
// renamed textures, etc.) belong here.
const BLOCK_TEXTURE_OVERRIDE = {
  "minecraft:chest":           "entity/chest/normal",
  "minecraft:trapped_chest":   "entity/chest/trapped",
  "minecraft:ender_chest":     "entity/chest/ender",
  "minecraft:campfire":        "block/campfire_fire",
  "minecraft:soul_campfire":   "block/soul_campfire_fire",
  "minecraft:water":           "block/water_still",
  "minecraft:lava":            "block/lava_still",
  // Renamed in 1.20.3 - blockstate file no longer exists under the old name
  "minecraft:grass":           "block/short_grass",
};

// Fallback color for mod blocks with no atlas entry
function fallbackColor(blockType) {
  let h = 0;
  for (let i = 0; i < blockType.length; i++)
    h = (Math.imul(h, 31) + blockType.charCodeAt(i)) | 0;
  h = (h >>> 0) & 0xffffff;
  const r = ((h >> 16) & 0xff) * 0.45 + 80;
  const g = ((h >>  8) & 0xff) * 0.45 + 80;
  const b = (  h        & 0xff) * 0.45 + 80;
  return (Math.round(r) << 16) | (Math.round(g) << 8) | Math.round(b);
}

function blockToTextureName(blockType) {
  // 1. Hard overrides
  if (BLOCK_TEXTURE_OVERRIDE[blockType]) return BLOCK_TEXTURE_OVERRIDE[blockType];

  const name = blockType.includes(":") ? blockType.split(":")[1] : blockType;

  // 2. Model-chain resolved map (covers stairs, slabs, carpets, renamed textures, etc.)
  if (_blockTextures && _blockTextures[name]) return _blockTextures[name];

  // 3. Direct atlas name (mod blocks that happen to follow the convention)
  return `block/${name}`;
}

// ── Geometry helpers ────────────────────────────────────────
// BoxGeometry has 24 UV pairs (4 per face × 6 faces).
// Remap each pair from [0,1] → [u0,v0 – u1,v1] in the atlas.
function makeAtlasBoxGeo(u0, v0, u1, v1) {
  const geo = new THREE.BoxGeometry(1, 1, 1);
  const uv  = geo.attributes.uv;
  for (let i = 0; i < uv.count; i++) {
    uv.setXY(i,
      u0 + uv.getX(i) * (u1 - u0),
      // Three.js Y is bottom-up; mcmeta atlas Y is top-down → flip
      1 - (v0 + (1 - uv.getY(i)) * (v1 - v0)),
    );
  }
  uv.needsUpdate = true;
  return geo;
}

function makeColorBoxGeo() {
  return new THREE.BoxGeometry(1, 1, 1);
}

// ── Mesh management ────────────────────────────────────────
const _meshes = [];

function clearScene() {
  for (const m of _meshes) {
    scene.remove(m);
    m.geometry.dispose();
    m.material.dispose();
  }
  _meshes.length = 0;
  if (gridHelper) { scene.remove(gridHelper); gridHelper = null; }
}

// ── Public API ──────────────────────────────────────────────
export function clearViewer() { clearScene(); }
export function resetCamera() { controls.reset(); }

export async function renderStructure(data) {
  clearScene();
  const { size, blocks } = data;
  if (!blocks || blocks.length === 0) return;

  // Load atlas if needed (no-op on subsequent calls)
  await ensureAtlas();

  document.getElementById("viewer-info").textContent =
    `${blocks.length.toLocaleString()} blocks - loading textures…`;

  // Group blocks by type
  const byType = new Map();
  for (const b of blocks) {
    if (!byType.has(b.type)) byType.set(b.type, []);
    byType.get(b.type).push(b.pos);
  }

  // Atlas coverage logging
  {
    const hits = [], misses = [];
    for (const type of byType.keys()) {
      const tex = blockToTextureName(type);
      (_uvmap[tex] ? hits : misses).push(`${type} → ${tex}`);
    }
    console.log(`[atlas] ${hits.length} textured, ${misses.length} fallback (${blocks.length} blocks total)`);
    if (misses.length) console.log("[atlas] missing:\n" + misses.join("\n"));
  }

  const cx = size[0] / 2, cy = size[1] / 2, cz = size[2] / 2;
  const dummy = new THREE.Object3D();

  const atlasMat = new THREE.MeshLambertMaterial({
    map: _atlasTexture,
    transparent: false,
  });

  for (const [type, positions] of byType) {
    const texName = blockToTextureName(type);
    const uvRect  = _uvmap[texName];

    let geo, mat;

    if (uvRect) {
      const [u0, v0, u1, v1] = uvRect;
      geo = makeAtlasBoxGeo(u0, v0, u1, v1);
      mat = atlasMat;
    } else {
      // Mod block or unmapped vanilla block - solid color fallback
      geo = makeColorBoxGeo();
      mat = new THREE.MeshLambertMaterial({ color: fallbackColor(type) });
    }

    const mesh = new THREE.InstancedMesh(geo, mat, positions.length);
    mesh.name  = type;

    for (let i = 0; i < positions.length; i++) {
      const [x, y, z] = positions[i];
      dummy.position.set(x - cx, y - cy, z - cz);
      dummy.updateMatrix();
      mesh.setMatrixAt(i, dummy.matrix);
    }
    mesh.instanceMatrix.needsUpdate = true;
    scene.add(mesh);
    _meshes.push(mesh);
  }

  // Grid
  const gSize = Math.max(size[0], size[2]) + 4;
  gridHelper  = new THREE.GridHelper(gSize, gSize, 0x333340, 0x282830);
  gridHelper.position.y = -cy - 0.51;
  scene.add(gridHelper);

  // Position camera
  const diag = Math.sqrt(size[0] ** 2 + size[2] ** 2);
  const dist = Math.max(diag, size[1]) * 1.5 + 10;
  camera.position.set(dist * 0.7, dist * 0.5, dist * 0.7);
  controls.target.set(0, 0, 0);
  controls.saveState();
  controls.update();

  document.getElementById("viewer-info").textContent =
    `${blocks.length.toLocaleString()} blocks`;
}

// Reset camera button
document.getElementById("btn-reset-cam").addEventListener("click", () => controls.reset());
