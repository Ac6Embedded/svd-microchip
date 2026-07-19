# svd-microchip

CMSIS SVD files for Microchip Arm Cortex-M devices (SAM and PIC32C/CK/CX/CZ families),
extracted from the official Microchip pack repository.

## Contents

517 SVD files from 59 device family packs, one file per device,
laid out as `<FAMILY>/<DEVICE>.svd`.

| Family | Files |
|---|---|
| PIC32CK_GC | 20 |
| PIC32CK_SG | 22 |
| PIC32CM_GC00 | 3 |
| PIC32CM_GV | 6 |
| PIC32CM_JH | 24 |
| PIC32CM_LE | 8 |
| PIC32CM_LS | 11 |
| PIC32CM_MC | 4 |
| PIC32CM_PL | 11 |
| PIC32CM_SG00 | 3 |
| PIC32CX_BZ | 5 |
| PIC32CX_BZ3 | 16 |
| PIC32CX_BZ6 | 4 |
| PIC32CX_MT | 17 |
| PIC32CX_SG | 2 |
| PIC32CX_SG41 | 4 |
| PIC32CX_SG60 | 2 |
| PIC32CX_SG61 | 2 |
| PIC32CZ_CA70 | 9 |
| PIC32CZ_CA80 | 12 |
| PIC32CZ_CA90 | 12 |
| PIC32CZ_CA91 | 7 |
| PIC32CZ_MC70 | 4 |
| SAM9X6 | 5 |
| SAM9X7 | 9 |
| SAMA5D2 | 19 |
| SAMA5D3 | 5 |
| SAMA7D65 | 9 |
| SAMA7G5 | 8 |
| SAMC20 | 16 |
| SAMC21 | 16 |
| SAMD09 | 2 |
| SAMD10 | 7 |
| SAMD11 | 4 |
| SAMD20 | 28 |
| SAMD21 | 34 |
| SAMD51 | 9 |
| SAMDA1 | 9 |
| SAME51 | 7 |
| SAME53 | 5 |
| SAME54 | 4 |
| SAME70 | 9 |
| SAMG | 9 |
| SAMHA0 | 7 |
| SAMHA1 | 10 |
| SAML10 | 6 |
| SAML11 | 6 |
| SAML21 | 15 |
| SAML22 | 9 |
| SAMR21 | 7 |
| SAMR30 | 2 |
| SAMR34 | 3 |
| SAMR35 | 3 |
| SAMRH707 | 1 |
| SAMRH71 | 1 |
| SAMS70 | 9 |
| SAMV70 | 6 |
| SAMV71 | 9 |
| SAMV71_RT | 1 |

## Sources

- Pack index: https://packs.download.microchip.com/index.idx
- Packs: the latest version of every `Microchip.(SAM*|PIC32C*)_DFP` atpack.
  Exact pack versions are recorded per file in `manifest.json`.

Excluded on purpose: AVR, PIC8/16/18/24, dsPIC and the MIPS based PIC32M packs.
They contain no Cortex-M SVDs.

## License and redistribution

The packs ship an Apache-2.0 license file: "Copyright (c) Microchip Technology Inc.
Licensed under the Apache License, Version 2.0". The three distinct texts found across
the packs (they differ only in copyright year) are in `LICENSES/`.
Redistribution is permitted as long as the license text is kept.

## Refresh

    python fetch.py

Re-runnable. Downloaded atpacks are cached in `.work/packs`. The fetch is
incremental: it checks upstream pack versions against `manifest.json` first and
downloads only the packs that changed, rebuilding only the affected families.
A GitHub Action runs it weekly (Monday 06:00 UTC) and commits any updates.
Deleting `manifest.json` forces a full rebuild.

## Provenance

All files are pristine vendor files, unmodified. Every file was parsed with xml.etree
and has the root element `device` (0 failures out of 517).
