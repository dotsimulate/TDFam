# me - this DAT
# panelValue - the PanelValue object that changed
# prev - the previous value of the PanelValue object that changed
# Make sure the corresponding toggle is enabled in the Panel Execute DAT.
#
# This script is deployed to /ui/dialogs/menu_op/{family}_panel_execute
# Family name is derived dynamically from the script's own name.

import ctypes

def _get_family():
	"""Get current family from TAB menu context."""
	current_op = op('/ui/dialogs/menu_op/current')
	return current_op[0,0].val if current_op else ''

def _get_installer(family=None):
	"""Get the installer component for this family via the Registry."""
	if not family:
		family = _get_family()
	registry = getattr(op, 'FAMREGISTRY', None)
	if registry and family in registry.InstalledFams:
		return registry.InstalledFams[family]
	return None

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
    installer = _get_installer(family)
    if not installer:
        return

    if panelValue == -1:
        return

    # Skip placement on right-click — let panelexec3 handle the pop menu
    nodetable = parent.OPCREATE.op('nodetable')
    if nodetable and nodetable.panel.rselect:
        return

    # Use the unified global inject script output
    inject_script = parent.OPCREATE.op('nodetable/inject_opfam_registry')
    if not inject_script:
        # Fallback to raw OP_fam
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

    ###

    display_name = inject_script[target_index, 'name'].val
    # normalized_name = display_name.lower().replace(' ', '_')

    # PlaceOp hook - returns dict with:
    #   returnValue: True = place, False = cancel+close, None = ActionOp
    #   lookupName: possibly modified by callback
    #   'nohook' string if no hook method exists

    lookup_name = display_name.lower().replace(' ', '_')
    result = op.FAMREGISTRY.CallHook(family, '_PlaceOp', panelValue, lookup_name)

    if isinstance(result, dict):
        should_place = result.get('returnValue', True)
    else:
        should_place = result if result != 'nohook' else True

    if should_place is False:
        parent.OPCREATE.par.winclose.pulse()
        return
    if should_place is None:
        # ActionOp - don't place, keep menu open
        return

    # Manage op clone before placement
    # Validates registry, acts on op name, color
    opType = inject_script[target_index, 'opType'].val
    clone = op.FAMREGISTRY.ext.OpFamRegistryExt.manageOpClone(family, opType, display_name)

    # Place OP
    ui.panes.current.placeOPs([clone],inputIndex=0,outputIndex=0)		

    parent.OPCREATE.par.winclose.pulse()
    op.FAMREGISTRY.CallHook(family, '_PostPlaceOp', clone)
