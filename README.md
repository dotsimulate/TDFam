# TDFam

Create custom operator families for TouchDesigner. A TDFam family is a named group of custom operators that appear together in TD's OP Create dialog, the menu opened with TAB.

Operators can live inside the TDFam component as COMPs, or outside it as `.tox` files in a folder. TDFam handles the connection between those operator sources, the TouchDesigner UI, and the lifecycle of placed operators.

## Contributors

- [Lyell Hintz / dotsimulate](https://dotsimulate.com)
- [Dan Molnar / function.str](https://www.functionstore.xyz/link-in-bio)

## TDFam Component

A TDFam component defines one family in a project. It stores the family parameters, points at the embedded COMP or external `.tox` folder, owns the optional callbacks DAT, and carries family-level metadata such as summary, documentation URL, support URL, and family pop-menu entries.

The public API is the TDFam component. Family users and family developers configure TDFam, write manifests, and use callbacks there. TDFam handles the TouchDesigner UI integration and operator lifecycle work behind the scenes.

## Op Manifests

Manifests define how TDFam recognizes and handles operators. A placed COMP operator gets a `FamManifest` child COMP. File-based operators can also use external JSON: either a sidecar next to the `.tox`, or a `manifest.json` in the operator folder.

The manifest sections are:

- `OpInfo`: operator identity and menu metadata. This includes `op_type`, `op_name`, `op_label`, `op_version`, `op_group`, `summary`, `doc_url`, `op_color`, `isFilter`, `compatible_types`, `search_words`, and `pop_menu`.
- `ParRetain`: parameter rules for stub and update operations.
- `StateRetain`: extension storage, raw storage, and DAT content to preserve during stub and update operations.
- `Shortcuts`: keyboard shortcut mappings.

`OpInfo.op_type` is the canonical operator identity used for lookup, placement, stubs, and updates. Labels, filenames, and node names can change; the type is what lets TDFam keep finding the same operator.

See the [Manifest Reference](docs/manifest-reference.md) for the full field list, JSON formats, retain rule syntax, and external manifest lookup order.

## Sources and Menu Metadata

A family can use embedded operators, file-based operators, or both. Embedded operators are COMPs inside the configured `Opcomp` / `custom_operators` container. File-based operators are `.tox` files in the configured `Opfolder`.

Embedded master COMPs may carry a trailing number in their name (e.g. `feedbackGen1`) without affecting the resolved `op_type`. When multiple masters resolve to the same type, TDFam picks the one with the highest `op_version` in its `OpInfo`; if versions are equal or absent, the highest trailing number wins. This lets you keep multiple iterations of a master COMP side by side and control which one is active through `op_version` or naming.

For file-based libraries, TDFam parses versions from filenames using the configured naming convention. It can also read sidecar JSON and folder manifests. If the same operator is available from more than one source, version resolution decides which one is used; ties go to the embedded operator.

Menu metadata can come from manifests and from family-level data:

- `OpInfo` controls per-operator identity, labels, groups, summaries, docs, colors, compatibility, search words, and operator pop-menu entries.
- `family_info` controls family summary, documentation fallback, support URL, and family-wide pop-menu entries.
- Config tables provide family-level defaults and bulk controls for grouping, sorting, label replacement, and OS compatibility.

## Placement, Stubs, Updates

When a family is installed, TDFam adds the custom entries to TD's OP Create dialog. When a user places an operator, TDFam prepares the clone, validates or creates manifest data, applies color and shortcuts, and runs callbacks.

Placed operators can later be converted into stubs. A stub is a lightweight placeholder that keeps the network shape without carrying the full operator implementation. This is useful for sending projects or networks around without distributing the private `.tox` files or paid components themselves.

Stubs preserve network position, size, wiring, cooking/bypass state, parameters covered by `ParRetain`, and state covered by `StateRetain`. Replacing a stub loads the full operator again from the installed family source.

When a manifest is validated during placement or update, TDFam checks whether the master COMP has a `Version` parameter. If it does and its value is higher than the `op_version` already recorded in `OpInfo`, the manifest is updated to the new version. This keeps manifest versions in sync with the master COMP version without requiring a manual manifest edit.

Updates follow a similar path: TDFam finds the matching source operator, loads the newer version, restores retained parameter and state data, reapplies menu/network metadata, reconnects the operator, and runs the matching callbacks.

## Quick Start

1. Add the TDFam `.tox` to your TouchDesigner project.
2. Set the family name and color.
3. Point `Opcomp` at embedded operator COMPs, or point `Opfolder` at a folder of `.tox` files.
4. Add or validate manifests for operators that need explicit identity, version, menu, shortcut, or retain behavior.
5. Toggle `Install` to put the family in the TAB menu.

For deeper integration, pulse `Createcallbacks` to generate a callbacks DAT, define `ParRetain` and `StateRetain` for update-safe operators, and use JSON import/export when family configuration should live under version control.

## Documentation

- [Concepts](docs/concepts.md): family component, sources, tags, stubs, config sync, and lifecycle.
- [Manifest Reference](docs/manifest-reference.md): `family_info`, `OpInfo`, `ParRetain`, `StateRetain`, `Shortcuts`, pop menus, and external manifests.
- [Callbacks & API](docs/callbacks-and-api.md): public TDFam methods, callbacks, and lifecycle hooks.
- [Config Reference](docs/config-reference.md): config tables, manifest-driven menu fields, family parameters, and JSON import/export.
- [Licensing and Attribution](docs/licensing.md): Apache-2.0 terms, NOTICE handling, and attribution guidelines.

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
