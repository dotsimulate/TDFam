# Callbacks & API Reference

## Public API

These methods are available on your TDFam installer extension instance.

### `Install(install: bool = None)`

Toggle family installation. Registers/unregisters with the Registry and injects/removes UI hooks. If `install` is `None`, reads from `par.Install`.

### `PlaceOp(target, op_type, name=None, x=None, y=None) -> OP`

Programmatically place an operator into `target` network. Triggers the full callback chain (`onPlaceOp` → `onPostPlaceOp`). Returns the placed operator.

### `FindOps(...) -> list`

Find placed operators belonging to this family. Mirrors TD's `findChildren` API.

```python
FindOps(
    type=None,           # op_type filter
    name=None,           # node name filter
    path=None,           # path filter
    depth=None,          # exact depth
    maxDepth=None,       # max search depth
    tags=[],             # required tags
    allTags=False,       # require all tags (vs any)
    parValue=None,       # parameter value filter
    parExpr=None,        # parameter expression filter
    parName=None,        # parameter name filter
    key=None,            # custom filter function — key(op) must return True to include
    include_stubs=False, # include stub operators
    network=None         # search root (default: install_location)
)
```

### `StubOp(comp) -> OP`

Create a stub from a placed operator. Returns the stub, or `None` on failure.

### `UpdateOp(comp) -> tuple`

Update an operator to the newest available version. Returns `(success: bool, message: str)`.

### `GetOperators() -> dict`

Returns all available operators with metadata. Dict keyed by operator name, values contain source info, version, OpInfo, and manifest data.

### `GetOperatorSource(lookup_name: str) -> tuple | None`

Returns the source for a specific operator: `('embedded', op)`, `('file', path)`, or `None`.

### `ExportConfig(path: str = None) -> dict | tuple`

Export config to a dict (no path) or write to a JSON file (with path). When writing to file, returns `(success: bool, message: str)`.

### `ImportConfig(source: str | dict) -> tuple`

Import config from a dict, JSON string, or file path. Returns `(success: bool, message: str)`.

---

## Callbacks

Callbacks hook into the operator lifecycle. Implement them in a callbacks DAT (pointed to by `par.Callbackdat`).

All callbacks receive an `info` dict containing at minimum `ownerComp` and `callbackName`.

### Placement

#### `onPlaceOp(info) -> bool | None`

Called before an operator is placed from the TAB menu.

| Key | Type | Description |
|-----|------|-------------|
| `lookupName` | `str` | Operator lookup name. **Modifiable** — change this to swap which operator gets placed. |
| `panelValue` | `int` | Panel click position. |

**Return values:**
- `True` — proceed with placement
- `False` — cancel and close menu
- `None` — cancel placement but keep menu open (for "action operators" that do something without placing)

#### `onPostPlaceOp(info)`

Called after an operator is placed.

| Key | Type | Description |
|-----|------|-------------|
| `clone` | `OP` | The placed operator. |

### Stubbing

#### `onPreStub(info) -> bool`

Called before creating a stub.

| Key | Type | Description |
|-----|------|-------------|
| `comp` | `OP` | The operator to stub. **Modifiable.** |

Return `False` to skip this operator.

#### `onPostStub(info)`

Called after stub creation.

| Key | Type | Description |
|-----|------|-------------|
| `stub` | `OP` | The created stub. |
| `original` | `OP` | The original operator (now deleted). |

### Replacing (Stub → Full Operator)

#### `onPreReplace(info) -> bool`

Called before replacing a stub with a full operator.

| Key | Type | Description |
|-----|------|-------------|
| `stub` | `OP` | The stub being replaced. **Modifiable.** |

Return `False` to skip.

#### `onPostReplace(info)`

Called after a stub is replaced.

| Key | Type | Description |
|-----|------|-------------|
| `newComp` | `OP` | The restored operator. |
| `stub` | `OP` | The original stub (now deleted). |
| `extraInfo` | `dict` | Data captured by `onCaptureExtraInfo`. |

### Updating

#### `onPreUpdate(info) -> bool`

Called before updating an operator to a newer version.

| Key | Type | Description |
|-----|------|-------------|
| `oldComp` | `OP` | The current operator. |
| `master` | `OP` | The new version source. **Modifiable.** |

Return `False` to skip.

#### `onPostUpdate(info)`

Called after an operator is updated.

| Key | Type | Description |
|-----|------|-------------|
| `newComp` | `OP` | The updated operator. |
| `extraInfo` | `dict` | Data captured by `onCaptureExtraInfo`. |

### State Capture

#### `onCaptureExtraInfo(info)`

Called during stub and update operations to capture arbitrary data for later restoration.

| Key | Type | Description |
|-----|------|-------------|
| `comp` | `OP` | The operator being captured. |
| `scenario` | `str` | `'stub'` or `'update'`. |

Set `info['returnValue']` to a dict. This dict is passed as `extraInfo` in `onPostReplace` / `onPostUpdate`.

### Parameter Preservation

#### `onPreserveSpecialParams(info)`

Called during stub/update to handle parameters that need custom preservation logic.

| Key | Type | Description |
|-----|------|-------------|
| `newComp` | `OP` | The new operator. |
| `source` | `OP` or `dict` | The old operator or stored params dict. |

#### `onCaptureChildrenParams(info)`

Called to capture/modify child component parameter data.

| Key | Type | Description |
|-----|------|-------------|
| `comp` | `OP` | The parent operator. |
| `children_data` | `dict` | Captured child params. **Modifiable.** |

### Manifest

#### `onDeployManifest(info)`

Called when a manifest is deployed to an operator (during `deployManifests`).

| Key | Type | Description |
|-----|------|-------------|
| `comp` | `OP` | The operator receiving the manifest. |
| `opType` | `str` | Resolved operator type. |
| `OpInfo` | `dict` | OpInfo data being deployed. |
| `ParRetain` | `dict` | ParRetain rules being deployed. |
| `Shortcuts` | `dict` | Shortcuts being deployed. |

### Tag Filtering

#### `onGetExcludedTags(info) -> set`

Return a set of tag names to exclude from operator type resolution.

#### `onGetCategoryTags(info) -> set`

Return a set of tags to treat as category tags during type resolution.

### Installation

#### `onPreInstall(info)` / `onPostInstall(info)`

Called before/after the family is installed. Minimal info dict (just `ownerComp` and `callbackName`).

---

## Creating a Callbacks DAT

Pulse `par.Createcallbacks` on your TDFam comp to generate a callbacks DAT from the built-in template. Set `par.Callbackdat` to point at it.

The template includes all callback signatures with docstrings. Delete the ones you don't need.
