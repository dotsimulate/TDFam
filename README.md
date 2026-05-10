# TDFam

Create custom operator families for TouchDesigner. A TDFam family is a named group of custom operators that appear together in TD's OP Create dialog, the menu opened with TAB.

Operators can live inside the TDFam component as COMPs, or outside it as `.tox` files in a folder. TDFam handles the connection between those operator sources, the TouchDesigner UI, and the lifecycle of placed operators.

## Features

- **TAB menu integration** — custom families appear in TD's OP Create dialog with their own tab, color, and search words; the tab bar resizes automatically as families are added
- **Dual operator sources** — embed operators as COMPs, point to a folder of `.tox` files, or use both; when both sources carry the same operator, the higher version wins
- **Manifests** — per-operator metadata covering display name, version, color, grouping, documentation links, and right-click menu entries
- **Stubs** — convert placed operators to lightweight placeholders that preserve network shape, wiring, and retained state without distributing source files; a stub can be replaced with the full operator at any time
- **Updates** — upgrade operators in-place to a newer version while preserving parameters and state through ParRetain and StateRetain rules
- **Callbacks** — lifecycle hooks at every stage: install, placement, stub, replace, update, and right-click (pop) menus
- **Config tables** — bulk controls for operator grouping, label replacement, and OS compatibility
- **Family registry** — a shared TDFamRegistry coordinates all installed families, handles UI injection into the OP Create dialog, and auto-promotes the highest compatible registry version across families
- **JSON config** — export and import family configuration as JSON for version control and portability
- **Programmatic API** — place, find, stub, and update operators from Python without using the menu

## Download

TDFam is distributed as `.tox` files. Get the latest from the [`modules/release/`](modules/release/) folder in this repository:

- **`TDFam_create.tox`** — the TDFam family component; one per family you create
- **`TDFamRegistry.tox`** — the shared registry; bundled inside `TDFam_create`, no separate install needed

## Contributors

- [Lyell Hintz / dotsimulate](https://dotsimulate.com)
- [Dan Molnar / function.str](https://www.functionstore.xyz/link-in-bio)

## Families created with TDFam

- TODO: List families created with TDFam here, links, creators, etc

## TDFam Component

The TDFam component (`TDFam_create`) defines one family. It is packaged inside each family by the developer — it stores the family name, color, operator sources, callbacks, and metadata. A family can use embedded operators (COMPs inside `Opcomp`), file-based operators (`.tox` files in `Opfolder`), or both. When both sources provide the same operator, TDFam picks the higher version.

Multiple families are ordered in the OP Create menu by their `Index` parameter. The index is absolute — it refers to a position in the full family tab bar including built-in families, so a custom family can be inserted between built-ins. Multiple families at the same index are sorted alphabetically. Set `Index` to `-1` to auto-assign: wildcard families fill the remaining slots after all built-ins, in alphabetical order.

Dev mode is available on the About page for development and testing. **Turn dev mode off before releasing to users.**

Behind the scenes, a shared **TDFamRegistry** component coordinates all installed families — it handles UI injection into the OP Create menu, operator management, stubs, and updates.

## Operators and Manifests

Each operator can carry a manifest that defines how it appears in the menu and how its data is preserved across stubs and updates.

| Manifest field | What it controls |
|---|---|
| `op_type` | Canonical operator identity used for lookup and placement |
| `op_label` | Display name in the OP Create menu |
| `op_group` | Menu grouping (e.g. "Generators", "Filters") |
| `op_color` | Operator color in the menu and network |
| `op_version` | Version tracking for updates |
| `isFilter` | Filter vs generator classification |
| `compatible_types` | Which TD operator types this can connect to |
| `summary` | One-line description shown in the menu |
| `doc_url` | Link to operator documentation |
| `search_words` | Additional terms for menu search |
| `pop_menu` | Right-click menu entries and actions |

File-based operators can use external JSON manifests (sidecar or folder-based). Family-level metadata — summary, documentation, support URL, and pop-menu entries — lives in an optional `family_info` DAT. Config tables provide bulk controls for grouping, label replacement, and OS compatibility.

See the [Manifest Reference](docs/manifest-reference.md) and [Config Reference](docs/config-reference.md) for the full field list and formats.

## Placement, Stubs, and Updates

When a family is installed, its operators appear in TD's OP Create dialog. The family tab bar resizes automatically as more families are installed. You can navigate between family tabs with `Tab` / `Shift+Tab`, and the arrow keys (`↑ ↓ ← →`). TDFam handles placement, manifest validation, color, shortcuts, and callbacks. Shortcuts can toggle or pulse a parameter, or dispatch a named callback through the family's callback DAT.

Placed operators can be converted to **stubs** — lightweight placeholders that preserve the network shape, wiring, and retained data without carrying the full implementation. This lets project files be shared between users without distributing private or paid `.tox` components. Replacing a stub loads the full operator back from the installed family.

**Updates** load a newer version of an operator while preserving retained parameters and state, so users don't lose their work when a family ships a new release.

See [Concepts](docs/concepts.md) and [Callbacks & API](docs/callbacks-and-api.md) for the full lifecycle and available hooks.

## Quickest Start

1. Add `TDFam_create.tox` to your project.
2. Set the family name, color, and version.
3. Point `Opcomp` or `Opfolder` at your operators.
4. Hit `Ensure Manifests` to deploy default [manifests](docs/manifest-reference.md) for all operators.
5. Toggle `Install`.

Your operators are now in the TAB menu.

To add callbacks, click `Createcallbacks` — it generates a callback DAT pre-populated with all available hooks. Reference it with the `Callbackdat` parameter. 

For manifests, stubs, and config — see [Concepts](docs/concepts.md).

> **Developer note:** Keep the `Version` parameter (Family tab) updated with each release. TDFam inherits it into operator manifests as `fam_version` and as a fallback `op_version` for operators that don't define their own. When packaging your family component for distribution, consider promoting `Version` to the top level so users can see it without diving into the component.

## Public API

Key methods on the TDFam extension instance, callable from Python:

| Method | What it does |
|---|---|
| `Install(install=None)` | Toggle family installation; omit argument to query current state |
| `PlaceOp(target, op_type, name, x, y)` | Place an operator programmatically without using the TAB menu |
| `FindOps(...)` | Find placed operators belonging to this family; mirrors TD's `findChildren` |
| `GetMasterOps()` | Return all available operators with their metadata |
| `GetOpSource(lookup_name)` | Get the source COMP or file path for a named operator |
| `StubOp(comp)` | Convert a placed operator to a stub |
| `UpdateOp(comp)` | Update a placed operator to the newest available version |
| `ExportConfig(path=None)` | Export family config to JSON |
| `ImportConfig(source)` | Import family config from a JSON string or file path |

See [Callbacks & API](docs/callbacks-and-api.md) for full signatures, callback hooks, and info dict keys.

## Updates

TDFam checks for registry updates automatically. Users can see available updates via the FAM UI button (top right of the OP Create dialog), and on the About page — the indicator turns yellow when an update is ready.

Family developers should keep the TDFamRegistry bundled inside their TDFam component up to date. If a user has a newer registry version already installed from another family, TDFam will load that instead of an older bundled one.

## Documentation

- [Concepts](docs/concepts.md): architecture, sources, tags, stubs, config sync, and lifecycle.
- [Manifest Reference](docs/manifest-reference.md): OpInfo, ParRetain, StateRetain, Shortcuts, pop menus, and external manifests.
- [Callbacks & API](docs/callbacks-and-api.md): methods, callbacks, and lifecycle hooks.
- [Config Reference](docs/config-reference.md): config tables, family parameters, and JSON import/export.
- [Licensing and Attribution](docs/licensing.md): Apache-2.0 terms, NOTICE handling, and attribution.

Example manifests live in [`install_scripts/OpFamRegistry/Manifest/`](install_scripts/OpFamRegistry/Manifest/).

## Requirements

- TouchDesigner 2023+

## License

TDFam is licensed under the Apache License, Version 2.0. See [LICENSE](LICENSE).

If you distribute TDFam, a modified version of TDFam, or a TouchDesigner
component or operator family that includes TDFam, preserve the Apache-2.0
license notices and the [NOTICE](NOTICE) attribution file as required by the
license.

Operator families, `.tox` files, manifests, callbacks, artwork, and
project-specific logic created with TDFam may use their own licenses.

Suggested attribution:

> Built with TDFam, an open-source TouchDesigner operator-family framework
> created by [Lyell Hintz / dotsimulate](https://dotsimulate.com) and
> [Dan Molnar / function.str](https://www.functionstore.xyz/link-in-bio).
