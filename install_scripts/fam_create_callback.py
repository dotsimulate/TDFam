# me - this DAT
# scriptOp - the OP which is cooking
# FAM CREATE CALLBACK
# Builds the operator family menu from GetOperators() API + menu-specific formatting

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

    # Get all operator data from the API
    all_ops = installer_comp.GetOperators()
    if not all_ops:
        return

    # Menu-specific settings from Config
    settings_data = config.get('settings', {})
    ungrouped_label = settings_data.get('ungrouped_label', 'Other')
    exclude_behavior = settings_data.get('exclude_behavior', 'hide')
    show_ungrouped = settings_data.get('show_ungrouped', '1')

    # Generator detection for menu type column
    custom_operators_base = installer_comp.par.Opcomp.eval()
    generators_comp = custom_operators_base.op('generators') if custom_operators_base else None
    generators = generators_comp.enclosedOPs if generators_comp else []
    types = [f'layouts/{fam_name}/defFilter', f'layouts/{fam_name}/defGenerator']

    # Sort by group then name
    sorted_ops = sorted(all_ops.values(), key=lambda o: (o.get('group') or 'ZZZ', o['op_name']))

    has_groups = any(o.get('group') is not None for o in sorted_ops)

    current_group = None
    for op_data in sorted_ops:
        os_compat = op_data['os_compatible']

        # Check exclude flag
        is_excluded = os_compat.get('exclude', 0) == 1
        if is_excluded and exclude_behavior == 'hide':
            continue

        # Group handling (menu-specific)
        op_group = op_data.get('group')
        if has_groups and op_group is None:
            if show_ungrouped != '1':
                continue
            op_group = ungrouped_label

        if op_group != current_group:
            current_group = op_group
            if current_group:
                scriptOp.appendRow(['', current_group, f'layouts/{fam_name}/defLabel'])

        # Get the source OP ref for inputConnectors and generator check
        source_type, source_ref = op_data['source']
        if source_type == 'embedded':
            maxinputs = 9999 if source_ref.name == 'composite' else len(source_ref.inputConnectors)
            node_type = types[source_ref in generators]
        else:
            maxinputs = 0
            node_type = types[0]

        opType = op_data['op_type'] + fam_name
        scriptOp.appendRow([
            op_data['op_name'],
            op_data['op_label'],
            node_type,
            '2',            # subtype
            '0',            # mininputs
            maxinputs,
            True,           # ordering
            '1',            # level
            'TouchDesigner Non-Commercial',
            str(os_compat.get('windows', 1)),
            '3',            # score
            fam_name,
            opType
        ])

    return
