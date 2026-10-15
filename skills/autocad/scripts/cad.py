#!/usr/bin/env python3
"""AutoCAD helper for Claude (command-line version of the AutoCAD MCP server).

Works with drawing files (.dxf) through the ezdxf library, and launches
AutoCAD (macOS or Windows) with command scripts (.scr) for things only
AutoCAD can do, such as reading/writing .dwg files or plotting.

Safety: existing files are never overwritten or deleted. Saving to a name
that already exists picks a new name ("-1", "-2", ...) instead.

Run `python3 cad.py --help` for the list of commands.
"""

import argparse
import glob
import json
import logging
import os
import platform
import subprocess
import sys
import time
from collections import Counter
from pathlib import Path

HOME_DIR = Path(os.environ.get("AUTOCAD_SKILL_HOME", Path.home() / ".autocad-skill"))
VENV = HOME_DIR / "venv"
VENV_PY = VENV / ("Scripts/python.exe" if os.name == "nt" else "bin/python")
WORKDIR = Path(os.environ.get("AUTOCAD_WORKDIR", Path.home() / "Documents" / "AutoCAD-Claude"))
DRAWINGS = WORKDIR / "drawings"
SCRIPTS = WORKDIR / "scripts"

UNITS = {"inch": 1, "ft": 2, "mm": 4, "cm": 5, "m": 6}
UNIT_NAMES = {v: k for k, v in UNITS.items()}


class CadError(Exception):
    pass


# ---------- environment ----------

def _load_ezdxf():
    """Import ezdxf, re-running this script with the skill's own venv if needed."""
    try:
        import ezdxf  # noqa: F401
        return ezdxf
    except ImportError:
        # Compare prefixes: the venv python is often a symlink to the system one.
        if VENV_PY.exists() and Path(sys.prefix).resolve() != VENV.resolve():
            os.execv(str(VENV_PY), [str(VENV_PY), *sys.argv])
        raise CadError("The ezdxf library is missing. Run: python3 cad.py setup")


def _autocad_app() -> Path | None:
    """Find AutoCAD: $AUTOCAD_APP, else the newest installed version."""
    if os.environ.get("AUTOCAD_APP"):
        return Path(os.environ["AUTOCAD_APP"])
    system = platform.system()
    if system == "Darwin":
        found = sorted(glob.glob("/Applications/Autodesk/AutoCAD 20*/AutoCAD 20*.app"))
    elif system == "Windows":
        found = sorted(glob.glob(r"C:\Program Files\Autodesk\AutoCAD 20*\acad.exe"))
    else:
        found = []
    return Path(found[-1]) if found else None


def _require_autocad() -> Path:
    app = _autocad_app()
    if not app or not app.exists():
        raise CadError("AutoCAD was not found. Set the AUTOCAD_APP environment "
                       "variable to the AutoCAD app (macOS) or acad.exe (Windows).")
    return app


# ---------- helpers ----------

def _resolve(path: str) -> Path:
    """Relative paths and bare names live in the drawings folder."""
    p = Path(path).expanduser()
    return p if p.is_absolute() else DRAWINGS / p


def _existing(path: str) -> Path:
    p = _resolve(path)
    if not p.exists() and Path(path).expanduser().exists():
        p = Path(path).expanduser().resolve()  # relative to the current folder
    if not p.exists():
        raise CadError(f"File not found: {p}")
    return p


def _free_name(path: Path) -> Path:
    """Return path, or path-1, path-2 ... if it already exists."""
    if not path.exists():
        return path
    n = 1
    while True:
        candidate = path.with_name(f"{path.stem}-{n}{path.suffix}")
        if not candidate.exists():
            return candidate
        n += 1


def _read_dxf(path: str):
    ezdxf = _load_ezdxf()
    p = _existing(path)
    if p.suffix.lower() == ".dwg":
        raise CadError("This is a .dwg file. Run `cad.py dwg-to-dxf` on it first.")
    return ezdxf.readfile(p), p


def _save(doc, target: Path) -> Path:
    if target.suffix.lower() != ".dxf":
        target = target.with_suffix(".dxf")
    target.parent.mkdir(parents=True, exist_ok=True)
    target = _free_name(target)
    doc.saveas(target)
    return target


def _read_json_arg(value: str):
    """Ops come from a file path, '-' for stdin, or inline JSON."""
    if value == "-":
        text = sys.stdin.read()
    elif value.lstrip().startswith(("[", "{")):
        text = value
    else:
        text = Path(value).expanduser().read_text(encoding="utf-8")
    data = json.loads(text)
    return data["ops"] if isinstance(data, dict) else data


def _ensure_layer(doc, layer: str):
    if layer not in doc.layers:
        doc.layers.add(layer)


def _select(doc, layer: str = "", entity_type: str = ""):
    found = []
    for e in doc.modelspace():
        if layer and e.dxf.get("layer", "0").lower() != layer.lower():
            continue
        if entity_type and e.dxftype().lower() != entity_type.lower():
            continue
        found.append(e)
    return found


def _pick(doc, op: dict):
    handles = op.get("handles")
    if handles:
        db = doc.entitydb
        return [db[h] for h in handles if h in db]
    layer, etype = op.get("select_layer", ""), op.get("type", "")
    if not layer and not etype:
        raise CadError(f"'{op['op']}' needs handles, select_layer or type to choose objects.")
    return _select(doc, layer, etype)


def _describe_entity(e) -> dict:
    t = e.dxftype()
    info = {"handle": e.dxf.handle, "type": t, "layer": e.dxf.get("layer", "0")}
    r = lambda v: [round(float(c), 3) for c in v][:2]
    if t == "LINE":
        info.update(start=r(e.dxf.start), end=r(e.dxf.end),
                    length=round(e.dxf.start.distance(e.dxf.end), 3))
    elif t == "CIRCLE":
        info.update(center=r(e.dxf.center), radius=round(e.dxf.radius, 3))
    elif t == "ARC":
        info.update(center=r(e.dxf.center), radius=round(e.dxf.radius, 3),
                    start_angle=round(e.dxf.start_angle, 2),
                    end_angle=round(e.dxf.end_angle, 2))
    elif t == "LWPOLYLINE":
        info.update(points=[r(p) for p in e.get_points("xy")], closed=e.closed)
    elif t in ("TEXT", "MTEXT"):
        info.update(text=e.dxf.text if t == "TEXT" else e.text,
                    position=r(e.dxf.insert))
    elif t == "INSERT":
        info.update(block=e.dxf.name, position=r(e.dxf.insert))
    elif t == "DIMENSION":
        info.update(measurement=round(e.get_measurement(), 3)
                    if hasattr(e, "get_measurement") else None)
    return info


# ---------- operations (shared by `new` and `edit`) ----------

def _apply(doc, op: dict) -> str:
    msp = doc.modelspace()
    kind = op.get("op")
    layer = op.get("layer", "0")
    attribs = {"layer": layer}

    if kind in ("line", "polyline", "rectangle", "circle", "arc", "text", "dimension"):
        _ensure_layer(doc, layer)

    if kind == "layer":
        name, colour = op["name"], op.get("colour", op.get("color", 7))
        linetype = op.get("linetype", "Continuous")
        if name in doc.layers:
            lay = doc.layers.get(name)
            lay.color, lay.dxf.linetype = colour, linetype
            return f"layer '{name}' updated"
        doc.layers.add(name, color=colour, linetype=linetype)
        return f"layer '{name}' added"
    if kind == "line":
        e = msp.add_line(op["start"], op["end"], dxfattribs=attribs)
    elif kind == "polyline":
        e = msp.add_lwpolyline(op["points"], close=op.get("closed", False), dxfattribs=attribs)
    elif kind == "rectangle":
        x, y = op["corner"]
        w, h = op["width"], op["height"]
        e = msp.add_lwpolyline([(x, y), (x + w, y), (x + w, y + h), (x, y + h)],
                               close=True, dxfattribs=attribs)
    elif kind == "circle":
        e = msp.add_circle(op["center"], op["radius"], dxfattribs=attribs)
    elif kind == "arc":
        e = msp.add_arc(op["center"], op["radius"], op["start_angle"], op["end_angle"],
                        dxfattribs=attribs)
    elif kind == "text":
        e = msp.add_text(op["text"], height=op.get("height", 2.5),
                         rotation=op.get("rotation", 0),
                         dxfattribs={**attribs, "insert": op["at"]})
    elif kind == "dimension":
        dim = msp.add_aligned_dim(p1=op["start"], p2=op["end"], distance=op.get("offset", 10),
                                  dimstyle="EZDXF", dxfattribs=attribs)
        dim.render()
        return "dimension added"
    elif kind == "move":
        targets = _pick(doc, op)
        for t in targets:
            t.translate(op.get("dx", 0), op.get("dy", 0), 0)
        return f"moved {len(targets)} object(s)"
    elif kind == "delete":
        targets = _pick(doc, op)
        for t in targets:
            msp.delete_entity(t)
        return f"deleted {len(targets)} object(s) from the working copy"
    elif kind == "change_layer":
        targets = _pick(doc, op)
        _ensure_layer(doc, op["to"])
        for t in targets:
            t.dxf.layer = op["to"]
        return f"{len(targets)} object(s) moved to layer '{op['to']}'"
    elif kind == "rename_layer":
        if op["old"] not in doc.layers:
            raise CadError(f"No layer called '{op['old']}'.")
        doc.layers.get(op["old"]).rename(op["new"])
        return f"layer '{op['old']}' renamed to '{op['new']}'"
    else:
        raise CadError(f"Unknown op: {kind!r}")
    return f"{kind} added (handle {e.dxf.handle})"


def _apply_all(doc, ops: list[dict]) -> list[str]:
    results = []
    for i, op in enumerate(ops, 1):
        try:
            results.append(_apply(doc, op))
        except KeyError as missing:
            raise CadError(f"op #{i} ({op.get('op')}) is missing {missing}") from None
    return results


# ---------- commands ----------

def cmd_setup(args):
    VENV.parent.mkdir(parents=True, exist_ok=True)
    if not VENV_PY.exists():
        subprocess.run([sys.executable, "-m", "venv", str(VENV)], check=True)
    subprocess.run([str(VENV_PY), "-m", "pip", "install", "--quiet", "--upgrade", "ezdxf"],
                   check=True)
    print(f"Ready. ezdxf installed in {VENV}")
    cmd_check(args)


def cmd_check(args):
    try:
        ezdxf = _load_ezdxf()
        ez = ezdxf.__version__
    except CadError:
        ez = None
    app = _autocad_app()
    print(json.dumps({
        "ezdxf": ez or "missing - run: python3 cad.py setup",
        "autocad": str(app) if app and app.exists() else "not found (DXF work still works)",
        "drawings_folder": str(DRAWINGS),
        "scripts_folder": str(SCRIPTS),
    }, indent=2))


def cmd_new(args):
    ezdxf = _load_ezdxf()
    if args.units not in UNITS:
        raise CadError(f"units must be one of {list(UNITS)}")
    doc = ezdxf.new("R2018", setup=True, units=UNITS[args.units])
    results = _apply_all(doc, _read_json_arg(args.ops)) if args.ops else []
    out = _save(doc, _resolve(args.name))
    print(json.dumps({"saved": str(out), "units": args.units, "results": results}, indent=2))


def cmd_edit(args):
    doc, src = _read_dxf(args.file)
    results = _apply_all(doc, _read_json_arg(args.ops))
    target = _resolve(args.out) if args.out else src.with_name(f"{src.stem}-edited.dxf")
    out = _save(doc, target)
    print(json.dumps({"source": str(src), "saved": str(out), "results": results}, indent=2))


def cmd_describe(args):
    doc, src = _read_dxf(args.file)
    from ezdxf import bbox
    msp = doc.modelspace()
    per_layer = Counter(e.dxf.get("layer", "0") for e in msp)
    extents = bbox.extents(msp)
    size = None
    if extents.has_data:
        size = {"min": [round(v, 3) for v in extents.extmin][:2],
                "max": [round(v, 3) for v in extents.extmax][:2],
                "width": round(extents.size.x, 3), "height": round(extents.size.y, 3)}
    texts = [e.dxf.text for e in msp.query("TEXT")] + [e.text for e in msp.query("MTEXT")]
    print(json.dumps({
        "file": str(src),
        "units": UNIT_NAMES.get(doc.units, f"code {doc.units}"),
        "layers": [{"name": l.dxf.name, "colour": l.color, "linetype": l.dxf.linetype,
                    "objects": per_layer.get(l.dxf.name, 0)} for l in doc.layers],
        "object_counts": dict(Counter(e.dxftype() for e in msp)),
        "extents": size,
        "texts": texts[:200],
        "blocks_used": dict(Counter(e.dxf.name for e in msp.query("INSERT"))),
    }, indent=2, ensure_ascii=False))


def cmd_list(args):
    doc, _ = _read_dxf(args.file)
    found = _select(doc, args.layer, args.type)[:args.limit]
    print(json.dumps([_describe_entity(e) for e in found], indent=2, ensure_ascii=False))


def _launch_autocad(extra: list[str]) -> str:
    app = _require_autocad()
    if platform.system() == "Darwin":
        running = subprocess.run(["pgrep", "-x", "AutoCAD"], capture_output=True).returncode == 0
        subprocess.Popen(["open", "-a", str(app), "--args", *extra])
    else:
        running = False
        # acad.exe spells the script switch /b instead of -b.
        subprocess.Popen([str(app), *["/b" if a == "-b" else a for a in extra]])
    if running:
        return ("AutoCAD was already open. macOS only passes start-up options to a "
                "fresh launch, so the script may not run automatically. If nothing "
                "happens, use Tools > Run Script in AutoCAD and pick the script file.")
    return "AutoCAD is starting."


def _write_script(lines: list[str]) -> Path:
    SCRIPTS.mkdir(parents=True, exist_ok=True)
    path = _free_name(SCRIPTS / f"script-{time.strftime('%Y%m%d-%H%M%S')}.scr")
    # AutoCAD scripts need a trailing newline after the last command.
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return path


def cmd_open(args):
    app = _require_autocad()
    p = _existing(args.file)
    if platform.system() == "Darwin":
        subprocess.Popen(["open", "-a", str(app), str(p)])
    else:
        subprocess.Popen([str(app), str(p)])
    print(f"Opening {p.name} in AutoCAD.")


def cmd_run_script(args):
    source = sys.stdin.read() if args.commands == "-" else \
        Path(args.commands).expanduser().read_text(encoding="utf-8")
    lines = source.rstrip("\n").split("\n")
    script = _write_script(lines)
    extra = [str(_existing(args.drawing))] if args.drawing else []
    print(f"Script saved to {script}. " + _launch_autocad([*extra, "-b", str(script)]))


def cmd_dwg_to_dxf(args):
    src = _existing(args.file)
    out = _free_name(src.with_suffix(".dxf"))
    script = _write_script(["FILEDIA 0", "DXFOUT", f'"{out}"', "V", "2018", "16",
                            "FILEDIA 1", "CLOSE"])
    note = _launch_autocad([str(src), "-b", str(script)])
    print(json.dumps({"output": str(out), "script": str(script), "note": note,
                      "next": f"cad.py wait \"{out}\""}, indent=2))


def cmd_dxf_to_dwg(args):
    src = _existing(args.file)
    out = _free_name(src.with_suffix(".dwg"))
    script = _write_script(["FILEDIA 0", "SAVEAS", "2018", f'"{out}"', "FILEDIA 1"])
    note = _launch_autocad([str(src), "-b", str(script)])
    print(json.dumps({"output": str(out), "script": str(script), "note": note,
                      "next": f"cad.py wait \"{out}\""}, indent=2))


def cmd_wait(args):
    p = _resolve(args.file)
    deadline = time.time() + args.timeout
    while time.time() < deadline:
        if p.exists() and p.stat().st_size > 0:
            time.sleep(1)  # let AutoCAD finish writing
            print(f"Ready: {p}")
            return
        time.sleep(1)
    raise CadError(f"{p} did not appear within {args.timeout}s. If AutoCAD was already "
                   "open, run the script from Tools > Run Script.")


def main():
    logging.getLogger("ezdxf").setLevel(logging.ERROR)
    ap = argparse.ArgumentParser(description="AutoCAD helper for Claude.")
    sub = ap.add_subparsers(dest="cmd", required=True)

    sub.add_parser("setup", help="install ezdxf into the skill's own venv").set_defaults(fn=cmd_setup)
    sub.add_parser("check", help="show what is installed and where files go").set_defaults(fn=cmd_check)

    p = sub.add_parser("new", help="create a new .dxf, optionally drawing ops into it")
    p.add_argument("name", help="file name, e.g. kitchen.dxf (relative = drawings folder)")
    p.add_argument("--units", default="mm", help="mm, cm, m, inch or ft")
    p.add_argument("--ops", help="ops JSON: file path, '-' for stdin, or inline")
    p.set_defaults(fn=cmd_new)

    p = sub.add_parser("edit", help="apply ops to a .dxf and save as a NEW file")
    p.add_argument("file")
    p.add_argument("--ops", required=True, help="ops JSON: file path, '-' for stdin, or inline")
    p.add_argument("--out", help="output name (default <name>-edited.dxf)")
    p.set_defaults(fn=cmd_edit)

    p = sub.add_parser("describe", help="summary: units, layers, counts, size, texts")
    p.add_argument("file")
    p.set_defaults(fn=cmd_describe)

    p = sub.add_parser("list", help="list objects with handle, type, layer, geometry")
    p.add_argument("file")
    p.add_argument("--layer", default="")
    p.add_argument("--type", default="", help="LINE, CIRCLE, LWPOLYLINE, TEXT, ...")
    p.add_argument("--limit", type=int, default=200)
    p.set_defaults(fn=cmd_list)

    p = sub.add_parser("open", help="open a .dxf/.dwg in AutoCAD for the user")
    p.add_argument("file")
    p.set_defaults(fn=cmd_open)

    p = sub.add_parser("run-script", help="write a .scr and launch AutoCAD with it")
    p.add_argument("commands", help="file with one command line per line, or '-' for stdin")
    p.add_argument("--drawing", help="drawing to open before the script runs")
    p.set_defaults(fn=cmd_run_script)

    p = sub.add_parser("dwg-to-dxf", help="ask AutoCAD to export a .dwg as .dxf")
    p.add_argument("file")
    p.set_defaults(fn=cmd_dwg_to_dxf)

    p = sub.add_parser("dxf-to-dwg", help="ask AutoCAD to save a .dxf as .dwg")
    p.add_argument("file")
    p.set_defaults(fn=cmd_dxf_to_dwg)

    p = sub.add_parser("wait", help="wait until a file AutoCAD is writing appears")
    p.add_argument("file")
    p.add_argument("--timeout", type=int, default=90)
    p.set_defaults(fn=cmd_wait)

    args = ap.parse_args()
    try:
        args.fn(args)
    except CadError as err:
        print(f"Error: {err}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
