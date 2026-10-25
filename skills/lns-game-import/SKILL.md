---
name: lns-game-import
description: Exactly how to bring work into the LootNShoot game - first-person animation clips (reloads, racks, bolt cycles, charging, equip, consumables) from Blender FBX into /Game/Anim with their notifies, wiring clips and meshes to item / weapon-stats data-table rows, importing a new gun, and baking inventory icons in the icon studio. Covers the game's animation contract (skeleton, FBX settings, event names, which hand carries the gun, start and end on the hold, how magazines, rounds, pumps and bolts move), editor access (lock, Remote Control, headless, backups, never package), the exact commands, the verify pass and the known gaps that need C++. Use it before authoring a clip meant for the game, before importing any clip, gun or icon into LootNShoot, and when handing such work between Claude and Codex.
---

# LNS game import: clips, guns, icons

Repo: `<repo>` (run every command below from there). UE 5.5 at `D:\UnrealEngine\EngineApp\UE_5.5`.
Deeper references: `Docs/AnimationContract.md` (the clip rulebook), `.claude/skills/gun-pipeline/SKILL.md` (new guns end to end),
`Docs/ITEM_PIPELINE.md` (item rows + icons), `Docs/WeaponHoldSystem.md` (holds, grips, sockets).

## 0. Hard rules
- **One editor driver at a time.** `bash Tools/editorlock.sh acquire <Name>` before any editor write or PIE, `release <Name>` after
  (or `bash Tools/editorlock.sh run <Name> <command...>`). Read-only queries need no lock.
- **Never package or cook.** The user packages. Never run a full build either; C++ belongs to Claude.
- **Never force-delete, never delete-then-reimport** (deleting a clip nulls every data-table reference to it). The scripts reimport in place.
- **Back up before overwriting.** The scripts below do it; by hand, copy the `.uasset` to `Saved/AssetBackups/<What>_<stamp>/` first.
- **The editor may be the user's.** Before writing, check no PIE and nothing unsaved (section 1); if either, stop and wait, do not save their work.
- **PIE:** drive only a PIE session you started. At every step read new `Command not recognized: <text>` lines in `Saved/Logs/LootNShoot.log`:
  they are the user's notes typed into the dev console and they override your plan ("i think its good" = stop testing).
- **Private refs** (photos, scans, manuals) never go into `Content/`, a commit or a package.
- Never write the user's open Blender files (the Grip Workshop scene, `Weapon_Grip_Polish.blend`). Never touch ConeCrushers.
- **90-95 % is done.** One verify pass, report the top 3 issues, move on.
- **Codex:** report with `python Tools/agent_mail/to_claude.py "<subject>" "<message>"`. Anything that needs C++ or a new runtime
  mechanism (section 2.4 gaps): stop and mail Claude; never edit `Source/`.

## 1. Editor access
| Need | Command |
|---|---|
| Editor up? | `python Saved/rc.py stmt "print('up')"` -> `RESULT ok=True` (Remote Control, port 30010; the user's launch has `-RCWebControlEnable`) |
| Safe to write? | `python Saved/rc.py stmt "import unreal; E=unreal.EditorLoadingAndSavingUtils; print('PIE', bool(unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem).get_game_world()), 'DIRTY', [p.get_name() for p in list(E.get_dirty_content_packages())+list(E.get_dirty_map_packages())])"` -> must print `PIE False DIRTY []` |
| Run an editor script | `bash Saved/uesave.sh <script.py> "<grep pattern>"` (refuses while a `-game` instance runs: saves would fail silently) |
| Editor NOT running | headless, PowerShell only (Git Bash mangles `/Game/` args): `& "D:\UnrealEngine\EngineApp\UE_5.5\Engine\Binaries\Win64\UnrealEditor-Cmd.exe" "<repo>\LootNShoot.uproject" -run=pythonscript "-script=<script.py>" -unattended -nop4 -nosplash -NullRHI -stdout -FullStdOutLogOutput *> <log>` (imports and row edits only; no PIE, no icons). Never while an editor has the project open. |
| Log | `Saved/Logs/LootNShoot.log` |

## 2. Animation contract (what the game actually consumes)
### 2.1 The file
| Item | Rule |
|---|---|
| Skeleton | `1SK_Mannequin` (body `SKM_Manny_Simple`). Author on `Tools/Anim/template_fp.blend` (Manny + the game's FP camera: `head` socket, 15 cm forward, 90 FOV). |
| Units / frame | cm (no 0.01 wrapper, never apply scale), 30 fps. UE (x, y, z) = Blender (x, -y, z). Guns: +Y muzzle, +X the gun's left, +Z up. |
| FBX | one clip per file, armature only: `apply_scale_options='FBX_SCALE_NONE', axis_forward='-Y', axis_up='Z', armature_nodetype='NULL', add_leaf_bones=False, bake_anim=True, use_armature_deform_only=True, object_types={'ARMATURE'}, path_mode='STRIP'`. |
| Keys | gun clips key `spine_02` and up only (pelvis / legs unkeyed: the lower body is locomotion). No camera or look direction baked in. |
| Name | `A_Weapon_<Verb>_<Gun>` (Verb: Reload, Rack, Equip, Unequip, ShellStart, ShellIn, ShellEnd, ShellEnd_Empty). FBX file name == asset name. |
| Path | gun clips MUST land in `/Game/Anim/Weapon/`: that path marks a clip hold-matched (it owns the arms and the gun rides the hand). |
| Events | `<Asset>.events.json` next to the FBX: `{"fps": 30, "events": [{"frame": 13, "name": "MagOut"}, ...]}`, frame 0 = the FBX's first frame. |
| Start / end | first and last frame = the gun's in-game hold, every upper bone within 1 cm / 2 deg, or the montage blend pops. |

### 2.2 Who carries the gun (WeaponRigComponent, during equip / reload / rack)
The weapon is attached RIGIDLY to a hand bone for the whole clip:
- `hand_r`, at the gun's right-grip frame, for every clip, except
- `hand_l`, at the support-grip frame, for a **bolt gun's rack clip** (Action3 on a gun with BoltMesh / BoltBodyMesh).

So: in your clip the weapon must not move relative to the carrying hand (gate: 0.1 cm / 0.2 deg on every frame). A separately animated
weapon-root track is ignored; the carrying hand IS the weapon root. Deliver in the manifest `gun_in_hand_r` (and for a bolt rack
`gun_in_hand_l`): the weapon root in that hand bone's frame at frame 0, UE axes, cm, quat xyzw. Claude sets the gun's `HandPose_R` /
`HandPose_L` sockets from it so the in-game hold equals your clip's first frame.

### 2.3 Moving parts are driven by the game, not by FBX prop tracks
Prop / root track JSONs (`*.props.json`) are review data only. The game moves parts like this:
| Part | Mechanism | Events | Data (row / mesh) |
|---|---|---|---|
| Magazine | MagOut: the weapon's mag hides and a copy rides `hand_l` through the MAGAZINE mesh's `HandPose_L` socket; MagGrab: old one dropped (physics), a fresh one in the hand; MagIn: prop gone, weapon mag shown | MagOut, MagGrab, MagIn, ReloadEnd | mag rigid to `hand_l` from MagOut to MagIn; deliver `mag_in_hand_l` (mag pivot in the hand_l frame) -> the mag mesh's `HandPose_L` |
| Single round / shell | ShellGrab: the round spawns rigid to `hand_l` (round mesh `HandPose_L`); ShellIn: round gone, one loaded | ShellGrab, ShellIn | stats `shellPropMesh` |
| Batch shells (M590) | the hand takes N shells, inserts one at a time | ShellsGrabbed, ShellInserted | stats `shellReloadStart/Insert/End/EndEmpty` |
| Pump, or a charging handle worked by the LEFT hand | `PumpMesh` (+ `PumpBodyMesh` = the gun without it) at `Pump_Socket`, slides along `PumpAxis` following `hand_l`, clamped to `PumpTravel` | PumpStart (fingers closed) .. PumpEnd (released); an Action3 rack clip follows for its whole length; Rack = rack complete | stats `pumpMesh`, `pumpBodyMesh`, `pumpAxis`, `pumpTravel`, `bUseProceduralPump` false |
| Bolt worked by the RIGHT hand | `BoltMesh` (pivot = bolt rear face) at `Bolt_Socket`; the knob is taken into `hand_r` at BoltGrab; lift = knob turn about +Y (0..BoltLift deg), stroke = travel back (0..BoltTravel cm) | BoltGrab .. BoltLocked; BoltRelease = rack complete | stats `boltMesh`, `boltBodyMesh`, `boltKnob`, `boltLift`, `boltTravel` |

**Event names the importer knows** (`Tools/Anim/qa/ue_import_clips.py`, NOTIFY): MagOut, MagGrab, MagIn, ReloadEnd (the reload completes:
ammo moves), Rack / BoltRelease (rack completes), ShellGrab, ShellIn, ShellsGrabbed, ShellInserted, PumpStart, PumpEnd, BoltGrab,
BoltLocked, ActionFinished (equip / unequip / generic action end), UseItemStart, UseItemEnd, ItemGone, ItemDrop (consumables),
ComboWindowOpen/Close, HitStart/HitEnd (melee), FootL/FootR. Anything else (BoltBack, ...) is skipped and listed as `skipped`.
Reference sets: mag reload = MagOut, MagGrab, MagIn, ReloadEnd (`A_Weapon_Reload_Pistol_Tactical`); pump rack = Rack, PumpEnd;
equip / unequip = ActionFinished. Keep every event at least half a frame inside the clip (an event ON the last frame is dropped).

### 2.3b Mechanism: slide / bolt cycle, lock-back, spent casings (2026-10-24, Glock pilot da86742)
Stats row field `mechanism` (FWeaponMechanism, `Source/LootNShoot/WeaponDataTable.h`); set it with `ue_row_set.py` (`stats_of`).
| Field | Meaning (Glock17 values) |
|---|---|
| `cyclePart` | the installed attachment slot that cycles (`Upper` = the Glock slide); `None` = nothing moves |
| `cycleMesh`, `cycleBodyMesh`, `cycleSocket` | OR a part cut out of the gun (AR-15 bolt carrier, MAC-10 bolt + knob): `cycleMesh` rests at `cycleSocket` (default `Cycle_Socket`) on its host = the installed `cyclePart` mesh, or the item mesh when `cyclePart` is None. Optional `cycleBodyMesh` = the host without the part (the host then stops drawing, like a split pump gun); leave it empty when the part only shows through a port. Both use the host's material slots |
| `bOpenBolt` | open bolt (MAC-10): rests BACK, runs forward to fire and back, the casing leaves as it returns; with `bLockBackOnEmpty` the last round leaves it FORWARD until `SlideRelease` (put that on the charging pull) |
| `cycleAxis`, `cycleTravel` | rearward direction in the part's frame (0,-1,0) and travel cm (3.4) |
| `cycleRearTime`, `cycleReturnTime` | s to the rear and back (0.025 / 0.055); the runtime shrinks both to fit 60/RPM at full auto |
| `bLockBackOnEmpty`, `releaseTime` | the last round holds it back; released by the reload's `SlideRelease` event (else when rounds are back) |
| `casingMesh`, `casingScale` | spent casing mesh + scale (`/Game/FX/Gun_VFX/Models/SM_Pistol_Shell` x0.1 = a real 19 mm case; placeholder) |
| `casingVelocity`, `casingSpread`, `casingSpin` | launch cm/s in the EjectionSocket frame (X out of the port) (330, 40, 160), spread 0.2, tumble deg/s |
| `casingRotation` | the casing in the socket frame at launch (yaw 90 = its long X axis along the bore) |
| `casingLife`, `casingSound` | seconds on the ground (12); landing sound (none yet: no asset, never download one) |
How it renders: the installed part keeps its sockets at rest and stops drawing; a copy moves (so sight / port / hand sockets never shake).
Manual actions (fire mode Pump / Bolt, or `bRequiresRackingBetweenShots`): nothing cycles on the shot; the fired case stays in the chamber and
leaves when the hand's pump / bolt stroke passes 80 % of its travel (split pump / bolt part), or when the rack completes (no split part).
So an M590 / Kar98k row only needs the casing fields; the pump / bolt parts already move with the hand.
More cycle sources (2026-10-24): `bCycleUsesSplitPart` = the gun's split pump / bolt part IS the cycle part (MAC-10 bolt + knob; the hand
still drives it inside a rack); `bChargeAfterEmptyReload` = an empty reload auto-plays the rack and only the completed rack releases the
part. AR-15: `cyclePart Upper` + `cycleMesh SM_AR15_BCG` + `cycleBodyMesh SM_AR15_UpperBody` (dust cover modelled open) at the Upper's
`Cycle_Socket` (identity; Tools/bpy/ar15/ar15_split_bcg.py splits the game Upper by its BCG slot, no re-bake).
Single-round reloads (Kar98k, 2026-10-24): the shell-reload clips (Start / Insert / End / EndEmpty, no Grab clip) on a BOLT gun (split bolt
part) are carried by the LEFT hand (the right one feeds rounds); the round in hand is drawn on `hand_r` through the prop's `HandPose_R`
socket; `ShellsGrabbed` inside an Insert clip takes ONE round; a bolt follow window (BoltGrab..BoltLocked) that closes with the bolt
>= 80 % back leaves it held OPEN until the next BoltGrab, which takes the knob where it is. Clips: Tools/guns/kar98k/load/splice_reload.py
(rack + approved loading pilot), prop SM_Round_792x57 (build_round.py).
Casings: `ULNSCasingSubsystem` (pooled 40, trace + bounce + settle), thrown at the cycle's rearmost point, replacing ShellEjectionFX.
Reload clips: put `SlideRelease` on the key where the thumb drops the slide stop (Glock: 'Gun down', just after MagIn). A clip that
already holds the user's polish is patched IN PLACE with `Tools/guns/mech/ue_add_slide_release.py` (request
`Saved/guns/slide_release_request.json` {asset, time}), and the event is added to the Grip Workshop clip's keys.json + events.json too.
Verify: `bash Tools/guns/mech/mech_verify.sh <plan with "spare": {magazine, ammo}> tour` with `MECH_TOUR=` one of
`Tools/guns/mech/glock_mech_tour_v3.txt` (first person: `lns.recoil.capture <tag> <s>` = one round + a frame N s later) /
`glock_mech_tour_v4.txt` (side camera `orbit dist pitch yaw zoff fov`, casing in the air, slide locked from the side). Debug cvars:
`lns.mech.hold <0..1>` (pins every cycle part), `lns.casing.debug 1` (logs throws / settles). Read the frames at full size, zoomed.
Harness traps (2026-10-24): `burst` frames are whole-window grabs and can catch an editor view (sky + black): use `lns.recoil.capture`
/ `lns.ui.shot`; `lns.live` waits and its 0.5 s step gap run on GAME time (under `slomo 0.02` one step = 25 s real: timeouts).

### 2.4 Known gaps (need C++ from Claude; mail before authoring around them)
- No hold-open state: when a follow window closes the part returns to rest. An open-bolt gun that "ends rearward" (MAC-10 charge) or a
  rifle loaded with its bolt open (Kar98k single load) shows the part snapping home.
- A shell / round reload is always carried by `hand_r`: a clip where the right hand loads rounds while the left holds the rifle needs a
  new carry mode.
- Mechanism: observers' lock-back ends on the next shot or SlideRelease (not replicated as state).
- A rack (Action3) plays on its own only for pump / bolt fire modes or `bRequiresRackingBetweenShots` guns (`OnReloadComplete`): a
  full-auto gun's charge clip (MAC-10) is wired but not yet played after a dry reload.
- `Tools/guns/gun_import.py` is proven on a pump gun (M590) that REPLACES a row, with ONE texture set and handoff_check's shotgun socket
  recipes. A new gun with its own row, several texture sets or a supplied sockets file follows 4b (scripts per gun in `Tools/guns/<gun>/`).

## 3. Import a clip (exact steps)
1. **Stage** the drop in your own folder: `Tools/Anim/<folder>/out/<Asset>.fbx` + `<Asset>.events.json` (Codex: `folder` = `codex`).
2. **Pre-flight in Blender** (your own script; refuse on any fail): 30 fps; carrier-hand rigidity (2.2); first / last frame on the hold;
   event names from 2.3, frames inside the clip; the mag / round rigid to `hand_l` between its grab and insert events.
3. **Request** (one file, per run; keep the previous one as `.prev`): `Tools/Anim/qa/import_request.json`
   `{"domains": [{"folder": "codex", "domain": "Weapon"}], "only": ["A_Weapon_Reload_MAC10"]}`
4. **Back up** a clip you are replacing: copy `Content/Anim/Weapon/<Asset>.uasset` to `Saved/AssetBackups/Clip_<Asset>_<stamp>/`.
5. **Import:** `bash Tools/editorlock.sh run <Name> bash Saved/uesave.sh Tools/Anim/qa/ue_import_clips.py "CLIPS"`
   Expect `CLIPS IMPORT /Game/Anim/Weapon/<Asset> <- <file> frames N tracks T notifies [...] skipped [] saved True`, then `CLIPS DONE`.
   `IMPORT FAILED` / `RENAME FAILED` / `CONSOLIDATE FAILED` / a non-empty `skipped`: stop, fix the source, re-run. Re-runs replace the
   notifies (never stack) and keep every data-table reference.
6. **Wire the row** with `Tools/Anim/qa/ue_row_set.py` (dry run first). Request `Saved/anim_import/row_request.json`:
   ```json
   {"apply": false, "edits": [
     {"table": "/Game/A_Inventory/DataTables/DT_Weapons", "row": "<Row>", "set": {"itemAnimations.action2Anim": "/Game/Anim/Weapon/A_Weapon_Reload_MAC10"}},
     {"stats_of": "<Row>", "set": {"pumpTravel": 6.5}}]}
   ```
   `bash Saved/uesave.sh Tools/Anim/qa/ue_row_set.py "ROWSET"` prints `field: before -> after`; read it, set `"apply": true`, run again.
   `<Row>` comes from the gun's plan.json (`import.item_row.row`); never guess a row: "SMG" is the UMP45, "Kedr" the Vector.
   It refuses unknown fields / rows / missing assets before writing, backs the tables up (`Saved/AssetBackups/RowSet_<stamp>/`), reads
   every field back and does not save on a mismatch. It never creates rows.
   Slots (`DT_Weapons` row `itemAnimations`): `idleAnim` hold, `equipAnim`, `unequipAnim`, `action2Anim` = THE reload (one clip for
   tactical and empty: `reloadEmptyAnim` is retired, leave it None), `action3Anim` = rack / bolt cycle / charge. Shell guns: the stats
   row (`stats_of`) `shellReloadStart`, `shellReloadInsert`, `shellReloadEnd`, `shellReloadEndEmpty`, `shellPropMesh`.
7. **Verify in game, once:** `bash Tools/guns/verify_gun.sh <plan.json> tour` (hip, ADS, fire, reload burst, third person -> one
   `review/verify_<hhmm>/sheet.jpg`; saves backed up and restored). A clip on an existing gun needs only a minimal plan:
   `{"gun": "<Gun>", "import": {"verify_row": "<Row>", "item_row": {"row": "<Row>"}}, "data": {"ammo": ["<DT_Ammo row>"]}}`.
   Read the sheet at full size: hands on the gun, mag / round in the fingers, no pop at start or end, the part moving with the hand.
8. **Report** the asset paths, the row diff and the sheet path (Codex: mailbox).

### 3b. Hand poses (HP_*) and HandPose sockets into the game
The in-game hold = the rig places the gun (BP `rig_profile`: `HipOffset` / `HipRotation` in camera space, X fwd / Y right / Z up, cm)
and the hands solve onto the gun's `HandPose_R` / `HandPose_L` with finger shapes from `/Game/Hands/Poses/HP_<Mesh>_R|L|RFire|RWrap`
(+ `HP_Hip_<Mesh>`, the hip upper body). Live preview in your own PIE: `lns.rig.hip "x y z"`, `lns.rig.hiprot "p y r"`.
- Format = the Grip Workshop's Send-to-game folder (example `Tools/Hands/manual/send/20261021T194827_pose/`): `export_manifest.json`
  (`exports` [{name, side}], `sockets` [{mesh, socket, matrix_blender}]) + one single-pose FBX per `HP_*` name.
- Install (lock held, no PIE, nothing dirty), request `{"op": "static", "dir": "<folder>"}`:
  `python Saved/rc.py stmt "import runpy; runpy.run_path(r'<repo>/Tools/Hands/manual/tool/ue_send_to_game.py', init_globals={'LNS_SEND_REQUEST': r'<request.json>'}, run_name='__lns_send__')"`
  -> one `LNS_SEND_RESULT {json}` line; it backs up what it replaces (`Saved/AssetBackups/WorkshopSend_<ts>/`).
- One master grip frame drives everything: HandPose socket, HP_* poses, the BP hip, and the first / last frames of every clip of
  that gun (user 2026-10-24: "use that frame for the other anims"). Trigger hand standard: high grip, three fingers wrapped, thumb
  across, index extended with its pad on the trigger (it leads the pose), wrist under 15 deg.

## 4. Import a gun (summary; the full stage list and premortem is gun-pipeline)
1. `Tools/guns/<gun>/plan.json` (copy `Tools/guns/m590/plan.json`): row it replaces or adds, runtime meshes, moving parts, sockets,
   materials, budget, data (ammo, capacity, recoil), anims.
2. Hand-off: runtime FBX (+ split parts at rest), textures, `sockets.json`. Check with no editor:
   `python Tools/guns/handoff_check.py <handoff dir> Tools/guns/<gun>/plan.json` (exit 1 = fix first; writes `sockets_measured.json`).
3. Import (lock held, editor up): `python Tools/guns/gun_import.py <handoff dir> Tools/guns/<gun>/plan.json` (stages assets, sockets,
   rows, hands, export, verify; re-run one with `--stages rows`). Backups + `live_before.json` land in `Saved/AssetBackups/<GUN>_<stamp>/`.
4. Icon: `--stages icon-start`, wait for `icons.bake: done` in the log, then `--stages icon-import`.
5. `bash Tools/guns/verify_gun.sh Tools/guns/<gun>/plan.json` (tour flash inventory pickup), fix only what fails, re-run that stage.
Then rough clips (section 3) and the user polishes the grips in the Grip Workshop (`Tools/Hands/manual`); agents never polish hands.

### 4b. A new gun with its own row (AR-15 2026-10-17, MAC-10 2026-10-24)
Never overwrite an existing gun's row, Blueprint or stats row unless the user said "replaces". Worked example: `Saved/items/ar15/`.
Template data for the closest existing gun (rows, Blueprint, stats, magazine rows, sockets, pose names): dump it first, e.g.
`Tools/guns/mac10/work/dump_templates.py` -> `templates.json`.
1. **Meshes** into `/Game/Weapons/<Gun>/`: Import Normals, combine, no Nanite, `auto_generate_collision` True when the FBX carries
   `UCX_` hulls (False drops them). Split parts (`<Gun>_Pump` / `_PumpBody`, `_Bolt` / `_BoltBody`): material slots in the item mesh's
   order (the runtime copies the item mesh's materials BY INDEX; gun_import's `assets` stage has the realign code). LODs by UE reduction
   [1, 0.45, 0.18] unless LOD FBXs are supplied.
2. **Textures / materials:** per set `T_<Gun>_<Set>_<Map>`: BaseColor sRGB default, ORM linear Masks, Normal Normalmap + flip green;
   one `MI_<Gun>_<Set>` per set on the shared master `/Game/Weapons/Shared/M_Gun_PBR` (exists: never recreate), Specular 0.5.
3. **Sockets** on the item mesh from the supplied sockets file (rotations as `unreal.Rotator(pitch=, yaw=, roll=)` KEYWORDS: positional
   order is a trap) plus `Chamber`, `Eye` (7.5 cm behind `Aim`), `Butt`; `HandPose_R` / `HandPose_L` = the clip's inverse
   gun-in-hand. The magazine mesh carries its own `HandPose_L` (mag in hand_l). Read every socket back.
4. **Stats row** `DT_WeaponsData.<WeaponId>` = the template gun's stats row + your fields with a one-line reason each
   (`Saved/items/ar15/weaponsdata_ar15.json`); split parts go here (`pumpMesh`, `pumpBodyMesh`, `pumpAxis`, `pumpTravel`,
   `bUseProceduralPump` false, or the bolt fields).
5. **Blueprint** `/Game/A_Inventory/Equipment/Weapons/Guns/BP_Weapon_<Gun>`, child of `BP_Weapon_Firearm`: `weapon_id`, the socket name
   properties, `weapon_stats_table`, `weapon_mesh`, and the template gun's `rig_profile` ONLY when the Blueprint is created
   (`Saved/items/ar15/ar15_weapon_setup.py`).
6. **Item + magazine rows** through the item pipeline (`Docs/ITEM_PIPELINE.md`): a spec `Saved/items/specs/<NNN>_<gun>.json` with
   `template` = the closest gun / magazine row, run by `Saved/items/run_spec.py` (edit its `SPEC`). Weapon row: `equippedActorClass` =
   your Blueprint, `magazine` (capacity, ammo ids), `attachmentSlots` (Magazine at `MagazineSocket` with the default magazine row).
   Magazine row: `attachmentData` + `magazineData.compatibleWeaponIds` = [your row]. Vendor: `Saved/items/ar15/ar15_vendor.py` pattern.
7. **Hand poses:** duplicate the template gun's `HP_<Mesh>_R/L/RFire/RWrap` + `HP_Hip_<Mesh>` under your mesh name (placeholders the user
   polishes); Grip Workshop source export of the item mesh + sockets to `Tools/Hands/src/weapons/` (gun_import `export` stage code).
8. Clips (section 3), icons (section 5), one verify pass (`Tools/guns/<gun>/plan.json` minimal + `verify_gun.sh`).

## 5. Icon studio (inventory icons)
- Icons are studio renders: `/Game/Textures/Items/Generated/T_<Row>` (a row name shared by two tables: `T_<Table>_<Row>`). Hand-made
  icons (`/Game/Textures/Items/T_*`) are never re-baked.
- Framing is automatic (`AIconStudioActor`): long guns side-on and level, muzzle right / stock left, padded to the tile; the image is
  baked for the unrotated footprint (`gridSize`, ~11 cm a cell). A bad pose or crop is fixed per row in
  `Tools/IconStudio/icon_overrides.json` (`cam_pitch`, `cam_yaw`, `mesh_yaw/pitch/roll`, `padding`, `exposure`, `largest_blob`), never
  by moving the mesh.
- Rebake (editor up, no PIE, lock held):
  1. Write `Saved/items/icon_rebake_only.txt` with exactly your rows, one `Table|Row` per line (`DT_Weapons|<Row>`). Without this file
     the bake redoes EVERY generated icon.
  2. `python Saved/rc.py file "<repo>/Saved/items/icon_rebake_start.py"` (opens
     `L_IconStudio`, starts `lns.icons.bake`), wait for `icons.bake: done` in the log.
  3. `python Saved/rc.py file "<repo>/Saved/items/icon_rebake_import.py"` (imports `Saved/SaveGames/ItemIcons/Base_<Row>.png` over
     `T_<Row>`, points the rows at it, reopens CortlandtStation). Delete `icon_rebake_only.txt` afterwards.
  4. Look at the PNG at full size: whole item in frame, sharp edge (no light rim), not stubby, stock left.
- A gun's icon comes from `gun_import.py --stages icon-start` / `icon-import` (same bake, that row only).
- Bake BEFORE a PIE pass that backs up `Saved/SaveGames` (the PNGs land there).

## 6. Lessons (append: date: symptom -> cause -> rule)
- 2026-09-28: re-imported clips lost every data-table reference -> the importer deleted the asset first -> reimport in place only.
- 2026-09-28: reloads fired every notify twice -> re-imports stacked notifies -> the importer clears the Events track first.
- 2026-09-30: a melee re-import landed on `<take>_Anim_Scene12` and the old asset stayed live -> `destination_name` = the target asset.
- 2026-10-22: the AR-15 played the M4's empty reload -> clips shared through a stats row -> anims live on the ITEM row (`itemAnimations`).
- 2026-10-22: an agent re-ran a reload test ~100 times after the user typed "i think its good" in the console -> read the console notes.
- 2026-10-24 (MAC-10, Codex's first full import; Codex's notes):
  - Relative `rc.py file Tools/...` paths resolved under Engine/Binaries/Win64 -> rc.py now sends an existing relative path absolute;
    absolute script paths stay the reproducible form.
  - A successful `MKEditorLib.data_table_upsert_row_json` returned an empty / falsy value -> judge success by the row read-back,
    never the return; canonicalize object references on both sides (class wrapper, `.Object` suffix) before comparing.
  - A loaded spare magazine "was missing" -> rounds live in `magazine_runtime_data.loaded_bullets`; `get_all_items()` covers only its own
    component, so also scan the equipped container components AutoAddItem uses. No `str(Guid)` identity compares. After a reload, assert
    the held gun's `current_magazine` count / capacity (MAC-10: 32/32).
  - The verify tour continued after `RESULT ok=False` -> wrappers turn that line into a nonzero exit, propagate pipeline failures and
    always stop their own PIE and restore saves on EXIT (`Tools/guns/mac10/final_verify.sh`).
  - An `Eye` socket did not fix a blocked peep ADS -> `UWeaponRigComponent::SolveSightFrame` uses Aim / FrontSight plus
    `rig_profile.eye_relief`; back up, set, read back, then judge the ring + front-post image. MAC-10 peep: 7 cm (template 18 cm). Do not
    generalise the number to other sight types.
  - A reload swept too close to the lens -> measure the minimum camera-to-mesh-SURFACE distance every frame (not the root); ease the arc
    forward / down keeping grip, timing, prop rigidity and hold endpoints; re-run the FBX pre-flight. MAC-10: 12.1 cm reload / 12.7 cm
    rack, action origin inside 30-70 cm; report stock extents separately.
- 2026-10-24 (MAC-10 Grip Workshop): Blender 4.0 crashed in Codex's executor even with escalation, while Claude's shell ran it ->
  on this machine an authorized Claude session runs the headless 4.0 steps on copies, through jobslots, from Codex's exact command,
  log path and PASS criteria; never substitute 4.5 for workshop files. Stage first (capture, catalogue, clips, selftest, still, into a
  fresh stage dir), Codex reviews and installs with backups + hash readback (worked example: `Tools/guns/mac10/workshop/20261024T184354/`
  stage_mac10_workshop_v6.py + install_mac10_workshop_v2.py). Key names must be unique: `read_markers` maps names to frames, so a
  ReloadEnd key and the final hold both named "Back to ready" collided; use distinct labels and verify fitted -> opened -> marker
  readback frame/name pairs before export. The reload fitter could not insert a key between keys 3 frames apart (candidate range
  `range(k0+2, k1-1)`): MAC-10 uses min_key_spacing=1.
- 2026-10-24: Codex's first clips (MAC-10 / Kar98k polish 002) used UseItemStart / ActionFinished for reloads and BoltBack for racks ->
  the game completes a reload on ReloadEnd and a rack on Rack / BoltRelease; the event table in 2.3 is the only vocabulary.
