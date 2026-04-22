# Callbacks & API Reference

## Public API

These methods are available on your TDFam installer extension instance.

### `Install(install: bool = None)`

Toggle family installation. Registers or unregisters with the Registry and injects or removes UI hooks. If `install` is `None`, reads from `par.Install`.

### `PlaceOp(target, op_type, name=None, x=None, y=None) -> OP`

Programmatically place an operator into `target`. This uses the same clone preparation, manifest validation, color application, and callback chain as the OP Create dialog path.

### `GetMasterOps() -> dict`

Return available operators for this family with full metadata.

The dict is keyed by operator type. Values include:

```python
{
    "op_type": "noise_gen",
    "op_name": "noise_gen",
    "op_label": "Noise Generator",
    "op_version": "1.2.0",
    "fam_version": "1.0.0",
    "op_fam": "MYFAM",
    "group": "Generators",
    "source": ("embedded", op("noise_gen")),
    "os_compatible": {"windows": 1, "mac": 1, "exclude": 0},
    "compatible_types": ["CHOP"],
    "isFilter": False
}
```

Manifest values are merged with config-table data. `OpInfo.op_group` takes priority over `group_mapping`; external folder categories are used as a fallback group for file-based operators.

### `GetOperatorSource(lookup_name: str) -> tuple | None`

Return the source for a specific operator: `("embedded", op)`, `("file", path)`, or `None`. Lookup uses manifest `op_type` when present, then filename/name fallbacks.

### `FindOps(...) -> list`

Find placed operators belonging to this family. Mirrors TD's `findChildren` style.

```python
FindOps(
    type=None,
    name=None,
    path=None,
    depth=None,
    maxDepth=None,
    tags=[],
    allTags=False,
    parValue=None,
    parExpr=None,
    parName=None,
    key=None,
    include_stubs=True,
    network=None
)
```

`type` matches manifest `OpInfo.op_type`, `<TYPE:...>` tags, or legacy type tags.

### `StubOp(comp) -> OP`

Create a stub from a placed operator. Returns the stub, or `None` on failure.

### `UpdateOp(comp) -> tuple`

Update an operator to the newest available version. Returns `(success: bool, message: str)`.

### `ExportConfig(path: str = None) -> dict | tuple`

Export config to a dict when no path is provided, or write JSON to `path`. File writes return `(success: bool, message: str)`.

### `ImportConfig(source: str | dict) -> tuple`

Import config from a dict, JSON string, or file path. Returns `(success: bool, message: str)`.

## Registry Helpers

Advanced integrations can call registry helpers through `op.FAMREGISTRY`, but the owner-comp API above is the usual entry point.

Useful registry calls include:

- `IsFamilyInstalled(fam_name)`
- `IsFamilyUIInstalled(fam_name)`
- `GetFamilyOwner(fam_name)`
- `GetFamilyExt(fam_name)`
- `UpdateFamilyName(family_owner, new_name)`
- `CallHook(fam_name, hook_name, *args)`

Registry family operations validate the owner comp. A duplicate family name held by another owner is rejected; family renames refresh registry dictionaries, UI entries, tags, and manifest family references.

## Callbacks

Callbacks hook into the operator lifecycle. Implement them in a callbacks DAT pointed to by `par.Callbackdat`.

All callbacks receive an `info` dict containing at minimum `ownerComp` and `callbackName`.

### Placement

#### `onPlaceOp(info) -> bool | None`

Called before an operator is placed from the TAB menu or `PlaceOp()`.

| Key | Type | Description |
|-----|------|-------------|
| `lookupName` | `str` | Operator lookup name. Modifiable. |
| `panelValue` | `int` or `None` | Panel click position, or `None` for programmatic placement. |

Return values:

- `True`: proceed with placement.
- `False`: cancel and close the menu.
- `None`: cancel placement but keep the menu open.

#### `onPostPlaceOp(info)`

Called after placement.

| Key | Type | Description |
|-----|------|-------------|
| `clone` | `OP` | The placed operator. |

### Stubbing

#### `onPreStub(info) -> bool`

Called before creating a stub.

| Key | Type | Description |
|-----|------|-------------|
| `comp` | `OP` | Operator to stub. Modifiable. |

Return `False` to skip this operator.

#### `onPostStub(info)`

Called after stub creation.

| Key | Type | Description |
|-----|------|-------------|
| `stub` | `OP` | The created stub. |
| `original` | `OP` | The original operator. |

### Replacing Stubs

#### `onPreReplace(info) -> bool`

Called before replacing a stub with a full operator.

| Key | Type | Description |
|-----|------|-------------|
| `stub` | `OP` | Stub being replaced. Modifiable. |

Return `False` to skip.

#### `onPostReplace(info)`

Called after a stub is replaced.

| Key | Type | Description |
|-----|------|-------------|
| `newComp` | `OP` | Restored operator. |
| `stub` | `OP` | Original stub. |
| `extraInfo` | `dict` | Data captured by `onCaptureExtraInfo`. |

### Updating

#### `onPreUpdate(info) -> bool`

Called before updating an operator.

| Key | Type | Description |
|-----|------|-------------|
| `oldComp` | `OP` | Current operator. |
| `master` | `OP` | New source. Modifiable. |

Return `False` to skip.

#### `onPostUpdate(info)`

Called after an operator is updated.

| Key | Type | Description |
|-----|------|-------------|
| `newComp` | `OP` | Updated operator. |
| `extraInfo` | `dict` | Data captured by `onCaptureExtraInfo`. |

### State Capture

#### `onCaptureExtraInfo(info)`

Called during stub and update operations to capture arbitrary data for later restoration.

| Key | Type | Description |
|-----|------|-------------|
| `comp` | `OP` | Operator being captured. |
| `scenario` | `str` | `stub` or `update`. |

Set `info["returnValue"]` to a dict. This dict is passed as `extraInfo` in `onPostReplace` and `onPostUpdate`.

#### `onPreserveSpecialParams(info)`

Called during stub/update to handle parameters that need custom preservation logic.

| Key | Type | Description |
|-----|------|-------------|
| `newComp` | `OP` | New operator. |
| `source` | `OP` or `dict` | Old operator or stored params dict. |

#### `onCaptureChildrenParams(info)`

Called to capture or modify child component parameter data.

| Key | Type | Description |
|-----|------|-------------|
| `comp` | `OP` | Parent operator. |
| `children_data` | `dict` | Captured child params. Modifiable. |

### Manifest Deployment

#### `onDeployManifest(info)`

Called when `Ensuremanifests` deploys or validates a manifest on an embedded operator.

| Key | Type | Description |
|-----|------|-------------|
| `comp` | `OP` | Operator receiving the manifest. |
| `opType` | `str` | Resolved operator type. |
| `OpInfo` | `dict` | Validated OpInfo data. |
| `ParRetain` | `dict` | ParRetain rules. |
| `Shortcuts` | `dict` | Shortcut mappings. |

External disk manifest deployment updates existing sidecars/folder entries directly and then refreshes caches and UI data.

### Tag Filtering

#### `onGetExcludedTags(info) -> set`

Return tags to exclude from operator type resolution.

#### `onGetCategoryTags(info) -> set`

Return tags to treat as category tags during type resolution.

### Installation

#### `onPreInstall(info)` / `onPostInstall(info)`

Called before/after installation.

#### `onPreUninstall(info)` / `onPostUninstall(info)`

Called before/after uninstallation.

## Right-Click Menu Notes

Families can add right-click menu entries with owner-comp `family_info.PopMenu`. Embedded manifest operators can add per-operator entries with `OpInfo.pop_menu`. `OpInfo.doc_url` enables the built-in `Documentation` item; `family_info.doc_url` is the fallback; `family_info.support_url` enables the built-in `Support` item.

Custom actions use the same family callback DAT mechanism as the rest of TDFam. Put the callback DAT function name in the manifest:

```json
{
  "PopMenu": [
    {
      "label": "Support",
      "callback": "onSupportDot"
    }
  ]
}
```

Then implement it in `par.Callbackdat`:

```python
def onSupportDot(info):
    return
```

The callback receives the standard `ownerComp` and `callbackName` keys plus `family`, `opType`, `opLabel`, `item`, `menuEntry`, and `scope`. `scope` is `family` for `family_info.PopMenu` entries and `operator` for `OpInfo.pop_menu` entries.

## Creating a Callbacks DAT

Pulse `par.Createcallbacks` on your TDFam comp to generate a callbacks DAT from the built-in template. Set `par.Callbackdat` to point at it.

The template includes callback signatures and docstrings. Delete the callbacks you do not need.
