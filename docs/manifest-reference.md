# Manifest Reference

Every placed operator gets a `FamManifest` child COMP containing DATs that define the operator's identity and retention behavior. Manifests can also be provided externally as JSON sidecar files alongside `.tox` files.

## OpInfo

Operator identity metadata.

```json
{
  "op_type": "noise_gen",
  "op_name": "noise_gen_v1.2.0",
  "op_label": "Noise Generator",
  "op_version": "1.2.0",
  "fam_version": "1.0.0",
  "op_fam": "MYFAM"
}
```

| Field | Description |
|-------|-------------|
| `op_type` | Canonical type identifier. Used to match operators during updates. |
| `op_name` | Full name including version. |
| `op_label` | Display name in the TAB menu. |
| `op_version` | Semantic version of this operator. |
| `fam_version` | Version of the family that shipped this operator. |
| `op_fam` | Family name. |

`op_type` is the primary key — it's how the system identifies what an operator _is_ regardless of its node name in the network.

## ParRetain

Rules governing which parameters are preserved across stub and update operations. Keys are relative component paths (`.` = the operator itself). Values are arrays of rules.

```json
{
  ".": [
    "Amplitude",
    "Frequency",
    "!Debug",
    "<Settings>",
    "Seed:stub",
    "Cache*:update"
  ],
  "filter1": [
    "Type",
    "Cutoff"
  ]
}
```

### Rule Syntax

| Pattern | Meaning |
|---------|---------|
| `ParName` | Retain this parameter in all scenarios |
| `ParName:stub` | Retain only during stub operations |
| `ParName:update` | Retain only during update operations |
| `!ParName` | Exclude this parameter |
| `!ParName:stub` | Exclude only during stub operations |
| `<PageName>` | Retain all parameters on this page |
| `Par*` | Wildcard — retain all matching parameters |

Rules are evaluated in order. Exclusions (`!`) override inclusions.

### Path Keys

- `.` — the operator comp itself
- `child_name` — a direct child comp
- `path/to/child` — a nested child comp
- `!child_name` — exclude all parameters from this child

If ParRetain is empty or missing, no parameters are retained.

## StateRetain

Rules for preserving non-parameter state: extension properties, component storage, and DAT content.

```json
{
  ".": {
    "extensions": {
      "MyExtClass": [
        "color",
        "fontSize",
        "!cache"
      ]
    },
    "storage": [
      "savedState",
      "calibration",
      "!sessionToken"
    ],
    "dats": [
      "config",
      "presets",
      "!debug_log"
    ]
  }
}
```

### Structure

Keys are component paths (same as ParRetain). Values are objects with up to three categories:

#### `extensions`

Preserves StorageManager-managed dicts on extension classes. Keys are extension class names, values are arrays of property rules.

The system looks for stored data under the key `{ClassName}Stored` in `comp.store()`.

#### `storage`

Preserves raw `comp.store()` entries. Array of key name rules.

#### `dats`

Preserves text/table DAT children by name. Array of DAT name rules.

### Rule Syntax

Same as ParRetain: `name`, `name:scenario`, `!name` (exclude), wildcards with `*`.

## Shortcuts

Keyboard shortcut mappings for the operator.

```json
{
  "ctrl.r": "refresh",
  "alt.s": "save"
}
```

Keys are shortcut combinations, values are action identifiers handled by the ShortcutManager.

## External Manifests

For file-based operators, manifests can be provided as JSON files alongside the `.tox` files. Two formats are supported:

### Sidecar JSON

A JSON file with the same base name as the `.tox`:

```
operators/
  noise_gen_v1.2.0.tox
  noise_gen_v1.2.0.json    ← sidecar manifest
```

Contents:

```json
{
  "OpInfo": { ... },
  "ParRetain": { ... },
  "StateRetain": { ... },
  "Shortcuts": { ... }
}
```

All fields are optional. Any missing fields fall back to defaults or what's already inside the `.tox`.

### Folder Manifest

A `manifest.json` at the folder root covering multiple operators:

```json
{
  "noise_gen": {
    "OpInfo": { ... },
    "ParRetain": { ... }
  },
  "color_ramp": {
    "OpInfo": { ... },
    "StateRetain": { ... }
  }
}
```

Keys are normalized operator names (lowercase, no version suffix). Sidecar files take priority over folder manifests.

## Filename Convention

File-based operators are parsed using a configurable regex (default: `(.+)_v(\d+\.\d+\.\d+)\.tox$`).

| Filename | Parsed Name | Parsed Version |
|----------|-------------|----------------|
| `noise_gen_v1.2.0.tox` | `noise_gen` | `1.2.0` |
| `my_op.tox` | `my_op` | `None` |

Unversioned files are valid but lose version comparison during source resolution.
