# opfam-create

A flexible system for creating custom operator families in TouchDesigner. Add your own operator menus to the TD UI.

## Overview

opfam-create provides `GenericInstallerEXT`, a base class that handles registering custom operator families with TouchDesigner's menu system. You wrap it in your own extension class and package it as a .tox.

**The core idea:** Your custom logic goes in your wrapper class, not in the installer. Treat `installer.py` and `install_scripts/` as a library you don't modify.

## Requirements

- TouchDesigner 2023 or 2025
- No external Python dependencies

## Structure

```
Your Installer .tox
├── installer.py              (from this repo - don't modify)
├── install_scripts/          (from this repo - don't modify)
├── YourWrapperEXT.py         (your code - extends GenericInstallerEXT)
├── custom_operators/         (your embedded operators, optional)
└── config tables             (group_mapping, settings, etc.)
```

## Features

- Register custom operator families in TD's UI
- Load operators from embedded components or external folders
- Group, sort, and label operators via config tables
- JSON import/export for version-controlled configuration
- Hooks for customizing placement, stub creation, and updates
- Stub system for lightweight project files

## Configuration

Settings are stored in table DATs inside your installer component:

| Table | Purpose |
|-------|---------|
| `settings` | Sort method, ungrouped label, exclude behavior |
| `group_mapping` | Assign operators to groups (column order = display order) |
| `replace_index` | Label string replacements |
| `os_incompatible` | Windows/Mac compatibility flags |

## Hooks

Override these in your wrapper class for custom behavior:

| Hook | Purpose |
|------|---------|
| `PlaceOp` | Intercept before operator placement |
| `PostPlaceOp` | Run after operator placed |
| `PreStub` / `PostStub` | Customize stub creation |
| `PreUpdate` / `PostUpdate` | Customize operator updates |
| `PreserveSpecialParams` | Handle special parameter copying |

## Examples

See `examples/fav/` for a minimal folder-based installer template.

## Documentation

Detailed documentation in `notes/` folder.

## License

MIT - See LICENSE file
