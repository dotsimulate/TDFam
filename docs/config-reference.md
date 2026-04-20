# Config Reference

TDFam uses table DATs for visual configuration and JSON for portability. Changes sync bidirectionally through a Config DependDict (the runtime source of truth).

## Config Tables

### `settings`

Key/value pairs controlling menu behavior.

| Key | Values | Default | Description |
|-----|--------|---------|-------------|
| `sort_within_group` | `alphabetical`, `by_name`, `custom` | `alphabetical` | How operators are sorted within groups. `custom` uses row order in `group_mapping`. |
| `ungrouped_label` | any string | `Other` | Group header for operators not assigned to any group. |
| `show_ungrouped` | `0`, `1` | `1` | Whether to show ungrouped operators in the menu. |
| `exclude_behavior` | `hide`, `disable` | `hide` | What to do with excluded/incompatible operators — hide them entirely or show them disabled. |

### `group_mapping`

Controls operator grouping and ordering in the TAB menu.

- **Row 0** (header) = group names. Column order determines display order in the menu.
- **Rows 1+** = operator names listed under each group column.

Each column is a list of operators belonging to that group. Empty cells are ignored.

Example table:

| Generators | Filters | Utility |
|-----------|---------|---------|
| noise_gen | blur | inspector |
| color_ramp | sharpen | |

### `label_replacements`

String find/replace rules applied to auto-generated operator labels.

| Column | Description |
|--------|-------------|
| `find` | String to search for |
| `replace` | Replacement string |

Example: find `_` → replace ` ` turns `noise_gen` into `noise gen`.

Applied in row order. The JSON import also accepts the legacy key `replace_index`.

### `os_incompatible`

OS compatibility and exclusion flags. Only operators that deviate from the default (compatible everywhere) need entries here.

| Column | Type | Description |
|--------|------|-------------|
| `operator_name` | string | Operator name |
| `windows` | `0`/`1` | `1` = compatible with Windows, `0` = incompatible |
| `mac` | `0`/`1` | `1` = compatible with Mac, `0` = incompatible |
| `exclude` | `0`/`1` | `1` = excluded from menu regardless of OS |

Operators not listed default to `windows=1, mac=1, exclude=0` (compatible everywhere). Incompatible/excluded operators are handled according to `exclude_behavior` in settings (hidden or disabled).

---

## JSON Import/Export

Use `ExportConfig()` and `ImportConfig()` to move configuration in and out of JSON. This is useful for version control or sharing configs between projects.

### JSON Format

```json
{
  "tables": {
    "group_mapping": {
      "Generators": ["noise_gen", "color_ramp"],
      "Filters": ["blur", "sharpen"],
      "Utility": ["inspector"]
    },
    "label_replacements": {
      "_": " ",
      "td": "TD"
    },
    "os_incompatible": {
      "metal_shader": {
        "windows": 0,
        "mac": 1,
        "exclude": 0
      }
    }
  },
  "settings": {
    "sort_within_group": "alphabetical",
    "ungrouped_label": "Other",
    "show_ungrouped": "1",
    "exclude_behavior": "hide"
  }
}
```

### `tables.group_mapping`

Object where keys are group names and values are arrays of operator names belonging to that group. Group order in JSON doesn't map to display order — column order in the DAT table determines that.

### `tables.label_replacements`

Object mapping find strings to replace strings. Corresponds to the `label_replacements` DAT table.

### `tables.os_incompatible`

Object keyed by operator name. Each value has `windows`, `mac`, and `exclude` integer flags.

### `settings`

Flat key/value object matching the `settings` table.

### Notes

- `ImportConfig` replaces each top-level key present in the JSON but leaves absent keys unchanged.
- All table fields in the JSON are optional. Omitted tables are left unchanged.
- `ExportConfig()` with no arguments returns a Python dict. Pass a file path to write JSON to disk.
