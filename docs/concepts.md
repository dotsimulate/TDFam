# TDFam Concepts

## What TDFam Does

TDFam lets you create custom operator families that appear in TouchDesigner's OP Create dialog, the menu opened with TAB. You define a family of operators as embedded COMPs, external `.tox` files, or both. TDFam handles the public family API, menu integration, placement, manifests, stubs, updates, and callbacks around those operators.

## Architecture

TDFam has one public surface and one documented internal system. The public surface is the TDFam family component that authors configure. The internal system is the TD Registry that TDFam injects or updates to coordinate TouchDesigner integration for all installed families.

### TDFam Family Component

The TDFam family component is the developer entry point. One TDFam family component defines one operator family in a project. It runs `OpFamExt`, which layers the public family API and parameter handlers on top of the lower `OpFamCreateExt` setup/config implementation.

The family component owns:

- Family identity: name, color, index, and version
- Operator sources: embedded `custom_operators` / `Opcomp` and external `.tox` `Opfolder`
- Family configuration: config DATs, runtime Config DependDict, and JSON import/export
- Family metadata: the optional `family_info` JSON DAT
- Developer extension points: the optional callbacks DAT referenced by `par.Callbackdat`
- Public methods such as `Install()`, `GetMasterOps()`, `PlaceOp()`, `FindOps()`, `StubOp()`, `UpdateOp()`, `ImportConfig()`, and `ExportConfig()`

Most custom family work should happen at this level. A family author configures the TDFam component, writes operator manifests, and optionally implements callbacks.

### TD Registry

The TD Registry (`op.FAMREGISTRY`) is documented internal infrastructure. It is injected by TDFam and shared by all TDFam families in a project. When multiple TDFam components bring Registry templates with them, version reconciliation keeps the highest compatible TD Registry version active.

The TD Registry is not a supported user or family-developer API. It is documented so the project architecture is understandable, but family code should go through the TDFam family component. TDFam calls the TD Registry on behalf of the family.

The TD Registry owns:

- Registered and installed family dictionaries
- Family owner validation, rename handling, and registry version reconciliation
- UI injection into `/ui/dialogs/menu_op`
- OP Create menu rows, family colors, compatibility data, search behavior, help summaries, and right-click menus
- Operator source lookup across embedded COMPs and external `.tox` folders
- Clone preparation, placement, manifest validation, and tagging
- Stub replacement and update operations
- Shortcut registration and dispatch
- Callback dispatch from internal events into the owning family's callback DAT

The TD Registry is implemented as a facade plus manager classes:

- `GlobalUIInjector`: mutates TD's OP Create dialog and related UI tables/scripts.
- `FileManager`: scans external folders, parses versions, reads sidecar/folder manifests, and resolves embedded vs file-based sources.
- `OpManager`: prepares clones, validates manifests, applies OpInfo rules, deploys manifests, registers shortcuts, and applies operator attributes.
- `StubManager`: converts full operators to stubs and restores stubs from source operators.
- `UpdateManager`: replaces placed operators with newer source versions while restoring retained data.
- `TagManager`, `ShortcutManager`, and `RegistryHelpers`: shared support for tags, shortcuts, colors, retain rules, and state capture/restore.

Family users and family developers should call the TDFam family component API. Direct TD Registry and manager calls belong to the TDFam implementation itself.

## Family Info

Each family can have a `family_info` JSON DAT on the owner comp. Its top-level keys are `summary`, `doc_url`, `support_url`, and `PopMenu`. This is family-level metadata: it applies to the family as a whole, not to one operator.

## Operator Sources

Operators can come from two places:

- Embedded: COMPs inside the family `Opcomp` / `custom_operators` container.
- File-based: `.tox` files in an external `Opfolder`.

Versioned file names use the configured naming convention, defaulting to:

```text
(.+)_v(\d+\.\d+\.\d+)\.tox$
```

When both embedded and file-based sources provide the same operator, the higher version wins. Ties go to embedded. File-based operators can also use sidecar JSON or folder `manifest.json` files; when `OpInfo.op_type` exists, it becomes the cache and lookup key instead of the filename-derived key.

## Manifests

Every placed COMP operator gets a `FamManifest` child COMP. A manifest contains:

| DAT | Purpose |
|-----|---------|
| `OpInfo` | Operator identity and menu metadata. |
| `ParRetain` | Parameters to preserve across stub and update operations. |
| `StateRetain` | Non-parameter state to preserve: extension storage, raw storage, and DATs. |
| `Shortcuts` | Keyboard shortcut mappings. |

Manifests are the source of truth for operator identity. `OpInfo` can also drive menu presentation with fields such as `op_group`, `summary`, `doc_url`, `op_color`, `isFilter`, `compatible_types`, `search_words`, and `pop_menu`.

External manifests support the same sections as in-TD manifests:

- Per-op sidecar JSON next to a `.tox`
- Category-folder `manifest.json`
- Root-folder `manifest.json`

Sidecars take priority over folder manifests. Existing in-TD manifest values take priority over external seeds when a loaded operator already has a manifest.

## Tags

TDFam uses TD tags to find and identify operators:

- `<FAM:YourFamily>` marks family membership.
- `<TYPE:op_type>` identifies the operator type.
- `<MANIFEST>` marks a full manifest.
- `<STUB>` marks a stub.

Family rename logic refreshes these tags and manifest family references on masters and placed instances so the TD Registry does not keep stale family names.

## Config Tables vs Manifests

Manifests define operator identity and optional per-operator metadata. Config tables are family-level controls used when TDFam builds the menu model:

- `group_mapping` controls default grouping and custom group order.
- `label_replacements` applies label text replacements.
- `os_incompatible` hides or disables operators by platform.
- `settings` controls sort and ungrouped behavior.

TDFam reads manifest data first for operator identity and per-operator fields, then applies config where config is designed to operate:

- `OpInfo.op_group` is used before `group_mapping`.
- File-based operators can fall back to their category folder when no manifest/config group is set.
- `label_replacements` is applied to generated or manifest-provided labels.
- `os_incompatible` supplies the per-operator OS/exclude flags.
- `settings` controls menu behavior such as ungrouped display and exclude behavior.

## Menu Integration

TDFam injects custom families into the OP Create dialog. Recent menu behavior is manifest-aware:

- `summary` values are merged into the OP Create help text summaries.
- `family_info.doc_url` provides the family-level documentation fallback.
- `family_info.support_url` adds a built-in `Support` item.
- `family_info.PopMenu` adds family-level right-click entries.
- `OpInfo.doc_url` overrides documentation for one embedded operator.
- `OpInfo.pop_menu` adds per-operator right-click entries for embedded menu entries and can route clicks to functions in the family callback DAT.
- `isFilter` selects filter vs generator menu layouts.
- `search_words` adds extra search matches beyond name and label.
- `op_color` applies per-operator network color.

Right-clicking an operator entry opens the custom pop menu and does not place the operator.

## Stubs and Updates

Stubs are lightweight placeholders for placed operators. They keep a network transferable without carrying the full operator implementation, which is useful when a project should preserve the shape and state of a private or paid operator family without distributing the source `.tox` files or full components.

Stubs preserve:

- Network position and size
- Input/output connections
- Parameter values governed by `ParRetain`
- Extension storage, raw storage, and DAT contents governed by `StateRetain`
- Cooking and bypass state

Replacing a stub requires the family source to be available again. TDFam resolves the operator type, loads the matching embedded or file-based source, validates its manifest, restores retained state, reapplies colors, reconnects the operator, and runs the relevant callbacks.

Updates use the same backend managers. TDFam finds the matching source operator, loads or copies the newer version, preserves configured parameter and state data, restores wiring and node attributes, validates the manifest, and runs update callbacks.

## Config Sync

Configuration flows between DAT tables, the runtime Config DependDict, and JSON import/export:

```text
DAT Tables <-> Config DependDict <-> JSON
```

Edit tables in TD's UI, or import/export JSON for version control. Changes sync through the Config DependDict.

## Operator Lifecycle

1. Install: family registers through the TDFam component; TDFam installs or updates the TD Registry if needed and injects UI hooks.
2. Place: user selects from the TAB menu; TDFam prepares the clone, validates manifest data, applies color/shortcuts, and places it.
3. Use: operator functions normally in the network.
4. Stub: full operator becomes a lightweight placeholder with retained state.
5. Replace: stub is restored to a full operator.
6. Update: operator is replaced by a newer source while retaining configured state.
7. Uninstall: family deregisters and UI hooks are removed.
