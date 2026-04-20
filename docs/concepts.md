# TDFam Concepts

## What TDFam Does

TDFam lets you create custom operator families that appear in TouchDesigner's TAB menu. You define a set of operators (as `.tox` files or embedded COMPs), configure how they're grouped and labeled, and TDFam handles registration, menu injection, placement, stubbing, and updates.

## Architecture: Two Halves

### TDFam (the Owner Comp)

This is your family component — the thing you configure and ship. It runs the `OpFamExt` extension and exposes parameters for:

- **Family identity** — name, color, index
- **Operator sources** — embedded `custom_operators` COMP and/or a path to an external `.tox` folder
- **Config tables** — DATs that control grouping, labeling, sorting, and OS compatibility
- **Callbacks DAT** — optional Python DAT with hooks into the operator lifecycle

The TDFam comp owns configuration and dynamic state. It talks to the Registry to request actions (place, stub, update) but doesn't touch the network directly.

You customize behavior through **parameters and callbacks** — not by subclassing or editing library code.

### Registry (`op.FAMREGISTRY`)

A singleton component that manages all registered families. It owns everything that touches the network:

- **UI injection** — modifies `/ui/dialogs/menu_op` to add your family to the TAB menu
- **Operator placement** — clones operators into the target network
- **Manifest management** — creates and validates FamManifest components on placed operators
- **Stub/Update logic** — creates stubs, replaces them, updates operators to newer versions
- **File loading** — scans external folders, parses versions, caches operator sources

The Registry is stable infrastructure. You don't modify it — you interact with it through your TDFam comp.

### How They Interact

```
Developer
  │
  ▼
TDFam Comp ──── parameters, config tables, callbacks DAT
  │
  │  Register / PlaceOp / StubOp / UpdateOp
  ▼
Registry ────── UI injection, manifest management, network operations
  │
  ▼
TouchDesigner network (placed operators, stubs)
```

## Core Concepts

### Operator Sources

Operators can come from two places:

- **Embedded** — COMPs inside a `custom_operators` container within your TDFam comp. These are disabled base COMPs that get cloned on placement. Set via `par.Opcomp`.
- **File-based** — `.tox` files in an external folder. Supports versioned filenames like `my_op_v1.2.3.tox`. Set via `par.Opfolder`.

When both sources provide the same operator, the one with the higher version wins. Ties go to embedded.

### Manifests

Every placed operator gets a `FamManifest` child COMP containing:

| DAT | Purpose |
|-----|---------|
| `OpInfo` | Operator identity — type, name, label, version, family |
| `ParRetain` | Rules for which parameters to preserve across stub/update |
| `StateRetain` | Rules for preserving non-parameter state (extensions, storage, DATs) |
| `Shortcuts` | Keyboard shortcut mappings |

Manifests are the operator's source of truth for identity. The system uses manifest data (not naming conventions) to match operators during updates.

### Tags

TDFam uses TD's tagging system to find and identify placed operators:

- `<FAM:YourFamily>` — marks membership in a family
- `<TYPE:op_type>` — identifies the operator type
- `<MANIFEST>` — has a full manifest (not a stub)
- `<STUB>` — is a stub

### Stubs

Stubs are lightweight placeholders that replace full operators. A stub preserves:

- Network position and size
- Input/output connections
- Parameter values (governed by ParRetain rules)
- Non-parameter state (governed by StateRetain rules)
- Cooking and bypass state

Stubs reduce project file size and load time. When you need the full operator back, the system replaces the stub with a fresh clone and restores preserved state.

### Config Tables vs Manifests

These serve different purposes:

- **Manifests** define operator **identity** — what an operator _is_ (type, version, label, retention rules). Manifests live inside the operator.
- **Config tables** define operator **presentation** — how operators appear in the menu (grouping, label overrides, sort order, OS filtering). Config tables live in your TDFam comp.

### Callbacks

TDFam provides hooks at every stage of the operator lifecycle. Implement these in a callbacks DAT (pulse `par.Createcallbacks` to generate one from the template, then set `par.Callbackdat` to point at it).

Callbacks follow a consistent pattern:
- **Pre-callbacks** (`onPreStub`, `onPreUpdate`, etc.) — can modify behavior or cancel the operation by returning `False`
- **Post-callbacks** (`onPostPlaceOp`, `onPostStub`, etc.) — react to completed operations
- **Capture callbacks** (`onCaptureExtraInfo`) — store arbitrary data for restoration later

### Config Sync

Configuration flows bidirectionally between three representations:

```
DAT Tables  ◄──►  Config DependDict  ◄──►  JSON
(visual)          (source of truth)        (portable)
```

Edit tables in TD's UI, or import/export JSON for version control. Changes sync automatically through the Config DependDict.

## Operator Lifecycle

1. **Install** — Family registers with Registry, UI hooks injected into TAB menu
2. **Place** — User selects from TAB menu, operator cloned into network with manifest
3. **Use** — Operator functions normally in the network
4. **Stub** — Convert to lightweight placeholder (preserves state per retention rules)
5. **Replace** — Restore stub to full operator
6. **Update** — Replace with newer version (preserves state per retention rules)
7. **Uninstall** — Family deregistered, UI hooks removed
