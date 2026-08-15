#!/usr/bin/env python3
"""Assemble the Elder Weathers release archive.

Builds a mod-manager-installable zip: the plugin at the archive root (so a mod
manager drops it straight into Data/), plus the reference docs. Build the ESP
first if dist/ is empty:

    PYTHONPATH=src python -m elder_weathers build --skyrim-esm "<Skyrim.esm>" --out dist/EWWeathers.esp
    python scripts/package.py
"""
import os
import shutil
import zipfile

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
VERSION = "1.0.0"
DIST = os.path.join(ROOT, "dist")
STAGE = os.path.join(DIST, f"ElderWeathers-{VERSION}")


def copy(src, dst):
    os.makedirs(os.path.dirname(dst), exist_ok=True)
    shutil.copy2(src, dst)


def main():
    esp = os.path.join(DIST, "EWWeathers.esp")
    if not os.path.exists(esp):
        raise SystemExit("dist/EWWeathers.esp not found; build the plugin first")

    if os.path.exists(STAGE):
        shutil.rmtree(STAGE)
    os.makedirs(STAGE)

    # the plugin at the archive root -> installs to Data/
    copy(esp, os.path.join(STAGE, "EWWeathers.esp"))
    for d in ("README.md", "LICENSE"):
        p = os.path.join(ROOT, d)
        if os.path.exists(p):
            copy(p, os.path.join(STAGE, "Docs", d))

    # project-docs/NEXUS-PAGE.md is deliberately NOT shipped. It is upload-form
    # scaffolding: category, raw BBCode, and a permissions checklist addressed
    # to the author. Users installing the mod have no use for it.

    archive = os.path.join(DIST, f"ElderWeathers-{VERSION}.zip")
    if os.path.exists(archive):
        os.remove(archive)
    with zipfile.ZipFile(archive, "w", zipfile.ZIP_DEFLATED) as z:
        for base, _, files in os.walk(STAGE):
            for fn in files:
                full = os.path.join(base, fn)
                z.write(full, os.path.relpath(full, STAGE))

    size = os.path.getsize(archive)
    print(f"packaged {archive} ({size / 1024:.0f} KiB)")
    for base, _, files in os.walk(STAGE):
        for fn in sorted(files):
            print("  " + os.path.relpath(os.path.join(base, fn), STAGE).replace("\\", "/"))


if __name__ == "__main__":
    main()
