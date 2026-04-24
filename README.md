# TDFam

Create custom operator families for TouchDesigner. A TDFam family is a named group of custom operators that appear together in TD's OP Create dialog, the menu opened with TAB.

Operators can live inside the TDFam component as COMPs, or outside it as `.tox` files in a folder. TDFam handles the connection between those operator sources, the TouchDesigner UI, and the lifecycle of placed operators.

## Contributors

- [Lyell Hintz / dotsimulate](https://dotsimulate.com)
- [Dan Molnar / function.str](https://www.functionstore.xyz/link-in-bio)

## TDFam Component

The TDFam component (`TDFam_create`) defines one family. It is packaged inside each family by the developer — it stores the family name, color, operator sources, callbacks, and metadata. A family can use embedded operators (COMPs inside `Opcomp`), file-based operators (`.tox` files in `Opfolder`), or both. When both sources provide the same operator, TDFam picks the higher version.

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

When a family is installed, its operators appear in TD's OP Create dialog. TDFam handles placement, manifest validation, color, shortcuts, and callbacks.

Placed operators can be converted to **stubs** — lightweight placeholders that preserve the network shape, wiring, and retained data without carrying the full implementation. This lets project files be shared between users without distributing private or paid `.tox` components. Replacing a stub loads the full operator back from the installed family.

**Updates** load a newer version of an operator while preserving retained parameters and state, so users don't lose their work when a family ships a new release.

See [Concepts](docs/concepts.md) and [Callbacks & API](docs/callbacks-and-api.md) for the full lifecycle and available hooks.

## Quickest Start

1. Add the TDFam `.tox` to your project.
2. Set the family name and color.
3. Point `Opcomp` or `Opfolder` at your operators.
4. Toggle `Install`.

Your operators are now in the TAB menu. For callbacks, manifests, stubs, and config — see [Concepts](docs/concepts.md).

## Updates

TDFam checks for registry updates automatically. Users can see available updates in the FAM UI button (top right), on the About page — the indicator turns yellow when an update is ready.

Family developers should keep the TDFamRegistry bundled inside their TDFam component up to date. If a user has a newer registry version on disk, TDFam will load that instead of an outdated bundled one.

## Documentation

- [Concepts](docs/concepts.md): architecture, sources, tags, stubs, config sync, and lifecycle.
- [Manifest Reference](docs/manifest-reference.md): OpInfo, ParRetain, StateRetain, Shortcuts, pop menus, and external manifests.
- [Callbacks & API](docs/callbacks-and-api.md): methods, callbacks, and lifecycle hooks.
- [Config Reference](docs/config-reference.md): config tables, family parameters, and JSON import/export.
- [Licensing and Attribution](docs/licensing.md): Apache-2.0 terms, NOTICE handling, and attribution.

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
