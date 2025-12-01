# Installer JSON Config System - Testing Status

**Created:** 2025-11-30
**Reference:** `installer_json_config_plan.md`

---

## Test Results

### ExportConfig
| Test | Status | Notes |
|------|--------|-------|
| Export to JSON file | ✅ PASS | `lop_config.json` created successfully |
| group_mapping export | ✅ PASS | 4 groups, correct operator lists |
| replace_index export | ✅ PASS | All replacements exported |
| os_incompatible export | ✅ PASS | Windows/Mac flags correct |
| relabel_index export | ✅ PASS | Index-based labels exported |
| settings export | ✅ PASS | Empty dict (no settings yet) |

### ImportConfig
| Test | Status | Notes |
|------|--------|-------|
| Import from JSON file | ✅ PASS | Tables populated correctly |
| group_mapping import | ✅ PASS | Columns/rows created correctly |
| replace_index import | ✅ PASS | Key-value pairs imported |
| os_incompatible import | ✅ PASS | Compatibility flags imported |
| relabel_index import | ✅ PASS | Index-label pairs imported |
| settings import | ✅ PASS | Settings table populated |
| Menu updates after import | ✅ PASS | OP_fam force cooked after import |

### Settings Table
| Test | Status | Notes |
|------|--------|-------|
| sort_within_group = alphabetical | ✅ PASS | Default sorting works |
| sort_within_group = by_name | ✅ PASS | Sorts by operator name |
| sort_within_group = custom | ✅ PASS | Preserves original order |
| ungrouped_label setting | ✅ PASS | Empty string = no header |
| Group order from column order | ✅ PASS | Left-to-right column order respected |
| exclude_behavior = hide | ✅ PASS | Excluded ops hidden from menu |
| exclude_behavior = disable | ✅ PASS | Excluded ops shown but disabled |
| show_ungrouped = 0 | ✅ PASS | Ungrouped ops hidden |
| show_ungrouped = 1 | ✅ PASS | Ungrouped ops shown |

### Subfolder Category Detection
| Test | Status | Notes |
|------|--------|-------|
| Subfolder = category name | ✅ PASS | Folder name used as category |
| Loose files = ungrouped | ✅ PASS | Uses ungrouped_label setting |
| Table overrides subfolder | ✅ PASS | group_mapping takes precedence |

### FAV Family (Folder-Only Wrapper)
| Test | Status | Notes |
|------|--------|-------|
| FavInstallerEXT creation | ✅ PASS | Minimal wrapper works |
| Folder path validation | ✅ PASS | Invalid paths handled gracefully |
| dynamic_refresh=True | ✅ PASS | Fresh scan on each placement |
| Case-insensitive matching | ✅ PASS | POPX.tox matches lookup for 'popx' |
| Configurable placement | ✅ PASS | install_location, node_x/y, expose work |
| FolderCache (tdu.Dependency) | ✅ PASS | Cache accessible from scriptDATs |

---

## Known Issues

*None yet*

---

## Test Commands

```python
# Export config
op.LOP.ExportConfig('D:/TD-tox/LOPS_tox/GITsync/active_dev/lop_config.json')

# Import config
op.LOP.ImportConfig('D:/TD-tox/LOPS_tox/GITsync/active_dev/lop_config.json')

# Reinit extensions (if needed after file sync)
exec(op.LOP.op('installer').text)
op.LOP.par.reinitextensions.pulse()

# Check settings table
print(op.LOP.op('settings'))

# Force recook menu
op.LOP.op('OP_fam').cook(force=True)
```

---

## Files Involved

- `installer.py` - GenericInstallerEXT with JSON Config System, FolderCache, hooks
- `install_scripts/fam_script_callbacks.py` - Dynamic sort/group from settings table
- `install_scripts/fam_create_callback.py` - Reads FolderCache, subfolder category detection
- `install_scripts/fam_panel_execute.py` - Operator placement with file-based loading
- `examples/FavInstallerEXT.py` - Minimal folder-only wrapper example
