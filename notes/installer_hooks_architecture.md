# Installer Hooks Architecture

**Created:** 2025-11-29
**Status:** IMPLEMENTED ✅

---

## Overview

The hooks system allows wrapper classes (like `ChatInstallerEXT`, `POPXInstallerEXT`) to inject family-specific logic into the generic installer's lifecycle operations without modifying `GenericInstallerEXT` itself.

**Design Principle:** Wrapper defines hook methods → Generic installer calls them if they exist → Wrapper logic executes at the right time.

---

## Current Hooks (Already Working)

These hooks are called from `fam_panel_execute.py`, NOT from `GenericInstallerEXT`:

| Hook | Signature | Location | Purpose |
|------|-----------|----------|---------|
| `PlaceOp` | `(panelValue, name) → bool` | `fam_panel_execute.py:100-103` | Before placement. Return `False` to cancel. |
| `PostPlaceOp` | `(clone)` | `fam_panel_execute.py:175-176` | After placement complete. |

**Example in ChatInstallerEXT:**
```python
def PlaceOp(self, panelValue, name):
    if panelValue == 1:
        self._get_target_chattd().openParameters()
        return False  # Cancel placement, just opened params
    return True  # Continue with normal placement

def PostPlaceOp(self, clone):
    # Copy API settings to new operator
    if hasattr(clone.par, 'Model'):
        clone.par.Model.val = self._get_target_chattd().par.Model.val
```

---

## New Hooks to Implement

### Hook Helper Method

```python
def _call_hook(self, hook_name, *args):
    """
    Call a hook method if defined on this instance (or subclass).

    Args:
        hook_name: Name of the hook method to call
        *args: Arguments to pass to the hook

    Returns:
        Hook's return value, or None if hook doesn't exist
    """
    hook = getattr(self, hook_name, None)
    if hook and callable(hook):
        return hook(*args)
    return None
```

---

## Stub Lifecycle Hooks

### PreStub

**Called in:** `createStub()` at line 625 (before any processing)

**Signature:** `PreStub(comp) → bool | None`

**Purpose:**
- Inspect component before stubbing
- Return `False` to skip this component
- Return `True` or `None` to continue

**Use Cases:**
- Skip certain operator types from stubbing
- Log/track which operators are being stubbed
- Validate component state before stubbing

**Integration Point:**
```python
def createStub(self, comp):
    # NEW: Pre-hook check
    if self._call_hook('PreStub', comp) is False:
        print(f"createStub: Skipped {comp.path} by PreStub hook")
        return None

    name = comp.name
    # ... rest of existing code ...
```

---

### PostStub

**Called in:** `createStub()` at line 731 (after stub fully configured, before return)

**Signature:** `PostStub(stub, original_comp)`

**Purpose:**
- Modify stub after creation
- Store additional data on stub
- Log/track stub creation

**Use Cases:**
- Add family-specific storage to stub
- Preserve additional state beyond standard params
- Trigger external systems on stub creation

**Integration Point:**
```python
def createStub(self, comp):
    # ... existing stub creation code ...

    copy.store('params', params)

    # NEW: Post-hook
    self._call_hook('PostStub', copy, comp)

    return copy
```

---

## Replace Lifecycle Hooks

### PreReplace

**Called in:** `ReplacestubFor()` at line 1117 (after validation, before master lookup)

**Signature:** `PreReplace(stub) → bool | None`

**Purpose:**
- Inspect stub before replacement
- Return `False` to skip this stub
- Modify stub data before replacement

**Use Cases:**
- Skip stubs that shouldn't be replaced yet
- Validate stub state
- Pre-process stub storage data

**Integration Point:**
```python
def ReplacestubFor(self, stub_path):
    stub = op(stub_path)
    # ... validation code ...

    try:
        ui.undo.startBlock(f'Replace Stub {stub.name}')

        # NEW: Pre-hook check
        if self._call_hook('PreReplace', stub) is False:
            ui.undo.endBlock()
            return None

        # Get operator type
        op_type = stub.fetch('op_type', None)
        # ... rest of code ...
```

---

### PostReplace

**Called in:** `ReplacestubFor()` at line 1226 (after connections restored, before stub destroyed)

**Signature:** `PostReplace(new_comp, stub)`

**Purpose:**
- Modify new component after replacement
- Transfer additional state from stub
- Trigger external systems

**Use Cases:**
- Restore family-specific storage from stub
- Apply additional configuration
- Re-initialize operator-specific systems

**Integration Point:**
```python
def ReplacestubFor(self, stub_path):
    # ... replacement code ...

    # Restore cooking and bypass state
    new_comp.allowCooking = stub.fetch('cooking', 1)
    new_comp.bypass = stub.fetch('bypass')

    # NEW: Post-hook (before stub destroy)
    self._call_hook('PostReplace', new_comp, stub)

    # Remove the stub
    stub.destroy()

    ui.undo.endBlock()
    return new_comp
```

---

## Update Lifecycle Hooks

### PreUpdate

**Called in:** `update_comp()` at line 1617 (after master found, before copy)

**Signature:** `PreUpdate(old_comp, master_comp) → bool | None`

**Purpose:**
- Inspect component before update
- Return `False` to skip this component
- Access both old and new master for comparison

**Use Cases:**
- Skip operators that shouldn't be updated
- Version comparison logic
- Pre-update validation

**Integration Point:**
```python
def update_comp(self, old_comp):
    operators_folder = self.ownerComp.op('custom_operators')
    if not operators_folder:
        return (False, "custom_operators folder not found")

    master_comp, match_method = self.find_matching_master_op(old_comp, operators_folder)
    if not master_comp:
        return (False, f"No matching master for {old_comp.path}")

    # NEW: Pre-hook check
    if self._call_hook('PreUpdate', old_comp, master_comp) is False:
        return (False, f"Update cancelled by PreUpdate hook for {old_comp.path}")

    try:
        new_comp = old_comp.parent().copy(master_comp)
        # ... rest of code ...
```

---

### PostUpdate

**Called in:** `update_comp()` after old destroyed, before return

**Signature:** `PostUpdate(new_comp)`

**Purpose:**
- Modify new component after update complete
- Trigger external systems
- Re-initialize operator systems

**Note:** Old params are NOT passed because they're already copied to new_comp. Just read from `new_comp.par.Whatever`. Use `PreserveSpecialParams` hook (called BEFORE destroy) if you need access to old_comp directly.

**Use Cases:**
- Re-initialize operator systems
- Apply post-update configuration
- Trigger external notifications

**Integration Point:**
```python
def update_comp(self, old_comp):
    # ... update code, params copied to new_comp ...

    old_comp.destroy()
    new_comp.name = old_name

    # Post-hook - old params already on new_comp
    self._call_hook('PostUpdate', new_comp)

    return (True, f"Successfully updated {new_comp.path}")
```

---

## Special Parameter Preservation Hook

### PreserveSpecialParams

**Called in:** `update_comp()` and `ReplacestubFor()` after standard parameter copy

**Signature:** `PreserveSpecialParams(new_comp, source)`

Where `source` is:
- `old_comp` (OP) for updates
- `params_dict` (dict) for stub replacement

**Purpose:**
- Handle family-specific parameters that need special copy logic
- Preserve ramp parameters, sequence parameters, etc.
- Handle parameters that the generic copy misses

**Use Cases (miniuv POPX):**
- Instancer Distribution parameters
- Ramp TOP parameters
- Custom sequence block preservation

**Integration Point:**
```python
# In update_comp(), after standard param copy loop:
for p in new_comp.pars():
    # ... existing copy logic ...

# NEW: Special param preservation hook
self._call_hook('PreserveSpecialParams', new_comp, old_comp)

# Restore connections...
```

---

## Batch Operation Filtering

### GetExcludedTags

**Called in:** `Createstubs()`, `Replacestubs()`, `Updateall()` when building operator list

**Signature:** `GetExcludedTags() → set | None`

**Purpose:**
- Return set of tags to exclude from batch operations
- Allows family-specific filtering without modifying generic code

**Use Cases (miniuv POPX):**
- Exclude `{"Falloff", "Generator", "Modifier", "Tool", "Simulation"}`
- Different exclusions for different batch operations

**Integration Point:**
```python
def Createstubs(self):
    # Get excluded tags from wrapper
    excluded_tags = self._call_hook('GetExcludedTags') or set()

    # Find all operators, excluding those with excluded tags
    familyOps = op('/').findChildren(type=COMP, key=lambda o: (
        self.family_name in o.tags and
        not any(tag in o.tags for tag in excluded_tags) and  # NEW
        not hasattr(o.parent, self.family_name) and
        # ... rest of conditions ...
    ))
```

---

## File-Based Operator Support Fix

### Problem

`ReplacestubFor()`, `Replacestubs()`, and `update_comp()` only check embedded `custom_operators`:

```python
# Current (broken for file-based):
operators_folder = self.ownerComp.op('custom_operators')
master_ops = operators_folder.findChildren(name=op_type, maxDepth=1)
```

### Solution

Use `Getoperatorsource()` which already handles both embedded and file-based:

```python
def _get_master_for_type(self, op_type, target_parent):
    """
    Get master operator for a type, checking both embedded and external folder.

    Returns:
        OP: The master operator (loaded into target_parent if file-based)
        None: If not found
    """
    source_result = self.Getoperatorsource(op_type)

    if source_result is None:
        return None

    if source_result[0] == 'embedded':
        return source_result[1]

    if source_result[0] == 'file':
        # Load from external .tox file
        try:
            loaded = target_parent.loadTox(source_result[1])
            return loaded
        except Exception as e:
            print(f"Error loading master from file {source_result[1]}: {e}")
            return None

    return None
```

---

## Complete Hook Summary

| Hook | When Called | Can Cancel | Arguments |
|------|-------------|------------|-----------|
| `PlaceOp` | Before op placement | Yes (return False) | `(panelValue, name)` |
| `PostPlaceOp` | After op placement | No | `(clone)` |
| `PreStub` | Before stub creation | Yes (return False) | `(comp)` |
| `PostStub` | After stub creation | No | `(stub, original_comp)` |
| `PreReplace` | Before stub replacement | Yes (return False) | `(stub)` |
| `PostReplace` | After stub replacement | No | `(new_comp, stub)` |
| `PreUpdate` | Before update | Yes (return False) | `(old_comp, master_comp)` |
| `PostUpdate` | After update | No | `(new_comp)` |
| `PreserveSpecialParams` | During param copy | No | `(new_comp, source)` |
| `GetExcludedTags` | Before batch ops | N/A | `()` → `set` (filter which ops to process) |
| `GetCategoryTags` | During type detection | N/A | `()` → `set` (category tags to exclude when finding op type) |

---

## Important Distinction: Two Types of Tag Filtering

### 1. `GetCategoryTags()` - For Operator Type Detection
When finding an operator's TYPE (e.g., "color_modifier"), we need to skip category tags.

**Example from miniuv's POPX:**
An operator has tags `["Color Modifier", "Modifier", "POPX"]`
- "Modifier" and "POPX" are CATEGORY tags
- "Color Modifier" is the OPERATOR TYPE tag

```python
def GetCategoryTags(self):
    # Tags that are category/family tags, NOT operator type tags
    return {"Falloff", "Generator", "Modifier", "Tool", "Simulation", "POPX"}
```

Used in: `createStub()`, `find_matching_master_op()`, `Createstubs()` type detection

### 2. `GetExcludedTags()` - For Batch Operation Filtering
Filter which operators to include in batch operations like `Createstubs()`, `Updateall()`.

```python
def GetExcludedTags(self):
    # Operators with these tags should NOT be included in batch operations
    return {"DoNotProcess", "Locked"}
```

Used in: `Createstubs()`, `Updateall()`, `Replacestubs()` operator filtering

---

## Example Wrapper Implementation

```python
class POPXInstallerEXT(GenericInstallerEXT):
    """POPX family installer with custom hooks."""

    def __init__(self, ownerComp):
        super().__init__(
            ownerComp=ownerComp,
            family_name='POPX',
            color=[0.8, 0.2, 0.4, 1],
            compatible_types=['CHOP', 'SOP'],
            operators_folder=ownerComp.par.Operatorsfolder.eval()
        )

    def GetExcludedTags(self):
        """Tags to exclude from batch operations."""
        return {"Falloff", "Generator", "Modifier", "Tool", "Simulation", "POPX"}

    def PreStub(self, comp):
        """Skip stubbing for simulation operators."""
        if 'Simulation' in comp.tags:
            print(f"Skipping stub for simulation op: {comp.path}")
            return False
        return True

    def PostStub(self, stub, original_comp):
        """Store additional POPX-specific data."""
        # Store instancer state
        if hasattr(original_comp, 'InstancerState'):
            stub.store('instancer_state', original_comp.InstancerState)

    def PostReplace(self, new_comp, stub):
        """Restore POPX-specific state from stub."""
        instancer_state = stub.fetch('instancer_state', None)
        if instancer_state and hasattr(new_comp, 'InstancerState'):
            new_comp.InstancerState = instancer_state

    def PreserveSpecialParams(self, new_comp, old_comp):
        """Handle Instancer Distribution and ramp parameters."""
        # Ramp TOP preservation
        if hasattr(old_comp.par, 'Rampdat') and hasattr(new_comp.par, 'Rampdat'):
            # Copy ramp data
            old_ramp = old_comp.par.Rampdat.eval()
            if old_ramp:
                new_comp.par.Rampdat = old_ramp

        # Instancer Distribution preservation
        if 'Instancer' in old_comp.tags:
            for par_name in ['Distributionmode', 'Instancecount', 'Seed']:
                if hasattr(old_comp.par, par_name) and hasattr(new_comp.par, par_name):
                    new_comp.par[par_name].val = old_comp.par[par_name].val
```

---

## Implementation Order

1. Add `_call_hook()` helper method
2. Add hooks to `createStub()` (PreStub, PostStub)
3. Add hooks to `ReplacestubFor()` (PreReplace, PostReplace)
4. Add hooks to `update_comp()` (PreUpdate, PostUpdate, PreserveSpecialParams)
5. Add `GetExcludedTags` filtering to batch operations
6. Fix file-based operator support with `_get_master_for_type()`
7. Update batch methods to use new helper and hooks

---

## Testing Checklist

- [ ] PreStub returning False skips stubbing
- [ ] PostStub receives correct stub and original
- [ ] PreReplace returning False skips replacement
- [ ] PostReplace receives correct new_comp and stub
- [ ] PreUpdate returning False skips update
- [ ] PostUpdate receives correct new_comp and old params
- [ ] PreserveSpecialParams called with correct arguments
- [ ] GetExcludedTags filters batch operations
- [ ] File-based operators work with stub/replace/update
