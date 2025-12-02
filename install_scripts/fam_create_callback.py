# me - this DAT
# scriptOp - the OP which is cooking
# FAM CREATE CALLBACK CUSTOM
# press 'Setup Parameters' in the OP to call this function to re-create the parameters.
import platform
import re

def onSetupParameters(scriptOp):
    return

def _parse_tox_info(filename):
    """Parse operator name and version from .tox filename."""
    match = re.match(r'(.+)_v(\d+\.\d+\.\d+)\.tox$', filename)
    if match:
        return (match.group(1), match.group(2))
    if filename.endswith('.tox'):
        return (filename[:-4], None)
    return (None, None)

# called whenever custom pulse parameter is pushed
def onPulse(par):
    return

def setup_table_dat(dat_name):
    """Create or get a Table DAT."""
    table_dat = parent(2).op(dat_name)
    if table_dat is None:
        table_dat = parent(2).create(tableDAT, dat_name)
    return table_dat

def onCook(scriptOp):
    # DEBUG - track what's happening
    debug("=== fam_create_callback onCook ===")
    debug(f"parent() = {parent()}")
    debug(f"parent().path = {parent().path}")
    debug(f"parent(2) = {parent(2)}")
    debug(f"parent(2).path = {parent(2).path}")

    # Get family name from installer extension attribute (promoted tdu.Dependency)
    # Try parent(1) first (new structure: extension on install_scripts)
    # Fall back to parent(2) (old structure: extension on grandparent)
    installer_comp = parent()
    debug(f"installer_comp = {installer_comp}")
    fam_name = None

    # Try to get FamilyName from parent(1) first
    try:
        fam_dep = installer_comp.FamilyName
        if hasattr(fam_dep, 'val'):
            fam_name = fam_dep.val
        else:
            fam_name = fam_dep
    except AttributeError:
        pass
    except Exception as e:
        # Catches "Cannot use an extension during its initialization"
        # This happens when OP_fam cooks during __init__ - just skip, will recook later
        pass

    debug(f"fam_name = {fam_name}")
    if not fam_name:
        debug("fam_name is None/empty - returning early")
        return
    scriptOp.clear()
    scriptOp.appendRow(['name','label','type','subtype','mininputs','maxinputs','ordering','level','lictype','os','score','family','opType'])
    
    relabel_table = setup_table_dat('relabel_index')
    replace_table = setup_table_dat('replace_index')
    os_table = setup_table_dat('os_incompatible')
    group_table = setup_table_dat('group_mapping')
    
    # Create a dictionary to map operators to groups
    group_index = {}
    for col in range(group_table.numCols):
        group_name = group_table[0, col].val
        for row in range(1, group_table.numRows):
            operator_name = group_table[row, col].val
            if operator_name:
                normalized_name = operator_name.lower().replace(' ', '_')
                group_index[normalized_name] = group_name
    
    # Define os_values and exclude_values
    os_values = {}
    exclude_values = {}
    for row in os_table.rows()[1:]:
        if row[0].val:
            op_name = str(row[0].val).lower().replace(' ', '_')
            os_values[op_name] = str(row[1].val) if len(row) > 1 else '1'
            exclude_values[op_name] = str(row[3].val) if len(row) > 3 else '0'

    label_index = {}
    for row in relabel_table.rows():
        if row[0].val and str(row[0].val).isdigit():
            label_index[int(row[0].val)] = row[1].val
    replace_index = {row[0].val: row[1].val for row in replace_table.rows() if row[0].val}

    # Get embedded operators from Opcomp parameter
    parent_comp = installer_comp.parent()
    debug(f"parent_comp = {parent_comp}")

    # Use Opcomp parameter if available
    custom_operators_base = None
    if hasattr(installer_comp.par, 'Opcomp'):
        custom_operators_base = installer_comp.par.Opcomp.eval()
        debug(f"installer_comp.par.Opcomp = {custom_operators_base}")

    if custom_operators_base:
        debug(f"custom_operators_base.path = {custom_operators_base.path}")
        embedded_ops = custom_operators_base.findChildren(tags=[fam_name], maxDepth=1)
        debug(f"Found {len(embedded_ops)} embedded ops with tag '{fam_name}'")
        for op_item in embedded_ops:
            debug(f"  - {op_item.name} tags={op_item.tags}")
        embedded_names = {o.name.lower() for o in embedded_ops}
    else:
        debug("custom_operators_base is None!")
        embedded_ops = []
        embedded_names = set()

    # Get folder-based operators (from cache)
    folder_ops = []

    # Get settings from settings table (in parent_comp / example_ops level)
    settings = parent_comp.op('settings')
    if not settings:
        settings = installer_comp.op('settings')
    ungrouped_label = settings['ungrouped_label', 1].val if settings and settings.row('ungrouped_label') else 'Other'
    exclude_behavior = settings['exclude_behavior', 1].val if settings and settings.row('exclude_behavior') else 'hide'
    show_ungrouped = settings['show_ungrouped', 1].val if settings and settings.row('show_ungrouped') else '1'

    # Read from FolderCache dependency - accessing .val creates cook dependency
    # When FolderCache changes, this scriptDAT will recook
    if hasattr(installer_comp, 'FolderCache'):
        folder_cache = installer_comp.FolderCache.val
        if folder_cache:
            for name, info in folder_cache.items():
                if name.lower() not in embedded_names:
                    folder_ops.append(type('FolderOp', (), {
                        'name': name,
                        'inputConnectors': [],
                        'path': info['path'],
                        'folder_category': info.get('category')  # None for ungrouped
                    })())

    # Combine and sort
    ops = list(embedded_ops) + folder_ops
    debug(f"Total ops (embedded + folder): {len(ops)}")
    ops = sorted(ops, key=lambda o: (group_index.get(o.name.lower(), 'ZZZ'), o.name))

    generators_comp = custom_operators_base.op('generators') if custom_operators_base else None
    generators = generators_comp.enclosedOPs if generators_comp else []
    types = [f'layouts/{fam_name}/defFilter', f'layouts/{fam_name}/defGenerator']
    
    current_group = None
    for i, o in enumerate(ops):
        # Skip operators with parentshortcut == 'Annotate' (only for embedded ops)
        if hasattr(o, 'par') and hasattr(o.par, 'parentshortcut') and o.par.parentshortcut.eval() == 'Annotate':
            continue

        op_name = o.name.lower()
        normalized_name = op_name.replace(' ', '_')

        # Check exclude flag - skip if exclude_behavior is 'hide'
        is_excluded = exclude_values.get(normalized_name, '0') == '1'
        if is_excluded and exclude_behavior == 'hide':
            continue

        # Get group from table first (table takes precedence)
        op_group = group_index.get(op_name)

        # If not in table, check for folder_category (folder-based ops)
        if op_group is None and hasattr(o, 'folder_category'):
            if o.folder_category:
                op_group = o.folder_category
            else:
                op_group = ungrouped_label

        # Check show_ungrouped setting
        if op_group is None:
            if show_ungrouped != '1':
                continue  # Skip ungrouped operators
            op_group = ungrouped_label
        if op_group != current_group:
            current_group = op_group
            # Add group header (skip if empty)
            if current_group:
                scriptOp.appendRow(['', current_group, f'layouts/{fam_name}/defLabel'])
            
        name = o.name
        normalized_name = name.lower().replace(' ', '_')
        os_compat = os_values.get(normalized_name, '1')

        if i in label_index:
            label = label_index[i]
        else:
            label = ' '.join(word.capitalize() for word in name.split('_'))
            for old, new in replace_index.items():
                label = label.replace(old, new)
        
        node_type = types[o in generators]
        subtype = '2'
        mininputs = '0'
        maxinputs = 9999 if o.name == 'composite' else len(o.inputConnectors)
        ordering = True
        level = '1'
        lictype = 'TouchDesigner Non-Commercial'
        score = '3'
        family = fam_name
        opType = name + fam_name
        scriptOp.appendRow([name, label, node_type, subtype, mininputs, maxinputs, ordering, level, lictype, os_compat, score, family, opType])
    
    return