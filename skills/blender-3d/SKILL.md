---
name: blender-3d
description: Standards, quality gates and a lessons log for ANY Blender 3D work (weapons, props, vehicles, interiors, characters' gear, kitbash, exports to Unreal) in LootNShoot or ConeCrushers. Load it before modelling, before showing renders, and before exporting. Covers the mandatory mesh_qc gate (holes, flipped faces, z-fighting, UV overlap, floating parts, slivers), the reference "spot the difference" loop with a camera matched to the photo, export rules, and known mistakes with their fixes. Append new mistakes to the lessons log.
---

# Blender 3D: standards, gates, lessons

> **LootNShoot:** the full step-by-step workflow (stage gates, the Glock v4 scripts, exact export, bake and UE import settings) is the repo skill `.claude/skills/model-factory/SKILL.md`. Follow it for LootNShoot models; this skill holds the shared core.

The user judges by eye, at full resolution, against real references. Three Glock attempts were rejected for looking
blobby and wrong in ways a side-by-side would have shown. Nothing reaches the user until it has passed every gate below.

## 0. Ground rules
- **Run Blender headless:** `D:/Blender/blender.exe -b <file.blend> --python <script.py> -- <args>` (Blender 4.0).
  - Never drive the user's open Blender (the `mcp__blender` tools) unless the user asks for it.
  - Renders and bakes are heavy jobs: `bash Tools/jobslots.sh run <cmd>` (LootNShoot). The machine allows at most two heavy jobs.
- **Scripts are the source of truth.** Build from `.py` files kept beside the assets, so any pass can be rebuilt; never hand-edit a `.blend` you can't regenerate.
  - Save numbered progress blends.
  - Never overwrite another agent's folder or a user-approved asset.
  - Back up before replacing anything.
- **No logos, brand names, serials or engravings.** A blank roll-mark recess is fine.
- **Reference photos are private.** Never commit them, publish them or bake them into textures.
- Review renders at full size and crop the important areas with PIL. Thumbnails hide every defect that matters.

## 1. The pipeline (each step is a gate; don't skip ahead)
1. **Contract.** Real dimensions (cm), axes, pivot, sockets, names, triangle budget, material slots, texture sizes.
   - When replacing an asset, measure the old one first (bounds, pivot, sockets, hand-contact surfaces) and keep everything gameplay depends on within 1 mm.
   - Write `CONTRACT.json`.
2. **Reference pack.** The user's photos first, then the real dimensions.
   - **Lock the exact variant** (model, generation, configuration) and check every reference against it. The traced profile master must be that variant. List any other-variant reference's differing features and which source wins, before modelling.
   - Make an orthographic blueprint, or derive one from the photos.
   - List every visible feature, with counts: serrations, holes, pins, screws, panels, text recesses.
3. **Blockout.**
   - Orthographic renders at the blueprint's scale, overlaid at 50 % with PIL.
   - Proportions and silhouette must match before ANY detail work. Detail can't fix wrong proportions.
4. **Detail.** Real chamfers on every edge, support loops or bevel + weighted normals, enough segments on every curve that shows in silhouette.
5. **QC gate:** run `mesh_qc.py` (§2) until it reports zero ERRORs. Read every WARN and fix it or justify it in STATUS.
6. **Spot the difference** (§3) against every reference photo. Loop until the written difference list is empty.
7. **Materials, UVs, bakes**, then the QC gate again (UV checks matter now).
8. **Export** (§5), re-import into a clean scene and re-run QC on the re-imported file.
9. **In-engine check.** Import, then look at it in the game from the player's real viewpoint (for a held item, first person at hip and aimed). Engine lighting shows what Cycles hides.
10. **Lessons.** Every mistake the user or a gate caught goes into §7 before you report.

## 2. QC gate: `scripts/mesh_qc.py`
```
D:/Blender/blender.exe -b model.blend --python-exit-code 1 --python ~/.claude/skills/blender-3d/scripts/mesh_qc.py -- --json qc.json [--collection Game] [--budget 60000]
```
The exit status is the verdict: 0 = PASS, 1 = an ERROR or a script crash (`--python-exit-code 1`). Wrappers must keep that status; never pipe it away through grep.

**ERRORs:**
- zero-area faces, zero-length edges, loose vertices or edges;
- edges shared by 3+ faces;
- open boundaries (holes; the object isn't airtight);
- flipped or inside-out faces, negative scale;
- missing UVs, UV0 outside 0–1 (baked assets), UV overlap above 0.5 % per material, zero-area UV faces;
- coplanar same-facing faces of different shells (**z-fighting**);
- **floating parts**: shells touching nothing within 0.1 mm;
- going over the triangle budget.

**WARNs:**
- coincident (unwelded) vertices, unapplied scale;
- non-planar quads/n-gons (diagonal shading seams);
- sliver triangles (boolean debris, the "spike" look);
- mirrored UVs, texel density spread above 2.5×, empty material slots.

**Legitimate exceptions** are declared, never silently ignored:
- `--open A,B`, or the custom property `qc_open=True`, for cards, decals and floor plates that are one-sided by design;
- `--allow-float` for exploded views;
- `--uv-overlap-ok` for deliberately stacked or mirrored islands;
- `--uv-tile` for tiling materials.

**What "done" means:**
- **Airtight:** every solid part is a closed shell. Hidden faces against a wall are still closed unless declared open.
- **No floating:** every pin, screw, sight or panel is seated on or into its support.
- **No z-fighting:** layered detail is recessed or raised by at least 0.2 mm, or the hidden copy is deleted.
- Flush contact between opposite-facing faces is fine; mesh_qc doesn't flag it.

## 3. Spot the difference (mandatory whenever a reference image exists)
Comparing by eye from a different angle misses most differences. Rebuild the photo's camera, render from it, and compare pixel to pixel.

1. **Landmarks.**
   - Pick at least 6 landmarks spread over the whole object and visible in the photo: tips, corners, sight posts, muzzle, the bottom corners of the base. Avoid points on curves that the photo's perspective hides.
   - Mark each one in Blender as an Empty named `LM_<name>`, or give its world position or a vertex index.
   - Read its pixel position in the photo with PIL (origin top-left).
2. **Camera match:** `blender -b model.blend --python scripts/camera_match.py -- match.json` (format in the script docstring).
   - It solves rotation, position and focal length, creates `REFCAM_<view>` at the photo's resolution, and renders with a transparent background and an optional neutral studio rig.
   - RMS error must be under 1 % of the photo width. Otherwise a landmark is wrong; fix it, don't accept the camera.
   - The script enforces this: `CAM VERDICT FAIL` skips the render and exits 2 (`max_rms_pct`, `result` and `allow_unmatched` are in its docstring).
3. **Compare:** `python scripts/ref_compare.py photo.jpg render.png out_prefix [--crop x0,y0,x1,y1]`.
   - It produces a sheet: photo | render | 50 % overlay | difference map.
   - In the difference map, red = only in the photo, cyan = only in the render, white/orange = photo/render edges.
   - The silhouette IoU is reported for plain-background photos; aim for at least 0.97 on product shots.
   - The script enforces `--min-iou` (default 0.95): below it, it prints `COMPARE VERDICT FAIL` and exits 3.
   - Make cropped sheets for every important region, and always for the surfaces the player sees most.
4. **Write the difference list.** For each difference: feature, location, which way it is off, and by how much. Go through these categories every time:
   - silhouette and outline;
   - proportions and positions;
   - feature present or missing;
   - feature counts (serrations, holes, ribs);
   - feature shape;
   - edge treatment (bevel size);
   - surface finish and colour value;
   - texture pattern scale;
   - gaps and seams between parts.
5. **Fix every item**, re-render from the same cameras, and repeat until the list is empty.
   - Keep the sheets in `review/` with a pass number.
   - Show the user the final sheets, not just beauty shots.
6. **Materials.** Judge colour and roughness with a matched camera too. Black anodised or nDLC steel is near-black (linear base colour 0.03–0.05), not mid-grey. Polymer is matte black.

## 4. Modelling standards
- **Topology:**
  - quads on curved and deforming surfaces; n-gons only on flat, hidden faces;
  - no sliver triangles: after a boolean, apply it, merge by distance, dissolve degenerate faces, limited dissolve, re-run QC;
  - prefer modelling cuts over stacking booleans on curved n-gon surfaces.
- **Shading:** a Weighted Normal modifier (or custom normals) on hard-surface parts, auto-smooth around 30°, and bevels sized to the real part (0.2–0.5 mm on small steel parts, 0.5–1.5 mm on polymer).
- **Scale and transforms:** model at real size in metres (1 BU = 1 m = 100 UE units), apply rotation and scale, no negative scale, pivots exactly where the contract says.
- **UVs:** UV0 unique, non-overlapping, in 0–1, consistent texel density, 8–16 px padding at the target size, islands straightened on hard-surface parts. A lightmap UV1 only if the project bakes static lighting.
- **Materials:** named slots per surface family (e.g. `M_<Asset>_Slide`), in a stable order. Textures are BaseColor / ORM / Normal (DirectX green for UE).
- **Budgets and LODs:** follow the contract. Silhouette first: LOD0 detail goes where the camera looks.
- **Collision:** `UCX_<MeshName>_NN` convex hulls, one per convex region, for world pickups and props.

## 5. Export to Unreal (FBX)
- Axes and units come from the project contract.
  - **LootNShoot guns:** UE (x, y, z) = Blender (x, −y, z); +Y is the muzzle, +X the gun's left. See `Tools/bpy/ar15/INTEGRATION.md`.
  - **LootNShoot props:** +X forward, pivot at the bottom-centre on Z=0 (`Docs/BLENDER_PROP_BRIEF.md`).
- FBX settings: `apply_unit_scale=True`, `apply_scale_options='FBX_SCALE_NONE'`, the axis forward/up the contract names, mesh smoothing FACE, tangent space on, no leaf bones.
- Sockets are delivered as JSON, applied by a UE Python script. Don't rely on `SOCKET_` empties unless the project already does.
- **After import, verify in UE:**
  - bounds and pivot with `get_bounds()`;
  - sockets;
  - material slots;
  - LOD screen sizes;
  - collision (Interchange with `auto_generate_collision=False` drops `UCX_` hulls; see §7).

## 6. Project notes
- **LootNShoot:**
  - `Docs/ITEM_PIPELINE.md`: catalog-render every item mesh before naming it. A "vest" 8 cm tall is a buckle; `_visor`, `_Faceshield`, `_Belts` and `_Headset` meshes are loose parts, not wearables.
  - Hand poses are keyed by mesh name: renaming a gun mesh breaks them.
  - **New guns ship with their mechanics** (`Docs/GUN_MECHANICS_PLAN.md`, planned):
    - every moving part (slide, BCG, charging handle, bolt catch, dust cover, trigger, hammer, pump, bolt) is its own complete mesh, pivoted at its travel origin;
    - a mechanism JSON gives each part's axis, travel and limits;
    - the Grip Workshop generates the fire cycle, lock-back, reloads, rack and inspect;
    - a POV preview contact sheet per action, plus a montage video of all actions, goes to the user before import.
  - The `level-polish` skill has the placement rules for props in levels.
- **ConeCrushers:** follow its `CLAUDE.md` and memory. Interiors must reuse a sibling car's real cabin before anything is hand-built, and must meet the interior review bar. Test renders at low resolution by default and high resolution only for final judging frames. No branding text anywhere.

## 7. Lessons log (append-only; newest last)
Format: `YYYY-MM-DD project: symptom -> root cause -> fix -> rule`.

- 2026-10-21 LootNShoot: the Codex Glock 17 was rejected 3 times as blobby and low-detail -> proportions and features were never compared against the photos from the photos' own angles -> §3 loop -> never show a model without matched-camera difference sheets.
- 2026-10-21 LootNShoot: the Codex G17 slide had 49 % UV overlap, 972 open edges and floating texture panels on the backstrap -> no automated gate -> mesh_qc -> run QC before every review, zero ERRORs.
- 2026-10-21 LootNShoot: Glock v3 blockout had spike triangles under the dust cover and a diagonal shading seam on the grip -> boolean debris and a non-planar n-gon -> clean booleans (merge, dissolve degenerate) and triangulate or support-loop non-planar faces -> QC slivers/non-planar WARNs are fixed before review.
- 2026-10-21 LootNShoot: Glock v3 compare -> too many thin slide serrations (the real gun has about 7 wide ones), grip texture far too fine, copper mag baseplate (real: black; only the follower is orange), slide mid-grey (real: near-black nDLC) -> features modelled from memory, not counted on the photo -> count every repeated feature on the reference and match its pitch; judge colour values against the photo.
- 2026-10-21 LootNShoot: user on Glock v3: "pistol grip is too stubby ... missing proper shape", "rendering is simply poor" -> (a) the replacement contract froze Codex's grip surfaces to 1 mm, so the old wrong shape survived; (b) the profile was eyeballed instead of traced; (c) flat grey clay-like lookdev -> keep only the gameplay anchors (bore, trigger, pivot, sockets) and let the shape follow the reference; trace side profiles from a near-orthographic photo's silhouette scaled to the real length; review renders use a studio HDRI/softboxes, AgX and real material values -> a contract never protects a shape the user hasn't approved; silhouette IoU ≥ 0.95 on the side photo before any detail work.
- 2026-10-21 tooling: a camera match over 1 % RMS was accepted and compared anyway -> a large error usually means the model's proportions differ -> solve on the trusted rigid landmarks and mark the rest `"check": true`; their errors measure the shape error.
- 2026-09 LootNShoot (level-polish): every `bl_lib` FBX arrived Y-mirrored in UE; `/Game/Mesh/ELB/*` meshes have pivots kilometres from the geometry -> measure the imported mesh in UE, never trust the modelling notes.
- ConeCrushers (EagleKart): Interchange with `auto_generate_collision=False` dropped the `UCX_` hulls -> check collision after every import.
- LootNShoot (items): pack meshes named "vest" and "helmet" were loose buckles, straps and visors that became wearable items -> catalog-render each mesh alone and judge by the mesh, not its name.
- 2026-10-21 tooling: `ref_compare.py` on an RGBA reference (g5_right_side.png) drew red streaks and gave IoU 0.84 for a 0.97 match -> the transparent pixels carry non-white RGB and the script ignores alpha -> composite RGBA references onto white with their alpha first -> flatten every RGBA reference before comparing.
- 2026-10-21 LootNShoot G17 v4: a homography (photo -> side plane) fitted to the slide's 0.4 mm top/bottom convergence put 10 px errors on the grip of a near-orthographic product render (matched lens 2.7 m) -> the convergence was real geometry, not perspective -> map with a similarity (rotation + uniform scale) when the matched camera is near-ortho -> verify any photo mapping by solving the camera on its own landmarks and reading the far check points.
- 2026-10-21 tooling: `camera_match.py` could not match the 3/4 marketing render (rms 1.5-2 %, focal on its bound, same minimum from every start) -> slide-only landmarks are near-collinear (roll ill-conditioned) and the image was a crop/composite that no centred pinhole explains -> add rigid off-axis points pinned by the side profile (beavertail tip, baseplate corners), initialise with a DLT (v4 `pnp.py`), allow lens shift for cropped images; if slide-only points cannot reach 1 %, use that image qualitatively only.
- 2026-10-21 LootNShoot: a 3/4-view landmark was put on the mirrored corner -> the UE/G frame (+X = gun left) is left-handed, so cross-product "image right" reasoning in G coordinates is mirrored -> do view geometry in Blender coordinates.
- 2026-10-21 tooling: Blender's selected-to-active bake refuses a low-poly hidden from render, yet a renderable low (within 0.1 mm of the high) darkens AO and AO-node rays -> keep the low renderable and turn off all its ray visibilities (`visible_camera/diffuse/glossy/transmission/volume_scatter/shadow`).
- 2026-10-21 tooling: Decimate (collapse) with `use_symmetry` stalled at 60k triangles for a 3.2k target on the barrel -> symmetric collapse cannot cross the mirror plane on asymmetric details -> decimate without symmetry and always print the achieved count against the budget.
- 2026-10-21 LootNShoot (G17 v4 -> UE): the ADS view sat 6.7 mm above the sights; the user caught it in game -> the contract `Aim` socket was authored on the old mesh and kept "per contract" (the mismatch was only noted in STATUS) -> measured `Aim` = rear-notch top centre and `FrontSight` = front-post top centre on the new slide by ray casts, X along the sight line -> when replacing a gun, re-measure every socket that touches a visible feature (sights, trigger face, rail) on the new mesh and ship the measured values; a contract keeps gameplay anchors, not stale positions.
- 2026-10-21 LootNShoot (UE 5.5 Python): `StaticMeshEditorSubsystem.get_lod_count` returned -1 and has no triangle getter; MI texture parameters set on a master created moments earlier in the same script returned False -> 5.5 API quirk / the new master's parameter info exists only after compile + save -> use `StaticMesh.get_num_lods()` / `get_num_triangles(lod)`; save the master before making instances and read every parameter back -> verify each import step by reading the asset back, never by the setter's return value.
- 2026-10-21 LootNShoot (PIE frames): CCTV `shot` tour captures alternated between the whole editor window and the EDITOR level viewport (useless); a teleport from another map's tour dropped the pawn to 1 hp (desaturated frames) -> wrong capture path / borrowed coordinates -> `lns.ui.shot` (Slate capture of the game viewport) and shoot from the map's own spawn -> check the first frame of every capture batch before shooting the rest.
- 2026-10-22 LootNShoot (textures_v1, procedural tiling textures): numpy spectral noise with "stretch" factors produced horizontal streaks where vertical were meant, and warp fields without a high-frequency cut turned stain edges into speckle → the anisotropy semantic was inverted and the warp noise was white-ish → `texlib.spectral(ax<1)` now elongates along x by definition; always band-limit warp fields (fmax ~30 cycles/tile) → look at a 1:1 crop of every set before rendering.
- 2026-10-22 LootNShoot (textures_v1): distinctive tile-scale features (water stains, dark boards, oil blobs) read as an obvious grid at 3x3 tiling → keep tile-scale features low-contrast and move big stains / grime to a separate macro mask sampled at 10+ m → check a 3x3 tiling sheet for every set.
- 2026-10-22 LootNShoot (UE 5.5): see model-factory §6 for the material rebuild-in-place, actor-yaw triplanar and force-resident capture lessons.
- 2026-10-22 ConeCrushers (mirrors): glass for three cars sat on surfaces the game never shows (a body mirror hidden by an M_Nothing slot, a second modelled head next to the interior's own head) -> the glass builder only looked at the fleet body blend -> build from the surface the player sees (BP slot overrides applied + the interior mesh appended) -> review renders must reproduce the in-game scene (hidden slots removed, interior present), not the raw source blend.
- 2026-10-22 ConeCrushers (68CAM interior): A-pillar trim ended in a jagged spike over a see-through gap ("pillars going down the windshield are broken") -> the old-cabin keep/remove rule deleted faces by centroid inside a dash BOX, which also caught the bottom 7 faces of each pillar trim, and the new dash stopped 5-9 cm short of the pillar foot -> keep those faces by UV island + position (old68.pillar_foot) and add dash end caps (dash section lofted out under the pillar foot, glass-clamped, buried in the door roll) -> after any box cull of a kitbashed shell, render the kept islands' open boundaries and run a one-sided (backface-culled, magenta background) review render from the seat; see-through gaps only show with culling.
- 2026-10-22 ConeCrushers (94 Widebody cabin transplant from the 99 Widebody): a rigid x/z offset that seats the sibling dash on the new windshield base still left its front pad + both wipers ON the 94's cowl (the 99 pad runs 14 cm further under its glass); round gauges / vents would oval under a y-scale -> per-island map: small islands rigid (offset at bbox centre), only tub / dash pad / headliner take a field (x-compress the pad front above z .6, pull the upper 7 cm in at the belt), then clamp field verts 8 mm inside the target roof + glass; drop exterior bits that rode along with the cabin (wipers, the sibling's rear-view mirror) -> after any transplant, render over-the-hood + cowl close-ups with the glass hidden AND opaque, and list islands that sit in front of the glass base.
- 2026-10-22 ConeCrushers (UE python): logged a socket's "before" transform as `so.relative_location` and then set it - the log printed the NEW value (the struct is a live reference), so the before record was lost (only the uasset backup + an earlier dump had it) -> copy values (`unreal.Vector(v.x, v.y, v.z)` / plain tuples) before any setter.
- 2026-10-22 tooling (mesh_qc.py): any object with unapplied scale crashed the gate ("not all arguments converted during string formatting": `'%s' % tuple(...)`) -> wrapped the tuple -> run the gate on a parts-only copy (drop body / COMP_ objects) so context meshes neither crash nor flood it.
- 2026-10-22 ConeCrushers (Laza interior, 85Wagon kit): first per-part QC = 104 ERRORs: radio buttons / fan knob / lighter / glove button / ignition key / vent barrel + throat + vanes / mat ribs / parcel shelf stood 0.5-3 mm OFF their host (floating, invisible in renders), lathe poles left zero-length edges, a gauge face was coplanar with its plate -> each fitting now overlaps its host by >= 0.2 mm, a weld + dissolve-degenerate pass runs on every part before the join, lathe() tags its output qc_open (rims buried in the host), decals pass via --allow-float -> QC the PARTS blend (save before the join, PARTS_BLEND=1), never the joined mesh (one object = one undiagnosable error list).
- 2026-10-22 ConeCrushers (seats): 4-6 pleat grooves 10 mm deep on a 24 mm ring step serrated the cloth/vinyl edge and the bolster silhouette -> 2 grooves, 6 mm -> groove spacing >= 4 ring steps, depth <= 6 mm on loft seats; also headrest posts started 10 mm behind the backrest face and their ends broke through as white spikes -> start posts at the backrest mid-thickness.
- 2026-10-22 ConeCrushers (89 CAM headlamps): "one side looks different" survived a lens material retune -> the two Ln1Mtl lens shells were exact mirrors (positions, normals, UVs, winding all within 1 mm); the 316-face lamp BUCKET behind them was chrome (M_Mirror slot) on the right and black (Engine3411Mtl slot) on the left, read through a 0.78-opacity lens -> moved the left bucket faces to the M_Mirror polygon group by editing SM_Foxbody's LOD0 mesh description in UE (no FBX round trip, slots/overrides/collision untouched) -> for a left/right mismatch on a see-through part, mirror-match EVERY face in the part's box (centroid -> mirrored nearest face, compare material), not just the visible shell.
- 2026-10-22 ConeCrushers (98 Coupe quarter window): v2 read as "just 2 bars forming an angle" -> the trim was swept along the body's small glass shell, but the real body opening ran ~4 cm past that glass to the A-pillar paint and ~4.5 cm above its apex (a see-through slit onto the cabin pillar trim), so the bars floated inside the hole -> ray-cast across every edge of the glass to measure where the paint starts, fill the band with glass welded to the body glass's exact boundary verts (same plane, no second layer = no double tint), and run ONE closed mitred ring (pillar leg stepping glass->paint, belt leg, division-bar channel) round the measured opening -> build window trim from the opening the body actually has (ray-cast it), never from the edges of whatever glass happens to be there.
- 2026-10-22 ConeCrushers (94 Widebody cabin transplant, packaged: "random geometry around windows inside"): three sources -> (a) the 99's own door glass + black window-frame bar + chrome frame strips rode along inside the "door card" islands, 4.5 cm inboard of the 94 glass (island classification by dominant material keeps minority glass/frame faces); (b) hidden-slot faces carried as "exterior" by a box test (|y| beyond a glass-line guess) were really the old cabin's window trims / cage post / headliner rim INSIDE the glass; (c) the field-mapped 99 headliner rim hung below, or poked through, the 94's tumblehome side glass -> drop door-island glass/frame faces above the belt; keep a carried face only if its FRONT side can see out with the finished cabin as an occluder (the hidden slots leave holes that leak rays) and it is not in a glass opening; crop the rim after subdividing it to 2.5 cm (raw crops of sliver tris = sawtooth) by rays to the glass (outward, inward, and from the seat eyes) + a 1.5 cm nearest-glass test -> after a transplant, render from the seat with the target's glass OPAQUE and colour faces by source (src face attribute) - glass-hidden renders make inside-the-glass junk look like exterior trim.
- 2026-10-22 tooling (Codex review of the exported bundle): the gates only reported -> mesh_qc crashed on its own negative-scale finding (`'%s' % tuple(...)` again), camera_match rendered and exited 0 at 5 % RMS, ref_compare exited 0 at IoU 0.54, qc_all.sh piped Blender through grep so failures never reached the caller -> verdict lines + exit codes (QC 1, camera 2, compare 3), `--python-exit-code 1` on every Blender run, wrappers collect each run's status -> a gate that can't fail a script isn't a gate; check exit codes, not printed words.
- 2026-10-22 LootNShoot (Codex review): the "Gen 5" Glock's profile master was a Gen 6 CAD render, so the long Gen 6 beavertail shipped (the brief asked for a long upswept tail, but the variant was never locked) -> lock one named variant in the reference pack, the profile master must be it, and list mixed references with which source wins per feature.
- 2026-10-22 ConeCrushers (94 Widebody pillars rebuilt, packaged: "still broken interior pillars"): (a) the windshield's boundary loop carried an internal slit (a doubled-back edge run to a tip 35 cm inside the glass), so the first A-pillar sweep followed it into the windshield; (b) the A->rail corner and rail->C hand-over paired chords running ALONG the sweep -> a flat knot/wedge; (c) junk tests that let glass occlude visibility kept spikes standing in the openings; (d) the 99 headliner had holes where the blue roof showed through the 94's translucent under-roof glass sheet -> drop loop vertices with a twin within 3 mm and spike vertices (detour > 3x chord), plot the anchors over the glass (side + top) before lofting; pair segments so every chord crosses the sweep; glass never occludes in visibility tests; close headliner holes with a dark liner under the roof skin -> after any window-trim work run an exterior skin test (cabin edges crossing body+glass, vertices beyond the skin from every interior ref point; p_exterior.py in cars/94WidebodyCoupe) and a culled seat render.
- 2026-10-22 ConeCrushers (same pass, skin test): the transplanted 99 seat belts ran through the 94 quarter glass and its body-colour rear header panel sat inside the rear-glass top (a band visible from outside) - both pre-existing, never checked; clipping the belts at the glass left floating strap spikes -> remove panels the new trims replace, swing straps rigidly about their floor anchor instead of clipping -> never clip a thin part at the skin; move it rigidly.
- 2026-10-22 ConeCrushers (94 pillars, in-game door camera): blue roof-rail paint showed in slivers between the headliner edge and the new rail trim when looking ACROSS the cabin from low on the far side - every review camera had looked at the near rail or from the driver's eye, and the roof liner stopped at |y| .52 -> a dark skirt from under the liner's outer edge down into the back of the rail trim, both sides -> review window surrounds from the opposite seat / door, low, looking across (cameras acrossL/R, doorcamL/R in cars/94WidebodyCoupe/p_rv.py) and count paint-coloured pixels above the trim line.
- 2026-10-22 ConeCrushers (99 Sedan stack decals, UE commandlet import): re-running the import script crashed `-run=pythonscript` (SharedPointer IsValid in AssetTools.CreateAsset) -> the commandlet's asset registry isn't scanned, so `EditorAssetLibrary.does_asset_exist` / `load_asset(package path)` said "missing" and the script created assets over existing ones -> test the `.uasset` file on disk and load by full object path (`/Game/X/Name.Name`) in headless scripts -> make every UE import script idempotent that way before the first run.
