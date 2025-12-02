# opfam-create Refactor Analysis

**Created:** 2025-12-01
**Updated:** 2025-12-01
**Branch:** dot_reorganize_all
**Purpose:** Map current architecture, identify issues, plan modular reorganization

---

## Decisions Made

| Decision | Choice |
|----------|--------|
| Dynamic family name approach | **Option A** - Self-deriving from script name |
| Module location | **install_scripts/src/** |
| Keep old installer.py | Yes, in root for reference |
| Class rename | **GenericInstallerEXT → OpFamCreateExt** |

---

## Progress

- [x] Created architecture analysis
- [x] Fixed `fam_panel_execute.py` - now fully dynamic
- [x] Added ActionOp pattern (PlaceOp returns None = keep menu open)
- [ ] Disable sync on deployed panel_execute
- [ ] Add tag helper method to base installer
- [ ] Remove string replacement from Install()
- [ ] Move installer.py to install_scripts/
- [ ] Modularize into install_scripts/src/
- [ ] Create ExampleOpsEXT with theme ActionOp demo

---

## Target File Structure

```
opfam-create/
├── installer.py                    # OLD - keep for reference only
├── install_scripts/
│   ├── installer.py                # NEW - main GenericInstallerEXT
│   ├── fam_panel_execute.py        # FIXED - dynamic family name
│   ├── fam_create_callback.py      # Already dynamic
│   ├── fam_script_callbacks.py     # Already dynamic
│   ├── fam_toggle/
│   ├── set_last_node_type
│   └── src/                        # Modular components
│       ├── file_loader.py          # File-based .tox loading & cache
│       ├── config_system.py        # JSON import/export, settings tables
│       ├── stub_system.py          # Stub creation/replacement
│       ├── update_system.py        # Operator update operations
│       ├── ui_injection.py         # Install/Uninstall UI modifications
│       └── tag_helpers.py          # Tag management for custom_operators
└── examples/
    ├── fav/FavInstallerEXT.py
    └── example_ops/
        ├── ExampleOpsEXT.py        # Theme ActionOp demo
        └── README.md               # Concise user guide
```

**Wrapper import changes:**
```python
# Old
from installer import GenericInstallerEXT

# New
from install_scripts.installer import OpFamCreateExt
```

---

## Current Monolith Breakdown (installer.py ~2300 lines)

### Section 1: Initialization & Config (Lines 1-91)
→ Stays in main `installer.py`

### Section 2: File-Based Loading (Lines 92-244)
→ Moves to `src/file_loader.py`
- `_refresh_folder_cache()`
- `_parse_tox_info()`
- `_parse_version()`
- `Getoperatorsource()`
- `Refreshfolder()`

### Section 3: Hooks System (Lines 247-342)
→ Stays in main `installer.py` (core functionality)
- `_call_hook()`
- `_get_master_for_type()`
- `_get_operator_type()`
- `_has_operator_type_tag()`

### Section 4: JSON Config System (Lines 345-711)
→ Moves to `src/config_system.py`
- All `_import_*` methods
- All `_export_*` methods
- `ImportConfig()`, `ExportConfig()`
- Settings table helpers

### Section 5: Installation Detection (Lines 714-809)
→ Moves to `src/ui_injection.py`
- `find_other_installers()`
- `_is_installation_needed()`
- `_count_installed_families()`

### Section 6: Install/Uninstall (Lines 811-1119)
→ Moves to `src/ui_injection.py`
- `Install()`
- `Uninstall()`

### Section 7-10: Stub System (Lines 1136-2035)
→ Moves to `src/stub_system.py`
- `createStub()`
- `Createstubs()`, `Replacestubs()`
- `CreatestubFor()`, `ReplacestubFor()`
- `CreatestubsInNetwork()`, `ReplacestubsInNetwork()`

### Section 11: Update System (Lines 2037-end)
→ Moves to `src/update_system.py`
- `copyPar()`, `copySimplePar()`
- `find_matching_master_op()`
- `update_comp()`
- `Updateall()`

---

## New Module: tag_helpers.py

**Problem discovered:** Base installer only READS tags. ChatInstallerEXT adds tags in its own code:
```python
# ChatInstallerEXT lines 231-239
if self.ownerComp.par.Family.eval() not in custom_op.tags:
    custom_op.tags.add(self.ownerComp.par.Family.eval())
custom_op.tags.add(type_tag)
```

**Solution:** Add helper methods to base installer so wrappers don't need to reimplement:

```python
# src/tag_helpers.py

def ensure_family_tags(installer, custom_ops_base=None):
    """
    Ensure all operators in custom_operators have the family tag.

    Args:
        installer: The GenericInstallerEXT instance
        custom_ops_base: Optional custom operators base. Defaults to installer.op('custom_operators')
    """
    custom_ops = custom_ops_base or installer.ownerComp.op('custom_operators')
    if not custom_ops:
        return

    family = installer.family_name
    for comp in custom_ops.findChildren(type=COMP, maxDepth=1):
        if family not in comp.tags:
            comp.tags.add(family)

def ensure_type_tags(installer, custom_ops_base=None, pattern='suffix'):
    """
    Ensure all operators have type tags.

    Args:
        installer: The GenericInstallerEXT instance
        custom_ops_base: Optional custom operators base
        pattern: 'suffix' for {type}{Family} (e.g., agentLOP)
                 'name' for just operator name as tag
    """
    custom_ops = custom_ops_base or installer.ownerComp.op('custom_operators')
    if not custom_ops:
        return

    family = installer.family_name
    for comp in custom_ops.findChildren(type=COMP, maxDepth=1):
        if pattern == 'suffix':
            type_tag = f"{comp.name}{family}"
        else:
            type_tag = comp.name

        if type_tag not in comp.tags:
            comp.tags.add(type_tag)

def tag_operators(installer):
    """
    Convenience method to ensure both family and type tags.
    Call this in wrapper's Install() or __init__().
    """
    ensure_family_tags(installer)
    ensure_type_tags(installer)
```

**Usage in wrapper:**
```python
class ExampleOpsEXT(OpFamCreateExt):
    def __init__(self, ownerComp):
        super().__init__(ownerComp, 'EXAMPLE', [0.2, 0.6, 0.8])
        # Ensure all custom_operators have proper tags
        from install_scripts.src.tag_helpers import tag_operators
        tag_operators(self)
```

---

## Fix: Sync File on Deployed Scripts

**Problem:** When `fam_panel_execute` is copied to `/ui/dialogs/menu_op/`, if source has sync enabled, the deployed copy also has sync enabled → could sync back to wrong location.

**Solution:** Clear sync path on deployed copy:

```python
# In Install(), after copying fam_panel_execute:
panel_execute = menuOp.copy(
    self.ownerComp.op('install_scripts/fam_panel_execute'),
    name=panel_execute_path
)
panel_execute.par.syncfile = ''  # Disable sync on deployed copy
```

---

## Fix: Remove String Replacement

**Old code (installer.py lines 1014-1018):**
```python
unique_id = -abs(hash(self.family_name) % 10000)
panel_execute_script = panel_execute.text.replace('OPNAME', self.family_name)
panel_execute_script = panel_execute_script.replace('-9999', str(unique_id))
panel_execute.text = panel_execute_script
```

**New code:**
```python
# fam_panel_execute now derives family dynamically from its own name
# No text replacement needed
panel_execute.par.syncfile = ''  # Just disable sync
```

---

## ActionOp Pattern (Already Implemented)

Added to `fam_panel_execute.py` for theme operators:

```python
# PlaceOp hook - can return:
#   True  = proceed with placement
#   False = cancel and close menu
#   None  = cancel but keep menu open (for action operators like theme switchers)
if hasattr(installer, 'PlaceOp'):
    result = installer.PlaceOp(panelValue, lookup_name)
    if result is None:
        # Action operator - don't place, keep menu open
        return
    if not result:
        parent.OPCREATE.par.winclose.pulse()
        return
```

---

## ExampleOpsEXT Plan

Demonstrate ActionOp pattern with theme switching:

```python
class ExampleOpsEXT(OpFamCreateExt):
    def __init__(self, ownerComp):
        super().__init__(ownerComp, 'EXAMPLE', [0.3, 0.3, 0.3])

        # Ensure operators have tags
        from install_scripts.src.tag_helpers import tag_operators
        tag_operators(self)

        # Theme state
        self.current_theme = 'dark'
        self.themes = {
            'dark': [0.2, 0.2, 0.25],
            'light': [0.85, 0.85, 0.8]
        }

    def PlaceOp(self, panelValue, lookup_name):
        """
        Hook: Called before operator placement.
        Returns:
            True  - proceed with placement
            False - cancel and close menu
            None  - cancel but keep menu open (action op)
        """
        # Check if this is a theme action operator
        if lookup_name in ('dark', 'light'):
            self._apply_theme(lookup_name)
            return None  # Keep menu open, don't place

        return True  # Normal operator, proceed

    def _apply_theme(self, theme_name):
        """Apply theme color to the family."""
        if theme_name not in self.themes:
            return

        self.current_theme = theme_name
        self.color = self.themes[theme_name]

        # Update colors table in menu_op
        colors_table = op('/ui/dialogs/menu_op/colors')
        if colors_table:
            for i in range(colors_table.numRows):
                if colors_table[i, 0].val == f"'{self.family_name}'":
                    for j, c in enumerate(self.color):
                        colors_table[i, j+1] = c
                    break

        print(f"EXAMPLE theme changed to: {theme_name}")
```

**custom_operators structure:**
```
custom_operators/
├── Theme/              # Category folder
│   ├── dark            # ActionOp - clicking applies dark theme
│   └── light           # ActionOp - clicking applies light theme
├── panel               # Regular operator
└── display             # Regular operator
```

**README.md for example_ops:**
```markdown
# Example Ops - ActionOp Demo

Demonstrates the opfam-create hook system with theme switching.

## Quick Start

1. Drop the installer component into your project
2. Toggle Install on
3. Open TAB menu → EXAMPLE family

## Theme Operators

Click "dark" or "light" in the Theme category to change the family color.
These are **ActionOps** - they trigger an action instead of placing an operator.

## How It Works

`PlaceOp` hook checks operator name:
- Returns `None` for theme ops → applies theme, menu stays open
- Returns `True` for regular ops → proceeds with placement

## Adding Your Own Operators

1. Add COMP to `custom_operators/`
2. Tags are auto-added on init
3. Use subfolders for categories
```

---

## Implementation Order

1. **Create install_scripts/src/ folder**
2. **Create tag_helpers.py** - New functionality, no dependencies
3. **Create file_loader.py** - Extract from old installer.py (reference)
4. **Create config_system.py** - Extract from old installer.py
5. **Create stub_system.py** - Extract from old installer.py
6. **Create update_system.py** - Extract from old installer.py
7. **Create ui_injection.py** - Extract from old installer.py (includes sync disable fix)
8. **Create install_scripts/installer.py** - New `OpFamCreateExt` class, imports from src/
9. **Create ExampleOpsEXT** - With theme ActionOp demo
10. **Test with existing wrappers** - Update imports in ChatInstallerEXT, FavInstallerEXT
11. **Keep old installer.py untouched** - Reference only, maybe rename to installer_old.py

---

## Questions Resolved

| Question | Answer |
|----------|--------|
| Separate files or internal classes? | Separate files in `install_scripts/src/` |
| Fix first or modularize together? | Fix `fam_panel_execute.py` first (DONE), then modularize |
| Where do tags come from? | Wrapper responsibility, but add helpers to base |
| Sync file on deployed scripts? | Disable with `par.syncfile = ''` |
