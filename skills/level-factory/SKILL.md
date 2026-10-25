---
name: level-factory
description: Build a LootNShoot level from scratch the Blender-first way, then bring it into Unreal as a working, optimised map. The steps are brief and research, a to-scale HTML plan the user approves, from-scratch textures and a print atlas, a kit of props in Blender, the whole map laid out in Blender with review renders, FBX export, the gameplay C++ the level needs, a phased UE import (textures, materials, meshes, cloth), Blueprints, a scripted map build, a planned lighting pass, the MapOpt optimisation pass and culling zones, a standalone verification tour, and setting the editor startup map. Use it whenever the user asks for a new map, room, interior or level built "in Blender first" or "from scratch", or to redo any stage of one. GunRange (Tools/bpy/gunrange/v1) is the reference implementation.
---

# Level factory: a level from an empty folder to a playable, optimised map

**Reference implementation:** GunRange, a gun store with an indoor range, built 2026-10-24/25 as the editor work level.
- Blender side: `Tools/bpy/gunrange/v1/`. Unreal side: `Tools/bpy/gunrange/v1/ue/`. Optimisation toolkit: `Tools/MapOpt/`.
- Every stage below names the GunRange script that did it. Copy it and change the content, not the method.
- `DESIGN.md` there has the user's words for each feature; `LIGHTING-RESEARCH.md` has the sourced lighting numbers.

Related skills:
- `model-factory` / `blender-3d`: the mesh_qc gate and modelling rules for single assets (read before stage 4).
- `level-polish`: dressing, storytelling and audits once the level stands (use after stage 13).
- `lns-game-import`: editor access rules, Remote Control, backups.

---

## 0. Rules that apply at every stage

- **From scratch.** Every prop, texture and print is made by our scripts. Never download assets; reference photos are viewed, never saved, committed or published. No logos, brand names or real business names anywhere (numbers and calibres are fine).
- **Plan before modelling.** The user approves a to-scale HTML plan before any modelling (user: "before any modeling, plan the layout. show it in an html").
- **One source of truth.** All dimensions live in `plan.py` (UE cm). The plan page, the Blender layout and the UE build all read it. Change numbers there only.
- **Show progress.** Send review sheets (SendUserFile) at the end of the plan, kit, layout and in-game stages, and whenever the user asks. Fix what the user points at, then sweep the whole level for the same class of problem.
- **Ship at 90 %.** Short messages; the top 3 issues per review.
- **Shared editor.**
  - Take `Tools/editorlock.sh acquire <owner>` with an owner name unique to your session (for example `Claude-<Task>-<first 6 chars of your session id>`). Two sessions once both used `Claude-GunRange`, and one rebuilt the editor out from under the other.
  - Locks go stale after 45 minutes and another session takes them over. In a long run, re-check `Tools/editorlock.sh status` before every editor step: on 2026-10-25 a session kept editing, and started and ended PIE, inside the other session's lock.
  - Never import or save while the user is in PIE: check `python Saved/rc.py file Saved/pie_check.py` for `PIESTATE 0`, and wait in the background if it isn't.
  - Heavy jobs (Blender, builds) go through `Tools/jobslots.sh run …`.
  - Budget about 25-30 minutes of editor time and one rebuild per batch. Never package.
  - Release the lock as soon as the batch is done, and tell the peer session that asked for it.
- **Back up before overwriting** anything you didn't create. Never force-delete.

---

## 1. Brief and research → `DESIGN.md`

- Quote the user's request verbatim. When they name a real place as a style reference (GunRange: "look up machine gun vegas"), search it, view the photos, and write down the style in words only.
- Write: style notes, zones with sizes, every gameplay feature the user asked for (one line each: what the user said, and how it will be built), budgets, and a premortem (what would make it wrong, and which check proves it didn't happen).
- Budgets from GunRange: kit LOD0 0.2-8k tris per prop; whole map under 500k tris; under 70 unique meshes; under 30 material instances; at most 4 lights on any floor pixel; about 13 shadow casters.

## 2. Plan → `plan.py` + `plan_page.py` → HTML for approval

- `plan.py`: zones (x/y ranges, ceiling heights), walls, every fixture list (racks, shelves, lanes, light positions), helper functions (`yd(n)`, `lane_y(i)`).
  - Frame: UE cm. X runs from the entrance to the back, Y is right when facing +X, Z is up.
- `plan_page.py` → `review/<Level>Plan.html`: a to-scale SVG floor plan, wall elevations, a section, and tables. Publish it as an artifact (`plan_page.css` holds the styling) and wait for the user's decisions.
  - GunRange's first round of answers: a 50 yd lane, melee on the counter, the lounge replaced by gear racks plus a bar, frosted storefront glass, all weapons lootable and respawning. Fold the answers into `plan.py` and republish.

## 3. Textures and prints → `tex/`

- `tex/make_gr_textures.py`: tileable PBR sets in numpy (texlib from `Tools/bpy/textures_v1`).
  - Each set's tile size is the real cm per repeat (Epoxy 100, CeilingTile 60.96 = one 2 ft tile, DiamondPlate 30, ExpandedMetal 20 plus an opacity mask).
  - Output: `T_Bld_<Set>_{BC,N,ORM,H}.png` + meta json. Normals are DirectX like textures_v1.
- Reuse the textures_v1 building sets where they fit (brick, wood floor, CMU, concrete slab, corrugated deck).
- `tex/make_print_atlas.py`: every printed thing on one 2048 RGBA masked atlas (`T_GR_Print`) plus `print_atlas.json` with each region's pixel rect. That covers targets, lane and board numbers, labels, price tags, signs and the rules board. Font: Inter (OFL), from Blender's datafiles.
- Gate: a preview sheet per set (3x3 tiling) reviewed for seams and repetition.

## 4. The kit → `grlib.py` + `kit.py` → `work/kit.blend`

- `grlib.PB`: one bmesh per piece, built from closed primitives (`box`, `cyl`, `prism`, `sweep`, `quad`, `print_quad`) with per-face material slots.
  - UVs are real-scale box UVs (1 UV unit = 1 m, u to the viewer's right); materials scale by 100 / tile cm. Prints use explicit atlas UVs.
- Anchors (the piece origin): `floor` = bottom centre; `wall` = back-bottom centre (geometry in +x); `ceiling` = top centre; plus `axis`, `hinge` and `clip` for moving parts.
  - Blender metres, +X = the face the player sees.
  - UE (x, y, z) = (Bx, -By, Bz) × 100, and UE yaw = -Blender rot_z.
- Material slot names are the UE material instance names (`MI_GR_*`). FBX keeps them, and the UE import assigns materials by slot name.
- `grlib` also builds Blender preview materials (the SETS and FLAT tables) so renders look like the game.
- **Gate: mesh_qc.** Run `mesh_qc.py --uv-tile --per-object-float --uv-overlap-ok <names>` on `kit.blend`. You need 0 errors, and every WARN has to be explained.
  - `--per-object-float` is required for kits of separate props.
  - The checker measures shell volume about the centroid, so pieces far from the origin don't read as inside-out.
- Review: `render_pieces.py` makes one Eevee thumbnail per piece; `render_kit.py` makes catalogue shots. Send the catalogue sheet.
- Doors for MooseKit (`LNSKitDoor`): the leaf pivot sits at the hinge edge, bottom; width runs along +X, thickness is centred on Y, height runs up Z. Our frames are kit meshes, so the door's `bBuildFrame` is false.
- Moving or physics parts:
  - Cloth sheets are a single grid (GunRange paper: 0.58 × 0.87 m, 12 × 18 quads, top edge at z 0 = the clip).
  - Cans have a cylindrical wrap UV.
  - A lane panel has its buttons at known local offsets that the C++ reads.

## 5. The map in Blender → `layout.py` → `work/map.blend` + `work/layout.json`

- `layout.py` places linked kit instances from `plan.py`. Every prop is seated on its support by construction: a support height table, never a guess. Shells are boxes with world-scale materials.
- `layout.json` (UE cm / degrees) is the contract with Unreal:
  - `meshes [{kit, x, y, z, yaw}]`
  - `shell [{name, mat, box: [x0,x1,y0,y1,z0,z1]}]`
  - `spawners [{row, x, y, z, yaw, pitch, roll, respawn, loaded}]`
  - `lights [{type, x, y, z, yaw, pitch, intensity, radius, w, h, color, cone}]`
  - `doors [...]`, `carriers [...]`, `can_pyramids [...]`, `player_start`
- Lights in Blender sit inside their fixtures with `visible_camera = False`. A light inside a baffle or wall shows as a white band in renders.
- Review: `render_map.py` renders Cycles shots (an ortho plan with the ceilings hidden, plus eye-height views) as a contact sheet. Send it.
  - Typical user catches: lines running the wrong way, an unreadable prop ("what are these rectangles"), rooms too dark.
  - Fix the class, not just the instance: if one prop doesn't read, check every prop.
- Pickup orientation: the game's pickup meshes run along **Y**, not X. A gun hung flat on a wall facing +Y needs yaw 90 and roll 0. Check one pickup mesh's bounds before writing spawner rotations.

## 6. Export → `export.py` → `export/`

- One FBX per kit piece in `export/static/`, origin at the piece's anchor, using forward -Y / up Z.
- Cloth pieces go to `export/skeletal/SK_*.fbx`: one root bone at the clip, every vertex weighted to it.
- The FBX root bone is the Blender armature *object's* name. Pieces that share a skeleton in UE must export with the same armature name (`SHARED_RIG` in `export.py`), or UE reports "incompatible Skeleton".
- `SM_GR_UnitBox`: a 1 m cube with its pivot at the bottom centre. Every shell wall, floor and ceiling is this box scaled, with a world-aligned material.
- `export_manifest.json`: per mesh, the collision policy (`complex_as_simple`, `none` for prints/labels/fixtures/wires, `box` for the unit box), the material slots and the anchor.

## 7. The gameplay C++ the level needs

GunRange added the following:
- `AGRTargetCarrier`: a motor track with SEND / RETURN / RESET buttons as Interact-channel boxes, replicated, cloth paper.
- `AGRCanPyramid`: physics cans with replicated reset.
- `ALNSLootSpawner::bSpawnLoaded`, plus an editor-only preview mesh and the item's icon as the sprite.
- MapOpt (stage 11).
- `ULNSClothBuildLibrary` in the editor module, because Python can't create cloth.

Rules:
- **Includes.** The `LootNShoot` module adds no include paths. A file in a subfolder includes its siblings by bare name and module-root headers as `"../X.h"`. `#include "GunRange/X.h"` from inside `GunRange/` fails.
- **No hard-coded asset paths in C++** (project rule). Meshes and materials go on the Blueprint subclass's defaults (stage 9).
- **Tick only while something moves.** Damage arrives on the server, so cosmetic reactions (the paper flinch) are `NetMulticast, Unreliable`.
- **Cloth has no physics asset,** so it takes no hits. A hidden static stand-in plate (QueryOnly) takes the bullet traces and carries the hole decals.
- **Hang paper 3 cm in front of its backer.** At 1 mm the cloth drifts behind the backer and only the cardboard shows.
- **Compile check without touching the editor:** `Build.bat LootNShoot Win64 Development …` (the game target). Then one editor rebuild with `LNS_BUILD_PAR=8 bash Saved/build_ln.sh`. It saves dirty packages, quits the LNS editor, builds, relaunches and reopens the work map; it refuses during PIE.
- **Commit identity:** `git -c user.name="Moosie Studios" -c user.email=<the user's email>`. Many repo files are CRLF: edit them with the Edit tool or a byte-preserving replace. `sed -i` on Git Bash rewrites every line ending.

## 8. UE import → `ue/gr_import.py` (one phase per Remote Control call)

`python Saved/rc.py stmt "PHASE='<phase>'; exec(open(r'<abs path>/ue/gr_import.py').read())"`

Each phase writes what it made into `ue/gr_import_report.json`.

- **`tex`**: imports to `/Game/<Level>/Textures`.
  - BC and Print: sRGB, Default. N: Normalmap, no green flip. ORM: Masks. Mask: Grayscale.
  - **Cap the size by texel density** (about 10 px/cm, so tile 20-50 cm → 512, 60-122 cm → 1024) with `max_texture_size`.
  - Never change shared textures that other maps use.
- **`mat`**: masters are created once and later cleared in place. `create_asset` over an existing asset opens a modal "Overwrite?" dialog.
  - Tiling sets: MIs on the triplanar master with `UseLocalSpace` 1.
    - Detile is on for random sets (module-aligned `DetileOffset`) and off for grids and lattices (ceiling tile, diamond plate, plywood).
    - A little grime at wall bases only on the old building sets.
  - For box-built interiors, reparent the tiling MIs to `M_GR_Uniplanar` (`ue/gr_uniplanar.py` + `.hlsl`): one dominant-axis projection, same look on box faces, about a third of the shader.
  - Small masters: `M_GR_Flat` (colour / roughness / metallic / emissive), `M_GR_Print` (masked UV0; the cloth MI overrides two-sided), `M_GR_Glass` (lit translucency), `M_GR_MaskedUV` (expanded metal on the kit's metre UVs).
- **`mesh`**: FBX import with `import_materials=False`, no auto collision, no lightmap UVs (Lumen only), no Nanite, combine meshes.
  - Assign MIs by slot name; the phase fails loudly on any unassigned slot.
  - Collision follows the manifest.
  - **Simulating bodies need a convex simple shape** (cans: `NDOP10_Z`); complex-as-simple can't simulate.
- **`cloth`**: imports the skeletal FBX, then `unreal.LNSClothBuildLibrary.make_hanging_cloth(mesh, 0, max_cm, pin_cm, ramp_cm, gravity, damping)`.
  - The top band is pinned and Max Distance ramps down the sheet.
  - Use `set_cloth_config_value` for any Chaos property Python can't reach.
  - Save the generated `*_Skeleton` assets too, or the next level load prompts.

## 9. Blueprints → `ue/gr_make_bps.py`

- Create each Blueprint once with `BlueprintFactory(parent_class=…)`, compile it, then set the meshes on the CDO's component templates (`get_default_object(bp.generated_class())`), compile again, save, and read back.
- **Loot Blueprint defaults** (`BP_GR_RespawnLoot`): `physics_settle` off, `respawn_delay` 10, **`snap_to_ground` off, `random_yaw` 0**. The base spawner snaps stock to the floor and spins it ±180°.
- For mutable state the user should edit later, prefer a class default on the BP over per-instance values.
- Level-specific extras run after the Blueprints, each as one idempotent script. GunRange has three:
  - `ue/gr_paper.py`: a paper material that cuts bullet holes from the carrier's render target.
  - `ue/gr_hits.py`: hole decals, plus the `GR_NoWorldDecal` actor tag so the gun skips its wall decal.
  - `ue/gr_cctv.py`: a lane camera and a monitor using the project's own CCTV actors.

  Reuse the project's existing actors (CCTV, doors, loot spawners) before writing new ones.

## 10. Build the map → `ue/gr_build_map.py`

- Open the level, or create it if it doesn't exist. Skip both if the world is already that map: a re-run after an error must not open the "save changes?" dialog.
  - Check `EditorLoadingAndSavingUtils.get_dirty_*_packages()` before switching levels.
- **Idempotent:** tag everything it spawns (`GR_Build`) and destroy only tagged actors before spawning. MapOpt batches copy the tag.
- **Shell:** UnitBox actors scaled per box, with the MI as a material override. A thin emissive panel outside frosted windows (daylight) stops them reading black.
- **Props:** a StaticMeshActor per kit instance (MapOpt batches them later). No-collision manifest pieces get no collision and no nav relevance. Skip the Blender preview copies of things a Blueprint draws itself (carrier trolleys, lane panels, papers, tables, cans).
- **Loot:** look up each row's category across the game mode CDO's `item_data_tables` (from `BP_FirstPersonGameMode`). Report rows found in no table (GunRange: `Mask` became `BallisticMask1`).
- **Doors, carriers, cans:** set properties with `set_editor_property`. On a Blueprint actor that reruns its construction script; `rerun_construction_scripts` isn't exposed to Python.
  - The panel transform is relative to the actor root.
  - Long lanes get extra stops (35 and 50 yd).
- **Game actors:**
  - PlayerStart.
  - An unbound post-process volume: Histogram exposure with min = max EV100 and bias 0. The project default bias is +1.
  - A NavMeshBoundsVolume. Its brush is 200 uu, so scale = size / 200.
- **Culling zones and portals:** one `AMOZone` box per room; one `AMOPortal` per opening (door, window, firing line), linked to its door actor.
- Python: build `unreal.Rotator(roll=, pitch=, yaw=)` and `unreal.Color(r=, g=, b=, a=)` with keywords only (the positional orders are roll/pitch/yaw and B/G/R/A). Component bounds come from `unreal.SystemLibrary.get_component_bounds`.

## 11. MapOpt → `Tools/MapOpt/mapopt.py` (works on any map)

`python Saved/rc.py stmt "CMD='audit'; exec(open(r'<repo>/Tools/MapOpt/mapopt.py').read())"`

- **`CMD='audit'`** writes `reports/<Map>.json` and `.html`. It covers:
  - actors, StaticMeshActors, instancing candidates, estimated draw calls, LOD0 tris;
  - flags (overlaps, shadows on tiny props, nav on no-collision);
  - lights (shadow casters, overlap);
  - texture GPU MB;
  - the package load set;
  - primitives per zone.

  The first audit of a map is kept as its "before" block.
- **`CMD='fix'`** is a dry run; **`CMD='fix'; APPLY=True`** applies the rules:
  - R1: overlap events off on static primitives.
  - R2: no shadows on props under 12 cm.
  - R3: no nav relevance on no-collision props.
  - R4: no shadows on lights with a small radius.
  - R5: light radius clamped to its zone.
  - R7: light radius = 1.35 × the traced distance to its target + 75 cm.
  - R8: dense downlights fold into one.
  - R6: StaticMeshActors batched into one HISM actor per zone, through `ULNSMapOptLibrary.batch_to_instances`. Batching per zone keeps culling working.
  - Tag a light `MO_Keep` to protect it (hero lights).
- **`CMD='unbatch'`** / **`'undo'`** puts the props back as loose actors for editing.
- **Culling at run time:** `UMOCullSubsystem` draws the camera's zone plus every zone seen through an open portal inside a widened view cone. Everything else is distance-culled. That's a render-thread update only: no streaming hitch, and gameplay and collision are untouched.
  - Console: `lns.mapopt.cull 0|1`.
  - Zone changes are logged as `MapOpt cull: zone X drawn|culled`.
- GunRange result: 937 → 301 actors, est. draw calls 1269 → 369, texture GPU 131 → 72 MB, floor light overlap p95 12 → 4.

## 12. Light it on purpose → `ue/gr_light_plan.py` (read `LIGHTING-RESEARCH.md`)

- Each zone gets only its **hero lights**: the ones that shape the space and cast its shadows. Every other fixture is just an emissive lens (`MI_GR_Lens` / LED), and Lumen bounce fills between them.
- Every light sits inside a modelled fixture. Positions come from `layout.json`.
- Use physical lumens per fixture (high-bay 16,000, troffer 12,000, track head 4,500, target head 20,000; see the plan table) and a **fixed EV100**. GunRange settled at **EV100 6.0**: the user found 7.25 and 6.75 too dark, and 9.5 was badly wrong.
- Targets from the research: retail 300-500 lx, range general ≥ 322 lx, target face about 1,000 lx. A spot's near field burns whatever is within 1-2 m, so no baffle or wall may sit inside a spot's cone. Wall-adjacent heroes cast shadows.
- Check with the Light Complexity view (the user uses it: it is lights per pixel, not shader cost) and the Shader Complexity view. Aim for p95 of at most 4 lights per floor pixel and about 13 shadow casters.

## 13. Verify in the standalone game, then hand over

- Tour: write `Saved/tour_<level>.txt`, then run `bash Tools/jobslots.sh run bash Saved/standalone_tour_map.sh <Map> tour_<level>.txt <prefix> <n frames> <OutDir>`.
  - Back up and restore `Saved/tour.txt`. The script backs up and restores the saves itself.
  - Ops: `name x y z pitch yaw` (pawn z = floor + 100; repeat each line twice), `hud off`, `fov 78`, `interact`, `cmd <console>`, `wait`, `quit`.
- One frame per zone from its entry, the hero walls, every moving feature before and after its button, and the culling views.
  - `interact` hits whatever is under the crosshair, so aim at the button (GunRange's first try picked up the magazine below the panel).
  - On-screen debug text doesn't draw with `hud off`; check the game log for the cull lines instead.
- Read every frame at full size. Check exposure (no white floors), orientation (guns flat, text reading the right way), floating or sunk props, papers visible, loot present ("PICK UP …" prompts).
- Then:
  - set the editor startup map: `EditorStartupMap=` in `Config/DefaultEngine.ini`, edited byte-for-byte, after a backup;
  - `Saved/relaunch_editor.sh` reopens `$LNS_EDITOR_MAP` (default GunRange);
  - commit the scripts;
  - release the lock;
  - tell any peer session about shared changes.

---

## Traps we hit (symptom → cause → fix)

| Symptom | Cause | Fix |
|---|---|---|
| Non-manifold edges after the kit build | `remove_doubles` welded touching parts | Don't weld; parts are separate closed shells |
| Zero-area UV faces | UVs computed before normals | `bm.normal_update()` before the UV pass |
| Mirrored textures / prints facing the wall | UV right vector picked arbitrarily | UV right = Z × n; prints take an explicit right vector |
| Blender 4.0 Mix node does nothing | Colour sockets looked up by name return the float ones | Colour A/B = inputs 6/7, result = output 2 |
| "Inside-out" pieces far from the origin | Signed volume about the world origin | mesh_qc centroid volume (both copies of the script) |
| White band across a review render | A light inside a baffle | Lights between baffles, `visible_camera = False` |
| Hall too dark in Blender | Spot high-bays | Rect discs, about 650 W in Blender |
| User: "what are these rectangles" | A prop that doesn't read (felt mats on glass) | Remove it; every prop must say what it is |
| Guns hang vertical on boards | Pickup meshes run along Y; the layout assumed X | yaw 90, roll 0 |
| Wall stock on the floor / spun | Spawner `bSnapToGround` and `RandomYaw` 180 | Loot BP: snap off, yaw 0 |
| Spawner billboards don't show the item | Generic MooseKit sprite | `ALNSLootSpawner` editor preview mesh + icon sprite (built) |
| Paper target invisible (you see the cardboard) | Sheet turned 180 deg: its front (normal -X) faced the backer; back face culled | Target yaw 0, sheet 3 cm off the clip, backer removed so the paper hangs free |
| Bullets pass through the paper | Skeletal cloth has no physics asset; the stand-in plate mesh was exported collision `none` | Hidden plate with a box (simple-as-complex), QueryOnly, ignores Visibility/Camera (or E shows "Send target") |
| Holes slide off / vanish on the cloth | Decals hang on the plate in space, not on the deforming sheet | Per-target RG render target, `StampHole` at the sheet UV, `M_GR_PaperTarget` cuts R / darkens G |
| Cans vanish when shot | The gun pushes with the round's whole momentum; 15 g can → 200 m/s, tunnels | 0.35 kg cans + CCD |
| Cans won't simulate | Complex-as-simple collision | Simple convex collision (`NDOP10_Z`) |
| Everything white in game, fine in the editor | `BP_FirstPersonCharacter` FollowCamera post-process forced EV100 0 in every map (camera PP beats volumes) | Removed the override (user OK); the map's PP sets exposure (EV100 6.0, bias pinned 0) |
| Mesh shows the world grid though its slot names the MI | Master failed to compile (sampler type: a linear mask needs Linear Grayscale/Color, an sRGB default needs Color) | Check `get_statistics` > 0 and the log "Failed to compile Material" |
| Paper / cloth shows the world grid in -game | Master lacks `used_with_skeletal_mesh` / `used_with_clothing` | Set both on the master (editor sets them only lazily) |
| Python edit to a skeletal mesh's materials does nothing | Arrays of structs iterate as copies | `m = arr[i]; m.set_editor_property(...); arr[i] = m` |
| A spawned actor sits 2 m off its layout spot | Editor spawn nudges actors out of overlaps | `set_actor_location(loc, False, True)` right after spawning |
| A part appears at the world origin (table in the doorway) | Static component under a Movable root detaches | Root Static (movable children are fine) |
| CCTV camera deleted by the lighting script | Sweep "actors with a light component": its LED is one | Filter `isinstance(a, unreal.Light)` |
| A wall behind a light still counts it in Light Complexity | Rect / point lights are culled by their sphere; spots by their cone | Near walls use spots aimed away, or a radius that stops at the wall |
| Monitor feed turned 90 deg | Engine plane faces +Z; `ScreenRotation` (90,180,0) put image-right up | `(roll 90, pitch 0, yaw -90)`, ScreenSize (W, H); check with get_up/forward/right |
| Light Complexity white | Radii covering whole rooms | Hero lights + emissive lenses, R7/R8, budget ≤ 4 per pixel |
| Shader Complexity red on floors | Triplanar compiles three projections | `M_GR_Uniplanar` for box geometry |
| `C1083 cannot open include` | Subfolder include paths | Bare sibling names, `"../X.h"` for the module root |
| Modal dialog freezes Remote Control | `new_level` / `load_level` with dirty packages; `create_asset` over an asset | Check dirty packages; detect the open world; rebuild assets in place |
| Edit applies but the diff touches every line | CRLF file rewritten by `sed -i` / Python `\n` | Edit tool or byte-preserving replace |
| Import during the user's play | No PIE check | `pie_check.py` → `PIESTATE 0` first |
| Two sessions collide on the editor | Same lock owner name | Owner name unique per session |
