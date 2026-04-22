# TDFam Concepts

## What TDFam Does

TDFam lets you create custom operator families that appear in TouchDesigner's TAB menu. You define a set of operators as embedded COMPs or external `.tox` files, configure how they are grouped and labeled, and TDFam handles registration, menu injection, placement, stubbing, and updates.

## Architecture

### TDFam Owner Comp

This is the family component you configure and ship. It runs the `OpFamExt` extension and exposes parameters for:

- Family identity: name, color, index, version
- Operator sources: embedded `custom_operators` COMP and/or external `.tox` folder
- Config tables: grouping, labels, sort behavior, and OS compatibility
- Callbacks DAT: optional hooks into placement, stubbing, replacement, updates, and install events

The TDFam comp owns configuration and dynamic state. You customize behavior through parameters, manifests, config tables, and callbacks.

### Registry

`op.FAMREGISTRY` is a singleton component that manages registered families. It owns network-facing work:

- UI injection into `/ui/dialogs/menu_op`
- Operator placement and clone preparation
- Manifest creation, validation, tagging, and disk deployment
- Stub, replace, and update logic
- External folder scanning, version parsing, and source resolution
- Help text, right-click menu, color, and compatibility injection

Most project code should interact with the registry through the TDFam owner comp API.

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

Family rename logic refreshes these tags and manifest family references on masters and placed instances so the registry does not keep stale family names.

## Config Tables vs Manifests

Manifests define operator identity and optional per-operator metadata. Config tables define family-level defaults and menu presentation:

- `group_mapping` controls default grouping and custom group order.
- `label_replacements` applies label text replacements.
- `os_incompatible` hides or disables operators by platform.
- `settings` controls sort and ungrouped behavior.

When both sources provide a value, manifest data is more specific. For example, `OpInfo.op_group` takes priority over `group_mapping`; file-based operators then fall back to their category folder if no manifest/config group exists.

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

Stubs are lightweight placeholders that preserve:

- Network position and size
- Input/output connections
- Parameter values governed by `ParRetain`
- Extension storage, raw storage, and DAT contents governed by `StateRetain`
- Cooking and bypass state

Replacing a stub or updating an operator loads a fresh source, validates its manifest, restores retained state, reapplies colors, and runs the relevant callbacks.

## Config Sync

Configuration flows between DAT tables, the runtime Config DependDict, and JSON import/export:

```text
DAT Tables <-> Config DependDict <-> JSON
```

Edit tables in TD's UI, or import/export JSON for version control. Changes sync through the Config DependDict.

## Operator Lifecycle

1. Install: family registers with the Registry and injects UI hooks.
2. Place: user selects from the TAB menu; TDFam prepares the clone, validates manifest data, applies color/shortcuts, and places it.
3. Use: operator functions normally in the network.
4. Stub: full operator becomes a lightweight placeholder with retained state.
5. Replace: stub is restored to a full operator.
6. Update: operator is replaced by a newer source while retaining configured state.
7. Uninstall: family deregisters and UI hooks are removed.
