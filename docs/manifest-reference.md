# Manifest Reference

Every placed operator gets a `FamManifest` child COMP containing DATs that define the operator's identity, menu behavior, and retention rules. File-based operators can also provide the same manifest data externally as JSON sidecars or folder manifests.

## family_info

`family_info` is a JSON DAT on the TDFam owner comp. TDFam creates it with empty defaults when missing. It stores family-level metadata and menu entries. The keys live at the top level; there is no `FamilyInfo` wrapper key.

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
| `summary` | Family-level help summary. Added to the registry summaries table under the family name. |
| `doc_url` | Family documentation URL. Used as the right-click `Documentation` fallback when the operator has no `OpInfo.doc_url`. |
| `support_url` | Optional support URL. Adds a built-in `Support` right-click item for this family. |
| `PopMenu` | Family-level right-click menu entries. These appear before per-operator `OpInfo.pop_menu` entries. |

## OpInfo

`OpInfo` is the operator identity and menu metadata block.

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
| `fam_version` | Version of the family that shipped this operator. Rewritten from the family owner during validation. |
| `op_fam` | Family name. Rewritten from the family owner during validation. |
| `op_group` | Optional menu group. Takes priority over `group_mapping`; file-based ops fall back to folder category when no manifest/config group exists. |
| `summary` | Optional help text merged into the OP Create dialog summaries table. |
| `doc_url` | Optional URL opened from the right-click `Documentation` item for embedded menu entries. `https://` is added when no scheme is provided. |
| `op_color` | Optional RGB list applied to placed, updated, or restored operators. This per-op color overrides the family color toggle for that operator. |
| `isFilter` | Optional boolean used to choose filter vs generator menu layout. If omitted, embedded ops use generator membership and file-based ops default to filter behavior. |
| `compatible_types` | Optional per-operator compatibility override used by the append/connect workflow. |
| `search_words` | Optional list, or comma/space-separated string, of extra search terms. |
| `pop_menu` | Optional right-click menu entries for embedded menu entries. See "Pop Menu Items" below for the exact callback contract. |

`op_type` is the primary key. It identifies what an operator is even if the node name, file name, or label changes.

When manifests are validated, TDFam preserves existing custom fields. It always rewrites `fam_version` and `op_fam` from the family owner, fills missing required identity fields from the operator name/version, and sanitizes in-TD `op_name` and `op_type` values for TouchDesigner naming.

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
| `ParName` | Retain this parameter in all scenarios. |
| `ParName:stub` | Retain only during stub operations. |
| `ParName:update` | Retain only during update operations. |
| `!ParName` | Exclude this parameter. |
| `!ParName:stub` | Exclude only during stub operations. |
| `<PageName>` | Retain all parameters on this page. |
| `Par*` | Wildcard; retain all matching parameters. |

For `.` / self rules, the default is all custom parameters, then exclusions are applied. For child entries, the default is nothing; inclusions opt parameters in.

## StateRetain

Rules for preserving non-parameter state: extension storage, raw component storage, and DAT content.

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

StateRetain uses the same rule syntax as ParRetain: `name`, `name:scenario`, `!name`, and wildcards with `*`.

| Section | Description |
|---------|-------------|
| `extensions` | Preserves StorageManager-style dictionaries stored as `{ClassName}Stored`. |
| `storage` | Preserves raw `comp.store()` entries, excluding extension `*Stored` keys. |
| `dats` | Preserves immediate text/table DAT children by name. |

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

## Pop Menu Items

`family_info.PopMenu` adds family-level entries to every operator in that family. `OpInfo.pop_menu` adds entries for one embedded manifest operator. The current per-operator right-click lookup reads embedded `Opcomp` manifests; file-based sidecar/folder `pop_menu` and `doc_url` data is preserved but is not used by the OP Create right-click menu yet.

Example:

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

Then implement `onSupportDot(info)` in the owning family's callback DAT:

```python
def onSupportDot(info):
    # Example:
    # import webbrowser
    # webbrowser.open('https://patreon.com/your-project')
    return
```

Current fields consumed by code:

| Field | Used by | Behavior |
|-------|---------|----------|
| `label` | `opfam_popMenuCallbacks.onOpen()` and injected `panelexec3` code | Text appended to `popMenu.par.Items`. Empty labels are skipped by `onOpen()`. |
| `disabled` | `opfam_popMenuCallbacks.onOpen()` and injected `panelexec3` code | When truthy, the label is appended to `popMenu.par.Disableditems`. |
| `callback` | `opfam_popMenuCallbacks.onClick()` | Family callback DAT function name. The click routes through the registry and calls `ownerComp.ext.OpFamExt.DoCallback(callback, info)`. |

The built-in `Documentation` item is always present. It is enabled only when `doc_url` is defined.
The built-in `Support` item appears when `family_info.support_url` is defined.

The callback receives an `info` dict with the standard callback fields plus:

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

### Cache and Lookup Rules

External operator folders are cached when the family initializes or when the folder is refreshed. If external `OpInfo.op_type` exists, the cache key uses that `op_type`; otherwise it uses the parsed filename key. This lets a `.tox` filename differ from the operator's canonical type without creating duplicate menu entries.

Lookup order for file-based manifest data:

1. Sidecar JSON next to the `.tox`
2. `manifest.json` in the category subfolder
3. Root `manifest.json`
4. Values already inside the loaded `.tox`
5. Generated defaults

## Deploying Manifests

Pulsing `Ensuremanifests` validates embedded operator manifests and updates existing external manifest files. Disk deployment is intentionally conservative:

- Existing sidecar JSON files are updated in place.
- Existing folder `manifest.json` entries are updated in place.
- Missing sidecars or missing folder-manifest entries are not created automatically.
- Non-`OpInfo` sections such as `ParRetain`, `StateRetain`, `Shortcuts`, and custom top-level data are preserved.
- After deployment, the folder cache, search-word cache, OP menu table, and injected UI data are refreshed.

## Filename Convention

File-based operators are parsed using a configurable regex. The default is:

```text
(.+)_v(\d+\.\d+\.\d+)\.tox$
```

| Filename | Parsed Name | Parsed Version |
|----------|-------------|----------------|
| `noise_gen_v1.2.0.tox` | `noise_gen` | `1.2.0` |
| `my_op.tox` | `my_op` | `None` |

Unversioned files are valid but lose version comparison during source resolution.
