---
name: gun-pipeline
description: The fast path for putting a NEW GUN into LootNShoot, from plan to the user's polish - plan, model (Codex or Claude), one-shot game import (meshes, materials, sockets, item rows, icon, equip, pickup), rough animations, Grip Workshop injection, the user polishes, done. Includes the premortem of the Glock 17, AR-15 and Mossberg 590 imports (what wasted time and credits) and the rule that removes each waste. Use it before planning any new gun, before importing one, and before generating its first animations. Modelling details live in model-factory.
---

# Gun pipeline: plan -> model -> import -> rough anims -> Grip Workshop -> user polish -> done

Third gun in (Glock 17 v4, AR-15, Mossberg 590). Target from now on: **one planning hour, one model hand-off, ONE import session (one build, one PIE pass), rough anims generated, the user polishes.** Every rule below exists because skipping it cost hours or credits on a previous gun.

## 0. Roles and budgets

| Stage | Owner | Budget | Output |
|---|---|---|---|
| 1 Plan | Claude | 30-60 min, no editor | `Tools/guns/<gun>/plan.json` + reference set locked |
| 2a Setup | Codex | references, measurements, rough blockout | variant-locked refs, dimensions JSON, solved cameras, blockout FBX |
| 2b Model | Claude, `model-factory` skill | model gates only | hand-off package (section 3) |
| 3 Import | Claude, ONE agent | ~30 min editor, 1 build, 1 PIE pass | the gun in game: equip, fire, ADS, reload, pickup, icon |
| 4 Rough anims | Claude | no editor except Send | key clips that open in the Grip Workshop |
| 5 Workshop inject | Claude | headless Blender only | setups + clips listed in the user's blend |
| 6 Polish | **the user** | their time | grips and keys sent with Send to game |
| 7 Close | Claude | 1 short PIE pass | contact sheet, commit, tracker |

The user's time is the scarce resource. Agents never hand-solve hands or polish animation: they make a clean, correct starting point and get out of the way (section 8, trap A1).

**Keep the ball rolling (user, 2026-10-22):**
- 90-95 % quality is DONE for every stage. Refinement happens later, in game, when it matters.
- Each gate gets ONE review round. The reviewer sends the top 3 issues only, in a few lines. Later rounds only for something broken (wrong shape, wrong variant, missing part), never for polish.
- Time-box: model about half a day, import one session. When the box runs out, ship with the open items listed in STATUS and move on.
- Messages to the user: the outcome in a few lines. Details live in STATUS and the tracker.

## 1. Plan (before any modelling)

Write `Tools/guns/<gun>/plan.json` from the game's runtime contract for the gun TYPE, never from generic advice:
- **Exact variant** (maker, model number, generation, barrel length) + 3-6 references of THAT variant, one near-orthographic side view as the profile master. Private photos stay in `refs_user/`.
- **Runtime pieces by type** (read `Source/LootNShoot/WeaponDataTable.h` for the current fields; copy names exactly):

| Type | Meshes the game uses | Moving parts the runtime drives today | Reload clips |
|---|---|---|---|
| Pistol (Glock) | frame = ItemMesh; slide, barrel, magazine as attachment rows | none yet (mechanics plan) | tactical + empty, mag prop = the gun's own mag |
| Rifle (AR-15) | merged config mesh(es) per build; magazine at `MagazineSocket` | none yet | tactical + empty |
| Pump (M590) | ItemMesh (full, all sockets) + `PumpBodyMesh` (no fore-end, same frame) + `PumpMesh` (fore-end + bars, pivot = rear face at `Pump_Socket`, slides along `PumpAxis` by `PumpTravel`) | the pump | `ShellReloadStart / Insert / End / EndEmpty`, `ShellPropMesh` |
| Bolt (sniper) | ItemMesh + `BoltBodyMesh` + `BoltMesh` at `Bolt_Socket` | the bolt (`BoltLift`, `BoltTravel`) | per type |

- **Replace or add?** Replacing an existing gun keeps its ROW NAME (loot tables, vendors, ammo, saves keep working). Mesh names change, so its hand poses (keyed by mesh name) are re-made in the Grip Workshop anyway.
- **Sockets list** for the type (`Tools/bpy/ar15/INTEGRATION.md` + the old gun's `Tools/Hands/src/weapons/<mesh>_sockets.json`): every socket the old gun had, plus `FrontSight`. All are MEASURED on the new mesh by ray casts at import, never copied.
- **Data**: caliber/ammo row, magazine row + compatibility (only this gun's mags), attachment slots, recoil profile (`Docs/RECOIL.md`), fire mode/RPM, value/weight/size, icon footprint.
- **Animation list**: idle hold, fire, reloads by type, pump/bolt rack, plus what the user wants to polish.

## 2. Setup (Codex) and model (Claude)
**Split decided by the user, 2026-10-22,** after an independent inspection scored Codex's M590 4/10 against the Glock bar: the shape was right, but surfaces, detail, textures and texel density were weak.
- **Codex** does the SETUP only: find variant-locked reference images, measurements and dimensions, solved reference cameras, and a rough blockout with correct proportions.
- **Claude** takes that and chisels it into the finished gun with model-factory: high-poly detail, bakes, lookdev, game mesh.
- Never hand Codex the detailing or texturing.
Send the modeller ONE brief built from plan.json (the M590 needed six corrective messages because the runtime contract, colour targets and variant rules arrived piecemeal). The brief contains: variant + refs, the runtime piece list with pivots, the socket list, triangle budgets per piece, material slots, measured colour RATIO targets from the photo (section 7), the review rig, the hand-off layout below, and the exit-code gates (`model-factory`). Review only at the gates the skill defines (silhouette IoU, oblique diff, first-person crops, texture proof); one consolidated review per gate, not a message per render.

## 3. Hand-off package (validated by script before import)
```
<handoff root>/
  handoff.json          gun id, variant, row to replace, piece -> fbx, sockets json, mechanism json, textures per slot, budgets, open items
  fbx/                  SM_<Gun>.fbx (full, ItemMesh), SM_<Gun>_Body.fbx / _Pump.fbx or _Bolt.fbx, LOD1/LOD2, UCX_ hulls inside
  parts/                authoring parts (bolt, elevator, trigger, safety, ...) for the future mechanics
  textures/             T_<Gun>_<Slot>_BaseColor (sRGB) / _Normal (OpenGL) / _ORM (linear), 4K hero, 2K rest
  <gun>_sockets.json    UE cm, pitch/yaw/roll, measured on THIS mesh
  <gun>_mechanism.json  per moving part: mesh, pivot, axis, travel, limits, linked_to
  STATUS.md, review/    final sheets, QC json, open items stated plainly
```
Blender 4.0-compatible FBX and scripts (the user's Blender and the Grip Workshop are 4.0). `Tools/guns/handoff_check.py` (to build on the M590 run) re-imports every FBX into a clean scene, runs mesh_qc with exit codes, checks names/pivots/sockets against plan.json and refuses on any mismatch.

## 4. Import (ONE agent, ONE script, ONE editor session)
`Tools/guns/gun_import.py <handoff.json>` over Remote Control, generalised from `Tools/bpy/glock17/v4/ue/ue_import_g17_v4.py`. In one run:
1. Back up every asset it will touch + dump `live_before.json`.
2. Meshes (+LODs, UCX kept: `auto_generate_collision=True`), textures (BaseColor sRGB, Normal flip green, ORM linear), master material + one MI per slot, `recompile_material`, read every parameter back.
3. Sockets from the JSON, then RE-MEASURED: `Aim` = rear sight/receiver top centre on the sight line, `FrontSight` = bead/post top, `Muzzle` = bore axis at the face. Write the measured values back to the JSON.
4. Data rows: replace the old gun's row in place (same row name), magazine compatibility, ammo, recoil, type fields (pump/bolt meshes, travel), `ShellPropMesh` / mag prop from the gun's OWN defaults.
5. Grip Workshop sources: export the gun's meshes + sockets to `Tools/Hands/src/weapons/` (what `ue_export_hands_*.py` did for the Glock).
6. Icon: the standard icon bake for this item only (`lns.icons.bakeall` path), dark items render dark.
Then ONE PIE pass, scripted (`Tools/guns/verify_gun.sh`, built from the Glock's `g17_tour.txt` / pickup test): equip -> hip frame, `lns.ads.check` (sight offset in px, must be ~0), fire -> muzzle flash at the tip, reload (tactical + empty / shell), drop -> pickup shows the full gun, inventory icon, third person. Output: ONE contact sheet + numbers. Read it at full size, fix, re-run only the failing op.

## 5. Rough animations (generated, not hand-solved)
Generate key clips (`lns.keyclip.v1`, Grip Workshop format) from templates per type, using the gun's sockets: idle hold (from the type's existing hold, re-seated on the new grip sockets), fire, reloads, pump/bolt rack. First and last key = the idle hold. Magazine/shell as a role with holders per key; notifies (mag out/in, ShellInserted, pump) placed at the keys. Send to game once so the gun is playable with placeholders. These are starting points: correct contacts and timing, no polish.

**Pump guns, shell batch reload (user design 2026-10-22) - DONE on the M590 (2026-10-22):** the hand grabs N shells from the belt, inserts them one by one, then grabs again until full or out of ammo.
- Runtime (`AWeaponRangedItemActor`, stats row): `ShellReloadGrab` clip; phases Start -> Grab -> Insert xN -> Grab ... -> End / EndEmpty (`ShellPhaseGrab` = 5, `NextShellPhase`). N = `ShellHandCapacity` (4) + 1 per `ShellHandDexterity` level reached (20, 35; `ULootNShootSkillComponent::GetShellHandBonus`, Dexterity = "weapon handling"), never more than the tube wants or the shells carried. Notifies: `ShellsGrabbed` (Grab) and `ShellInserted` (Insert). The weapon draws `ShellsInHand` shells on `hand_l` by the shell's `HandPose_L` + k x `ShellHandStep`; replicated (`ShellsInHand`, SkipOwner) like the phase. Fire ends it after the shell in hand; leftover shells go back (taken from the reserve only as they go in). No Grab clip = the old single-shell cycle.
- Clips: `Tools/Hands/manual/tool/shell_keys.py` (headless, copy of the blend) makes the setup start pose + six key clips; `Tools/guns/m590/send_clips.py` sends them; `Tools/guns/m590/ue_shell_rows.py` wires the row. Check: `verify_gun.sh <plan> reload` (from 2, from empty, fire interrupt; ShellReload lines in numbers.txt).
- Workshop: keys.json `parts` (grip_keyanim): the pump as its own object riding the gun on its slide with the left hand locked to it; shells as the game mesh on the left hand by its grip socket (Set key snaps both).

## 6. Grip Workshop inject, then the user polishes
Add the gun to `Tools/Hands/manual/setup_catalog.json` (setup per hand grip: right on the grip/wrist, left on the support surface or the pump; the pump/bolt as a moving holder), and its clips' `keys.json` under `Tools/Hands/manual/clips/` so they appear in Animation > step 3 "Open a game animation". Tell the user: reopen the blend; static grips (R, L, pump) in Static pose -> Send to game; animations in Animation mode -> Send to game. Never auto-import the user's captures; never write their open blend.

## 7. Measured, not argued
- **Colour**: region RATIOS and chromaticity from the photo (wood/metal, pad/wood; r/g, b/g), same crops in photo and render, one locked exposure. A clipped white background cannot calibrate exposure.
- **Shape**: silhouette IoU >= 0.95 side; oblique fit solved on off-axis rigid points with held-out check points; read the error VECTORS before changing geometry (the M590 "stock error" was 75 % camera).
- **In game**: ADS offset px, muzzle flash distance from the tip, pickup completeness, icon luminance - numbers on the contact sheet.

## 8. Premortem: what wasted time and credits on guns 1-3, and the rule now
| # | What happened | Cost | Rule |
|---|---|---|---|
| A1 | AR-15 hands: agents ran a procedural grasp solver through many rejected candidates (thumb, rail clearance, "why are we digressing") | days | Agents never solve or polish hands. Generate the rough hold, inject into the Grip Workshop, the user polishes. |
| A2 | Codex Glock rejected 4x (blobby, stubby) - no reference gates | 4 model passes | model-factory gates with exit codes; variant locked. |
| A3 | Glock "Gen 5" traced from a Gen 6 render | wrong beavertail shipped | Variant lock in plan.json, profile master must be that variant. |
| A4 | M590: my first assembly advice ignored the game's pump runtime (3 meshes) | rework of the split | Plan reads WeaponDataTable.h fields for the type first. |
| A5 | M590 brief arrived in 6+ corrective messages (budgets, colour, crops, contract) | Codex + review cycles | One brief from plan.json; one review per gate. |
| A6 | Review renders lied: AR-15 white strips from the rim light; M590 black read as grey under a softbox | several passes | One standard review rig; colour judged by ratios, not by eye. |
| A7 | Glock ADS 6.7 mm off: `Aim` copied from the old contract | user caught it in game | Re-measure every visible-feature socket on the new mesh at import. |
| A8 | Muzzle flash not at the tip; pickup showed a bare frame; icons too light; reload used the SMG mag | 4 separate fix rounds after "done" | The scripted verify pass covers each (section 4) before reporting. |
| A9 | Icon capture on weapon draw froze AI fights | perf bug hunt | Icons only from the inventory flow / bake; never at runtime draw. |
| A10 | Agents used the editor too long (many builds and PIE runs); lock waits between agents | credits, user annoyance | One import agent per gun, one build, one PIE pass; C++ checks with the game-target compile. |
| A11 | Test assets left in /Game (undo history held them) | user cleanup | Test sends go to a scratch folder created and deleted in the same session, or not at all. |
| A12 | First-person clip not updated (`_FP` variant) | "no change in game" | Send to game writes the base AND the `_FP` clip. |
| A13 | Blender 4.5 blend handed to a 4.0 user | can't open | FBX hand-off; scripts 4.0-compatible. |
| A14 | Renders judged from thumbnails / wrong frames ("imported too high" was an old screenshot) | confusion | Full-size frames taken after the step, labelled with time and step. |

## 9. Build-out (do these on the M590 run, reuse forever)
`Tools/guns/`: `plan_template.json` per type, `handoff_check.py`, `gun_import.py`, `verify_gun.sh` (+ contact sheet), `rough_anims.py` (key-clip templates per type), `workshop_inject.py`. Each gun after the M590 should only need a plan.json, a hand-off and these four commands.

**Built on the M590 (2026-10-22)** - the import half, and for pump guns the rough anims + workshop inject (`Tools/Hands/manual/tool/shell_keys.py`: setup start pose, rack + shell clips, `parts` rules; generalise it into `rough_anims.py` on the next gun). Still to build: `plan_template.json`, a type-generic `rough_anims.py` / `workshop_inject.py`.
```
python Tools/guns/handoff_check.py <handoff dir> Tools/guns/<gun>/plan.json      # no editor; exit 1 on ERROR
bash Tools/editorlock.sh acquire <Gun>
python Tools/guns/gun_import.py <handoff dir> Tools/guns/<gun>/plan.json          # stages assets,sockets,rows,hands,export,verify
python Tools/guns/gun_import.py <handoff dir> <plan> --stages icon-start          # then wait for "icons.bake: done" in the log
python Tools/guns/gun_import.py <handoff dir> <plan> --stages icon-import
bash Tools/guns/verify_gun.sh Tools/guns/<gun>/plan.json [tour flash inventory pickup]   # one PIE pass -> review/verify_<hhmm>/sheet.jpg
bash Tools/editorlock.sh release <Gun>
```
- `handoff_check.py` (+ `bl_fbx_load.py`, `bl_gun_measure.py`, Blender 4.0 headless): finds the newest-revision runtime FBX / parts / textures, mesh_qc per runtime mesh with exit codes (a floating shell that is a declared moving part inside the frame, e.g. the bolt, is downgraded to WARN), names = files, identity pivots, Body + Pump at rest == Full vertex for vertex, parts at rest inside Full, texture sanity. Then MEASURES every socket of the plan on the mesh in the game frame (ray casts; recipes for Muzzle ring, bead/post FrontSight, sight-line Aim, fore-end Pump_Socket / LeftHandSocket / GripCyl_L, wrist GripCyl_R, trigger face, bolt face / Chamber, ejection port, loading port, butt pad Stock, safety, action release), the pump travel (bolt face back past the port's rear edge) and the hand-pose re-seat from the replaced gun (`Tools/Hands/src/weapons/<old>.fbx` + sockets). Writes `<gun>/sockets_measured.json`, `<gun>/handoff_check.json`.
- `gun_import.py` (host half sends itself over Remote Control, one RC call per stage; plan.json `import` section drives it): backup + `live_before.json`, meshes (Import Normals, combine, no Nanite), split-part slots realigned to the item mesh, UE LOD reduction (`import.lod_percent`), V-HACD pickup hulls, textures, shared master `/Game/Weapons/Shared/M_Gun_PBR` (BaseColor / Normal / ORM / Specular; created once) + `MI_<Gun>_<Family>`, sockets with a frame proof (UE bounds == measured bounds), item row + the BP's stats row updated in place and read back, placeholder `HP_*` poses duplicated from the replaced gun, Grip Workshop export, `work/ue_import.json`, icon bake for the one row.
- `verify_gun.sh` (+ `verify_tour.txt`, `pie_ops.py`, `contact_sheet.py`, `editor_window.ps1`): backs up and restores Saved/SaveGames (byte-compared), unthrottles the editor and shows a minimized editor without focus for the pass (both restored), runs the tour (hip, ADS + `lns.ads.check`, fire burst, shell reload burst, third person), the flash frames (`lns.recoil.capture`), the bag (icon), firecheck (flash distance from Muzzle, meshes drawn), drop + row-id spawn (pickup meshes). Burst frames are whole-window captures: the sheet crops them on the viewport's blue top line.

## 10. Lessons log (append: date: symptom -> cause -> rule)
- 2026-10-22: pipeline written after three guns; premortem table above is the starting log.
- 2026-10-22 (Codex, M590 modelling; in its game-asset-efficiency skill too):
  1. Split the build into material, camera, bake and export stages, and rerun only the stages a change affects.
  2. Run UV-overlap, checker and per-face material-family checks BEFORE baking. Clearing a slot reset face indices once.
  3. Lock one rig, one exposure and the exact comparison crops on day one.
  4. Solve cameras on off-axis rigid points, with the stock extremities held out.
  5. Preflight Blender, exit codes, job slots and the runtime contract once, then reuse the helpers.
  6. Agree the quality stop point up front, keep the export checks, and drop repeated unchanged tests and extra beauty renders.
- 2026-10-22 (M590 import, Claude):
  1. The pump FBX's slots came Wood, Barrel, Metal; the item mesh's Wood, Rubber, Metal, Barrel. `MakeSplitPart` copies the item mesh's materials BY INDEX -> gun_import realigns split-part slots to the item mesh's order.
  2. Bead gun ADS: an Aim line grazing the bead TOP hid the bead behind the receiver -> the eye-to-bead-BASE line must clear the whole top profile (on the M590 the heat shield binds, Aim sits 0.59 cm over the receiver).
  3. mesh_qc flagged the bolt floating inside the receiver (a moving part, 6.9 mm clear) -> handoff_check downgrades declared moving parts enclosed by the frame; any other floating shell stays an ERROR.
  4. `rc.py cmd` runs a console command in the EDITOR world, and console args split on spaces (a path under "Unreal Projects" broke `lns.live <path>`) -> PIE commands go through `pie_ops.py cmd`; tours use the default `Saved/live.txt`.
  5. A minimized editor draws no viewport ("Slate could not draw the viewport's window": no shots) and PIE drops to ~3 fps with the background throttle -> verify_gun.sh shows the window without focus and sets `bThrottleCPUWhenNotForeground` off for the pass, restoring both.
  6. Tour `burst` frames are whole-editor-window captures (FScreenshotRequest), and the first one can show the editor world -> crop on the viewport's blue top line; image-match and frame-difference crops locked onto the wrong place.
  7. MSYS process substitution keeps Python's `\r` even through `tr`, and Python text-mode writes put CRLF into .sh files -> `${v%$'\r'}` after `read`; write scripts in binary or newline=''.
  8. The editor crashed 30 s after a PIE teardown on a package another session had force-deleted hours earlier (`/Game/Anim/_GWTest/A_Consume_Smoke_Cigarette`, "Failed to unload all packages during ForceDeleteObjects") -> never ForceDelete in the session that created or used the asset; leave scratch assets for after a restart and list them.
  9. The icon bake writes its PNG into Saved/SaveGames/ItemIcons -> bake BEFORE the SaveGames backup of the PIE pass.
- 2026-10-22 (M590 rough anims + shell batch reload, Claude):
  1. The Tools/Hands/src/weapons/<old gun>_sockets.json was stale (HandPose_R 9 cm off the live socket); the hip pose json matched the live sockets to 0.03 cm -> seed a new gun's hold from pose_<old>_hip.json + the NEW gun's live HandPose sockets, and check it against the live export.
  2. Two keys across a 200 deg forearm turn (supinated pump grip -> pronated shell grip) flip the wrist the short way -> borrow the old clip's in-between arms, and start contact keys from the old clip's arm at that moment (place_arm keeps its swivel and roll).
  3. The old shotgun clips turn the forearm 60-80 deg per frame -> a replacement clip's check gate is the old clip's own speed +10 % (reload_keys.source_gate), else Send refuses every rough clip.
  4. Chained phase clips meet on one pose ("Ready to load") -> give it ONE source (one function) and unique key names per clip (markers are matched by name: two "Ready to load" keys collapsed onto one frame).
  5. Python text-mode read + write turned CRLF sources into LF (whole-file diffs) -> read and write C++/py in binary (or newline='') and keep the file's own line ending.
  6. A PIE reload test emptied the gun's Ammo slot (lns.give only fills the bag) -> verify_gun.sh reload stage installs a fresh ammo stack in the slot (pie_ops shells) after equipping.
  7. In game the recoil kick lifts the gun off the rack clip's left hand right after a shot (the old rack clip did the same) -> judge rack contacts on the dry-reload rack (EndEmpty), not right after a shot.
  8. "The shotgun stops reloading after a couple of reloads" (user, same day) was not a stuck flag: the verify's 3 reloads always ran on a fresh 40-shell Ammo slot (lesson 6), while the user's slot held 6 and a tube reload never took the 84 slugs in the bag -> tube guns now load carried rounds once the slot is dry (`LoadRoundsFromCarried`); the verify reload stage loops 8+ cycles with interrupts (fire, sprint, ADS, inventory, holster, nearly out) and runs one pass with the slot EMPTY and shells only in the bag, and the user's own PIE session in Saved/Logs is read before guessing.
