# Prop replacement brief: LootNShoot loot, all new

You are building **all-new replacement props** for the loot in **LootNShoot**, a first-person co-op PvE extraction shooter in Unreal Engine 5.5. It is set in a dead New York, and survivors live in an abandoned subway station. The current loot meshes are a mix of store packs and placeholders. Replace them with one consistent, from-scratch set made in Blender with Python scripts.

Nobody can answer questions while you work. When something is unclear, decide sensibly, write the decision in `props/PROGRESS.md`, and keep going.

## Files in this folder
| File | What it is |
|---|---|
| `items.md` / `items.json` | Every loot row in the game today (221): table, row id, display name, inventory grid size, current mesh size in cm, the use animation it plays, equip slot. This is your **coverage map**. Rows tagged `NoSpawn` / `CraftOnly` are low priority. |
| `consume_contract.json` | For every consumable animation: the prop shape the hands were animated around (dimensions, pivot, axes, moving parts, event timings). **Consumables must follow it** (section 4). |
| `skeleton_ue5_manny_rest.json` | Bone names, head and tail positions and parents of the character skeleton (UE5 Mannequin), for rigging clothes (section 7). |

Also read:
- `../../skills/model-factory/SKILL.md` and `../../skills/blender-3d/SKILL.md`: the modelling rules and the QC gate. The checker is `skills/blender-3d/scripts/mesh_qc.py`.
- `../../guns/`: the five guns already built (AR-15, Glock 17, MAC-10, Mossberg 590, Kar98k), with their sockets. Your attachments, magazines and ammo must fit these guns.

## 1. Hard rules
1. **From scratch.** No downloaded models, textures, HDRIs, scans or kitbash packs. Every mesh and texture comes from your scripts (procedural shaders, numpy, PIL). Fonts: only OFL fonts shipped with Blender (e.g. Inter / DejaVu).
2. **No real brands.** No logos or trademarks of any kind. Labels are generic ("BEANS", "WATER 500 ml", "5.56 × 45", "BANDAGE") or invented, plausible names that are clearly fictional.
3. **Real size.** Model at real-world dimensions in metres; pick a believable real object and measure it. The game shows these in the player's hands, close to the camera. Never scale at export.
4. **Reproducible.** Every prop is built by a Python script that recreates it from nothing (`<item>.py`), like `donut/donut.py`.
5. **Game-ready.** Budgets are in section 5. Clean topology, no hidden interior junk, closed shells, sensible UVs, baked textures.
6. **No reference images in the repo.** Look things up if you can, but commit only your own renders.

## 2. Environment
```sh
uv venv -p 3.11 .venv && uv pip install -p .venv bpy numpy pillow   # Blender 5 as a Python module
.venv/bin/python props/food/canned_beans/canned_beans.py              # builds, renders, exports
```
- Headless only. Render previews with **Cycles on CPU**: 32-64 samples, 1024 px, the studio light rig from `donut/donut.py`, transparent or neutral grey background. EEVEE needs a GPU and may be unavailable.
- **Export FBX** with `bpy.ops.export_scene.fbx`: `apply_unit_scale=True`, `apply_scale_options='FBX_SCALE_NONE'`, `axis_forward='-Y'`, `axis_up='Z'`, `mesh_smooth_type='FACE'`, `use_tspace=True`, `add_leaf_bones=False`, `path_mode='STRIP'`, `bake_anim=False`.
  - Check on your first prop that the FBX exporter loads in this bpy build. If it doesn't, export glTF (`.glb`) and note it in `PROGRESS.md`; Unreal imports both.
- QC: `.venv/bin/python -c "import bpy; ..."` or run `skills/blender-3d/scripts/mesh_qc.py` the way its SKILL.md says. It was written for Blender 4.0: patch small API differences, don't skip the gate.

## 3. Conventions (Unreal reads these directly)
- **Frame.** Blender Z up, metres. Unreal location = (x, -y, z) × 100 cm.
- **Names.**
  - Static mesh: `SM_<Item>` plus `SM_<Item>_<Part>` for each moving part (`SM_SodaCan`, `SM_SodaCan_Tab`).
  - Skeletal mesh: `SK_<Item>`.
  - Materials: `M_<Item>_<Surface>`.
  - Textures: `T_<Item>_<Surface>_{BaseColor,Normal,ORM}.png`.
- **Pivots.** Hand-held consumables use the pivot and axes in `consume_contract.json` (e.g. drinks: base centre, +Z up). Pickups with no contract: bottom centre, resting naturally on a table, the long axis along +Y (the current pickup convention).
- **Moving parts are separate meshes**, each with its pivot exactly at its joint:
  - screw cap: the bottom centre of the cap, on the neck axis;
  - can pull tab: the rivet;
  - lid: the hinge line;
  - syringe plunger and needle cap: on the barrel axis;
  - spoon: its own object;
  - a magazine follower or rounds, if visible.

  Give each its rest transform relative to the main mesh in `manifest.json`.
- **Collision.** One or more convex hulls per pickup, named `UCX_SM_<Item>_00`, `_01`, … (Unreal's convention), exported in the same FBX. A simple box or cylinder is fine for small items.
- **LODs.** Anything over 2k triangles gets `SM_<Item>_LOD1.fbx` (about 50 %) and `SM_<Item>_LOD2.fbx` (about 25 %).
- **Textures.** PNG.
  - BaseColor: sRGB.
  - Normal: OpenGL (Blender's bake default); say so in the manifest.
  - ORM: linear, with R = ambient occlusion, G = roughness, B = metallic.
  - One texture set per prop where possible; tiny props of one family may share an atlas.
  - Size by texel density: about 20 px/cm for things seen in the hands (labels must read), about 10 px/cm otherwise. Usually 1024 for hand-held items, 512 for tiny ones, 2048 at most for clothes or large gear.
- **Look.** Lived-in, believable and present day: a dead New York half a year after the fall. Slight wear on corners, dust and scuffs, faded labels; nothing cartoonish. Label art is generated (shapes, stripes, nutrition-panel blocks, barcodes, plain type), never photographed.

## 4. Consumables: build them for the animations we have
Every consumable plays a first-person clip that was animated around a specific prop shape. `consume_contract.json` → `props` has each shape's dimensions, pivot, axes and moving parts, and `clip_events_s` has when the parts move (CapOff, TabPop, Bite1, …). The table below is the summary.

The rule: **keep the pivot, the axes and the grip dimensions within about 10 % of the contract, and model every listed moving part as its own mesh.** Inside that, design freely: new brands, shapes, materials and variants.

| Clip (family) | Prop the hands expect | Moving / separate parts | Current rows using it | Make (examples) |
|---|---|---|---|---|
| `Drink_Can` | Can 6.6 Ø × 12.2 cm, pivot base centre, +Z up | **Pull tab** 1.2 × 2.5 cm on a rivet at the top centre (pivot = rivet, opens about local X); the drinking hole on the +Y side of the lid | `SodaCan`, `Cola`, `Coffee`, `SpiritsBottle` | Soda, cola, energy drink, **canned** coffee, a canned cocktail or hard seltzer (these rows play the can clip, so the replacement must be a can) |
| `Drink_TwistBottle` | PET bottle 6.5 Ø × 22 cm (waist 5.7 Ø at 9.5 cm), neck 2.9 Ø | **Screw cap** 3.1 Ø × 1.4 cm, pivot at the cap's bottom centre on the neck axis | `Water`, `PlasticBottle`, `UsedWaterBottle`, `JuiceBox`, `WaterJug` | Water 500 ml / 1 L, sports drink, juice bottle, a gallon jug (bigger body, same cap rule) |
| `Drink_Beer` | Longneck glass 28 cm tall, lip 3.4 Ø | **Crown cap** 3.9 Ø × 0.95 cm at z 27.4 (the clip pinches it, turns it 3 × 60° and lifts it) | `Lemonade`, `SauceBottle`, `Thermos`, `WhiskeyBottle`, `WineBottle` | Beer, glass lemonade / cola, cider, hot-sauce bottle. Whiskey, wine and thermos need a small cap on a narrow neck that this clip can turn and lift (a short screw cap); note which ones would want their own clip later |
| `Eat_CanSpoon` | Open food can about 7.8 Ø × 11.2 cm in the **left** hand (pivot base centre); **spoon** in the right hand | **Spoon** 17 cm (handle 10.5 × 1.1 × 0.3, bowl 4 × 2.8 × 1.1), pivot at the pinch point 5 cm from the handle end, +Z toward the bowl, +X = bowl up. Can: a separate opened **ring-pull lid**, and an "opened" state | `CannedBeans`, `TunaCan`, `Sardines`, `Sprats`, `Meatballs`, `OliveJar`, `MRE01-04` | Beans, soup, tuna, peaches, chili, pet-food-grade "mystery meat"; ration pouches (torn top) |
| `Eat_Apple` | Sphere about 7.5 Ø, pivot centre | Optional bitten stages swapped on Bite1-3 | `Apple`, `Banapple` | Apple, pear, orange, potato?; bitten stages are a plus |
| `Eat_Banana` | Long fruit; the grip is a 3.5 × 2.5 cm section near the bottom | Optional peeled state | `Banana` | Banana |
| `Eat_BarFlat` | Flat bar 5.4 × 0.42 × 12.8 cm, pivot centre, +Z = the bite end | A torn-open wrapper end | `Chocolate` | Chocolate, granola / protein bar, jerky strip |
| `Eat_Bar` | Bar 3.5 × 2.5 × 18 cm, +Z = the bite end | none | none today | Sausage stick, baguette end, a carrot |
| `Eat_Disc` | Disc 7.5 Ø × 1.5 cm, pivot centre, disc axis = Y | none | `Cookie` | Cookie, cracker, rice cake |
| `Bandage_Wrap`, `Bandage_Forearm` | Roll 7 Ø × 5 cm wide, 2.4 cm core, pivot roll centre, axis = local X | A loose tail end; the pack as a separate pickup | `Bandage`, `BandagePack`, `BandageRoll` (Wrap); `IVBag` (Forearm) | Gauze roll, elastic bandage, hemostatic pack, sealed wrapper; an IV bag with a coiled line |
| `Inject_Forearm`, `Syringe_Thigh` | Syringe / auto-injector about 12 cm, pivot at the barrel centre, +Z toward the needle | **Needle cap** (pulled 4.5 cm along +Z), **plunger** (3.8 cm travel; rear thumb pad) | `AdrenalineSyringe`, `MorphineSyringe`, `PainkillerSyringe` | Adrenaline / morphine / painkiller auto-injectors, colour-coded |
| `Surgery_Kit` | Box 16 × 10 × 5, pivot centre | **Lid** 16 × 10 × 0.8, hinged on the far long edge (+Y), opens 110°; **scalpel** 10 cm + 3.2 cm blade, pivot at the pinch point, +Z toward the blade | `FirstAidTin`, `MedKitLarge` | Surgical kit, first-aid tin; the large kit can be a bag with a zip |
| `Smoke_Cigarette`, `Lighter_Flick` | Cigarette 8.5 × 0.8 (filter 2.5, pivot at the filter end, +Z toward the tip); lighter 2.5 × 1.3 × 6 + hood | Lighter **hood** and **striker wheel**; a flame card; an ember | `Cigarettes` (the lighter rows `Lighter` and `Zippo` are loot today; `Lighter_Flick` is ready for them) | Pack + single cigarette, disposable lighter, flip lighter |
| `Smoke_Bong` | Bong 30 cm (see contract) | Downstem + bowl as a separate mesh | `Bong` | Glass bong |

Every consumable row has a clip today. New consumable ideas without one (pills, an MRE heater): model them sensibly, flag them in the manifest as `"clip": null`, and give them a hand-hold pivot (the centre of the gripped part). Better still, make them fit one of the clips above (pills in a bottle with a screw cap → `Drink_TwistBottle`).

## 5. Everything else
Work through `items.md` by table. Replace every row with something as good or better; add new items when a category is thin. Budgets are LOD0 triangles.
- **Weapon attachments and magazines (2-10k tris, 1024-2048).**
  - New attachments for the five guns in `../../guns/`: a red dot and a holographic sight (picatinny), a 1-4× LPVO, a suppressor per calibre, a vertical and an angled foregrip, a weapon light, a laser box, a sling mount.
  - New magazines: AR-15 30-round, Glock 17 17-round, MAC-10 32-round, Kar98k stripper clip, plus a shotgun shell carrier.
  - Fit-check each one on the matching gun FBX in Blender (rail positions and sockets are in `guns/<gun>/sockets/` where present) and render it mounted.
- **Ammo (0.3-3k).**
  - Loose rounds: 9 × 19, 5.56 × 45, 7.92 × 57 (Kar98k), 12 gauge shell and slug.
  - Boxes: 20 / 50-round.
  - Variants by tip colour (AP, HP).
- **Tools (1-8k), valuables (0.5-5k), crafting materials, throwables (frag, molotov), containers:** one each per row. The game loves keys, keycards, radios, watches, books and tins, so make those pieces of character.
- **Gear (vests, backpacks, helmets, 8-25k, 2048):** skeletal and rigged (section 7), or at least modelled and UV'd so they can be rigged later.
- **Weapons are out of scope** (the guns are done; melee weapons are being redone separately).

## 6. Per-prop deliverables and repo layout
```
props/
  PROGRESS.md                     your log: decisions, what's done, what's next (update every batch)
  catalog.md                      one line per finished prop: row it replaces, folder, tris, texture size, preview
  <category>/<item>/              category = food, drinks, medical, attachments, ammo, tools, valuables, materials, throwables, containers, gear, clothes
    <item>.py                     builds everything below from nothing
    <item>.blend                  the source scene (keep it under 50 MB: pack only your own textures)
    fbx/SM_<Item>.fbx             main mesh (+ UCX hulls), moving parts as SM_<Item>_<Part>.fbx, LODs
    textures/T_<Item>_*.png
    <item>.png                    a 3/4 hero render; <item>_parts.png if it has moving parts (exploded)
    manifest.json                 see below
```
`manifest.json`:
```json
{"item": "SodaCan", "replaces_rows": ["SodaCan", "Cola"], "category": "drinks", "clip": "A_Consume_Drink_Can",
 "dims_cm": [6.6, 6.6, 12.2], "pivot": "base centre, +Z up",
 "parts": {"SM_SodaCan_Tab": {"pivot": "rivet", "rest_location_cm": [0, 0, 11.6], "rest_rotation_deg": [0, 0, 0], "opens": "about local X, 55 deg"}},
 "tris": {"LOD0": 1800, "LOD1": 900, "LOD2": 450}, "textures": {"size": 1024, "normal": "OpenGL"},
 "collision": "UCX_SM_SodaCan_00 (cylinder hull)", "variants": ["cola", "lemon", "energy"], "notes": ""}
```
- Commit and **push after every finished set** (5-10 props) with a contact sheet `props/<category>/_sheet.png`, so progress is visible.
- Work on the branch `props-v1`, and open a pull request to `main` once the first set is pushed. Keep pushing to that branch.

## 7. Clothes and gear (rigged)
- **Skeleton.** `skeleton_ue5_manny_rest.json` has the UE5 Mannequin's core bones (spine, neck, head, arms with twist bones, legs) with their rest head and tail positions in cm. Its frame is Unreal skeletal-mesh space: Z up, the character faces +Y, its left side is +X. In Blender: location_m = (x, -y, z) / 100.
  - Build an armature from it with these **exact bone names and parents**. Unreal binds by name.
  - The rest pose is the mannequin's A-pose. The body is about 180 cm tall.
- **Body.** No body mesh is provided (it's Epic's and can't be shared). Build your own simple proxy body around the bones (capsules or a low-poly figure) to tailor against, and don't export it.
- **Skinning.** Skin every garment to the core and twist bones only, with automatic weights plus a cleanup pass. Make sure shoulders, elbows, hips and knees deform cleanly by posing the armature (arms up 90°, a 60° knee bend) in a QC render.
- **Export.** FBX with the armature, `add_leaf_bones=False`, one garment per file: `SK_<Item>.fbx`. Under the skeleton rule, the armature's root bone must be named `root`.
- **Slots in the game:** Shirt, Pants, Boots, Gloves, Mask, Helmet, Belt, Vest, Backpack. One garment per slot, layered: shirts sit under vests, helmets over masks. Keep gaps from the body about 0.3-0.8 cm so layers don't clip.
- Clothes are the stretch goal. Do all consumables and attachments first.

## 8. Quality gate (every prop, before it counts as done)
1. `mesh_qc` shows 0 errors: no non-manifold edges, flipped faces, zero-area faces, overlapping UVs (except deliberate mirroring), floating parts or z-fighting.
2. Dimensions within 10 % of the contract (consumables) or of a real object you name in the manifest.
3. The FBX re-imports into a clean scene with the same parts, pivots, materials and scale. Check it in the build script.
4. The hero render reads at a glance: you can tell what it is, the label is legible, and there is no logo.
5. Moving parts tested: render the part at rest and fully open, and the exploded parts render.
6. `manifest.json` complete; a line in `catalog.md`.

## 9. Order of work
1. **Drinks** (`Drink_Can`, `Drink_TwistBottle`, `Drink_Beer`).
2. **Canned and pouch food** + the spoon (`Eat_CanSpoon`).
3. **The other food clips** (apple, banana, flat bar, disc).
4. **Medical** (bandages, injectors, surgery kit).
5. **Smoking** (cigarettes, lighters, bong).
6. **Magazines and attachments.**
7. **Ammo.**
8. **Tools, valuables, materials, throwables, containers.**
9. **Gear.**
10. **Clothes.**

Start each family with the prop that defines it, get it through the full gate, then do the variants by changing labels and colours (one script with variant arguments is ideal).
