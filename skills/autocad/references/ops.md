# Ops reference

`cad.py new` and `cad.py edit` take a JSON list of ops, applied in order. A `{"ops": [...]}` object also works. Points are `[x, y]` in drawing units. Every drawing op accepts `"layer"` (default `"0"`); a layer that doesn't exist yet is created with default colour, so add a `layer` op first when colour or linetype matters.

## Layers

| op | fields | notes |
|---|---|---|
| `layer` | `name`, `colour` (default 7), `linetype` (default `Continuous`) | Updates colour/linetype if the layer exists. Colours: 1 red, 2 yellow, 3 green, 4 cyan, 5 blue, 6 magenta, 7 white/black, 8 grey. Linetypes: `Continuous`, `DASHED`, `CENTER`, `HIDDEN`, `PHANTOM`, `DOT`. |
| `rename_layer` | `old`, `new` | Objects on it follow. |

## Drawing

| op | fields |
|---|---|
| `line` | `start`, `end` |
| `polyline` | `points` (list of `[x, y]`), `closed` (default false) |
| `rectangle` | `corner` (lower-left), `width`, `height` |
| `circle` | `center`, `radius` |
| `arc` | `center`, `radius`, `start_angle`, `end_angle` — degrees, anticlockwise from +x |
| `text` | `text`, `at` (lower-left of the text), `height` (default 2.5), `rotation` (degrees) |
| `dimension` | `start`, `end`, `offset` (default 10) — aligned dimension drawn `offset` units to the left of the start→end direction; negative puts it on the right. For a horizontal line drawn left→right, positive = above. |

## Editing (choose objects)

Each editing op selects objects by **one** of:
- `handles`: list of handle strings from `cad.py list`, or
- `select_layer` and/or `type` (DXF type: `LINE`, `LWPOLYLINE`, `CIRCLE`, `ARC`, `TEXT`, `MTEXT`, `INSERT`, `DIMENSION`, `HATCH`...). Matching is case-insensitive.

| op | extra fields |
|---|---|
| `move` | `dx`, `dy` |
| `delete` | — |
| `change_layer` | `to` (created if missing) |

## Example: edit

```bash
python3 "$CAD" edit plan.dxf --ops - <<'EOF'
[
  {"op": "move", "select_layer": "FURNITURE", "dx": 300, "dy": 0},
  {"op": "delete", "handles": ["2F", "30"]},
  {"op": "change_layer", "type": "TEXT", "to": "ANNOTATION"},
  {"op": "rename_layer", "old": "Layer1", "new": "WALLS"},
  {"op": "circle", "center": [1200, 800], "radius": 450, "layer": "FURNITURE"}
]
EOF
```

## Beyond the ops

For anything the ops don't cover (hatches, blocks, splines, MTEXT, paper-space layouts), write a short Python script that uses ezdxf directly and run it with the skill's venv (`~/.autocad-skill/venv/bin/python`). Keep the same safety habit: read the source file, `saveas` to a new path that doesn't exist yet.
