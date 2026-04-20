# TDFam

Create custom operator families in TouchDesigner. Add your own operators to TD's TAB menu with grouping, versioning, stubs, and state preservation.

## Setup

1. Add the TDFam `.tox` to your project
2. Set `Family`, `Color`, and at least one operator source (`Opcomp` or `Opfolder`)
3. Toggle `Install` — your operators appear in the TAB menu

Optionally configure `group_mapping`, `label_replacements`, and `settings` tables for menu layout. Pulse `Createcallbacks` to generate a callbacks DAT for lifecycle hooks.

## Features

- Operators from embedded COMPs or external `.tox` folders with version parsing
- Grouping, sorting, and label overrides via config tables
- Stub system for lightweight project files with ParRetain and StateRetain
- Manifest-driven operator identity and versioning
- Callbacks at every lifecycle stage (placement, stub, update)
- JSON import/export for portable configuration

## Documentation

| Doc | Description |
|-----|-------------|
| [Concepts](docs/concepts.md) | Architecture and core concepts |
| [Manifest Reference](docs/manifest-reference.md) | OpInfo, ParRetain, StateRetain, Shortcuts |
| [Callbacks & API](docs/callbacks-and-api.md) | Public methods and lifecycle hooks |
| [Config Reference](docs/config-reference.md) | Config tables and JSON import/export |

## Requirements

- TouchDesigner 2023+

## License

MIT
