# me - this DAT
# scriptOp - the OP which is cooking
# FAM CREATE CALLBACK
# Builds the operator family menu from Config DependDict and Properties

def onSetupParameters(scriptOp):
    return

def onPulse(par):
    return

def onCook(scriptOp):
    # Get installer and check if ready
    installer_comp = parent()

    try:
        fam_name = installer_comp.Properties['family_name']
        config = installer_comp.Config
    except Exception:
        # Extension not ready yet (happens during __init__)
        return

    if not fam_name:
        return

    scriptOp.clear()
    scriptOp.appendRow(['name','label','type','subtype','mininputs','maxinputs','ordering','level','lictype','os','score','family','opType'])

    # Read from Config DependDict (source of truth)
    group_mapping = config.get('group_mapping', {})
    replace_index_data = config.get('replace_index', {})
    os_incompatible = config.get('os_incompatible', {})
    relabel_index_data = config.get('relabel_index', {})
    settings_data = config.get('settings', {})

    # Build group_index: operator_name -> group_name
    group_index = {}
    for group_name, operators in group_mapping.items():
        for op_name in operators:
            normalized_name = op_name.lower().replace(' ', '_')
            group_index[normalized_name] = group_name

    # Build os_values and exclude_values from os_incompatible
    os_values = {}
    exclude_values = {}
    for op_name, os_data in os_incompatible.items():
        normalized = op_name.lower().replace(' ', '_')
        os_values[normalized] = str(os_data.get('windows', 1))
        exclude_values[normalized] = str(os_data.get('exclude', 0))

    # Build label_index from relabel_index (index -> label)
    label_index = {}
    for idx_str, label in relabel_index_data.items():
        if idx_str.isdigit():
            label_index[int(idx_str)] = label

    # replace_index is already in correct format (find -> replace)
    replace_index = replace_index_data

    # Get embedded operators from Opcomp parameter
    custom_operators_base = None
    if hasattr(installer_comp.par, 'Opcomp'):
        custom_operators_base = installer_comp.par.Opcomp.eval()

    if custom_operators_base:
        embedded_ops = custom_operators_base.findChildren(tags=[fam_name], maxDepth=1)
        embedded_names = {o.name.lower() for o in embedded_ops}
    else:
        embedded_ops = []
        embedded_names = set()

    # Get folder-based operators (from cache)
    folder_ops = []

    # Get settings from Config DependDict
    ungrouped_label = settings_data.get('ungrouped_label', 'Other')
    exclude_behavior = settings_data.get('exclude_behavior', 'hide')
    show_ungrouped = settings_data.get('show_ungrouped', '1')

    # Read from Properties folder_cache - accessing creates cook dependency
    # When folder_cache changes, this scriptDAT will recook
    folder_cache = installer_comp.Properties['folder_cache']
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