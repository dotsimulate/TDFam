# Installer Architecture Vision - Checkpoint

**Created:** 2025-11-29
**Context:** Analysis of installer patterns and requirements for custom operator families

---

## Core Ethos

The `GenericInstallerEXT` should be **completely generic and untouched** by op-family developers. All family-specific code belongs in a **wrapper class** (like `ChatInstallerEXT`).

---

## The Anti-Pattern (What NOT to do)

Hardcoding family-specific logic directly into the generic installer:

- **Hardcoded `excluded_tags`**: Family-specific category tags baked into the base class
- **Hardcoded compatibility**: Family-specific connection rules embedded in generic code
- **Hardcoded `preserve_special_params`**: Family-specific parameter handling in base class
- **Custom tag detection logic**: Family-specific naming conventions in generic code

This should all live in a wrapper class, not the generic installer.

---

## Target Architecture

```
┌─────────────────────────────────────────────────────────────┐
│               GenericInstallerEXT (installer.py)             │
│  ────────────────────────────────────────────────────────── │
│  • Zero family-specific code                                 │
│  • Config sources: Tables OR JSON (flexible)                 │
│  • Operator sources: embedded base OR external folder(s)     │
│  • Hooks API: Pre/Post for Place, Stub, Update, Replace      │
│  • Connection map, compatible_types via config               │
└─────────────────────────────────────────────────────────────┘
                              │
                    wraps/instantiates
                              │
                              ▼
┌─────────────────────────────────────────────────────────────┐
│         WrapperClass (YourFamilyInstallerEXT)                │
│  ────────────────────────────────────────────────────────── │
│  • Family-specific hooks: PostPlaceOp, PreStub, etc.         │
│  • Custom tag handling (excluded_tags, naming conventions)   │
│  • Special param preservation (Instancer, ramps)             │
│  • Venv management, dependencies                             │
│  • ALL family-specific code lives here                       │
└─────────────────────────────────────────────────────────────┘
```

---

## Key Features to Implement

### 1. File-Based Distribution (Priority)

**Current:** All operators live in `custom_operators` base COMP (disabled) inside the installer

**Target:** Support external folder(s) as operator sources:
- Patch updates: "download this .tox, drop in folder"
- Personal op families without heavy installer .tox files
- Auto-update systems can push individual operators
- Git-friendly versioning (operators as discrete files)
- Option to still use embedded `custom_operators` as fallback/default

**Implementation ideas:**
- `Operatorsfolder` parameter pointing to external path
- Priority system: external folder > embedded base
- Version comparison (if external is newer, use it)
- Lazy loading from disk when operator is placed

### 2. Flexible Configuration

**Current:** Tables define things like compatible types, colors, etc.

**Target:** Support both tables AND JSON config:
- JSON for text-based, git-friendly config
- Tables still work for TD-native approach
- Config can define: family name, color, compatible_types, connection_map, excluded_tags, etc.

### 3. Hooks API Expansion

**Current hooks (in ChatInstallerEXT):**
- `PlaceOp(panelValue, name)` - before placing
- `PostPlaceOp(clone)` - after placing

**Target hooks to add:**
- `PreStub(comp)` / `PostStub(stub)` - stub lifecycle
- `PreUpdate(old_comp)` / `PostUpdate(new_comp)` - update lifecycle
- `PreReplace(stub)` / `PostReplace(new_comp)` - replace lifecycle
- `GetExcludedTags()` - return family-specific excluded tags
- `PreserveSpecialParams(new_comp, old_comp)` - family-specific param preservation

### 4. Favorites Family Concept (Dan's idea)

A special family that's just frequently used ops from any family - like a palette

---

## Conversations Reference

### Key Requirements:
- External folder support for operator distribution
- Stub restoration with connections and sequence params preserved
- Per-operator hooks for custom stub/update behavior
- Favorites family concept - user's personal collection of tools
- Clean separation between generic installer and family-specific code

---

## Technical Notes

### custom_operators in TD
- It's a **disabled base COMP** in TouchDesigner, not a folder
- Represented as folder in this workspace only for dev purposes
- Contains master operators that get copied when user places an op

### Current Operator Source Flow
1. User triggers op placement from menu
2. `fam_script_callbacks` handles the placement
3. Copies operator from `custom_operators` base inside installer
4. Runs `PostPlaceOp` hook if defined in wrapper

### File-Based Flow (Target)
1. User triggers op placement from menu
2. Check external folder first (if configured)
3. If found and version >= embedded, load from file
4. Else fall back to embedded `custom_operators`
5. Run hooks as normal

---

---

## Technical Findings

### TouchDesigner Methods for Loading .tox from File

**Primary method: `COMP.loadTox()`**
```python
loadTox(filepath, unwired=False, pattern=None, password=None) → OP
```
- Load the component from the given file path into this component
- `filepath` - The path and filename of the .tox to load
- `unwired` - If True, component inputs remain unwired
- `pattern` - Only load operators matching pattern (no wildcards)
- `password` - Decrypt encrypted tox

**Alternative: `COMP.reload()`**
```python
reload(filepath, password=None) → None
```
- Reloads the component from the given file path
- Replaces children, top level parameters, update flags, node width/height, storage, comments, inputs
- Keeps original node x,y position

**External .tox parameters (built-in to all COMPs):**
- `externaltox` - Path to external .tox file
- `enableexternaltox` - Toggle to enable loading from external
- `enableexternaltoxpulse` - Pulse to re-load from external

### UI Injection During Install() - What Gets Modified in /ui/dialogs/menu_op

The `Install()` method in `installer.py` (lines 155-400) performs extensive modifications to TouchDesigner's native UI to integrate the custom family. This is critical to understand.

```
┌─────────────────────────────────────────────────────────────────────────┐
│                    UI INJECTION FLOW (installer.py Install())            │
└─────────────────────────────────────────────────────────────────────────┘

/ui/dialogs/bookmark_bar/
    └── {family}_toggle                    [CREATED - lines 166-186]
        └── Copies install_scripts/fam_toggle
        └── On/off toggle button in top bar
        └── Binds to op.{family}.par.Install

/ui/dialogs/menu_op/
    ├── {family}_insert                    [CREATED - insertDAT, lines 189-206]
    │   └── Inserts family name into families list
    │   └── Wires into chain: insert1 → {family}_insert → [next]
    │
    ├── colors                             [MODIFIED - lines 205-221]
    │   └── Appends row: ['{family}', r, g, b, a]
    │   └── Family color for menu highlighting
    │
    ├── set_last_node_type                 [CREATED - lines 223-261]
    │   └── Copies install_scripts/set_last_node_type
    │   └── Script that detects if clicked node has family tag
    │   └── Sets $lasttype variable for menu routing
    │
    ├── launch_menu_op                     [MODIFIED - lines 262-270]
    │   └── Injects: "cvar menu_type=$type\n\trun set_last_node_type\n\tset type = $lasttype"
    │   └── Makes TD run set_last_node_type before showing menu
    │
    ├── create_node                        [MODIFIED - lines 305-320]
    │   └── Injects: "if($type=='{family}')\n\texit\nendif"
    │   └── Prevents TD from trying to create native ops for custom family
    │
    ├── search/panelexec1                  [MODIFIED - lines 318-336]
    │   └── Injects ENTER key handler for this family
    │   └── Uses unique_id = -abs(hash(family_name) % 10000)
    │
    ├── {family}_panel_execute             [CREATED - lines 334-350]
    │   └── Copies install_scripts/fam_panel_execute
    │   └── Replaces 'OPNAME' with family name
    │   └── THE KEY: Actually places operators when clicked
    │
    ├── compatible                         [MODIFIED - lines 348-398]
    │   └── Appends row and column for family
    │   └── Defines wire compatibility matrix (what connects to what)
    │
    └── nodetable/
        ├── inject_{family}_fam            [CREATED - scriptDAT, lines 278-294]
        │   └── Copies nodetable/families op
        │   └── Sets callbacks to install_scripts/fam_script_callbacks
        │   └── Wires: [input] → inject_{family}_fam → families
        │   └── Intercepts menu data flow, substitutes custom operators
        │
        └── eval4                          [MODIFIED - lines 295-308]
            └── Appends family to expression:
            └── "[x for x in families.keys()] + ['{family}']"
            └── Adds family to menu tabs
```

### Why This Matters for File-Based Loading

**What STAYS THE SAME:**
- All UI injection (toggle, menu integration, compatible table, etc.)
- The install_scripts files themselves
- How operators appear in the menu
- Wire compatibility logic

**What CHANGES:**
- Where `fam_panel_execute.py` gets the master operator from (line 105)
- Where `fam_create_callback.py` scans for available operators (line 46)
- Potentially: version comparison logic, external folder parameter

The UI integration is **decoupled** from the operator source - this is good architecture.

---

### Current install_scripts Flow

```
┌─────────────────────────────────────────────────────────────────────────┐
│                         OPERATOR PLACEMENT FLOW                          │
└─────────────────────────────────────────────────────────────────────────┘

1. fam_create_callback.py
   └── Builds OP_fam table from custom_operators base
       └── ops = op('../custom_operators').findChildren(tags=[fam_name], maxDepth=1)
       └── Uses config tables: relabel_index, replace_index, os_incompatible, group_mapping

2. fam_script_callbacks.py
   └── Populates the op menu from OP_fam table
       └── familyOps = parent(2).op('OP_fam')
       └── Handles search, filtering, grouping, OS compatibility

3. fam_panel_execute.py (THE KEY FILE)
   └── Actually places the operator when user clicks
       └── Line 100-103: Calls PlaceOp hook if exists (can cancel placement)
       └── Line 105: master = op.OPNAME.op('custom_operators').findChildren(name=lookup_name, maxDepth=1)[0]
       └── Line 106: clone = op.OPNAME.copy(master, name=normalized_name+'1')
       └── Line 124: ui.panes.current.placeOPs([clone], inputIndex=0, outputIndex=0)
       └── Line 126-127: Calls PostPlaceOp hook if exists
```

### Current Config Tables (in installer)

| Table | Purpose |
|-------|---------|
| `relabel_index` | Map operator index to custom label |
| `replace_index` | String replacements for auto-generated labels |
| `os_incompatible` | OS compatibility flags (Windows/Mac) |
| `group_mapping` | Operator → Group assignments for menu organization |
| `OP_fam` | Generated table of all operators (built by fam_create_callback) |

### File-Based Implementation Strategy

#### Operator Source Resolution Logic

**Simple, efficient rules:**

```
┌─────────────────────────────────────────────────────────────────────────┐
│                    OPERATOR SOURCE RESOLUTION                            │
└─────────────────────────────────────────────────────────────────────────┘

1. Match in BOTH embedded & folder, external has NO version in filename
   → Use EMBEDDED (authoritative, no patch versioning)

2. Match in BOTH embedded & folder, external HAS version in filename
   → VERSION COMPARE: higher wins, tie goes to embedded

3. Only in EMBEDDED (no folder match)
   → Use EMBEDDED

4. Only in FOLDER (no embedded match)
   → Use FOLDER (FAV family style, custom additions)
```

**Why this works:**
- Unversioned .tox in folder = user testing or FAV family → embedded is safer/authoritative
- Versioned .tox in folder = intentional patch → do proper comparison
- No embedded match = pure folder mode (FAV family, personal ops)
- No nested loops, O(n + m) complexity

#### Folder Location Configuration

The external folder path is set in the **wrapper class** (not generic installer):

```python
# In ChatInstallerEXT (wrapper class)
class ChatInstallerEXT(DotChatUtil):
    def __init__(self, ownerComp):
        # ... existing init ...

        # Set operators folder for file-based loading
        # Could be from parameter, config, or hardcoded path
        self.operators_folder = self.get_operators_folder_path()

    def get_operators_folder_path(self):
        """Return path to external operators folder, or None for embedded-only"""
        # Option 1: From parameter
        if self.ownerComp.par.Operatorsfolder.eval():
            return self.ownerComp.par.Operatorsfolder.eval()

        # Option 2: Convention-based (next to installer)
        # return f"{project.folder}/LOP_operators"

        # Option 3: AppData location
        # return f"{app.userPaletteFolder}/LOPs/operators"

        return None  # Embedded-only mode
```

#### External Folder Structure

**Filename convention:**
```
operators/
  agent.tox              ← No version, will lose to embedded if match exists
  agent_v1.2.3.tox       ← Versioned, will compare against embedded par.Version
  my_custom_op.tox       ← No embedded match, just loads from folder
  chat_v2.0.0.tox        ← Versioned patch
```

**Version parsing (regex):**
```python
import re

def parse_tox_info(filename):
    """Parse operator name and version from .tox filename"""
    # Pattern: name_vX.Y.Z.tox or name.tox
    match = re.match(r'(.+)_v(\d+\.\d+\.\d+)\.tox$', filename)
    if match:
        return (match.group(1), match.group(2))  # (name, version)

    # No version in filename
    if filename.endswith('.tox'):
        return (filename[:-4], None)  # (name, None)

    return None

# Examples:
# "agent_v1.2.3.tox" → ("agent", "1.2.3")
# "agent.tox"        → ("agent", None)
# "my_op_v0.1.0.tox" → ("my_op", "0.1.0")
```

#### Core Implementation

**Modify `fam_panel_execute.py` line 105-106:**

```python
# CURRENT:
master = op.OPNAME.op('custom_operators').findChildren(name=lookup_name, maxDepth=1)[0]
clone = op.OPNAME.copy(master, name=normalized_name+'1')

# FILE-BASED ALTERNATIVE:
import os
import re

def parse_version(ver_string):
    """Parse version string to tuple for comparison"""
    if not ver_string:
        return None
    try:
        return tuple(int(x) for x in ver_string.split('.'))
    except:
        return None

def get_operator_source(lookup_name):
    """Get operator from external folder or embedded custom_operators"""
    # Get folder path from wrapper class (if set)
    external_folder = getattr(op.OPNAME, 'operators_folder', None)

    # Find embedded operator
    embedded_ops = op.OPNAME.op('custom_operators').findChildren(name=lookup_name, maxDepth=1)
    embedded = embedded_ops[0] if embedded_ops else None

    # Find external .tox (check both versioned and unversioned filenames)
    external_path = None
    external_version = None

    if external_folder and os.path.isdir(external_folder):
        for f in os.listdir(external_folder):
            if not f.endswith('.tox'):
                continue
            name, version = parse_tox_info(f)
            if name == lookup_name:
                external_path = os.path.join(external_folder, f)
                external_version = version
                break  # Found match

    # Resolution logic
    if external_path and not embedded:
        # Only in folder → use folder
        return ('file', external_path)

    if embedded and not external_path:
        # Only in embedded → use embedded
        return ('embedded', embedded)

    if not embedded and not external_path:
        # Neither exists
        return None

    # Both exist - check versioning
    if external_version is None:
        # External has no version → embedded wins (authoritative)
        return ('embedded', embedded)

    # External has version - compare
    embedded_version = None
    if hasattr(embedded.par, 'Version'):
        embedded_version = parse_version(embedded.par.Version.eval())

    external_ver_tuple = parse_version(external_version)

    if embedded_version is None:
        # Embedded unversioned, external versioned → use external
        return ('file', external_path)

    # Both versioned - higher wins, tie goes to embedded
    if external_ver_tuple > embedded_version:
        return ('file', external_path)

    return ('embedded', embedded)


# Usage in placement:
source_type, source = get_operator_source(lookup_name)

if source_type == 'file':
    # Load from .tox file
    # NOTE: loadTox() loads as child and returns the loaded op directly
    target_parent = ui.panes.current.owner
    clone = target_parent.loadTox(source)
    clone.name = normalized_name + '1'
elif source_type == 'embedded':
    clone = op.OPNAME.copy(source, name=normalized_name+'1')
```

**For `fam_create_callback.py` - Scan both sources:**

```python
import os

def get_all_available_operators(fam_name):
    """Build combined list of operators from embedded + external folder"""

    # Scan embedded custom_operators
    embedded_base = op('../custom_operators')
    embedded_ops = {}
    if embedded_base:
        for o in embedded_base.findChildren(tags=[fam_name], maxDepth=1):
            embedded_ops[o.name] = o

    # Scan external folder
    external_folder = getattr(parent(2), 'operators_folder', None)
    external_ops = {}

    if external_folder and os.path.isdir(external_folder):
        for f in os.listdir(external_folder):
            if f.endswith('.tox'):
                name, version = parse_tox_info(f)
                external_ops[name] = {
                    'path': os.path.join(external_folder, f),
                    'version': version
                }

    # Merge - embedded keys + external-only keys
    all_op_names = set(embedded_ops.keys()) | set(external_ops.keys())

    # For menu building, we just need the names
    # The source resolution happens at placement time
    return sorted(all_op_names)
```

#### Use Cases Supported

| Use Case | Configuration | Behavior |
|----------|--------------|----------|
| **Standard LOPs** | `operators_folder` set, has embedded ops | Hybrid: embedded + versioned patches |
| **FAV Family** | `operators_folder` set, NO embedded ops | Pure folder mode, all ops from folder |
| **Legacy/Simple** | `operators_folder` = None | Embedded-only (current behavior) |
| **Patch Distribution** | User adds `agent_v1.2.3.tox` to folder | Version compared, higher wins |

---

### Caching Strategy & Refresh

#### The Problem
Scanning the external folder on every operator placement could be slow with many files. Need a caching strategy.

#### Solution: `dynamic_refresh` Toggle (IMPLEMENTED)

**CRITICAL DISCOVERY:** Regular Python attributes (like `_folder_cache = {}`) are NOT accessible from scriptDATs via `parent(2)._folder_cache`. Only `tdu.Dependency` objects are promoted to the COMP and accessible.

```python
class GenericInstallerEXT:
    def __init__(self, ownerComp, family_name, color,
                 compatible_types=None,
                 connection_map=None,
                 operators_folder=None,
                 dynamic_refresh=False,
                 install_location=None,  # NEW: configurable placement
                 node_x=0,
                 node_y=0,
                 expose=True):

        # ... existing init ...

        # Installer placement config (NEW - not hardcoded to root at 0,0)
        self.install_location = install_location if install_location else op('/')
        self.node_x = node_x
        self.node_y = node_y
        self.expose = expose

        self.operators_folder = operators_folder
        self.dynamic_refresh = dynamic_refresh

        # CRITICAL: Use tdu.Dependency, NOT regular dict!
        # Regular attributes are NOT accessible via parent(2).attribute from scriptDATs
        # Only tdu.Dependency objects are promoted to the COMP
        self.FolderCache = tdu.Dependency({})  # {name: {'path': str, 'version': str|None, 'category': str|None}}

        # Cache on init if not dynamic mode
        if operators_folder and not dynamic_refresh:
            self._refresh_folder_cache()

    def _refresh_folder_cache(self):
        """Scan folder and build cache. Also scans subfolders for categories."""
        new_cache = {}

        if not self.operators_folder or not os.path.isdir(self.operators_folder):
            self.FolderCache.val = new_cache
            return

        for item in os.listdir(self.operators_folder):
            item_path = os.path.join(self.operators_folder, item)

            if os.path.isdir(item_path):
                # Subfolder = category name
                category_name = item
                for f in os.listdir(item_path):
                    if f.endswith('.tox'):
                        name, version = self._parse_tox_info(f)
                        if name:
                            # CRITICAL: Store keys lowercase for case-insensitive matching
                            new_cache[name.lower()] = {
                                'path': os.path.join(item_path, f),
                                'version': version,
                                'category': category_name
                            }

            elif item.endswith('.tox'):
                # Loose file = no category (ungrouped)
                name, version = self._parse_tox_info(item)
                if name:
                    new_cache[name.lower()] = {
                        'path': os.path.join(self.operators_folder, item),
                        'version': version,
                        'category': None
                    }

        # Update the dependency - this triggers dependent scriptDATs to recook!
        self.FolderCache.val = new_cache
        print(f"{self.family_name}: Folder cache refreshed - {len(new_cache)} operators found")

    def Refreshfolder(self):
        """
        Pulse button / manual call to rescan external folder.
        Call this after adding/removing .tox files from folder.
        """
        self._refresh_folder_cache()

        # Regenerate OP_fam table to update menu
        op_fam = self.ownerComp.op('OP_fam')
        if op_fam:
            op_fam.cook(force=True)
```

**In fam_create_callback.py - reading the cache:**

```python
# Read from FolderCache dependency - accessing .val creates cook dependency
# When FolderCache changes, this scriptDAT will recook automatically!
if hasattr(installer_comp, 'FolderCache'):
    folder_cache = installer_comp.FolderCache.val
    if folder_cache:
        for name, info in folder_cache.items():
            if name.lower() not in embedded_names:
                folder_ops.append(type('FolderOp', (), {
                    'name': name,
                    'inputConnectors': [],
                    'path': info['path'],
                    'folder_category': info.get('category')  # For grouping
                })())
```

#### Usage Modes

| Mode | `dynamic_refresh` | Behavior | Use Case |
|------|-------------------|----------|----------|
| **Production** | `False` (default) | Cache on init, manual refresh | Distribution, end users |
| **Development** | `True` | Scan every placement | Testing, development |

#### Wrapper Class Passes the Flag

```python
# In ChatInstallerEXT (production)
self.installer = GenericInstallerEXT(
    ownerComp,
    family_name='LOP',
    color=[0.2, 0.6, 0.8, 1],
    operators_folder=self.get_operators_folder_path(),
    dynamic_refresh=False  # Production: use cache
)

# During development/testing
self.installer = GenericInstallerEXT(
    ...
    dynamic_refresh=True  # Dev: always fresh
)
```

#### FAV Family - Minimal Wrapper Example (IMPLEMENTED)

```python
class FavInstallerExt(GenericInstallerEXT):
    """
    Super lightweight wrapper for personal favorites family.
    Users collect their favorite .tox files in a folder.
    Uses INHERITANCE pattern (not instantiation).
    """
    def __init__(self, ownerComp):
        import os
        # Get folder path - only use if it actually exists on this machine
        operators_folder = ownerComp.par.Operatorsfolder.eval()

        if not operators_folder:
            print(f"FAV Install: Warning - No Operatorsfolder specified.")
        elif not os.path.isdir(operators_folder):
            print(f"FAV Install: Warning - Path does not exist: {operators_folder}")
            operators_folder = None  # Don't use stale path

        # Initialize via super() - uses inheritance, not delegation
        # FAV uses dynamic_refresh=True so folder is scanned on each placement
        super().__init__(
            ownerComp=ownerComp,
            family_name=ownerComp.par.Family.eval(),
            color=ownerComp.parGroup.Color.eval(),
            compatible_types=['COMP', 'TOP', 'CHOP', 'SOP', 'DAT', 'MAT'],
            operators_folder=operators_folder,
            dynamic_refresh=True,  # Scan fresh each placement
            install_location=ownerComp.parent(),  # Stay where it is
            node_x=ownerComp.nodeX,  # Preserve current position
            node_y=ownerComp.nodeY,
            expose=True
        )

    def Install(self):
        """Re-read params and call parent Install/Uninstall."""
        if self.ownerComp.par.Install:
            # Re-read from parameters in case they changed since init
            self.color = self.ownerComp.parGroup.Color.eval()
            self.operators_folder = self.ownerComp.par.Operatorsfolder.eval()
            super().Install()
        else:
            super().Uninstall()
```

**FAV Installer Parameters (minimal):**
| Parameter | Type | Purpose |
|-----------|------|---------|
| `Operatorsfolder` | File/Folder | Path to user's favorites folder |
| `Install` | Toggle | Enable/disable family |
| `Refreshfolder` | Pulse | Rescan folder after adding ops |

---

## Next Steps (ALL COMPLETED ✅)

1. ✅ Design config schema (JSON) that parallels current table-based config
2. ✅ Define hooks API contract for stub/update lifecycle
3. ✅ Prototype file-based loading in fam_panel_execute.py
4. ✅ Add `Operatorsfolder` parameter to installer
5. ✅ Update fam_create_callback to scan both sources
6. ✅ Implement `Refreshfolder` and caching logic
7. ✅ Create lightweight FAV family wrapper template

---

## Key Learnings / Gotchas

### 1. tdu.Dependency Required for ScriptDAT Access
Regular Python attributes on extension classes are NOT accessible from scriptDATs via `parent(2).attribute`. Only `tdu.Dependency` objects are promoted to the COMP. Use:
```python
self.FolderCache = tdu.Dependency({})  # NOT self._folder_cache = {}
```

### 2. Extensions Don't Reinit When Parameters Change
When user changes parameters after init, the extension instance keeps old values. Wrapper classes must re-read parameters in `Install()`:
```python
def Install(self):
    self.operators_folder = self.ownerComp.par.Operatorsfolder.eval()  # Re-read!
    super().Install()
```

### 3. Case-Insensitive Filename Matching
Filenames like `MyOp_v1.0.0.tox` must match lookups for `myop`. Store cache keys lowercase and compare lowercase:
```python
new_cache[name.lower()] = {...}  # Store lowercase
if name and name.lower() == lookup_name:  # Compare lowercase
```

### 4. Configurable Installer Placement
Installers shouldn't hardcode position at `op('/'), nodeX=0, nodeY=0`. Use constructor args:
```python
install_location=ownerComp.parent(),
node_x=ownerComp.nodeX,
node_y=ownerComp.nodeY,
expose=True
```
