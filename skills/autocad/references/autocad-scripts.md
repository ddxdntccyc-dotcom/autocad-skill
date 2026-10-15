# Writing AutoCAD scripts (.scr)

`cad.py run-script` writes each input line to a `.scr` file (in the scripts folder, so the user can read it later) and starts AutoCAD with it. A script is replayed exactly as if typed at the command line, so it only works if every prompt gets an answer.

## Rules that make scripts run unattended

1. **One line = one Enter.** Each line is a command or an answer to the previous prompt. An empty line is a bare Enter (accept default / finish a command).
2. **Turn dialogs off.** Start with `FILEDIA 0` (and `CMDDIA 0` for plotting) so commands ask on the command line instead of opening a file dialog, and restore with `FILEDIA 1` / `CMDDIA 1` at the end.
3. **Use the dash version of commands** where it exists — `-LAYER`, `-PLOT`, `-PURGE`, `-INSERT`, `-XREF` — they prompt on the command line instead of opening a dialog.
4. **Quote paths** that contain spaces: `"/Users/me/My Drawings/plan.pdf"`.
5. **Never overwrite**: use `SAVEAS` to a new name rather than `QSAVE`/`SAVE`, and pick output names that don't exist yet.
6. **Spaces are Enter too** in most prompts, so don't put a space inside a value unless it is in quotes.
7. When unsure of a command's exact prompt sequence, tell the user it's a best guess and keep the script short; if it stalls, AutoCAD just waits at the prompt and the user can finish by hand.

## Examples

Layer cleanup:
```
-LAYER
M
DIMENSIONS
C
1
DIMENSIONS

ZOOM
E
```

Purge and audit (on a drawing passed with `--drawing`), then save a copy:
```
FILEDIA 0
-PURGE
A
*
N
AUDIT
Y
SAVEAS
2018
"/Users/me/Documents/AutoCAD-Claude/drawings/plan-clean.dwg"
FILEDIA 1
```

Plot model space to PDF (prompt order can differ between versions — confirm with the user before relying on it):
```
FILEDIA 0
CMDDIA 0
-PLOT
Y

AutoCAD PDF (General Documentation).pc3
ISO full bleed A3 (420.00 x 297.00 MM)
M
L
N
E
F
C
Y
monochrome.ctb
Y
A
"/Users/me/Documents/AutoCAD-Claude/drawings/plan.pdf"
N
Y
CMDDIA 1
FILEDIA 1
```

## Platforms

- **macOS**: the helper runs `open -a <AutoCAD.app> --args <drawing> -b <script>`. Start-up arguments only reach a fresh launch — if AutoCAD is already open, the user must run the script from **Tools → Run Script…**.
- **Windows**: the helper runs `acad.exe <drawing> /b <script>`. Same caveat for an already-running AutoCAD (use the `SCRIPT` command there).
