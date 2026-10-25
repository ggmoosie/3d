# LootNShoot: proposed item set (v1)

**Rule: one base mesh, many skins.** Each base mesh is modelled once (low/mid poly, baked from a high-poly), then
dressed with several texture sets. In UE this means one master material per family plus a material instance per skin:
cheap to render, huge visible variety. All brand names are invented; nothing is real.

**How we get AAA from low/mid poly**
- High-poly sculpt/bevel → bake normals + AO onto the game mesh. Silhouettes stay cheap; edges and dents read as real.
- Labels and packaging are generated at 20 px/cm, so they're legible in the hands: nutrition panels, barcodes, batch codes, ingredients, fine print.
- Every skin gets a wear pass: edge scuffs, dents in the normal map, faded print, dust in crevices, finger smudges, rust on tin.
- Optional "aged" variant per skin: dented, label torn, Sharpie notes. Survivor flavour at no modelling cost.

Legend: ★ replaces an existing row · ⚑ no clip yet (needs a new animation or a re-use check) · tris = LOD0 triangles

---

## A. Drinks (clips we have)

### A1. Pull-tab can (`Drink_Can`): 3 meshes, 1 shared tab
| Mesh | Size | Skins |
|---|---|---|
| Standard can 355 ml | 6.6 × 12.2 cm | ★Cola **Kolossal Cola**, **Kolossal Zero**, lemon-lime **Zing!**, orange **Sunny Pop**, root beer **Burl's**, ginger ale **Copper Kettle**, iced tea **Front Stoop Tea**, seltzer **Fizz** (lime / grapefruit / plain), tonic **Bitter End**, lager **Five Boroughs Lager**, ★hard seltzer **Rooftop Spritz** |
| Tall can 473 ml | 6.6 × 16.8 cm | Energy **VOLT** (original / blue razz / sugar-free / "Nitro"), tallboy **Iron Horse Malt**, **Bodega Iced Coffee** |
| Slim can 250 ml | 5.3 × 13.4 cm | ★cold brew **Dark Shift**, espresso **Third Rail**, energy shot **SPARK** |
~1.2k tris each · 1024 tex · 20 skins

### A2. Screw-cap bottle (`Drink_TwistBottle`): 4 meshes, 1 shared cap rule
| Mesh | Skins |
|---|---|
| PET 500 ml (waisted) | ★water **Hudson Spring**, **Pure Peak**, store brand **Value Fresh**, sports drink **HYDRA** (glacier / fruit punch / lemon), ★**used bottle** (refilled, cloudy water, tape, Sharpie "BOILED") |
| PET 1 L | water **Hudson Spring 1L**, iced tea **Front Stoop**, ★juice **Orchard Gold** (apple / orange) |
| Gallon jug | ★distilled water **Clear Run**, spring water, survivor "rain water" jug |
| ⚑→A2 Pill bottle (screw cap, fits this clip) | painkiller **Ibuprin 200**, antibiotic **Amoxiflex**, iodine tablets, multivitamin, anxiety meds **Calmaxa**, "unmarked pills" |
~0.8-1.5k tris · 1024 · 17 skins

### A3. Crown-cap / short-cap glass bottle (`Drink_Beer`): 5 meshes
| Mesh | Skins |
|---|---|
| Longneck 355 ml | beer **Gowanus Pale Ale**, **Ironworks Stout**, **Coney Lager**, cider **Hudson Valley Cider** |
| Heritage soda bottle (contour) | ★**Grandma Jo's Lemonade**, glass **Kolossal Classic**, cream soda **Dutch Mill** |
| Hot-sauce woozy (short screw cap) | ★**Diablo Verde**, **Red Hook Hot**, **Scorpion Tears** |
| Wine bottle (short screw cap) | ★**Finger Lakes Red**, white, rosé |
| Whiskey / spirits flask bottle | ★**Old Bowery Rye**, ★**Volga Bay Vodka**, **Port Royal Rum**, moonshine mason jar (survivor) |
~1-2k tris · 1024 · 17 skins

### A4. Thermos ★ (Drink_Beer cup-cap variant): 1 mesh, 4 skins (steel, green enamel, red tartan, dented army)

---

## B. Food (clips we have)

### B1. Opened can + spoon (`Eat_CanSpoon`): 3 can meshes, ring-pull lid, 3 utensils
| Mesh | Skins |
|---|---|
| Food can 7.8 × 11.2 (ring pull, opened state) | ★beans **Bayside Baked Beans**, chili **Lone Star Chili**, chicken noodle **Mama Rosa's**, tomato soup, peaches **Sunvale**, corn, pasta rings **Little Os**, ★meatballs **Nonna's**, dog food **Good Boy** (desperation), **mystery can** (label gone, Sharpie "???") |
| Flat oval tin (fish) ⚑ grip check | ★tuna **Bluefin Bay**, ★sardines **Captain Haddie**, ★sprats **Baltic Gold** |
| Glass jar + lid (same clip) | ★olives **Castello Olives**, peanut butter **Nutty Joe's**, pickles **Lower East Pickle Co.** |
| Ration pouch (torn top) | ★Field Ration menus 1-6: chili mac, beef stew, veg lasagna, chicken & rice, cheese tortellini, maple sausage (tan pouch, stencilled menu number) |
| Utensils | metal spoon, plastic ration spoon (tan), spork |
~1-2k tris · 1024 · 22 skins

### B2. Round fruit (`Eat_Apple`): 3 meshes + 3 bitten stages each
apple (red / green / yellow / bruised), orange (navel / blood), ★Banapple (craft: apple-shaped, yellow-green striped skin) · ~1k tris · 512-1024

### B3. Banana (`Eat_Banana`): 1 mesh + peeled state · skins: green, ripe, spotty, brown

### B4. Flat bar (`Eat_BarFlat`): 1 wrapper mesh + torn end
★chocolate **Brooklyn Bar** (milk / dark / almond), granola **Trail Mix Bar**, protein **MAX 30g**, energy **Fuel Up**, fruit leather, emergency ration bar **Survival 400** (silver, 3600 kcal) · ~600 tris · 1024 · 9 skins

### B5. Bar (`Eat_Bar`): no current rows, 3 meshes
salami stick **Bodega Stick**, carrot, baguette end · ~800 tris

### B6. Disc (`Eat_Disc`): 3 meshes
★cookie (chocolate chip / oatmeal / double choc), sandwich cookie **Black & White**, rice cake, hardtack ration biscuit · ~600 tris

---

## C. Medical (clips we have)

### C1. Bandage roll (`Bandage_Wrap`): 2 meshes + sealed pack pickup
★gauze roll (white), elastic wrap (tan + clips), cohesive wrap (blue / red), ★hemostatic gauze **ClotStop**, ★trauma dressing pack **Field Trauma 6"**, bloodied/used variant · 8 skins

### C2. IV bag (`Bandage_Forearm`): bag + coiled line
★saline 0.9 %, lactated ringer's, blood O−, plasma · 4 skins

### C3. Syringe / auto-injector (`Inject_Forearm`, `Syringe_Thigh`): 2 meshes (pen injector, glass syringe), cap + plunger
★adrenaline **EpiShot** (yellow), ★morphine **Morphex** (red), ★painkiller **Analgex** (blue), antidote **Atrox** (green), combat stim **RUSH** (black/orange, new buff), antibiotic shot, B12 vitamin · 7 skins

### C4. Kit box + lid + scalpel (`Surgery_Kit`): 2 meshes
★tin box: red first-aid tin, white surgical kit, olive military IFAK box, repurposed cookie tin · ★large trauma bag (clamshell zip, same hinge) · 5 skins

---

## D. Smoking (clips we have)
| Mesh | Skins |
|---|---|
| Cigarette pack (hard flip-top) + single cigarette | ★**Liberty Lights**, **Red Hook Reds**, **Menthol Breeze**, **Union Blues**, **Canal Street Ultra**, roll-your-own tin |
| Disposable lighter (hood + wheel) | ★8 colours + 3 printed (skyline, flames, camo) |
| Flip lighter (lid + wheel) | ★chrome, brass, black matte, engraved eagle, worn army |
| Bong + downstem | ★clear, blue, green, filthy |
~0.5-3k tris · 26 skins

---

## E. Ammo, magazines, attachments (fit the five guns)
- **Loose rounds:** ★9×19 (FMJ / HP / AP), ★5.56×45 (FMJ / green tip / AP black tip / HP), ★7.62 + 7.92×57 (FMJ / AP), ★12 ga (buck red, slug, birdshot green).
- **Ammo box:** 1 mesh × 2 sizes (20 / 50). One skin per round type, fictional maker **Patriot Arms Co.**
- **Ammo can:** .50 cal steel can; skins: OD, tan, rusty.
- **Magazines:** ★AR 30-rd (steel grey / polymer black / FDE / OD), ★Glock 17-rd + 33-rd extended, ★MAC-10 32-rd, Kar98k stripper clip, shotgun shell carrier.
- **Optics:** red dot, holographic, 1-4× LPVO.
- **Muzzle:** suppressor 9 mm + 5.56.
- **Grips and accessories:** vertical and angled foregrip, weapon light, laser box, sling mount. Skins: black / FDE / OD.

## F. Tools (27 rows → about 18 meshes)
screwdriver (flat / phillips × 3 handle colours) · pliers family (pliers, cutters, shears) · adjustable wrench · claw hammer ·
tape measure (yellow / orange / black) · spirit level (2 lengths) · pencil / carpenter pencil / pen · ★duct tape (silver / black / camo / orange) ·
rope & cable coil (one coil mesh, 4 skins) · carabiner · lifting sling · oil can · fire extinguisher (red ABC / black CO2) ·
cordless hammer drill (yellow / red / teal, no brand) · flashlight + large torch · walkie / field radio / site radio · binoculars

## G. Valuables & quest items (37 rows)
- **Keys:** 1 key mesh × 6 cuts + ring, ★hall door / master / padlock / shop ring.
- **Keycards:** 1 mesh × 6 skins: Transit worker, Security, Hospital, Precinct, Lab, Signal Room.
- **Transit pass:** 1 mesh, worn / new / unlimited.
- **Badge:** city police / fire / EMS.
- **Watches:** field, tactical, gold dress.
- **Electronics:** smartphone (cracked / intact), flip phone, laptop, ★old PC tower, ★gamepad, ★headphones, external drive, graphics card.
- **Cash and gold:** money roll, ★loose-change jar, gold chain, wedding ring, gold tooth.
- **Reading:** ★paperback (1 mesh × 10 covers), ★book pile, ★field manual, ★newspaper (6 headlines from the outbreak week), ★playing cards + box.
- **Containers you carry home:** ★lunch tin (4), ★jerrycan (red fuel / green / blue water), ★toolbox, ★lantern, ★shooting glasses.

## H. Crafting materials
★filament spool (black / orange / white + red, green, glow) · ★scrap metal · nuts & bolts jar · wire spool · circuit board · batteries (AA pack, 9 V, car battery) · gunpowder tin · rags · plastic scrap

## I. Throwables
★frag (OD / training blue) · ★molotov (reuses the A3 bottles + rag, 3 skins) · flashbang · smoke grenade (white / red / green)

## J. Containers
★small pouch · ammo can (E) · medical case · document case · key case · secure tin

## K. Gear & clothes (later phase, rigged)
helmets (combat / riot / ★hard hat yellow, white, orange / bike) · vests (plate carrier, chest rig, ★hi-vis yellow / orange) · packs (assault, hiking, school, duffel, sling) ·
clothes on shared base meshes: T-shirt × 12 prints/colours, flannel × 4, work jacket × 3, cargo / work pants × 4, boots × 5, gloves × 4, masks × 8

---

## Totals (A-J, before gear/clothes)
| | Base meshes | Skins / variants |
|---|---|---|
| Drinks | 13 | ~58 |
| Food | 13 | ~45 |
| Medical | 7 | ~24 |
| Smoking | 5 | ~26 |
| Ammo/mags/attachments | ~22 | ~45 |
| Tools, valuables, materials, throwables, containers | ~55 | ~110 |
| **Total** | **~115** | **~310** |

## Build order (matches the clips we have)
1. A1 can (defines the label pipeline + wear pass for every family) → all can skins
2. A2 / A3 bottles → B1 cans + spoon + pouches → B2-B6
3. C medical → D smoking
4. E ammo + mags + attachments (fit-checked on guns/)
5. F-J
6. K gear and clothes

## Decisions for you
1. **Flat fish tins** don't match the 7.8 × 11.2 can grip. Do we accept a slightly-off grip, or make an `Eat_TinSpoon` clip?
2. **Pill bottles** on the screw-cap clip: yes? (no new animation needed)
3. **New clips I can author in Blender** if wanted: pills (shake into palm), ration bar unwrap, MRE heater, energy gel squeeze.
