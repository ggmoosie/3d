# 3d

Blender scenes built as Python scripts and rendered headless (Blender 5 via `pip install bpy`, Python 3.11).

Each folder holds one model: `<name>.py` builds and renders it, `<name>.blend` is the scene, and `<name>.png` is the render.

```sh
uv venv -p 3.11 .venv && uv pip install -p .venv bpy
.venv/bin/python donut/donut.py 128   # trailing number = render samples (16 for previews)
```
