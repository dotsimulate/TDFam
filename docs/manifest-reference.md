# Manifest Reference

Every placed COMP operator gets a `FamManifest` child COMP. The manifest contains DATs — `OpInfo`, `ParRetain`, `StateRetain`, and `Shortcuts` — that define the operator's identity, menu behavior, and what data survives stubs and updates.

Manifests are per-operator. Family-level metadata uses a separate `family_info` DAT on the TDFam owner comp — see [Family Info](#family-info) below.

## OpInfo

`OpInfo` is the operator identity block. It controls how the operator appears in the TAB menu, how TDFam finds it during placement and updates, and what metadata is attached to it.

`op_type` is the primary key for the entire system. It identifies what an operator _is_ — lookup, placement, stubs, updates, cache keying, and tag matching all use `op_type`. It stays stable even if the node name, file name, or label changes.

```json
{
  "op_type": "noise_gen",
  "op_name": "noise_gen_v1.2.0",
  "op_label": "Noise Generator",
  "op_version": "1.2.0",
  "fam_version": "1.0.0",
  "op_fam": "MYFAM",
  "op_group": "Generators",
  "summary": "Band-limited procedural noise source.",
  "doc_url": "https://example.com/docs/noise_gen",
  "op_color": [0.2, 0.6, 0.4],
  "isFilter": false,
  "compatible_types": ["CHOP", "TOP"],
  "search_words": ["random", "texture", "grain"],
  "pop_menu": [
    {
      "label": "Support",
      "callback": "onSupportDot",
      "disabled": false
    }
  ]
}
```

| Field | Description |
|-------|-------------|
| `op_type` | Canonical type identifier. Used for lookup, placement, stubs, and updates. |
| `op_name` | Node name used when a clone is prepared for placement. |
| `op_label` | Display label shown in the TAB menu. |
| `op_version` | Semantic version of this operator. |
| `fam_version` | Version of the family that shipped this operator. Rewritten automatically during validation. |
| `op_fam` | Family name. Rewritten automatically during validation. |
| `op_group` | Optional menu group. Takes priority over `group_mapping`; file-based ops fall back to their folder category when no manifest or config group exists. |
| `summary` | Optional help text merged into the OP Create dialog summaries table. |
| `doc_url` | Optional URL opened from the right-click `Documentation` item. `https://` is added when no scheme is provided. |
| `op_color` | Optional `[R, G, B]` list applied to placed, updated, or restored operators. Overrides the family color for this operator. |
| `isFilter` | Optional boolean. Selects filter vs generator menu layout. If omitted, embedded ops use generator layout and file-based ops default to filter. |
| `compatible_types` | Optional per-operator compatibility override for the append/connect workflow. |
| `search_words` | Optional list, or comma/space-separated string, of extra search terms for the TAB menu. |
| `pop_menu` | Optional right-click menu entries. See [Pop Menu Items](#pop-menu-items). |

### Validation behavior

When manifests are validated (during placement or `Ensuremanifests`), TDFam:

- Preserves existing custom fields — manifest data is the source of truth.
- Always rewrites `fam_version` and `op_fam` from the family owner.
- Fills missing identity fields (`op_name`, `op_type`, `op_label`) from the operator's display name.
- Fills `op_version` from the file version or `par.Version` if missing.
- Sanitizes `op_name` and `op_type` to valid TouchDesigner node names.

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

### Defaults

The defaults are different for the operator itself vs its children:

- **Self (`.`)**: starts with all custom parameters, then exclusions narrow the set.
- **Children** (e.g. `"filter1"`): starts with nothing, then inclusions add parameters.

This means for self rules you typically only need to list what to _exclude_, while for children you list what to _include_.

### Rule Syntax

| Pattern | Meaning |
|---------|---------|
| `ParName` | Retain this parameter in all scenarios. |
| `ParName:stub` | Retain only during stub operations. |
| `ParName:update` | Retain only during update operations. |
| `!ParName` | Exclude this parameter. |
| `!ParName:stub` | Exclude only during stub operations. |
| `<PageName>` | Retain all parameters on this page. |
| `Par*` | Wildcard; retain all matching parameters. |

## StateRetain

Rules for preserving non-parameter state: extension storage, raw component storage, and DAT content. Uses the same rule syntax as ParRetain (`name`, `name:scenario`, `!name`, `*` wildcards).

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

| Section | What it preserves |
|---------|-------------------|
| `extensions` | StorageManager-style dictionaries stored as `{ClassName}Stored`. |
| `storage` | Raw `comp.store()` entries, excluding extension `*Stored` keys. |
| `dats` | Immediate text/table DAT children by name. |

External manifests can provide `StateRetain`; it is merged into an existing in-TD manifest only for missing top-level keys.

## Shortcuts

Keyboard shortcut mappings for the operator.

```json
{
  "ctrl.r": "refresh",
  "alt.s": "save"
}
```

Keys are shortcut combinations, values are action identifiers handled by the ShortcutManager.

## Deploying Manifests

Pulsing the `Ensuremanifests` parameter validates all manifests for the family: embedded operator manifests are validated in place, and existing external manifest files are updated.

Disk deployment is intentionally conservative:

- Existing sidecar JSON files are updated in place.
- Existing folder `manifest.json` entries are updated in place.
- **Missing sidecars or missing folder-manifest entries are not created automatically.** To use external manifests for a file-based operator, create the sidecar or folder `manifest.json` entry first — then `Ensuremanifests` will keep it in sync.
- Non-`OpInfo` sections (`ParRetain`, `StateRetain`, `Shortcuts`, and any custom top-level data) are preserved.

After deployment, the folder cache, search-word cache, OP menu table, and injected UI data are refreshed.

## Family Info

`family_info` is separate from per-operator manifests. It is a JSON DAT on the TDFam owner comp that stores family-level metadata — information that applies to the family as a whole, not to any single operator. TDFam creates it with empty defaults when missing.

```json
{
  "summary": "Tools for fast project setup.",
  "doc_url": "https://example.com/family-docs",
  "support_url": "https://patreon.com/example",
  "PopMenu": [
    {
      "label": "Open Family Tools",
      "callback": "onOpenFamilyTools",
      "disabled": false
    }
  ]
}
```

| Key | Description |
|-----|-------------|
| `summary` | Family-level help summary, shown in the OP Create dialog under the family name. |
| `doc_url` | Family documentation URL. Used as the right-click `Documentation` fallback when an operator has no `OpInfo.doc_url`. |
| `support_url` | Optional support URL. Adds a built-in `Support` right-click item for every operator in this family. |
| `PopMenu` | Family-level right-click menu entries. These appear on every operator in the family, before any per-operator `pop_menu` entries. |

## Pop Menu Items

Right-click menu entries can be defined at two scopes:

- **Family-level**: `family_info.PopMenu` — appears on every operator in the family.
- **Per-operator**: `OpInfo.pop_menu` — appears only on that operator (embedded operators only; file-based `pop_menu` data is preserved but not yet used in the right-click menu).

```json
{
  "pop_menu": [
    {
      "label": "Support",
      "callback": "onSupportDot",
      "disabled": false
    }
  ]
}
```

| Field | Behavior |
|-------|----------|
| `label` | Menu item text. Empty labels are skipped. |
| `disabled` | When truthy, the item is shown disabled. |
| `callback` | Function name in the family's callback DAT. |

### Built-in entries

The `Documentation` item is always present and enabled when `doc_url` is defined (per-operator `OpInfo.doc_url` or family `family_info.doc_url` as fallback). The `Support` item appears when `family_info.support_url` is defined.

### Implementing a callback

Define the function in the DAT pointed to by `par.Callbackdat`:

```python
def onSupportDot(info):
    import webbrowser
    webbrowser.open('https://patreon.com/your-project')
```

The callback receives an `info` dict with:

| Key | Description |
|-----|-------------|
| `family` | Family name active in the OP Create dialog. |
| `opType` | OP Create menu op type for the clicked entry. |
| `opLabel` | OP Create menu label for the clicked entry. |
| `item` | Clicked pop-menu label. |
| `menuEntry` | Original `PopMenu` or `pop_menu` entry dict. |
| `scope` | `family` for `family_info.PopMenu`, `operator` for `OpInfo.pop_menu`. |

## External Manifests

For file-based operators, manifests can be provided as JSON files alongside the `.tox` files. Two formats are supported.

### Sidecar JSON

A JSON file with the same base name as the `.tox`:

```text
operators/
  noise_gen_v1.2.0.tox
  noise_gen_v1.2.0.json
```

Contents:

```json
{
  "OpInfo": { "...": "..." },
  "ParRetain": { "...": "..." },
  "StateRetain": { "...": "..." },
  "Shortcuts": { "...": "..." }
}
```

### Folder Manifest

A `manifest.json` at the folder root or in a category subfolder can cover multiple operators:

```json
{
  "noise_gen": {
    "OpInfo": { "...": "..." },
    "ParRetain": { "...": "..." }
  },
  "color_ramp": {
    "OpInfo": { "...": "..." },
    "StateRetain": { "...": "..." }
  }
}
```

Keys are normalized operator names: lowercase and without the version suffix parsed from the file name. Sidecar files take priority over folder manifests.

### Lookup Order

External operator folders are cached when the family initializes or when the folder is refreshed. If external `OpInfo.op_type` exists, the cache key uses that `op_type`; otherwise it uses the parsed filename key. This lets a `.tox` filename differ from the operator's canonical type without creating duplicate menu entries.

Lookup order for file-based manifest data:

1. Sidecar JSON next to the `.tox`
2. `manifest.json` in the category subfolder
3. Root `manifest.json`
4. Values already inside the loaded `.tox`
5. Generated defaults

## Filename Convention

File-based operators are parsed using a configurable regex (set via the `Namingconvention` parameter). The default is:

```text
(.+)_v(\d+\.\d+\.\d+)\.tox$
```

| Filename | Parsed Name | Parsed Version |
|----------|-------------|----------------|
| `noise_gen_v1.2.0.tox` | `noise_gen` | `1.2.0` |
| `my_op.tox` | `my_op` | `None` |

Unversioned files are valid but lose version comparison during source resolution.
