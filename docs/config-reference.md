# Config Reference

TDFam uses table DATs for visual family configuration and JSON for portability. The tables are the editable surface; TDFam syncs them into runtime config when building the family menu.

Manifest fields are the preferred place for per-operator metadata. Config tables define family-level defaults and bulk presentation behavior.

## Config Tables

### `settings`

Key/value pairs controlling menu behavior.

| Key | Values | Default | Description |
|-----|--------|---------|-------------|
| `sort_within_group` | `alphabetical`, `by_name`, `custom` | `alphabetical` | How operators are sorted within groups. `custom` uses row order in `group_mapping`. |
| `ungrouped_label` | any string | `Other` | Group header for operators not assigned to any group. |
| `show_ungrouped` | `0`, `1` | `1` | Whether to show ungrouped operators in the menu. |
| `exclude_behavior` | `hide`, `disable` | `hide` | What to do with excluded/incompatible operators: hide them or show them disabled. |

### `group_mapping`

Controls default operator grouping and optional custom sort order.

- Row 0 contains group names.
- Column order determines display order.
- Rows 1+ contain operator names under each group.
- Empty cells are ignored.

Example:

| Generators | Filters | Utility |
|------------|---------|---------|
| noise_gen | blur | inspector |
| color_ramp | sharpen | |

Group resolution order:

1. `OpInfo.op_group`
2. `group_mapping`
3. File-based category folder
4. `settings.ungrouped_label`, if ungrouped operators are shown

### `label_replacements`

String find/replace rules applied to generated labels.

| Column | Description |
|--------|-------------|
| `find` | String to search for. |
| `replace` | Replacement string. |

Rules are applied in row order. JSON import also accepts the legacy key `replace_index`.

### `os_incompatible`

OS compatibility and exclusion flags. Only operators that deviate from the default need entries.

| Column | Type | Description |
|--------|------|-------------|
| `operator_name` | string | Operator name. |
| `windows` | `0`/`1` | `1` = compatible with Windows, `0` = incompatible. |
| `mac` | `0`/`1` | `1` = compatible with Mac, `0` = incompatible. |
| `exclude` | `0`/`1` | `1` = excluded from menu regardless of OS. |

Operators not listed default to `windows=1`, `mac=1`, `exclude=0`. Incompatible or excluded operators are handled according to `settings.exclude_behavior`.

## Manifest-Driven Menu Data

Use `family_info` for family-level menu data and `OpInfo` for per-operator menu data.

`family_info` is a JSON DAT on the owner comp:

```json
{
  "summary": "",
  "doc_url": "",
  "support_url": "",
  "PopMenu": []
}
```

| OpInfo field | Effect |
|--------------|--------|
| `op_group` | Assigns the operator to a menu group. |
| `op_label` | Sets the display label before label replacements are applied. |
| `summary` | Adds help text in the OP Create dialog. |
| `doc_url` | Enables the right-click `Documentation` item for embedded menu entries. |
| `pop_menu` | Adds custom right-click menu entries for embedded menu entries. Clicks can route to functions in the family callback DAT. |
| `op_color` | Applies a per-operator network color. |
| `isFilter` | Chooses filter vs generator menu display. |
| `compatible_types` | Overrides append/connect compatibility for this operator. |
| `search_words` | Adds extra search terms. |

| family_info key | Effect |
|-----------------|--------|
| `summary` | Adds a family-level help summary. |
| `doc_url` | Provides the family documentation fallback. |
| `support_url` | Adds the built-in `Support` right-click item. |
| `PopMenu` | Adds family-level right-click entries. |

## Family Parameters That Affect Config

| Parameter | Description |
|-----------|-------------|
| `Family` | Family name. Rename is rejected if another owner already holds the name; accepted renames update registry/UI references and manifest tags. |
| `Colorr`, `Colorg`, `Colorb` | Family menu/network color. Existing placed ops are updated only when they still match the old family color; custom colors are preserved. |
| `Colorfileops` | Applies the family color to file-based operators when they do not define `OpInfo.op_color`. |
| `Opcomp` | Embedded operator source container. |
| `Opfolder` | External `.tox` source folder. |
| `Namingconvention` | Regex used to parse file-based operator names and versions. |
| `Compatibletypes` | Family-level append/connect compatibility types. |
| `Ensuremanifests` | Validates embedded manifests and updates existing external manifest JSON entries. |

## JSON Import/Export

Use `ExportConfig()` and `ImportConfig()` to move family config in and out of JSON.

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

### Notes

- `ImportConfig` replaces each top-level key present in the JSON but leaves absent keys unchanged.
- All table fields are optional. Omitted tables are left unchanged.
- `ExportConfig()` with no arguments returns a Python dict.
- Passing a file path to `ExportConfig(path)` writes JSON to disk.
