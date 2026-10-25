# Guns

Game-ready firearm models made from scratch in Blender for **LootNShoot**, a first-person co-op extraction shooter in Unreal Engine 5.5. Every gun is split into the parts the game animates (slides, bolts, pumps, magazines) and exported as FBX for Unreal, with LODs, PBR textures and attach sockets.

| Gun | Folder | Game meshes | LODs | Textures | Preview |
|---|---|---|---|---|---|
| AR-15 (M4 / free-float build, swappable parts) | [`ar15`](ar15) | 16 + 32 loose kit parts | LOD1, LOD2 | 4K/2K/1K mask atlases | [render](ar15/render.png) · [exploded](ar15/exploded.png) |
| Glock 17 Gen 5 | [`glock17`](glock17) | 5 | LOD1, LOD2 | 4K/2K per part | [render](glock17/render.png) · [exploded](glock17/exploded.png) |
| MAC-10 | [`mac10`](mac10) | 4 | LOD1, LOD2 | 4K/2K | [render](mac10/render.jpg) · [exploded](mac10/exploded.jpg) |
| Mossberg 590 (20 in, walnut) | [`m590`](m590) | 9 | none | 4K | [render](m590/render.png) · [exploded](m590/exploded.png) |
| Kar98k | [`kar98k`](kar98k) | 3 | LOD1, LOD2 | 4K | [render](kar98k/render.png) |

## Conventions
- **FBX for Unreal:** imports at real-world scale, Z up. Mesh names are the Unreal asset names (`SM_<Gun>_<Part>`); material slot names are the texture set names.
- **Textures:** `T_<Gun>_<Set>_{BaseColor,Normal,ORM}.png`. BaseColor is sRGB. ORM is linear (R = ambient occlusion, G = roughness, B = metallic). Normal maps are **OpenGL** tangent space: flip green in Unreal. The AR-15 uses mask atlases and a procedural material instead; see [`ar15/MATERIALS.md`](ar15/MATERIALS.md).
- **Sockets:** `sockets/*.json` lists the attach points the game uses (muzzle, chamber, aim and so on), in mesh space.
- **Parts:** "body" meshes are the gun without its moving part (bolt, pump, slide), so the moving part can animate on its own.

Who built what: the AR-15 and Glock were built by Claude from Python Blender scripts (included under `scripts/`); the MAC-10, Mossberg 590 and Kar98k were built by Codex. All of it was art-directed by Moosie Studios. Reference photos are not included.
