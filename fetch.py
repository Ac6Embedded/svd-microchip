#!/usr/bin/env python3
"""Fetch Microchip SAM / PIC32C SVD files from packs.download.microchip.com.

Incremental. Every run downloads only the pack index (metadata) and compares
the latest version of every pack whose name matches (SAM*|PIC32C*)_DFP against
the versions recorded in manifest.json. Unchanged packs are neither downloaded
nor re-extracted. If nothing changed the script prints 'up to date' and leaves
the working tree untouched. Changed packs are downloaded, their <FAMILY>/
directory at the repo root is rebuilt, files are validated, and manifest.json
is updated.

Deleting manifest.json forces a full rebuild, so the original full-fetch
behavior is preserved.

Python 3 stdlib only, runs on Linux and Windows. Downloaded atpacks are cached
in .work/packs, but incremental behavior does not depend on that cache: it
comes from the version comparison against manifest.json.
"""

import hashlib
import json
import re
import shutil
import sys
import time
import urllib.request
import xml.etree.ElementTree as ET
import zipfile
from datetime import datetime, timezone
from pathlib import Path

BASE = "https://packs.download.microchip.com"
ROOT = Path(__file__).resolve().parent
WORK = ROOT / ".work"
PACKS = WORK / "packs"
SVD_BASE = ROOT
LICDIR = ROOT / "LICENSES"

# Entries at the repo root that are never family directories and must never
# be deleted by a full rebuild. Everything else at the root is a family dir.
PROTECTED = {
    ".git", ".github", ".gitignore", ".work",
    "LICENSES", "README.md", "manifest.json", "fetch.py",
}


def clean_family_dirs():
    """Remove only family directories at the repo root.

    Full-rebuild cleanup. The SVD output base is now the repo root itself, so
    a blind rmtree(SVD_BASE) would destroy the whole repository including .git.
    This deletes each child directory of ROOT except the protected entries and
    leaves every non-family file and directory untouched.
    """
    for child in ROOT.iterdir():
        if child.is_dir() and child.name not in PROTECTED:
            shutil.rmtree(child)

# Pack selection: Arm SAM and PIC32C device family packs.
# This intentionally excludes AVR, XMEGA, PIC8/16/18/24, dsPIC and the
# MIPS-based PIC32M* packs, none of which match this pattern.
PACK_RE = re.compile(r"^(SAM|PIC32C).*_DFP$")

UA = "Mozilla/5.0 (svd-microchip fetch script)"


def download(url, dest, attempts=3, force=False):
    """Stream url to dest with retries.

    Returns True if a network download happened, False if an existing cached
    copy was kept. With force=True the file is always re-downloaded.
    """
    dest = Path(dest)
    if not force and dest.exists() and dest.stat().st_size > 0:
        print(f"  keep {dest.name} ({dest.stat().st_size} bytes)")
        return False
    tmp = dest.with_suffix(dest.suffix + ".part")
    for i in range(attempts):
        try:
            req = urllib.request.Request(url, headers={"User-Agent": UA})
            with urllib.request.urlopen(req, timeout=120) as r, open(tmp, "wb") as f:
                shutil.copyfileobj(r, f, 1024 * 1024)
            tmp.replace(dest)
            print(f"  got  {dest.name} ({dest.stat().st_size} bytes)")
            return True
        except Exception as e:
            print(f"  retry {i + 1}/{attempts} {url}: {e}")
            time.sleep(3)
    raise RuntimeError(f"download failed: {url}")


def parse_index(path):
    """Return sorted list of (pack_name, version) for packs we want."""
    packs = []
    for _, el in ET.iterparse(str(path)):
        if el.tag == "pdsc":
            full = el.get("name", "")  # e.g. Microchip.SAMD21_DFP.pdsc
            m = re.match(r"^Microchip\.(.+)\.pdsc$", full)
            if m and PACK_RE.match(m.group(1)):
                packs.append((m.group(1), el.get("version")))
            el.clear()
    return sorted(packs)


def family_of(pack_name):
    """Microchip.PIC32CM-JH_DFP -> PIC32CM_JH, SAMD21_DFP -> SAMD21."""
    return pack_name[: -len("_DFP")].replace("-", "_")


def load_manifest():
    """Return the parsed manifest, or None if missing or unreadable."""
    path = ROOT / "manifest.json"
    if not path.exists():
        return None
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None


def extract_pack(name, version, atpath, lic_seen):
    """Extract one atpack into <FAMILY>/ and LICENSES/.

    Returns (file_entries, lic_name, issues). The family directory must not
    contain stale files from a previous version; the caller removes it first.
    """
    fam = family_of(name)
    famdir = SVD_BASE / fam
    entries = []
    issues = []
    lic_name = None
    with zipfile.ZipFile(atpath) as z:
        svd_members = [n for n in z.namelist() if n.lower().endswith(".svd")]
        lic_members = [
            n for n in z.namelist()
            if re.search(r"(?i)(^|/)(license|licence)[^/]*$", n)
        ]
        for member in sorted(svd_members):
            data = z.read(member)
            base = Path(member).name
            famdir.mkdir(parents=True, exist_ok=True)
            out = famdir / base
            if out.exists():
                if out.read_bytes() == data:
                    continue
                issues.append(
                    f"{name}: duplicate {base} with different content, "
                    f"kept first copy, skipped {member}"
                )
                continue
            # validate before keeping
            try:
                root = ET.fromstring(data)
            except ET.ParseError as e:
                issues.append(f"{name}: {member} not well-formed ({e}), dropped")
                continue
            tag = root.tag.split("}")[-1]
            if tag != "device":
                issues.append(
                    f"{name}: {member} root element is '{tag}' not 'device', dropped"
                )
                continue
            out.write_bytes(data)
            entries.append({
                "path": f"{fam}/{base}",
                "device": base[: -len(".svd")],
                "family": fam,
                "source": f"Microchip.{name}.{version}",
                "provenance": "pristine",
            })
        # license files: keep one copy per unique content
        for member in sorted(lic_members):
            data = z.read(member)
            h = hashlib.sha256(data).hexdigest()
            if h not in lic_seen:
                fname = f"{name}-{Path(member).name}"
                (LICDIR / fname).write_bytes(data)
                lic_seen[h] = fname
            if lic_name is None:
                lic_name = lic_seen[h]
    if not entries:
        issues.append(f"{name}: no usable .svd files in atpack")
        if famdir.exists() and not any(famdir.iterdir()):
            famdir.rmdir()
    return entries, lic_name, issues


def main():
    WORK.mkdir(exist_ok=True)
    PACKS.mkdir(exist_ok=True)

    # Metadata check: always fetch a fresh index, it is the source of truth
    # for the latest pack versions.
    print("downloading pack index (metadata)")
    idx = WORK / "index.idx"
    download(f"{BASE}/index.idx", idx, force=True)
    print("parsing index")
    packs = parse_index(idx)
    print(f"selected {len(packs)} packs")

    manifest = load_manifest()
    if manifest is None:
        # no manifest to compare against: full rebuild from a clean tree.
        # Only family directories are removed; protected repo entries stay.
        clean_family_dirs()

    old_sources = {}
    old_files_by_family = {}
    old_issues = []
    if manifest is not None and SVD_BASE.is_dir():
        for s in manifest.get("sources", []):
            m = re.match(r"^Microchip\.(.+)$", s.get("name", ""))
            if m:
                old_sources[m.group(1)] = s
        for f in manifest.get("files", []):
            old_files_by_family.setdefault(f["family"], []).append(f)
        old_issues = list(manifest.get("issues", []))

    # Compare index versions against the manifest to find work to do.
    changed = []
    for name, version in packs:
        old = old_sources.get(name)
        if old is None or old.get("version") != version:
            changed.append((name, version))
        elif old.get("files", 0) > 0 and not (SVD_BASE / family_of(name)).is_dir():
            # manifest says this family has files but the directory is gone
            changed.append((name, version))
    removed = sorted(set(old_sources) - {n for n, _ in packs})

    if not changed and not removed:
        print("artifact downloads: 0")
        print("up to date")
        return 0

    print(f"{len(changed)} pack(s) changed, {len(removed)} removed")
    LICDIR.mkdir(exist_ok=True)
    SVD_BASE.mkdir(exist_ok=True)

    # Seed the license dedupe map from the files already in LICENSES/ so a
    # partial rebuild reuses existing names instead of writing duplicates.
    lic_seen = {}
    for p in sorted(LICDIR.iterdir()):
        if p.is_file():
            lic_seen.setdefault(hashlib.sha256(p.read_bytes()).hexdigest(), p.name)

    # Keep old issues that do not concern changed or removed packs.
    stale = {n for n, _ in changed} | set(removed)
    issues = [line for line in old_issues if not any(n in line for n in stale)]

    downloads = 0
    built = {}  # pack name -> (source entry, file entries)
    for name, version in changed:
        fam = family_of(name)
        atname = f"Microchip.{name}.{version}.atpack"
        url = f"{BASE}/{atname}"
        print(f"pack {name} {version}")
        try:
            if download(url, PACKS / atname):
                downloads += 1
        except RuntimeError as e:
            issues.append(str(e))
            continue  # keep the previous state of this pack, if any
        if (SVD_BASE / fam).exists():
            shutil.rmtree(SVD_BASE / fam)
        entries, lic_name, pack_issues = extract_pack(
            name, version, PACKS / atname, lic_seen
        )
        issues.extend(pack_issues)
        built[name] = (
            {
                "name": f"Microchip.{name}",
                "url": url,
                "version": version,
                "license": "Apache-2.0",
                "license_file": lic_name,
                "files": len(entries),
            },
            entries,
        )

    for name in removed:
        fam = family_of(name)
        if (SVD_BASE / fam).exists():
            shutil.rmtree(SVD_BASE / fam)
        print(f"removed {name} (no longer in index)")

    # Assemble the manifest in index order, reusing entries for unchanged
    # packs and for changed packs whose download failed.
    sources = []
    files = []
    for name, version in packs:
        if name in built:
            src, entries = built[name]
        elif name in old_sources:
            src = old_sources[name]
            entries = old_files_by_family.get(family_of(name), [])
        else:
            continue  # new pack whose download failed, retried next run
        sources.append(src)
        files.extend(entries)

    total_bytes = sum((ROOT / f["path"]).stat().st_size for f in files)
    out = {
        "vendor": "Microchip",
        "generated": datetime.now(timezone.utc).strftime("%Y-%m-%d"),
        "index": f"{BASE}/index.idx",
        "sources": sources,
        "files": files,
        "stats": {"total_files": len(files), "total_bytes": total_bytes},
        "issues": issues,
    }
    # write bytes so line endings are LF on Windows and Linux alike
    (ROOT / "manifest.json").write_bytes(
        (json.dumps(out, indent=2) + "\n").encode("utf-8")
    )

    print(f"\n{len(files)} svd files, {total_bytes / 1e6:.1f} MB")
    print(f"artifact downloads: {downloads}")
    for i in issues:
        print("issue:", i)
    return 0


if __name__ == "__main__":
    sys.exit(main())
