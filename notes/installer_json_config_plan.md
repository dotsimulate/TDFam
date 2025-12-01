# Installer JSON Config System - Implementation Plan

**Created:** 2025-11-29
**Status:** IMPLEMENTED ✅

---

## Overview

A JSON-based configuration system for the installer that:
- Uses **tables as the runtime source** (TD-optimized)
- Provides **JSON as import/export format** (git-friendly, LLM-editable, diffable)
- Enables **dynamic runtime changes** via Python properties or JSON import
- Keeps **developer control** without forcing complexity on simple use cases

---

## Core Principles

1. **Tables are ALWAYS the runtime source** - no JSON parsing during menu operations
2. **JSON is serialization** - import/export mechanism, not runtime dependency
3. **Everything is dynamic** - sorting, grouping, labels all changeable at runtime
4. **Developer responsibility** - wrapper decides what to expose, when to persist
5. **Not user-facing by default** - these are dev tools unless explicitly exposed

---

## Architecture

```
┌─────────────────────────────────────────────────────────────────────────┐
│                         RUNTIME (always tables)                          │
├─────────────────────────────────────────────────────────────────────────┤
│  group_mapping    │  replace_index   │  os_incompatible  │  relabel_index│
│  (table DAT)      │  (table DAT)     │  (table DAT)      │  (table DAT)  │
├───────────────────┴──────────────────┴───────────────────┴───────────────┤
│                           settings (table DAT)                           │
│     sort_within_group | group_order | ungrouped_label | ...              │
└─────────────────────────────────────────────────────────────────────────┘
                    ▲                           │
                    │ ImportConfig()            │ ExportConfig()
                    │                           ▼
┌─────────────────────────────────────────────────────────────────────────┐
│                         JSON CONFIG FILE                                 │
│  {                                                                       │
│    "tables": { group_mapping, replace_index, os_incompatible, ... },    │
│    "settings": { sort_within_group, group_order, ungrouped_label, ... } │
│  }                                                                       │
└─────────────────────────────────────────────────────────────────────────┘
                    ▲
                    │ Direct table manipulation (alternative to JSON)
                    │
┌─────────────────────────────────────────────────────────────────────────┐
│                      DIRECT TABLE ACCESS                                 │
│  settings = op.LOP.op('settings')                                       │
│  settings['sort_within_group', 1] = 'alphabetical'                      │
│  settings['group_order', 1] = '["LOPs Controllers", "LLM"]'             │
└─────────────────────────────────────────────────────────────────────────┘
```

---

## JSON Config Schema

```json
{
  "tables": {
    "group_mapping": {
      "LOPs Controllers": ["agent", "chat", "mcp_client", "mcp_server"],
      "LLM": ["summarize", "handoff", "add_message", "sentiment"],
      "Tools": ["search", "web_viewer", "tool_dat"]
    },
    "replace_index": {
      "Rag": "RAG",
      "Ocr": "OCR",
      "Glsl": "GLSL",
      "Tts": "TTS",
      "Stt": "STT",
      "Dat": "DAT",
      "Comp": "COMP",
      "Oai": "OAI"
    },
    "os_incompatible": {
      "florence": {"windows": 1, "mac": 0},
      "tts_kyutai": {"windows": 1, "mac": 0},
      "stt_kyutai": {"windows": 1, "mac": 0}
    },
    "relabel_index": {
      "0": "^ ChatTD",
      "1": "^ Python Manager"
    }
  },
  "settings": {
    "sort_within_group": "alphabetical",
    "ungrouped_label": "Other"
  }
}
```

---

## Tables Structure

### Existing Tables (unchanged structure)

| Table | Structure | Purpose |
|-------|-----------|---------|
| `group_mapping` | Columns = group names, cells = operator names | Assign operators to groups |
| `replace_index` | Col 0 = old string, Col 1 = new string | Label string replacements |
| `os_incompatible` | Col 0 = op name, Col 1 = windows, Col 2 = mac | OS compatibility flags |
| `relabel_index` | Col 0 = index, Col 1 = label | Override labels by index |

### New Table: `settings`

| Key | Value | Description |
|-----|-------|-------------|
| `sort_within_group` | `alphabetical` / `custom` / `by_name` | How operators sort within groups |
| `ungrouped_label` | `Other` (or empty `''`) | Label for ungrouped operators. Empty string = no group header |
| `exclude_behavior` | `hide` / `disable` | How to handle excluded operators |
| `show_ungrouped` | `1` / `0` | Whether to show operators not assigned to any group |

**Note:** Group order is determined by column order in `group_mapping` table (left to right).

**Why a table for settings?**
- Consistent with existing table pattern
- Persists with the toe file (memory-safe)
- Readable/writable like other tables
- No TD storage complexity

---

## Methods on GenericInstallerEXT

### ImportConfig(path)

```python
def ImportConfig(self, path):
    """
    Import JSON config file into tables.

    Args:
        path (str): Full path to JSON config file

    Returns:
        tuple: (success: bool, message: str)
    """
    import json

    try:
        with open(path, 'r') as f:
            config = json.load(f)
    except json.JSONDecodeError as e:
        return (False, f"JSON parse error: {e}")
    except FileNotFoundError:
        return (False, f"File not found: {path}")

    # Import tables
    if 'tables' in config:
        self._import_group_mapping(config['tables'].get('group_mapping', {}))
        self._import_replace_index(config['tables'].get('replace_index', {}))
        self._import_os_incompatible(config['tables'].get('os_incompatible', {}))
        self._import_relabel_index(config['tables'].get('relabel_index', {}))

    # Import settings
    if 'settings' in config:
        self._import_settings(config['settings'])

    # Force recook OP_fam to rebuild menu
    op_fam = self.ownerComp.op('OP_fam')
    if op_fam:
        op_fam.cook(force=True)

    return (True, f"Imported config from {path}")
```

### ExportConfig(path)

```python
def ExportConfig(self, path):
    """
    Export current tables to JSON config file.

    Args:
        path (str): Full path for JSON output file

    Returns:
        tuple: (success: bool, message: str)
    """
    import json

    config = {
        "tables": {
            "group_mapping": self._export_group_mapping(),
            "replace_index": self._export_replace_index(),
            "os_incompatible": self._export_os_incompatible(),
            "relabel_index": self._export_relabel_index()
        },
        "settings": self._export_settings()
    }

    try:
        with open(path, 'w') as f:
            json.dump(config, f, indent=2)
        return (True, f"Exported config to {path}")
    except Exception as e:
        return (False, f"Export error: {e}")
```

### Settings Access Pattern

**install_scripts read tables directly (family-agnostic):**
```python
# In fam_script_callbacks.py - reads table, works for ANY wrapper
settings = parent(2).op('settings')
sort_method = settings['sort_within_group', 1].val if settings and settings.row('sort_within_group') else 'alphabetical'
ungrouped_label = settings['ungrouped_label', 1].val if settings and settings.row('ungrouped_label') else 'Other'

# Group order comes from group_mapping column order
group_table = parent(2).op('group_mapping')
group_order = [group_table[0, col].val for col in range(group_table.numCols)]
```

**GenericInstallerEXT provides helper methods (optional convenience):**
```python
def _get_setting(self, key, default=None):
    """Get a setting value from settings table."""
    settings = self.ownerComp.op('settings')
    if settings and settings.row(key):
        return settings[key, 1].val
    return default

def _set_setting(self, key, value):
    """Set a setting value in settings table."""
    settings = self.ownerComp.op('settings')
    if not settings:
        settings = self.ownerComp.create(tableDAT, 'settings')
        settings.appendRow(['key', 'value'])

    if settings.row(key) is None:
        settings.appendRow([key, value])
    else:
        settings[key, 1] = value
```

**Wrapper devs can add properties if they want (optional):**
```python
# In their wrapper class - NOT required
@property
def sort_within_group(self):
    return self._get_setting('sort_within_group', 'alphabetical')

@sort_within_group.setter
def sort_within_group(self, value):
    self._set_setting('sort_within_group', value)
```

**Key principle:** Scripts always read from `settings` table directly. Properties are optional sugar for external callers.

---

## Integration Points

### fam_script_callbacks.py Changes

Currently hardcoded (line 218):
```python
nodes = sorted(grouped_nodes[group_name], key=lambda k: k['nodeLabel'].lower())
```

Should become:
```python
# Get sort method from settings table directly
settings = parent(2).op('settings')
sort_method = settings['sort_within_group', 1].val if settings and settings.row('sort_within_group') else 'alphabetical'

if sort_method == 'alphabetical':
    nodes = sorted(grouped_nodes[group_name], key=lambda k: k['nodeLabel'].lower())
elif sort_method == 'by_name':
    nodes = sorted(grouped_nodes[group_name], key=lambda k: k['nodeName'].lower())
elif sort_method == 'custom':
    # Use order from group_mapping table (row order = display order)
    nodes = grouped_nodes[group_name]  # Preserve original order
else:
    nodes = sorted(grouped_nodes[group_name], key=lambda k: k['nodeLabel'].lower())
```

Group ordering (line 213):
```python
for group_name in grouped_nodes.keys():
```

Should become:
```python
# Get group order from group_mapping column order (left to right)
group_table = parent(2).op('group_mapping')
group_order = [group_table[0, col].val for col in range(group_table.numCols)]

# Get ungrouped label from settings
settings = parent(2).op('settings')
ungrouped_label = settings['ungrouped_label', 1].val if settings and settings.row('ungrouped_label') else 'Other'

# Sort groups: column order first, then alphabetical for unlisted
def group_sort_key(name):
    if name in group_order:
        return (0, group_order.index(name))
    return (1, name.lower())

sorted_groups = sorted(grouped_nodes.keys(), key=group_sort_key)

for group_name in sorted_groups:
```

---

## Folder-Based Operator Categorization

**Current behavior:** Folder ops scanned flat, no category assignment from folder structure.

**Enhanced behavior:**
- Subfolders in `operators_folder` = category names
- Loose .tox files = ungrouped (uses `ungrouped_label`)
- Table `group_mapping` still works for overrides
- Subfolder + table coexist (table wins for conflicts)

### Scanning Logic Update

In `fam_create_callback.py`, update folder scanning:

```python
if folder_path and os.path.isdir(folder_path):
    # Scan subfolders for categorized ops
    for item in os.listdir(folder_path):
        item_path = os.path.join(folder_path, item)

        if os.path.isdir(item_path):
            # Subfolder = category
            category_name = item
            for f in os.listdir(item_path):
                if f.endswith('.tox'):
                    name, version = _parse_tox_info(f)
                    if name and name.lower() not in embedded_names:
                        folder_ops.append(type('FolderOp', (), {
                            'name': name,
                            'inputConnectors': [],
                            'path': os.path.join(item_path, f),
                            'folder_category': category_name  # NEW
                        })())

        elif item.endswith('.tox'):
            # Loose file = ungrouped
            name, version = _parse_tox_info(item)
            if name and name.lower() not in embedded_names:
                folder_ops.append(type('FolderOp', (), {
                    'name': name,
                    'inputConnectors': [],
                    'path': os.path.join(folder_path, item),
                    'folder_category': None  # Ungrouped
                })())
```

Then in group assignment logic:
```python
# For folder ops, use folder_category if no table entry
if hasattr(o, 'folder_category') and o.folder_category:
    if op_name not in group_index:  # Table takes precedence
        group_index[op_name] = o.folder_category
```

---

## Developer Workflow

### Simple Wrapper (Most Developers)

```python
class MyFamilyInstallerEXT(GenericInstallerEXT):
    def __init__(self, ownerComp):
        super().__init__(
            ownerComp=ownerComp,
            family_name='MYFAM',
            color=[0.5, 0.8, 0.3, 1],
            compatible_types=['TOP', 'CHOP']
        )
        # That's it - tables define everything else
```

### With Config Persistence

```python
class MyFamilyInstallerEXT(GenericInstallerEXT):
    def __init__(self, ownerComp):
        super().__init__(
            ownerComp=ownerComp,
            family_name='MYFAM',
            color=[0.5, 0.8, 0.3, 1],
            compatible_types=['TOP', 'CHOP']
        )

        # Load saved config on init
        config_path = ownerComp.par.Configfile.eval()
        if config_path and os.path.exists(config_path):
            self.ImportConfig(config_path)
```

### With Exposed Parameters

```python
class MyFamilyInstallerEXT(GenericInstallerEXT):
    def __init__(self, ownerComp):
        super().__init__(...)

    # Expose ImportConfig as parameter pulse
    def Importconfig(self, path=None):
        if path is None:
            path = self.ownerComp.par.Configfile.eval()
        return self.ImportConfig(path)

    def Exportconfig(self, path=None):
        if path is None:
            path = self.ownerComp.par.Configfile.eval()
        return self.ExportConfig(path)
```

---

## Dynamic Menu Updates Use Case

```python
# Runtime switching between menu configurations
# Direct table manipulation - works for ANY family, no wrapper class name needed

def switch_to_simple_mode(installer_op):
    """
    Args:
        installer_op: The installer COMP (e.g., op.LOP, op.POPX, op.MYFAM)
    """
    # Manipulate settings table directly
    settings = installer_op.op('settings')
    settings['sort_within_group', 1] = 'alphabetical'
    installer_op.op('OP_fam').cook(force=True)

def switch_to_advanced_mode(installer_op):
    settings = installer_op.op('settings')
    settings['sort_within_group', 1] = 'by_name'
    installer_op.op('OP_fam').cook(force=True)

# To change group order, reorder columns in group_mapping table

# Usage:
switch_to_simple_mode(op.LOP)
switch_to_advanced_mode(op.POPX)
```

---

## Implementation Order

1. Add `settings` table creation/management to GenericInstallerEXT
2. Add `_get_setting()` / `_set_setting()` helper methods
3. Add private import helper methods (_import_group_mapping, etc.)
4. Add private export helper methods (_export_group_mapping, etc.)
5. Add public ImportConfig() and ExportConfig() methods
6. Update fam_script_callbacks.py to read settings table for sort/group
7. Update fam_create_callback.py for subfolder category detection
8. Test with LOPs and a simple test family
9. Document for developers

---

## Testing Checklist

- [x] ImportConfig loads valid JSON and populates tables
- [x] ImportConfig handles invalid JSON gracefully (returns error, doesn't break)
- [x] ExportConfig produces valid JSON matching current tables
- [x] Round-trip: Export → Import produces identical tables
- [x] `settings` table `sort_within_group` value affects menu sorting
- [x] `group_mapping` column order affects group display order
- [x] `settings` table `ungrouped_label` value affects ungrouped operators
- [x] Subfolder scanning assigns categories correctly
- [x] Table `group_mapping` overrides subfolder category
- [x] Table changes + force cook updates menu without restart
- [x] Settings persist in toe file (table-based storage)
- [x] `exclude_behavior` hide/disable works correctly
- [x] `show_ungrouped` setting hides/shows ungrouped operators

---

## Notes

- JSON validation happens at import time via `json.load()` - errors caught early
- Tables remain authoritative - JSON is just a transport format
- All settings are optional in JSON - missing = use defaults
- Wrapper complexity is developer choice - simple works, complex available
