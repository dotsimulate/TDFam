# TDFam

Create custom operator families for TouchDesigner. A TDFam family is a named group of custom operators that appear together in TD's OP Create dialog, the menu opened with TAB.

Operators can live inside the TDFam component as COMPs, or outside it as `.tox` files in a folder. TDFam handles the connection between those operator sources, the TouchDesigner UI, and the lifecycle of placed operators.

## Contributors

- [Lyell Hintz / dotsimulate](https://dotsimulate.com)
- [Dan Molnar / function.str](https://www.functionstore.xyz/link-in-bio)

## Quick Start

1. Add the TDFam `.tox` to your TouchDesigner project.
2. Set the family name and color.
3. Point `Opcomp` at embedded operator COMPs, or point `Opfolder` at a folder of `.tox` files.
4. Toggle `Install` to put the family in the TAB menu.

For deeper integration, pulse `Createcallbacks` to generate a callbacks DAT, add manifests for version and retain behavior, and use JSON import/export for config under version control.

## TDFam Component

The TDFam component defines one family in a project. It is intended to be packaged within families by developers — it stores the family parameters, points at embedded COMPs or an external `.tox` folder, owns the optional callbacks DAT, and carries family-level metadata.

## Operators and Manifests

A family can use embedded operators (COMPs inside `Opcomp`), file-based operators (`.tox` files in `Opfolder`), or both. When multiple sources provide the same operator, TDFam resolves which version to use based on manifest metadata and version numbers.

Each operator can carry a manifest (`FamManifest`) that defines its identity, menu metadata, parameter and state retention rules, and keyboard shortcuts. File-based operators can use external JSON manifests. Family-level metadata — summary, documentation, support URL, and pop-menu entries — lives in an optional `family_info` DAT. Config tables provide bulk controls for grouping, label replacement, and OS compatibility.

See the [Manifest Reference](docs/manifest-reference.md) and [Config Reference](docs/config-reference.md) for details.

## Placement, Stubs, and Updates

When a family is installed, its operators appear in TD's OP Create dialog. TDFam handles placement, manifest validation, color, shortcuts, and callbacks.

Placed operators can be converted to **stubs** — lightweight placeholders that preserve the network shape, wiring, and retained data without carrying the full implementation. This lets project files be shared between users without distributing private or paid `.tox` components. Replacing a stub loads the full operator back from the installed family.

**Updates** load a newer version of an operator while preserving retained parameters and state, so users don't lose their work when a family ships a new release.

See [Concepts](docs/concepts.md) and [Callbacks & API](docs/callbacks-and-api.md) for the full lifecycle and available hooks.

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
