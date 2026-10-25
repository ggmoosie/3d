# AR-15 kit: materials, baked masks and skins

How a UE master material uses the masks that `build_ar15.py --assemble` bakes into `out/bake/`.

## Slots and texture sets

Every mesh uses the five contract slots, always in this order: `Receiver`, `Steel`, `BCG`, `Polymer`, `Handguard`.

| Slot | Surface | UV atlas (UV0) | Texture size |
|---|---|---|---|
| `Receiver` | Black hard-anodised aluminium: upper, lower, trigger guard, charging handle, buffer tube. (The pass-3 BUIS base was here; the pass-4 sights are polymer.) | `Kit_Receiver`, shared by both guns. | 4096 |
| `Steel` | Manganese phosphate: barrel, birdcage, FSB, gas parts, pins, small parts, castle nut; the flip-up sights' cross bolts, nuts, hinge pins, aperture drum, windage carrier and front post (pass 4). | `Kit_Steel`, shared by both guns. | 2048 |
| `BCG` | Phosphated carrier and bolt. | `Kit_BCG`, shared. | 1024 |
| `Polymer` | A2 grip, M4 stock; the flip-up sights' bodies, leaves, knob and elevation drum (pass 4, MBUS-3 style). | `Kit_Polymer`, shared. | 2048 |
| `Handguard` | Anodised handguard. | `MLOK_Handguard` (SM_AR15_MLOK) or `M4Quad_Handguard` (SM_AR15_M4Quad): one per handguard. | 4096 |

The magazine `SM_AR15_Mag30` has its own atlases: `Mag30_Receiver` (1024), `Mag30_Steel` (512) and `Mag30_Polymer` (512).

**Pass 3: a sixth slot, `Brass`.** It is used only by the cartridge `SM_AR15_MagRound` and the merged `SM_AR15_Mag30_Loaded`, with its own atlas `MagRound_Brass` (512). The look values are: base (0.72, 0.50, 0.19) linear, metallic 1, roughness 0.30, and worn edges lighter (0.86, 0.66, 0.30) at roughness 0.18.

**Game kit textures (pass 3).** The game part meshes (`out/game/`) keep the atlases above, and `out/bake/game/<atlas>_{AO,Curv,N,Masks}.png` holds one mask set per atlas covering every game part. For each mesh and slot, `game_parts.json` lists which atlas and which files to use. The `Handguard` slot takes `MLOK_Handguard` on `SM_AR15_HG_MLOK` and `M4Quad_Handguard` on `SM_AR15_HG_M4Quad`.

- **Texel density, two tiers (pass 2; pass-3 values).**
  - `Receiver` and `Handguard`, the surfaces the first-person camera sits on, are at 4096: 79.8 px/cm (0.13 mm per texel).
  - `Steel`, `BCG` and `Polymer` stay at the pass-1 density: 39.9 px/cm at 2048 / 1024.
  - Enclosed islands (bores, magwell walls, the handguard liner) are packed at 40 % scale. Their texel density is 40 % of their tier's.
  - The magazine's atlases use the standard tier. `Mag30_Receiver` drops to 1024 at about 37 px/cm instead of a 2048 map that would be 15 % used.
  - The UVs don't depend on resolution. `ar15_assemble.HERO_SLOTS` / `HERO_SIZE` set the tiers.
- **Shared atlases.** The kit-wide atlases hold every part of that slot from both builds.
  - Each part keeps the same UVs in both guns and in its own per-part FBX.
  - So one skin texture for `Receiver`, `Steel`, `BCG` or `Polymer` fits both guns and the loose parts.
  - Regions a gun does not use stay empty in that gun's bakes. For example, the FSB island stays empty in the M-LOK bakes.

## Baked maps (per gun, per slot)

Files are named `out/bake/<gun>_<slot>_<map>.png`, where `<gun>` is `SM_AR15_MLOK`, `SM_AR15_M4Quad` or `SM_AR15_Mag30`.

| Map | Content | UE texture settings |
|---|---|---|
| `_AO` | Ambient occlusion of the assembled gun: Cycles, 3 cm rays, only that gun in the scene. | Masks (no sRGB), linear. |
| `_Curv` | Curvature. 0.5 is flat, values above 0.5 are convex edges, values below 0.5 are concave creases. It comes from a 0.9 mm Bevel-node edge detector split into convex and concave by a 2.5 mm local AO. | Masks (no sRGB), linear. |
| `_N` | Tangent-space normal map. `Receiver` holds the engraved markings (SAFE / SEMI / AUTO, the roll mark on the magwell panel). `Polymer` holds the A2 grip's diamond checkering and back-strap grooves. | Normalmap, **Flip Green Channel ON**: Blender bakes OpenGL Y+, UE expects DirectX. |
| `_Masks` | Packed copy: R = AO, G = Curv, B = 1. It saves samplers. | Masks (no sRGB). |

The other slots don't need a normal map. Their bevels are real geometry, shaded by the custom (weighted) normals exported in the FBX. Import them with **Normal Import Method = Import Normals** (not "Compute").

## Master material (one material, one instance per slot)

Parameters:
- `BaseColor` (vector, the current tint system drives this one);
- `BaseRoughness`, `BaseMetallic`, `Specular`;
- `EdgeWear` (0-1), `EdgeWearColor` (bare aluminium / steel), `EdgeWearRoughness`;
- `CavityDirt` (0-1), `AOStrength`;
- optional `SkinTex` + `SkinBlend`, and `NormalTex`.

Graph:
1. **AO.**
   - `AO = lerp(1, Masks.R, AOStrength)`.
   - Multiply it into the base colour.
   - Plug it into the material's `Ambient Occlusion` pin too, so specular occlusion works.
2. **Convex edge wear.**
   - `wear = smoothstep(0.68, 0.92, Masks.G) * EdgeWear`.
   - Optionally multiply `wear` by a world-aligned grunge noise, so the wear breaks up along the edges.
   - Then apply it:
     - `BaseColor = lerp(BaseColor, EdgeWearColor, wear)`;
     - `Metallic = lerp(BaseMetallic, 1, wear)` (the bare metal shows under the anodise or phosphate);
     - `Roughness = lerp(BaseRoughness, EdgeWearRoughness, wear)`.
3. **Concave dirt.**
   - `dirt = saturate((0.5 - Masks.G) * 2) * CavityDirt`.
   - Darken the base colour by `1 - 0.6 * dirt` and raise the roughness by `+0.2 * dirt`.
4. **Normal.** Use the `_N` texture on `Receiver` and `Polymer`, a flat normal elsewhere.
5. **Look values used in the renders** (linear), from `ar15_render.LOOK`:

   | Slot | Base | Roughness | Metallic | Edge wear |
   |---|---|---|---|---|
   | Receiver | 0.014 | 0.44 | 0.0, specular 0.50 | colour 0.26, metallic 1, roughness 0.30 |
   | Handguard | 0.016 | 0.46 | 0.0, specular 0.50 | as Receiver |
   | Steel | 0.022 | 0.52 | 0.35 | colour 0.20 |
   | BCG | 0.035 | 0.30 | 0.85 | |
   | Polymer | 0.012 | 0.62 | 0.0 | colour 0.035, a lighter rubbed edge, no metal |
   | Brass | (0.72, 0.50, 0.19) | 0.30 | 1.0 | colour (0.86, 0.66, 0.30), roughness 0.18 |

## Skins

- **A painted skin** is a `SkinTex` per slot, authored on UV0. Use the atlas layouts (`out/AR15_master.blend`, UV editor) as a guide.
  - The masks keep the wear in the same places under every skin: worn edges show metal through the paint when `wear` is applied after the skin.
- **A projected skin** (camo) needs no UV work.
  - Use a triplanar projection in object space. Units are cm, and the gun frame is fixed, so the pattern stays put when the gun moves.
  - Use the same `wear` mask to cut the paint at the edges.
- **The current tint system** drives `BaseColor` on one slot instance. For a coloured furniture skin, that is `Polymer`.

## Re-baking

Run `build_ar15.py --assemble` to re-bake everything (the bakes are part of the run; `--nobake` skips them).

- The bake shaders live in `ar15_bake.py`: `curvature_shader`, `receiver_bump_shader` and `polymer_bump_shader`.
- The engraving text is in `ar15_post.py markings`.
- Change those and rerun. The UVs come from the same build, so the maps always match the exported meshes.
