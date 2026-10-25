---
name: model-factory
description: The LootNShoot 3D asset workflow, end to end, for any model built for the game (weapons, attachments, props, consumables, building kits, textures) from reference photos to a verified in-game asset. Covers the stage gates, the exact scripts and settings (Blender headless, FBX, bakes, UE import, sockets, LODs, collision, materials), the automatic quality checks (mesh_qc, matched-camera spot-the-difference, bake-loss proof), progress shots for the user, hands and Grip Workshop hand-off, and the known traps. Use it before starting any model, when resuming one, and before showing the user anything.
---

# Model factory: how a LootNShoot model gets made

The reference implementation is the **Glock 17 Gen 5 v4** (`Tools/bpy/glock17/v4/`). The user called it "absolutely insanely good". It was built from scratch after four rejected attempts, using exactly this workflow. When in doubt, open the matching v4 script and copy its approach.

The same core gates and scripts also live in the user-level `blender-3d` skill (`~/.claude/skills/blender-3d/`), which serves both of the user's projects. This repo copy is the LootNShoot-specific, versioned workflow. When you change a bundled script, update both copies.

---

## 0. Ground rules (non-negotiable)

- **Blender headless only:** `D:/Blender/blender.exe -b <file.blend> --python <script.py> -- <args>` (Blender 4.0).
  - Never drive the user's open Blender (`mcp__blender_*`).
  - Renders and bakes are heavy: wrap them in `bash Tools/jobslots.sh run <cmd>`. At most two heavy jobs run on the machine.
- **System Python for geometry math:** numpy, scipy and skimage for SDF modelling, tracing, PnP and sheets. Blender only builds, bakes, renders and exports.
- **Scripts are the source of truth.** Every step is a rerunnable `.py` in the asset folder. Never hand-edit a `.blend` you can't regenerate. Save numbered work blends.
- **No logos, brand names, serials or engravings.** A blank roll-mark recess is fine.
- **No asset packs and no downloaded models or textures.** Everything is made from scratch.
- **Reference photos are private.** Keep them in `refs_user/`; never commit, publish or bake them into textures. git ignores images under `Tools/`; keep it that way.
- **Never package** (the user packages). Never touch ConeCrushers processes.
- **Unreal access:**
  - editor lock: `bash Tools/editorlock.sh acquire <Name>` / `release <Name>`;
  - Remote Control: `python Saved/rc.py file|stmt`;
  - rebuild and relaunch: `LNS_BUILD_PAR=12 bash Saved/build_ln.sh` with the lock held and PIE stopped;
  - PIE harness: `bash Saved/w3/fix2/GM/o.sh`.
- **Back up before overwriting** any UE asset: `Saved/AssetBackups/<Asset>_<ts>/`. Content has no version control.
- **Test budget** (user rule): one build, one short PIE pass, representative frames. Thoroughness goes into the checks and scripts, not into editor time.
- **Commits:** explicit paths only, because other agents work in parallel.
  - `git -c user.name="Moosie Studios" -c user.email="<your email>" commit`
  - The message ends with `Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>`.

## 1. Folder layout (one folder per asset version)

```
Tools/bpy/<asset>/vN/
  CONTRACT.json        what the game depends on (names, pivot, axes, sockets, slots, texture sizes, budgets)
  <asset>_spec.py      real measurements in the asset frame (mm), feature counts read off the photos
  refs_user/           (private) the user's reference photos; never committed
  work/                numbered blends, npz caches, masks, intermediate renders
  review/              progress_<hhmm>.jpg, diff_<view>_p<N>_sheet.jpg, proof_*.jpg, PROGRESS.md
  export/game|lod|textures/ + <asset>_sockets.json
  ue/                  UE-side scripts: import, sockets, icon, pickup, probes
  STATUS.md            what was built, contract deltas, triangle counts, what's left
```

## 2. The stage gates (don't skip ahead)

| # | Stage | Script(s), from the Glock v4 | Gate to pass |
|---|---|---|---|
| S0 | **Contract** | `measure_contract.py`, `delta.py` | `CONTRACT.json` written. Replacing an asset: measure the old one first and keep only the gameplay anchors (bore, trigger, pivot, sockets, names). |
| S1 | **Reference pack** | `pxgrid.py`, `landmarks.py` | Exact variant locked (model, generation, configuration) and every reference checked against it; real dimensions listed; every repeated feature counted on the photos (serrations, studs, pins, holes) |
| S2 | **Silhouette and blockout** | `trace.py`, `profiles.py`, `sdf.py`, `parts.py`, `bl_high.py` | On the near-orthographic photo: silhouette IoU **≥ 0.95** from a matched camera with RMS **< 1 %** of width |
| S3 | **Detail** (high-poly) | `parts.py` (SDF), `masks.py` | Every counted feature present, at real bevel sizes |
| S4 | **QC gate** | `scripts/mesh_qc.py` | **Zero ERRORs.** Every WARN fixed or justified in STATUS |
| S5 | **Spot the difference** | `scripts/camera_match.py`, `pnp.py`, `silcam.py`, `scripts/ref_compare.py` | A written diff list, emptied, for every reference view, plus crops of the key areas |
| S6 | **Lookdev** | `lookdev.py`, `bl_render.py` | Colour and roughness judged at matched angles against the photos |
| S7 | **Game mesh** | `bl_low.py`, `fix_ucx.py`, `sliver_report.py` | Within budget; mesh_qc clean on each part ALONE; LODs and UCX in place |
| S8 | **Bake** | `bake.py`, `proof.py` | Bake-loss proof sheet: high-poly vs baked game mesh, same cameras, no visible loss |
| S9 | **Export** | `export.py` | Clean re-import of the FBX passes mesh_qc again; sockets JSON written |
| S10 | **UE import** | `ue/ue_import_<asset>.py` | Names, sockets, LODs, collision, materials and textures verified by script (`ue_import.json`) |
| S11 | **In engine** | PIE harness, `ingame_sheet.py` | One short pass: hip, ADS (`lns.ads.check`), third person, world pickup, inventory icon |
| S12 | **Hands** | Grip Workshop | Hand fit checked (`handfit_check.py`); the user polishes and presses **Send to game** |
| S13 | **Ship it** | — | STATUS.md, PROGRESS.md, committed; the lessons log updated |

At the end of EVERY stage, save a **progress sheet** to `review/progress_<hhmm>.jpg`: beauty renders, plus the latest matched diff sheet, plus an exploded view from S3 on. Add one line to `review/PROGRESS.md`. The user asks for progress shots constantly.

## 3. Stage details and settings

### S0 Contract (frame, units, anchors)
- **Units:** model in metres. 1 Blender unit = 1 m = 100 UE units (cm). Specs are written in mm.
- **Gun frame:** `Tools/bpy/ar15/INTEGRATION.md` and `CONTRACT.json`.
  - UE (x, y, z) = Blender (x, −y, z).
  - +Y is the muzzle, +X the gun's LEFT, +Z up.
  - Origin at the top of the grip / trigger area, per the contract.
- **Prop frame** (`Docs/BLENDER_PROP_BRIEF.md`): +X forward, pivot at the bottom centre on Z = 0, all transforms applied.
- **Contracts protect gameplay, not shape.** Keep the pivot, bore and trigger, sockets, assembly names and material slots. Never freeze a surface the user hasn't approved: Codex's stubby grip survived for exactly this reason.

### S1 References
- **Lock the exact variant first** (model, generation, configuration: Glock 17 Gen 5 is not Gen 6) and write it in `CONTRACT.json`. Check every reference against it.
  - The profile master (the near-orthographic view S2 traces) must be that variant.
  - When a reference shows another variant, list its differing features in STATUS and say which source wins for each, before modelling. Ask the user when it isn't obvious.
- The user's photos go first, then the real published dimensions.
- Read pixels with `pxgrid.py`: a zoomed, labelled pixel grid of a photo crop.
- Count every repeated feature on the photo, with pitch and angle. Never model them from memory.

### S2 Silhouette → blockout
- **Tracing:** `trace.py` maps the near-orthographic photo into the asset frame, scaled to the real overall length, and traces the silhouette (similarity map). `profiles.py` rasterises the side profiles.
- **Modelling:** `sdf.py` + `parts.py` build each part as signed-distance functions, then narrow-band marching cubes at about 0.1–0.2 mm. It's watertight by construction and booleans are free. Poly hard-surface modelling is fine too, if it passes the same gates.
- **Camera matching:**
  - `camera_match.py` solves rotation, position and focal length from 6+ landmarks. Mark them as Empties named `LM_<name>`, or give vertex indices.
  - Points marked `"check": true` are reported but not solved on. Solve on the rigid, trusted landmarks; check-point errors then MEASURE shape error.
  - Use `focal_range` to stop a runaway lens.
  - `pnp.py` (a DLT plus robust solve) and `silcam.py` (silhouette IoU refinement) help on hard photos.

### S3 Detail
- **Bevels:** 0.2–0.5 mm on small steel parts, 0.5–1.5 mm on polymer. Use enough segments wherever the silhouette shows.
- **Fine surface texture** (grip studs, stippling) is authored as a height or mask function (`masks.py`) and baked, not modelled as geometry.
- **Parts that come apart in game** (magazine, slide, barrel) are modelled complete on ALL sides: underside, chamber, feed lips, inner faces.

### S4 QC gate: `scripts/mesh_qc.py`
```
D:/Blender/blender.exe -b <blend> --python-exit-code 1 --python .claude/skills/model-factory/scripts/mesh_qc.py -- --json qc.json [--collection Game] [--budget 60000] [--objects A,B]
```
The exit status is the verdict: 0 = PASS, 1 = an ERROR (or a script crash, through `--python-exit-code 1`). Wrapper scripts must keep that status; a pipe through grep hides it. `qc_all.sh` in the Glock example shows how.
**ERRORs:**
- zero-area faces and zero-length edges;
- loose vertices or edges;
- edges shared by 3+ faces;
- open boundaries (not airtight);
- flipped or inside-out faces, negative scale;
- missing UVs, UV0 outside 0–1, UV overlap over 0.5 % per material, zero-area UV faces;
- coplanar same-facing faces (z-fighting);
- floating shells (more than 0.1 mm from anything);
- over the triangle budget.

**WARNs:**
- unwelded vertices, unapplied scale;
- non-planar n-gons, sliver triangles;
- mirrored UVs, texel density spread over 2.5×, empty material slots.

**Declared exceptions only:** `--open`, `--allow-float` (exploded views), `--uv-overlap-ok`, `--uv-tile`. Run it on each separable part ALONE as well as on the assembly.

### S5 Spot the difference
- `camera_match.py` per photo; RMS must be under 1 % of the width.
- Then `python scripts/ref_compare.py photo.jpg render.png review/diff_<view>_p<N> [--crop x0,y0,x1,y1]`. The sheet shows photo | render | 50 % overlay | difference map:
  - red = only in the photo;
  - cyan = only in the render;
  - white / orange = photo / render edges.
- **Both tools enforce their gate:**
  - `camera_match.py` prints `CAM VERDICT PASS|FAIL`. On FAIL (RMS over `max_rms_pct`, default 1 %, or the lens stuck on a `focal_range` bound) it skips the render and exits 2.
  - `ref_compare.py` prints `COMPARE VERDICT`. On a plain-background photo it exits 3 when IoU is under `--min-iou` (default 0.95; use 0.97 for final product-shot passes).
  - A busy background has no IoU; the written difference list is the gate there.
- **Write the difference list** in STATUS.md, going through these categories every time:
  - silhouette;
  - proportions;
  - feature present or missing;
  - counts;
  - shape;
  - bevel size;
  - finish and colour value;
  - texture pitch;
  - gaps and seams.
- Fix everything and loop until the list is empty.

### S6 Lookdev (`lookdev.py`, `bl_render.py`)
- **Render setup:** Cycles GPU with 128+ samples and denoise, AgX, a softbox studio plus a soft gradient world.
- **Measured material values** (linear base colour, roughness, metallic), Glock 17:

  | Surface | Base | Roughness | Metallic |
  |---|---|---|---|
  | nDLC slide | 0.034–0.038 | 0.40 ± 0.06 | 1 |
  | Polymer frame | 0.031 (slightly warmer) | 0.68, with micro-noise | 0 |
  | Barrel | 0.055 | 0.32 | 1 |
  | Small steel parts | 0.045 | 0.36 | 1 |
  | Sight white dot | 0.80 | 0.45 | 0 |
  | Orange follower | (0.85, 0.20, 0.02) | 0.45 | 0 |

- **No flat values:**
  - roughness breakup (handling smudges, ±0.06);
  - curvature-driven edge wear on steel only, very subtle on a new gun;
  - cavity darkening and dust in recesses;
  - glossier wear on contact areas.

### S7 Game mesh (`bl_low.py`)
- **Per assembly:**
  1. Decimate (collapse, triangulate) to the budget, then clean slivers (`sliver_report.py`).
  2. Weighted normals (face area) on all-smooth geometry, `auto_smooth_angle = π`; the bake carries the bevels.
  3. Smart UV, packed in 0–1 with a 16 px margin at the final size.
  4. One material slot per part (`M_<Asset>_<Part>`).
- **LODs:** LOD1 = 45 %, LOD2 = 18 % (decimate collapse).
- **Collision:** `UCX_<Mesh>_NN` convex hulls, light, at most about 96 vertices each (`fix_ucx.py`: extreme points along 96 Fibonacci directions).
- **Budgets:**
  - hero first-person weapon: ~55–60k triangles LOD0 for the whole gun (the Glock is 53k);
  - attachments: 2–15k;
  - props: 2–15k (set pieces up to ~25k);
  - consumables: 1–5k.

### S8 Bake (`bake.py`)
- **Method:** Cycles GPU, selected-to-active, `cage_extrusion = 0.6 mm`, `max_ray_distance = 1.6 mm`, `margin = 16 px EXTEND`.
- **Maps:**
  - `T_<Asset>_<Part>_Normal`: tangent space, OpenGL in Blender; flip green on UE import;
  - `T_..._BaseColor`: sRGB;
  - `T_..._ORM`: R = AO (64 samples, this assembly's own shells only, so parts that come apart carry no foreign shadows), G = roughness, B = metallic.
- **Sizes:** 4096 for hero surfaces seen in first person (Glock frame and slide); 2048 for the rest; 1024 for small props.
- **Proof:** `proof.py` renders the same views from the high-poly lookdev and from the baked game mesh, plus 1:1 first-person crops of the key surfaces. Any visible loss is a bake bug.

### S9 Export (`export.py`)
```python
bpy.ops.export_scene.fbx(filepath=path, use_selection=True, apply_unit_scale=True, apply_scale_options='FBX_SCALE_NONE',
    axis_forward='-Y', axis_up='Z', object_types={'MESH'}, path_mode='STRIP', bake_anim=False, mesh_smooth_type='FACE',
    use_tspace=True, use_mesh_modifiers=True, add_leaf_bones=False, use_custom_props=False)
```
- Game meshes go to `export/game/`, LODs to `export/lod/<Mesh>_LOD1.fbx`, and sockets to `export/<asset>_sockets.json` (UE cm, pitch/yaw/roll).
- Re-import the FBX into a clean scene and re-run mesh_qc.

### S10 UE import (`ue/ue_import_<asset>.py`)
- **FbxImportUI:**
  - `import_materials=False`, `import_textures=False`, `import_as_skeletal=False`;
  - `combine_meshes=True`;
  - `normal_import_method=FBXNIM_IMPORT_NORMALS`;
  - `auto_generate_collision=True`. Interchange with False DROPS the `UCX_` hulls (the EagleKart trap).
  - Uniform scale 1, no forced front X.
- **Replace in place:** same asset paths and names, so item rows, attachment rows and hand poses keyed by mesh name keep working. Back up first and dump `live_before.json` (sockets, LODs, collision, materials).
- **LODs:** import from `export/lod`. Screen sizes are `[1.0, r·1.778/500, r·1.778/1500]`, where r is the bounds radius.
- **Sockets:** live sockets win. Restore any socket the re-import lost; add contract sockets the asset lacks.
  - Gun sockets: `Muzzle`, `Aim` (rear-sight top centre, X along the sight line), `FrontSight`, `Optic_Socket`, `Grip_Socket`, `MagazineSocket`, `TacticalSocket`, `HandPose_L`/`_R`, and more (see INTEGRATION.md).
- **Textures:**
  - BaseColor: sRGB, `TC_Default`;
  - Normal: `TC_Normalmap`, `flip_green_channel=True` (OpenGL bake);
  - ORM: linear (sRGB off), `TC_Masks`.
- **Materials:** `M_<Asset>_PBR` (or the shared master) plus `MI_<Asset>_<Part>`. **Python-authored materials must call `recompile_material`,** or they render as Default with no error.
- **Verify by script:** triangles per LOD, screen sizes, sockets, hull count, materials and textures, written to `work/ue_import.json`.

### S11 In engine (one short PIE pass)
- `lns.equip <Row>`, then capture frames: hip, ADS, third person, a world pickup (it must show ALL fitted parts), and the inventory icon (`lns.icons.bakeall`; dark items must render dark).
- Guns: `lns.ads.check` puts rear and front sights at about 0 px, and the muzzle flash sits at the tip.
- Assemble the frames with `ingame_sheet.py` into `review/ingame_<hhmm>.jpg`. Look at them at full size.

### S12 Hands → Grip Workshop (`Tools/Hands/manual/`)
- `handfit_check.py` reports whether the existing hand poses still fit (finger penetration and gaps in cm).
- Add or refresh the weapon's setup in `setup_catalog.json` (see `Tools/bpy/glock17/v4/hands/workshop_g17_v4.py`).
- The user polishes in `Weapon_Grip_Polish.blend` (N panel → Grip Polish).
  - The **shared weapon grip** carries across every key.
  - **Move item** places consumables in the hand.
  - **Send to game** imports gun `HP_*` poses, melee holds and consumable holds, with backups and safety refusals.
- **Never auto-import a user's capture without being asked.**

### S13 Guns only: mechanics
Model every moving part as its own complete mesh, pivoted at its real travel origin (slide, BCG, charging handle, bolt catch, dust cover, trigger, hammer). Write a mechanism JSON with each part's axis, travel and limits. See `Docs/GUN_MECHANICS_PLAN.md`.

## 4. Textures for environments (procedural, from scratch)
- **Tiling sets:** made with Blender procedural shaders and/or numpy, baked seamless at 2048². Each has BaseColor, Normal, ORM and optional Height, with a documented real-world scale in cm per tile.
- **Value ranges:** albedo 0.04–0.8, with roughness variation.
- **Material:** a world-aligned (triplanar) master with WorldAlignedNormal (correct on all six faces, inside AND outside), per-actor hue/value variation, macro variation or detile, and an optional grime gradient.
- **Review:** a 2×2-tiling lit test sheet per set, judged at full size.
- **Example:** `Tools/bpy/textures_v1/` and `MAPPING.md`.

## 5. Traps (each one cost real time)
- **Y-mirror on import:** every `bl_lib` FBX arrived Y-mirrored in UE. Measure the imported mesh with `get_bounds()`; never trust the notes.
- **Far pivots:** `/Game/Mesh/ELB/*` meshes have geometry kilometres from their pivot. Re-base by trace.
- **UCX hulls:** Interchange with `auto_generate_collision=False` drops them.
- **Python materials** render as Default unless you call `recompile_material`.
- **`unreal.Color` is BGRA positionally.** Use keyword arguments.
- **Booleans** leave sliver triangles ("spikes"), and non-planar n-gons leave diagonal shading seams. mesh_qc WARNs on both; fix before review.
- **Bad camera matches:** a match over 1 % RMS was once accepted, and its diff sheets were meaningless. Large RMS usually means the model's proportions are off: move the suspect landmarks to `check`.
- **Photo backgrounds:** a thin border frame or watermark on a photo can poison the background estimate (`ref_compare` now samples inside the edge).
- **Runtime icon captures:** they are expensive. The AI freeze came from guns capturing icons on draw. Never trigger a capture outside the inventory flow.
- **Bad reload props:** a reload prop used the first matching magazine row (the SMG mag on the Glock). Resolve parts from the weapon's own defaults.
- **Pickups showing a bare frame:** new guns created without `LoadNewWeaponItem` showed only the frame on pickup.

## 6. Lessons log (append newest last: date: symptom → root cause → fix → rule)
- 2026-10-21: the Codex Glock was rejected four times as blobby or stubby → shape eyeballed, never matched against the photos, and the contract froze the bad grip → S2 silhouette gate plus S5 loop; contracts protect only gameplay anchors.
- 2026-10-21: the v4 Glock was approved ("insanely good") → SDF modelling from a traced side profile, IoU 0.986, a camera match, counted features, measured material values, a bake-loss proof → this file.
- 2026-10-21: "rendering is simply poor" → flat grey clay lookdev → S6 values table plus AgX and softbox for every review render.
- 2026-10-22 (textures_v1, UE 5.5 materials): `MaterialEditingLibrary.delete_all_material_expressions` left 31 of 64 nodes; `delete_asset` on a master its MIs reference fails ("in use"); `create_asset` over an existing name opens a modal "Overwrite Existing Object" dialog that blocks Remote Control until someone clicks → rebuild a Python master IN PLACE: delete every `unreal.ObjectIterator(unreal.MaterialExpression)` whose outer is the material, check the count is 0, re-add nodes, `recompile_material` → never `create_asset` onto an existing path from an unattended script.
- 2026-10-22 (textures_v1): triplanar in actor-local space via TransformPosition/Transform (World→Local) wrecked the normals on non-uniformly scaled boxes (tangential detail ×22) → project in the actor's YAW frame instead (position relative to ActorPosition, rotated by the local X axis; scale ignored) → test local-space materials on non-uniform-scaled meshes.
- 2026-10-22 (textures_v1): SceneCapture shots taken right after a texture import showed the lowest mips (blurry, wrong normals scores) → `MaterialInterface.set_force_mip_levels_to_be_resident(True, True, secs, 0, True)`, return to let the editor tick ~15 s, then capture → split capture scripts into setup / capture / cleanup calls.
- 2026-10-22 (Codex review of the exported bundle): the gates only reported; `mesh_qc` crashed on its own negative-scale finding (`'%s' % tuple(...)`, the same bug as the unapplied-scale branch), `camera_match` rendered and exited 0 at 5 % RMS, `ref_compare` exited 0 at IoU 0.54, and `qc_all.sh` piped Blender through grep so failures never reached the caller → verdict lines plus exit codes (QC 1, camera 2, compare 3), `--python-exit-code 1` on every Blender run, `qc_all.sh` collects each run's status → a gate that can't fail a script isn't a gate; check exit codes, not printed words.
- 2026-10-22 (Codex review): the "Gen 5" Glock's profile master was a Gen 6 CAD render, so the long Gen 6 beavertail shipped. The brief asked for a long upswept tail, but the variant was never locked → S1 variant lock: one named variant, the profile master must be it, and mixed references are listed with which source wins.
