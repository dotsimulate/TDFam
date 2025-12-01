# Installer Architecture - Implementation Progress

**Last Updated:** 2025-11-30
**Reference:** `installer_architecture_vision.md`

---

## Status Legend
- ✅ Complete
- 🔄 In Progress
- ⏳ Not Started

---

## Key Features

### 1. File-Based Distribution
| Item | Status | Notes |
|------|--------|-------|
| `Operatorsfolder` parameter support | ✅ | Passed via wrapper constructor to GenericInstallerEXT |
| External folder scanning in menu | ✅ | `fam_create_callback.py` scans folder for .tox files |
| File-based operator placement | ✅ | `fam_panel_execute.py` uses `loadTox()` for folder ops |
| Version comparison logic | ✅ | In `Getoperatorsource()` - compares filename version vs embedded `par.Version` |
| Caching with `FolderCache` (tdu.Dependency) | ✅ | Built on init if `dynamic_refresh=False`; tdu.Dependency enables scriptDAT cook dependencies |
| `Refreshfolder()` method | ✅ | Rescans folder and force-cooks OP_fam |
| `dynamic_refresh` toggle | ✅ | Constructor arg, defaults to False |

### 2. Wrapper Architecture (Inheritance)
| Item | Status | Notes |
|------|--------|-------|
| ChatInstallerEXT inherits GenericInstallerEXT | ✅ | Uses `super()` for parent calls |
| Wrapper only passes config | ✅ | All logic in generic installer |
| `family_name` attribute exposed | ✅ | Set in constructor, accessible via `parent(2).family_name` |

### 3. Flexible Configuration (JSON Config System)
| Item | Status | Notes |
|------|--------|-------|
| JSON config schema | ✅ | Documented in `installer_json_config_plan.md` |
| `settings` table | ✅ | Key/value table for sort_within_group, ungrouped_label, exclude_behavior, show_ungrouped |
| `_get_setting()` / `_set_setting()` | ✅ | Helper methods for settings table access |
| `ImportConfig(source)` | ✅ | Imports JSON config into tables. Accepts: file path, JSON string, or dict |
| `ExportConfig(path)` | ✅ | Exports tables to JSON. Returns dict if no path, writes file if path provided |
| Import/export helpers | ✅ | `_import_group_mapping`, `_export_group_mapping`, etc. |
| Dynamic sort method | ✅ | `fam_script_callbacks.py` reads from settings table |
| Group order from table | ✅ | Column order in `group_mapping` determines display order |
| Subfolder category detection | ✅ | `fam_create_callback.py` scans subfolders for categories |
| Exclude functionality | ✅ | `os_incompatible` table has `exclude` column; `exclude_behavior` setting (hide/disable) |
| Show ungrouped setting | ✅ | `show_ungrouped` setting controls visibility of operators not in group_mapping |
| Empty ungrouped label | ✅ | Setting `ungrouped_label` to `""` shows no group header |

### 4. Hooks API Expansion
| Item | Status | Notes |
|------|--------|-------|
| `PlaceOp(panelValue, name)` | ✅ | Existing - before placing, in fam_panel_execute.py |
| `PostPlaceOp(clone)` | ✅ | Existing - after placing, in fam_panel_execute.py |
| `PreStub(comp)` | ✅ | Returns False to skip, in `createStub()` |
| `PostStub(stub, original_comp)` | ✅ | After stub created, in `createStub()` |
| `PreUpdate(old_comp, master_comp)` | ✅ | Returns False to skip, in `update_comp()` |
| `PostUpdate(new_comp)` | ✅ | After update complete, in `update_comp()` |
| `PreReplace(stub)` | ✅ | Returns False to skip, in `ReplacestubFor()` |
| `PostReplace(new_comp, stub)` | ✅ | After replacement, in `ReplacestubFor()` |
| `GetExcludedTags()` | ✅ | Returns set of tags to exclude from batch ops |
| `GetCategoryTags()` | ✅ | Returns set of category tags for operator type detection (miniuv pattern) |
| `PreserveSpecialParams(new_comp, source)` | ✅ | In `update_comp()` and `ReplacestubFor()` |
| `_call_hook(hook_name, *args)` | ✅ | Helper method to call hooks if defined |
| `_get_master_for_type(op_type, target_parent)` | ✅ | Supports both embedded and file-based masters |
| `_get_operator_type(comp)` | ✅ | Extracts op type using hook-aware logic (LOPs or miniuv pattern) |
| `_has_operator_type_tag(comp)` | ✅ | Checks if comp has proper operator type tag |

### 5. Favorites Family Concept
| Item | Status | Notes |
|------|--------|-------|
| FAV family wrapper template | ✅ | `FavInstallerEXT.py` - minimal example demonstrating folder-only families |
| Minimal installer for folder-only ops | ✅ | Uses `dynamic_refresh=True`, configurable placement |
| Configurable placement | ✅ | `install_location`, `node_x`, `node_y`, `expose` parameters in constructor |
| Extension re-reads params in Install() | ✅ | FAV wrapper re-reads `operators_folder` and `color` since extensions don't reinit |
| Case-insensitive filename matching | ✅ | Cache keys and live scan use `.lower()` for lookups |

---

## Next Steps (from vision doc)

| # | Task | Status |
|---|------|--------|
| 1 | Design config schema (JSON) | ✅ |
| 2 | Define hooks API contract for stub/update lifecycle | ✅ |
| 3 | Prototype file-based loading in fam_panel_execute.py | ✅ |
| 4 | Add `Operatorsfolder` parameter to installer | ✅ |
| 5 | Update fam_create_callback to scan both sources | ✅ |
| 6 | Implement `Refreshfolder` and caching logic | ✅ |
| 7 | Create lightweight FAV family wrapper template | ✅ |

---

## Files Modified

| File | Changes |
|------|---------|
| `installer.py` | Added file-based loading, hooks system, JSON config system (ImportConfig, ExportConfig, settings table), `_call_hook()`, `_get_master_for_type()`, `_get_operator_type()`, `_has_operator_type_tag()`; Changed `_folder_cache` to `FolderCache` (tdu.Dependency); Added configurable placement (`install_location`, `node_x`, `node_y`, `expose`); Cache keys lowercased for case-insensitive matching |
| `examples/FavInstallerEXT.py` | Minimal wrapper demonstrating folder-only families; Uses `dynamic_refresh=True`; Re-reads parameters in `Install()` since extensions don't reinit; Configurable placement via constructor |
| `install_scripts/fam_panel_execute.py` | Added file-based loading via `Getoperatorsource()` and `loadTox()`; Fixed to read from inject script output (sorted table) instead of raw OP_fam; Fixed no-group-header handling; Uses dynamic family name for inject script lookup; Added License check (`and license`); Generates unique names to avoid conflicts |
| `install_scripts/fam_create_callback.py` | Reads from `FolderCache` dependency (triggers recook on cache change); Scans external folder with subfolder category detection; fixed variable shadowing (`os` → `os_compat`, `type` → `node_type`); fixed family name retrieval; Added exclude_values and show_ungrouped support; Handles missing `custom_operators` for folder-only families |
| `install_scripts/fam_script_callbacks.py` | Added dynamic sort method and group ordering from settings table; Added exclude_behavior (hide/disable) support; Added show_ungrouped setting; Uses ungrouped_label for fallback group name; Skips empty group headers |

## Implementation Log

### 2025-11-29: Hooks System Implementation
- Added `_call_hook()` helper method (line 214-228)
- Added `_get_master_for_type()` for file-based master loading (line 230-258)
- Added hooks to `createStub()`: `PreStub` (line 724), `PostStub` (line 827)
- Added hooks to `update_comp()`: `PreUpdate` (line 1726), `PostUpdate` (line 1771), `PreserveSpecialParams` (line 1754)
- Added hooks to `ReplacestubFor()`: `PreReplace` (line 1212), `PostReplace` (line 1324), `PreserveSpecialParams` (line 1301)
- Added `GetExcludedTags` filtering to `Createstubs()` (line 839), `Updateall()` (line 1784), `Replacestubs()` (line 949), `ReplacestubsInNetwork()` (line 1437)
- Updated `Replacestubs()`, `ReplacestubsInNetwork()` to use `_get_master_for_type()`
- Created `installer_hooks_architecture.md` design document

### 2025-11-29: GetCategoryTags Hook Implementation
- Added `_get_operator_type()` helper (line 260-290) - supports both LOPs `{type}{familyName}` pattern and miniuv POPX category exclusion pattern
- Added `_has_operator_type_tag()` helper (line 292-306) - checks if comp has proper type tag using hook-aware logic
- Updated `createStub()` to use `_get_operator_type()` (line 732)
- Updated `Createstubs()` to use `_has_operator_type_tag()` for type tag warnings (line 861)
- Updated `find_matching_master_op()` to use both helpers (lines 1690-1691)
- Updated `Updateall()` to use `_has_operator_type_tag()` (line 1817)
- Updated `installer_hooks_architecture.md` with GetCategoryTags vs GetExcludedTags distinction

### 2025-11-29: JSON Config System Implementation
- Created `installer_json_config_plan.md` design document
- Added JSON Config System section to `installer.py` (lines 310-645)
- Added `_ensure_settings_table()` helper
- Added `_get_setting()` / `_set_setting()` for settings table access
- Added import helpers: `_import_group_mapping`, `_import_replace_index`, `_import_os_incompatible`, `_import_relabel_index`, `_import_settings`
- Added export helpers: `_export_group_mapping`, `_export_replace_index`, `_export_os_incompatible`, `_export_relabel_index`, `_export_settings`
- Added `ImportConfig(path)` - imports JSON to tables, force cooks OP_fam
- Added `ExportConfig(path)` - exports tables to JSON
- Updated `fam_script_callbacks.py`:
  - Group order now comes from `group_mapping` column order (line 213)
  - Sort method reads from `settings` table (line 217)
  - Supports `alphabetical`, `by_name`, `custom` sort methods
- Updated `fam_create_callback.py`:
  - Subfolder scanning for category detection (lines 86-114)
  - `folder_category` attribute on folder ops
  - Table `group_mapping` takes precedence over subfolder category
  - `ungrouped_label` from settings table for loose files

### 2025-11-30: Config System Bug Fixes & Enhancements
- Fixed `ImportConfig` to accept multiple input types: file path, JSON string, or dict
- Fixed `ExportConfig` to return dict if no path provided
- Fixed import helpers to clear tables BEFORE checking if data is empty
- Added `exclude` column to `os_incompatible` table
- Added `exclude_behavior` setting: "hide" (skip entirely) or "disable" (show grayed out)
- Added `show_ungrouped` setting: "1" shows all ops, "0" hides ops not in group_mapping
- Fixed empty `ungrouped_label` to not show any header row
- Fixed `fam_script_callbacks.py` to use `ungrouped_label` for fallback instead of hardcoded 'Other'

### 2025-11-30: Panel Execute Fixes
- Fixed `fam_panel_execute.py` to read from inject script output instead of raw OP_fam
  - The inject script applies sorting from `fam_script_callbacks.py`
  - Click index now maps to correct operator regardless of sort method
- Fixed no-group-header case (when `ungrouped_label` is empty)
  - Added `has_group_headers` flag to detect when no defLabel rows exist
  - Adjusted position calculation for flat list without headers
- Changed hardcoded `inject_LOP_fam` to dynamic `inject_{family_name}_fam`

---

## Code Corrections

**Vision doc line 469-477** - The temp/copy pattern for file loading doesn't work correctly.

❌ **Wrong (causes nesting):**
```python
temp = target_parent.create(baseCOMP, '__temp_loader__')
temp.loadTox(source)
clone = target_parent.copy(temp, name=normalized_name+'1')
temp.destroy()
```

✅ **Correct:**
```python
# loadTox loads as child and returns the loaded op
clone = target_parent.loadTox(tox_path)
clone.name = normalized_name + '1'
```

---

## Testing Notes

- Tested with `tester_boy.tox` in `D:/TD-tox/LOPS_tox/INSTALLvenv/operators`
- Successfully appears in LOP menu
- Successfully places at root level with correct structure

### 2025-11-30: FAV Family Wrapper & Configurable Placement
- Created `FavInstallerEXT.py` - minimal wrapper demonstrating folder-only families
  - Uses `dynamic_refresh=True` to scan folder on each placement
  - Re-reads `operators_folder` and `color` in `Install()` since extensions don't reinit when params change
  - Validates folder path exists before passing to parent
- Added configurable placement to `GenericInstallerEXT.__init__()`:
  - `install_location` (OP): Target parent for installer, defaults to `op('/')`
  - `node_x`, `node_y` (int): Position for installer node
  - `expose` (bool): Whether to expose the installer
- Changed `_folder_cache` dict to `FolderCache = tdu.Dependency({})`:
  - Regular Python attributes on extensions are NOT accessible via `parent(2).attribute` from scriptDATs
  - Only `tdu.Dependency` objects are promoted to the COMP and accessible
  - Setting `FolderCache.val = new_cache` triggers dependent scriptDATs to recook
- Updated `fam_create_callback.py` to read from `FolderCache.val` instead of doing `os.listdir()`
- Fixed case-sensitivity bug in folder cache:
  - Cache keys now stored lowercase: `new_cache[name.lower()] = {...}`
  - Live scan comparison now uses lowercase: `if name and name.lower() == lookup_name`
  - Fixes operators like `POPX_1_0_0_alpha.tox` not being found when lookup uses lowercase
- Fixed License check in `fam_panel_execute.py`: added `and license` to handle installers without License op
- Fixed unique name generation in file-based placement to avoid conflicts
