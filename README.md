# 3d

Blender scenes built as Python scripts and rendered headless (Blender 5 via `pip install bpy`, Python 3.11).

Each folder holds one model: `<name>.py` builds and renders it, `<name>.blend` is the scene, and `<name>.png` is the render.

```sh
uv venv -p 3.11 .venv && uv pip install -p .venv bpy
.venv/bin/python donut/donut.py 128   # trailing number = render samples (16 for previews)
```

## Guns

[`guns/`](guns) holds game-ready firearm models (AR-15, Glock 17, MAC-10, Mossberg 590, Kar98k) built for the LootNShoot game: FBX parts with LODs, PBR textures, sockets and renders. That folder has its own layout; see [`guns/README.md`](guns/README.md).
