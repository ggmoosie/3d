# Skills

Claude Code skills behind the models in this repo: the step-by-step workflows, quality gates and lessons learned for building game assets in Blender and bringing them into Unreal Engine 5.5 (LootNShoot). Each folder has a `SKILL.md`; copy a folder into `.claude/skills/` (project) or `~/.claude/skills/` (user) to use it.

| Skill | What it covers |
|---|---|
| [`level-factory`](level-factory/SKILL.md) | A whole level, Blender-first: brief, to-scale HTML plan, textures and print atlas, prop kit, map layout and review renders, FBX export, gameplay C++, phased UE import, Blueprints, scripted map build, planned lighting, MapOpt optimisation and culling, verification tour. Reference: the GunRange level. |
| [`gun-pipeline`](gun-pipeline/SKILL.md) | A new gun from plan to the player's hands: model, one-shot game import, rough animations, hand-pose hand-off, with the lessons from the Glock 17, AR-15 and Mossberg 590 imports. |
| [`model-factory`](model-factory/SKILL.md) | Any 3D asset end to end: stage gates, Blender headless scripts, bakes, UE import, sockets, LODs, collision, and the automatic checks (`scripts/mesh_qc.py`, matched-camera comparison). |
| [`blender-3d`](blender-3d/SKILL.md) | The cross-project Blender rules and quality gates (same checker scripts), plus a lessons log. |
| [`lns-game-import`](lns-game-import/SKILL.md) | Getting clips, guns, data rows and icons into the game: the animation contract, editor access, exact commands and the verify pass. |

Paths like `<repo>` and `D:/Blender/blender.exe` are placeholders for your own project and install. Reference photos are never part of these workflows' outputs.
