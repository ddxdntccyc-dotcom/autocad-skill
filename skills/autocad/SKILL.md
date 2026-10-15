---
name: autocad
description: Create, read and edit AutoCAD drawings (.dxf and .dwg) and drive AutoCAD with command scripts (.scr). Use this skill whenever the user wants to draw a floor plan, room, layout, part outline or any 2D CAD drawing; asks what is inside a DXF/DWG file (layers, objects, sizes, texts); wants to move, delete or re-layer objects, rename layers or add dimensions; wants to convert DWG to DXF or back; or wants to open a drawing in AutoCAD or automate something AutoCAD does from its command line - even if they don't say "AutoCAD" and only mention a plan, a drawing file or CAD.
---

# AutoCAD

This skill lets you work on AutoCAD drawings through a small command-line helper, `scripts/cad.py`, that sits next to this file. It edits **.dxf** files directly (with the `ezdxf` library) and launches **AutoCAD** with a generated script for things only AutoCAD can do: reading/writing **.dwg**, plotting, or any other command-line feature.

Why this split: AutoCAD (especially on Mac) can't be remote-controlled while it is open, so the reliable path is to work on files, and hand AutoCAD a script only when it must do the work itself.

## First run

Use the absolute path of `scripts/cad.py` (the folder this SKILL.md is in). Call it `CAD` below.

```bash
python3 "$CAD" check
```

If `ezdxf` is reported missing, run `python3 "$CAD" setup` once. It creates a private virtual environment in `~/.autocad-skill/venv` and installs ezdxf there; afterwards `cad.py` switches to it automatically, so nothing touches the user's system Python.

`check` also shows where files go. Bare file names and relative paths resolve to the drawings folder (default `~/Documents/AutoCAD-Claude/drawings`, override with `AUTOCAD_WORKDIR`). Absolute paths are used as-is. If AutoCAD isn't found, DXF work still works; the user can set `AUTOCAD_APP` to point at it.

## Safety rules (the user's drawings matter)

- The helper never overwrites or deletes a file. Every save goes to a new name (`room.dxf` → `room-1.dxf` if taken; edits default to `<name>-edited.dxf`). Report the actual path it prints, since it may differ from what you asked for.
- Before `run-script`, show the user the AutoCAD commands you are about to run and why. Don't put commands in a script that overwrite or delete existing files (no `QSAVE`/`SAVE` over the original, no `ERASE` across a whole drawing they didn't ask for).
- Everything stays on the user's computer.

## Commands

| Goal | Command |
|---|---|
| New drawing (optionally with content) | `cad.py new NAME.dxf --units mm --ops OPS` |
| Change a drawing (saved as a new file) | `cad.py edit FILE.dxf --ops OPS [--out NAME.dxf]` |
| Summary: units, layers, counts, size, all text | `cad.py describe FILE.dxf` |
| Objects with handle, type, layer, geometry | `cad.py list FILE.dxf [--layer L] [--type LINE] [--limit N]` |
| Show it to the user in AutoCAD | `cad.py open FILE` |
| DWG → DXF (then read/edit the DXF) | `cad.py dwg-to-dxf FILE.dwg` then `cad.py wait OUT.dxf` |
| DXF → DWG | `cad.py dxf-to-dwg FILE.dxf` then `cad.py wait OUT.dwg` |
| Anything else AutoCAD's command line can do | `cad.py run-script - [--drawing FILE]` (commands on stdin) |

`OPS` is a JSON list of operations — pass `-` and feed it with a heredoc, so no temp file is needed:

```bash
python3 "$CAD" new studio.dxf --units mm --ops - <<'EOF'
[
  {"op": "layer", "name": "WALLS", "colour": 7},
  {"op": "layer", "name": "TEXT", "colour": 3},
  {"op": "rectangle", "corner": [0, 0], "width": 5000, "height": 4000, "layer": "WALLS"},
  {"op": "text", "text": "Studio 20 m²", "at": [2000, 2000], "height": 200, "layer": "TEXT"},
  {"op": "dimension", "start": [0, 0], "end": [5000, 0], "offset": -500}
]
EOF
```

The full list of ops (drawing and editing) with every field is in `references/ops.md` — read it the first time you build an ops list.

## Typical workflows

**Draw something new.** Settle units first (architecture usually mm; ask if unclear). Work out coordinates before writing ops: origin at a sensible corner, walls as closed polylines/rectangles, one layer per kind of thing (walls, doors, furniture, text, dimensions) with distinct colours. Text height and dimension offset should be in drawing units, so a 5 m room in mm needs text around 150–250, not 2.5. Create with `new`, then `describe` the result to confirm the extents match what you intended, then offer to `open` it.

**Understand an existing drawing.** `describe` first (cheap, gives the big picture), then `list` filtered by layer or type for detail. Summarise in the user's terms — rooms, sizes, labels — rather than dumping handles.

**Edit.** `list` to find the objects (note their handles, or use a layer/type filter), then `edit` with `move` / `delete` / `change_layer` / `rename_layer` and any new geometry. The original stays untouched; tell the user the new file name.

**DWG files.** ezdxf can't read DWG, so convert with `dwg-to-dxf`, wait for the output with `wait`, then work on the DXF. To hand back a DWG, `dxf-to-dwg` the edited DXF.

**AutoCAD scripts.** For plotting to PDF, purge, audit, attaching xrefs and similar, write the command lines exactly as typed at AutoCAD's command line and run them with `run-script`. Read `references/autocad-scripts.md` for the rules that make scripts run unattended (FILEDIA, quoting paths, answering every prompt).

**If AutoCAD was already open**, macOS doesn't pass the script to the running app; the helper says so. Tell the user to run it from **Tools → Run Script…** and give them the script path the helper printed. `wait` will time out in that case, which is expected.

## Explaining AutoCAD

Questions like "how do I make a viewport" or "what does OFFSET do" don't need the helper — just answer, ideally with the exact command names and prompts, and offer to do it for them when a script could.
