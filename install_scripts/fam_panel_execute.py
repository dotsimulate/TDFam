# me - this DAT
# panelValue - the PanelValue object that changed
# prev - the previous value of the PanelValue object that changed
# Make sure the corresponding toggle is enabled in the Panel Execute DAT.
#
# This script is deployed to /ui/dialogs/menu_op/{family}_panel_execute
# Family name is derived dynamically from the script's own name.

import ctypes

def _get_family():
	"""Derive family name from this script's name."""
	return me.name.rsplit('_panel_execute', 1)[0]

def _get_installer():
	"""Get the installer component for this family.

	Uses inject script's callbacks parameter to find actual installer,
	since op.{family} may point to a parent component (Shortcutcomp mode).
	"""
	family = _get_family()
	# Use inject script's callbacks to find actual installer
	inject_script = parent.OPCREATE.op(f'nodetable/inject_{family}_fam')
	if inject_script:
		callbacks_dat = inject_script.par.callbacks.eval()
		if callbacks_dat:
			return callbacks_dat.parent()
	# Fallback to direct shortcut for backwards compatibility
	return getattr(op, family, None)

def onOffToOn(panelValue):
	return

def whileOn(panelValue):
	return

def onOnToOff(panelValue):
	return

def whileOff(panelValue):
	return

def onValueChange(panelValue, prev):
    family = _get_family()
    installer = _get_installer()

    if op('current')[0,0].val != family:
        return

    license = installer.op('License')
    if panelValue == -1:
        return

    # Use the inject script output (sorted/displayed table) instead of raw OP_fam
    # The inject script applies sorting from fam_script_callbacks.py
    inject_script = parent.OPCREATE.op(f'nodetable/inject_{family}_fam')
    if not inject_script:
        # Fallback to raw OP_fam if inject not found
        inject_script = installer.op('OP_fam')

    rows_per_column = parent.OPCREATE.op('nodetable').par.tablerows.eval()

    # Get the valid operator count for this group
    group_starts = []
    group_operators = []
    current_group = -1
    operator_count = 0

    for i in range(inject_script.numRows):
        if inject_script[i, 'type'].val.endswith('defLabel'):
            if current_group >= 0:
                group_operators.append(operator_count)
            group_starts.append(i)
            current_group += 1
            operator_count = 0
        elif inject_script[i, 'name'].val:
            operator_count += 1

    # Handle case where there are no group headers (empty ungrouped_label)
    if not group_starts:
        # No group headers - treat all operators as one flat list starting after header row
        group_starts = [0]  # Virtual start at row 0 (header row)
        group_operators = [operator_count]
        has_group_headers = False
    else:
        group_operators.append(operator_count)
        has_group_headers = True

    # Calculate total columns needed for each group
    columns_per_group = []
    for i, ops in enumerate(group_operators):
        # If has group headers and ops is exactly rows_per_column, need 2 columns for header
        # If no group headers, just calculate based on ops count
        if has_group_headers and ops == rows_per_column:
            cols = 2
        elif has_group_headers:
            cols = (ops + (rows_per_column - 1)) // rows_per_column
        else:
            # No headers - just divide ops by rows
            cols = (ops + rows_per_column - 1) // rows_per_column if ops > 0 else 1
        columns_per_group.append(cols)

    # Handle both regular clicks and ENTER key
    target_index = -1
    if panelValue == -8358:  # ENTER key
        destil = parent.OPCREATE.op('nodetable/destil')
        if destil.numRows > 1:
            selected_name = destil[1,0].val
            # Find the selected name in inject_script
            for i in range(inject_script.numRows):
                if inject_script[i, 'name'].val == selected_name:
                    target_index = i
                    break
    else:
        # Original click logic
        column_number = panelValue // rows_per_column

        # Find which group this column belongs to
        columns_counted = 0
        actual_group_index = 0
        for i, cols in enumerate(columns_per_group):
            if column_number < columns_counted + cols:
                actual_group_index = i
                break
            columns_counted += cols

        # Calculate position within the found group
        columns_into_group = column_number - columns_counted

        if has_group_headers:
            # With group headers: first column has header, subtract 1
            if columns_into_group == 0:  # First column of group
                position_in_group = (panelValue % rows_per_column) - 1  # Subtract 1 for header
            else:  # Overflow column
                operators_in_previous_columns = rows_per_column - 1
                position_in_group = operators_in_previous_columns + (panelValue % rows_per_column)
        else:
            # No group headers: all positions are operators, no header to subtract
            position_in_group = panelValue  # Direct index since no headers

        # Validate position is within group's operator count
        if position_in_group < 0 or position_in_group >= group_operators[actual_group_index]:
            return

        # Get the actual operator
        group_start = group_starts[actual_group_index]
        if has_group_headers:
            target_index = group_start + 1 + position_in_group  # +1 to skip header row
        else:
            target_index = group_start + 1 + position_in_group  # +1 to skip table header (row 0)

    # Common validation for both click and ENTER
    if target_index == -1 or target_index >= inject_script.numRows:
        return

    if not inject_script[target_index, 'name'].val:
        return
    display_name = inject_script[target_index, 'name'].val
    lookup_name = display_name.lower()
    normalized_name = lookup_name.replace(' ', '_')

    # PlaceOp hook - can return:
    #   True  = proceed with placement
    #   False = cancel and close menu
    #   None  = cancel but keep menu open (ActionOp)
    #   'nohook' = no hook defined, proceed with placement
    result = installer.CallHook('_PlaceOp', panelValue, lookup_name)
    if result is False:
        parent.OPCREATE.par.winclose.pulse()
        return
    if result is None:
        # ActionOp - don't place, keep menu open
        return
    # result is True or 'nohook' - proceed with placement

    # Get operator source - supports both embedded and file-based loading
    source_result = None
    if hasattr(installer, 'Getoperatorsource'):
        source_result = installer.Getoperatorsource(lookup_name)

    clone = None
    is_file_based = False

    if source_result is None:
        # Fallback to original embedded-only behavior
        custom_ops = installer.par.Opcomp.eval() if hasattr(installer.par, 'Opcomp') else None
        if not custom_ops:
            print(f"Error: Operator '{lookup_name}' not found - no operators_comp and no file source")
            return
        masters = custom_ops.findChildren(name=lookup_name, maxDepth=1)
        if not masters:
            print(f"Error: Operator '{lookup_name}' not found in custom_operators")
            return
        master = masters[0]
        clone = installer.copy(master, name=normalized_name+'1')

    elif source_result[0] == 'file':
        # Load from external .tox file
        tox_path = source_result[1]
        is_file_based = True
        try:
            target_parent = ui.panes.current.owner
            # loadTox loads .tox as child and returns the loaded op
            clone = target_parent.loadTox(tox_path)
            # Generate unique name to avoid conflicts
            base_name = normalized_name
            counter = 1
            while target_parent.op(f"{base_name}{counter}"):
                counter += 1
            clone.name = f"{base_name}{counter}"
        except Exception as e:
            print(f"Error loading .tox file '{tox_path}': {e}")
            clone = None
            # Fallback to embedded if file load fails AND operators_comp exists
            custom_ops_base = installer.par.Opcomp.eval() if hasattr(installer.par, 'Opcomp') else None
            if custom_ops_base:
                masters = custom_ops_base.findChildren(name=lookup_name, maxDepth=1)
                if masters:
                    clone = installer.copy(masters[0], name=normalized_name+'1')
                    is_file_based = False

    elif source_result[0] == 'embedded':
        # Use embedded operator (normal path)
        master = source_result[1]
        clone = installer.copy(master, name=normalized_name+'1')

    if clone is None:
        print(f"Error: Could not create operator '{lookup_name}'")
        return

    clone.allowCooking = True
    clone.bypass = False

    # Apply family color to file-based ops if Colorfileops is enabled
    if is_file_based and hasattr(installer.par, 'Colorfileops') and installer.par.Colorfileops.eval():
        color = installer.par.Colorr.eval(), installer.par.Colorg.eval(), installer.par.Colorb.eval()
        clone.color = color

    # Handle license copying - check clone.family since master may not exist for file-based
    # Only copy license if the installer has a License op
    if clone.family == 'COMP' and license:
        existing_license = clone.op('License')
        if existing_license:
            try:
                existing_content = existing_license.par.Bodytext.eval()
                current_content = license.par.Bodytext.eval()
                if existing_content != current_content:
                    existing_license.destroy()
                    clone.copy(license)
            except:
                existing_license.destroy()
                clone.copy(license)
        else:
            clone.copy(license)

    clone.viewer = ui.preferences['network.viewer']
    ui.panes.current.placeOPs([clone], inputIndex=0, outputIndex=0)
    parent.OPCREATE.par.winclose.pulse()
    installer.CallHook('_PostPlaceOp', clone)
