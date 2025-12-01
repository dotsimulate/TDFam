# FAV - Favorites Family Installer

A minimal folder-based operator family for TouchDesigner. Point it at a folder of .tox files and they appear in your TD operator menu as the "FAV" family.

## What It Does

- Scans a folder for .tox files
- Adds them to TD's operator creation menu under "FAV"
- No embedded operators - everything comes from your folder
- Subfolders become category groups in the menu

## Usage

1. Add the FAV installer .tox to your project
2. Set the `Operatorsfolder` parameter to your folder of .tox files
3. Toggle `Install` on

Your operators now appear in TD's Tab menu under FAV.

## Folder Structure

```
your_operators/
├── Category A/
│   ├── tool1.tox
│   └── tool2.tox
├── Category B/
│   └── effect1.tox
└── loose_tool.tox       # Ungrouped
```

## Parameters

| Parameter | Purpose |
|-----------|---------|
| `Operatorsfolder` | Path to your .tox folder |
| `Install` | Toggle family on/off |
| `Family` | Family name (default: FAV) |
| `Color` | Menu color |

## Notes

- Uses `dynamic_refresh=True` so folder changes are picked up on each placement
- Case-insensitive filename matching
- Re-reads folder path on each Install in case it changed
