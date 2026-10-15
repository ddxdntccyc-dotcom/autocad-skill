# AutoCAD skill for Claude

A [Claude skill](https://docs.claude.com/en/docs/agents-and-tools/agent-skills/overview) that lets Claude create, read and edit AutoCAD drawings and drive AutoCAD with command scripts.

- **DXF** files are created and edited directly (via [ezdxf](https://ezdxf.mozman.de/)) — works on any OS, no AutoCAD needed.
- **DWG** conversion, plotting and anything else from AutoCAD's command line run through a generated `.scr` script that launches AutoCAD (macOS or Windows).
- **Your files are never overwritten or deleted.** Every save goes to a new name (`plan-edited.dxf`, `plan-1.dxf`, …).
- Nothing leaves your computer.

## What you can ask

- "Draw a 5×4 m studio with a door on the south wall and dimensions"
- "What's in `~/Downloads/site-plan.dwg`? List the layers and the room labels"
- "Move everything on FURNITURE 30 cm to the right and save a copy"
- "Rename Layer1 to WALLS and make it red"
- "Convert this DXF to DWG", "Open it in AutoCAD"

## Install

### Claude Code (as a plugin)

```bash
/plugin marketplace add <your-github-user>/autocad-skill
/plugin install autocad@autocad-skill
```

### Claude Code (as a plain skill)

```bash
git clone https://github.com/<your-github-user>/autocad-skill.git
cp -r autocad-skill/skills/autocad ~/.claude/skills/
```

### Claude desktop / claude.ai

Download `autocad.zip` from the [Releases](../../releases) page (or zip the `skills/autocad` folder yourself) and upload it under **Settings → Capabilities → Skills**. In the claude.ai sandbox only the DXF features work, since AutoCAD isn't there.

## Requirements

- Python 3.10+
- `ezdxf` — installed automatically into a private venv (`~/.autocad-skill/venv`) the first time Claude runs `cad.py setup`
- AutoCAD (optional; only for DWG, plotting and scripts). Found automatically under `/Applications/Autodesk/AutoCAD 20xx` on macOS or `C:\Program Files\Autodesk\AutoCAD 20xx` on Windows.

## Configuration (optional environment variables)

| Variable | Default | Meaning |
|---|---|---|
| `AUTOCAD_WORKDIR` | `~/Documents/AutoCAD-Claude` | Where new drawings (`drawings/`) and scripts (`scripts/`) go |
| `AUTOCAD_APP` | auto-detected | Path to `AutoCAD 20xx.app` (macOS) or `acad.exe` (Windows) |
| `AUTOCAD_SKILL_HOME` | `~/.autocad-skill` | Where the private venv lives |

## Using the helper yourself

The skill is driven by one script, which you can also run by hand:

```bash
python3 skills/autocad/scripts/cad.py --help
python3 skills/autocad/scripts/cad.py describe examples/apartment-3-rooms.dxf
```

See [`skills/autocad/references/ops.md`](skills/autocad/references/ops.md) for the drawing/editing operations.

## Known limit

macOS passes a script to AutoCAD only when AutoCAD **starts**. If AutoCAD is already open, run the script yourself from **Tools → Run Script…** — Claude tells you which file.

## Layout

```
.claude-plugin/        plugin + marketplace manifests (for /plugin install)
skills/autocad/
  SKILL.md             instructions Claude reads
  scripts/cad.py       the helper (CLI)
  references/          ops list, AutoCAD scripting notes
examples/              a sample drawing
```

## License

MIT

---

## בעברית בקצרה

סקיל ל-Claude שמאפשר ליצור, לקרוא ולערוך שרטוטי AutoCAD. קובצי DXF נערכים ישירות; DWG, הדפסה לPDF ופקודות אחרות רצים דרך סקריפט ש-AutoCAD מריץ. הקבצים המקוריים אף פעם לא נדרסים. התקנה: ראו למעלה ("Install").
