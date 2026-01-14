# me - this DAT
# scriptOp - the OP which is cooking
# CUSTOM CODESCRIPT CALLBACK 
# press 'Setup Parameters' in the OP to call this function to re-create the parameters.
def setupParameters(scriptOp):
    page = scriptOp.appendCustomPage('Operators')
    p = page.appendInt('Rows', label='Rows')
    p = page.appendToggle('Append', label='Append Nodes')
    p = page.appendStr('Compatible', label='Compatible OPs')
    p = page.appendStr('Search',label='Search String')
    p = page.appendStr('Source',label='Source')
    p = page.appendStr('Connectto',label='Connect To')
    p = page.appendToggle('All',label='Display All')
    p = page.appendToggle('Experimental',label='Display Experimental')
    p = page.appendStr('Limitcustom', label='Limit Custom')
    return

# called whenever custom pulse parameter is pushed
def onPulse(par):
    return

import re
def cook(scriptOp):
    # Get current family
    if not scriptOp.inputs[0]:
        scriptOp.clear()
        return
    currFamily = scriptOp.inputs[0][0,0].val

    # Get Registry
    registry = getattr(op, 'FAMREGISTRY', None)
    if not registry:
        scriptOp.copy(scriptOp.inputs[0])
        return

    # Find the original families operator and nodetable
    nodetable = op('/ui/dialogs/menu_op/nodetable')
    families_op = nodetable.op('families') if nodetable else None
    
    # Check if this family is one of ours
    installer = registry.InstalledFams.get(currFamily)

    # If this isn't one of our custom families, copy input and un-bypass families
    if not installer:
        if families_op:
            families_op.bypass = False
        scriptOp.copy(scriptOp.inputs[0])
        return

    # It's one of our families - bypass families_op
    if families_op:
        families_op.bypass = True

    familyOps = installer.op('OP_fam') if installer else None
    if not familyOps or familyOps.numRows < 2 or familyOps.numCols == 0:
        scriptOp.copy(scriptOp.inputs[0])
        return

    if 'name' not in [familyOps[0, c].val for c in range(familyOps.numCols)]:
        scriptOp.copy(scriptOp.inputs[0])
        return

    # Original processing code starts here
    scriptOp.clear()
    scriptOp.appendRow(['name','label','type','subtype','mininputs','maxinputs','ordering','level','lictype','os','score','family','opType'])
    append = scriptOp.par.Append
    searchString = scriptOp.par.Search.eval().lower().strip()
    source = scriptOp.par.Source.eval()
    connectTo = scriptOp.par.Connectto.eval()
    license = licences.type
    tableRows = scriptOp.par.Rows


    if not connectTo:
        connectTo = 'Bla'

    if not append:
        compatible = ['x']
    else:
        compatible = [i.split(':')[0] for i in scriptOp.par.Compatible.eval().split(' ')]

    allNodes = []
    if currFamily == 'Custom':
        limitCustom = scriptOp.par.Limitcustom.eval()
        connectTo = op('/ui/dialogs/menu_op/connectto')[0,0]
        if limitCustom != '*':
            if connectTo != None:
                allFamilies = [connectTo.val]
            else:
                allFamilies = [limitCustom.split(' ')[0]]
        else:
            allFamilies = families.keys()
    else:
        allFamilies = [currFamily]


    for family in allFamilies:
        if family == currFamily:  # Replace the hardcoded LOP check
            familyOps = installer.op('OP_fam')

            # Guard: check OP_fam has proper structure before processing
            if not familyOps or familyOps.numRows < 2 or familyOps.numCols == 0:
                continue

            # Check 'name' column exists
            if 'name' not in [familyOps[0, c].val for c in range(familyOps.numCols)]:
                continue
            
            group_table = installer.op('group_mapping')
            # print(f"\nGroup mapping table contents:")
            # print(group_table.text)

            # Set up OS compatibility and exclude table
            os_table = installer.op('os_incompatible')
            os_values = {}
            exclude_values = {}
            if os_table:
                import platform
                current_os = platform.system().lower()

                # Use column 1 for Windows, column 2 for Mac, column 3 for exclude
                os_col_index = 1 if current_os == 'windows' else 2

                # Build the OS values and exclude dictionaries
                for row in os_table.rows()[1:]:
                    if row[0].val:  # Make sure operator name exists
                        op_name = str(row[0].val).lower().replace(' ', '_')
                        os_compat = str(row[os_col_index].val) if os_col_index < len(row) else '1'
                        os_values[op_name] = os_compat
                        # Get exclude flag (column 3)
                        exclude_flag = str(row[3].val) if len(row) > 3 else '0'
                        exclude_values[op_name] = exclude_flag

            # Get exclude_behavior, show_ungrouped, and ungrouped_label from settings
            settings = installer.op('settings')
            exclude_behavior = settings['exclude_behavior', 1].val if settings and settings.row('exclude_behavior') else 'hide'
            show_ungrouped = settings['show_ungrouped', 1].val if settings and settings.row('show_ungrouped') else '1'
            ungrouped_label = settings['ungrouped_label', 1].val if settings and settings.row('ungrouped_label') else 'Other'

            # Create group index
            group_index = {}
            if not group_table:
                continue
            for col in range(group_table.numCols):
                group_name = group_table[0, col].val
                for row in range(1, group_table.numRows):
                    operator_name = group_table[row, col].val
                    if operator_name:
                        # Store both the original format and the normalized format
                        normalized_name = operator_name.lower().replace(' ', '_')
                        group_index[operator_name.lower()] = group_name  # For original format lookup
                        group_index[normalized_name] = group_name  # For normalized format lookup
            
            # print(f"\nGroup index mapping:")
            # print(group_index)

            # Group nodes by their group
            grouped_nodes = {}
            for i in range(1, familyOps.numRows):
                type = familyOps[i,'name'].val
                if not type:  # Skip empty rows (group labels)
                    continue

                normalized_type = type.lower().replace(' ', '_')

                # Check exclude flag
                is_excluded = exclude_values.get(normalized_type, '0') == '1'
                if is_excluded and exclude_behavior == 'hide':
                    continue  # Skip this operator entirely

                # print(f"\nProcessing operator: {type}")
                label = familyOps[i,'label'].val
                isFilter = familyOps[i,'type'].val == f'layouts/{currFamily}/defFilter'

                # Get OS compatibility value
                os_compat = os_values.get(normalized_type, '1')  # Default to '1' (compatible) if not found

                # Try both original and normalized formats for lookup
                group_name = group_index.get(type.lower()) or group_index.get(normalized_type)

                # Check show_ungrouped setting
                if group_name is None:
                    if show_ungrouped != '1':
                        continue  # Skip ungrouped operators
                    group_name = ungrouped_label

                #  print(f"Group: {group_name}")

                if 'x' in compatible or type in compatible or (connectTo == 'DAT' and currFamily == familyOps):
                    node = {}
                    node['nodeName'] = type
                    node['nodeLabel'] = label
                    node['opType'] = familyOps[i,'opType']
                    node['score'] = 0
                    node['os'] = os_compat  # Add OS compatibility

                    if not len(searchString) or searchString in type.lower() or searchString in label.lower():
                        node['score'] = 0
                        labelByCapital = re.findall('[A-Z][^A-Z]*', familyOps[i,'label'].val)
                        if label.lower() == searchString:
                            node['score'] = 5
                        elif type.lower() == searchString:
                            node['score'] = 4
                        elif label.lower().startswith(searchString):
                            node['score'] = 3
                        elif searchString in label.lower().split(' '):
                            node['score'] = 2
                        elif any([s.lower().startswith(searchString) for s in labelByCapital]):
                            node['score'] = 2
                        if node['score'] > 0:
                            opType = ['defGenerator','defFilter'][isFilter]
                        else:
                            opType = ['defGeneratorDisable','defFilterDisable'][isFilter]
                    else:
                        opType = ['defGeneratorDisable','defFilterDisable'][isFilter]
                    if source == 'output' and not isFilter and familyOps[i,'maxInputs'] == 0 and currFamily == connectTo:
                        opType = ['defGeneratorDisable','defFilterDisable'][isFilter]
                    if familyOps[i,'licenseType'] == 'Pro' and 'Pro' not in license:
                        opType = ['defGeneratorDisable','defFilterDisable'][isFilter]
                    elif familyOps[i,'licenseType'] == 'Commercial' and 'Non-Commercial' in license:
                        opType = ['defGeneratorDisable','defFilterDisable'][isFilter]

                    # Check OS compatibility - if not supported, disable the operator
                    if os_compat == '0':
                        opType = ['defGeneratorDisable','defFilterDisable'][isFilter]

                    # Check exclude with disable behavior
                    if is_excluded and exclude_behavior == 'disable':
                        opType = ['defGeneratorDisable','defFilterDisable'][isFilter]

                    node['isFilter'] = 'layouts/{0}/{1}'.format(family,opType)
                    node['subType'] = 2
                    node['minInputs'] = familyOps[i,'mininputs']
                    node['maxInputs'] = familyOps[i,'maxinputs']
                    node['visibility'] = 1
                    node['ordered'] = True
                    node['supported'] = 1
                    node['licLevel'] = familyOps[i,'lictype']
                    node['custom'] = False
                    node['family'] = family
                    node['group'] = group_name

                    if scriptOp.par.Experimental.eval():
                        if group_name not in grouped_nodes:
                            grouped_nodes[group_name] = []
                        grouped_nodes[group_name].append(node)
                    elif node['visibility'] < 2 and scriptOp.par.All.eval():	
                        if group_name not in grouped_nodes:
                            grouped_nodes[group_name] = []
                        grouped_nodes[group_name].append(node)
                    elif node['visibility'] < 1 and not scriptOp.par.All.eval():
                        if group_name not in grouped_nodes:
                            grouped_nodes[group_name] = []
                        grouped_nodes[group_name].append(node)
            # Get group order from group_mapping column order (left to right)
            group_order = [group_table[0, col].val for col in range(group_table.numCols)]

            # Build custom order index: {group_name: {op_name: row_index}}
            custom_order = {}
            for col in range(group_table.numCols):
                grp = group_table[0, col].val
                custom_order[grp] = {}
                for row in range(1, group_table.numRows):
                    op_name = group_table[row, col].val
                    if op_name:
                        custom_order[grp][op_name.lower()] = row

            # Get sort method from settings table
            sort_method = settings['sort_within_group', 1].val if settings and settings.row('sort_within_group') else 'alphabetical'

            # Sort groups: column order first, then alphabetical for unlisted
            def group_sort_key(name):
                if name in group_order:
                    return (0, group_order.index(name))
                return (1, name.lower())

            sorted_groups = sorted(grouped_nodes.keys(), key=group_sort_key)

            # Sort groups and append to scriptOp
            for group_name in sorted_groups:
                # Add group header (skip if empty)
                if group_name:
                    scriptOp.appendRow(['', group_name, f'layouts/{family}/defLabel'])

                # Sort nodes within group based on settings
                if sort_method == 'alphabetical':
                    nodes = sorted(grouped_nodes[group_name], key=lambda k: k['nodeLabel'].lower())
                elif sort_method == 'by_name':
                    nodes = sorted(grouped_nodes[group_name], key=lambda k: k['nodeName'].lower())
                elif sort_method == 'custom':
                    # Sort by row order in group_mapping table
                    grp_order = custom_order.get(group_name, {})
                    nodes = sorted(grouped_nodes[group_name],
                                   key=lambda k: grp_order.get(k['nodeName'].lower(), 999))
                else:
                    # Default to alphabetical
                    nodes = sorted(grouped_nodes[group_name], key=lambda k: k['nodeLabel'].lower())
                
                # Add all nodes in this group
                for node in nodes:
                    scriptOp.appendRow([node['nodeName'], node['nodeLabel'], node['isFilter'], 
                                      node['subType'], node['minInputs'], node['maxInputs'],
                                      node['ordered'], node['visibility'], node['licLevel'],
                                      node['os'], node['score'], node['family'], node['opType']])
                
                # Add empty rows to complete the column of 28
                num_nodes = len(nodes) + 1  # +1 for the group header
                if num_nodes < 28:
                    empty_rows_needed = 28 - num_nodes
                    for _ in range(empty_rows_needed):
                        scriptOp.appendRow()

        else:
            for i in families[family]: #loop over all ops of family
                if 'x' in compatible or i.type in compatible:
                    node = {}
                    node['nodeName'] = i.type 
                    node['nodeLabel'] = i.label
                    node['opType'] = i.OPType
                    node['score'] = 0

                    if not len(searchString) or searchString in i.type.lower() or searchString in i.label.lower():
                        node['score'] = 0
                        labelByCapital = re.findall('[A-Z][^A-Z]*', i.label)
                        if i.label.lower() == searchString:
                            node['score'] = 5
                        elif i.type.lower() == searchString:
                            node['score'] = 4
                        elif i.label.lower().startswith(searchString):
                            node['score'] = 3
                        elif searchString in i.label.lower().split(' '):
                            node['score'] = 2
                        elif any([s.lower().startswith(searchString) for s in labelByCapital]):
                            node['score'] = 2
                        if node['score'] > 0:
                            opType = ['defGenerator','defFilter'][i.isFilter]
                        else:
                            opType = ['defGeneratorDisable','defFilterDisable'][i.isFilter]
                    else:
                        opType = ['defGeneratorDisable','defFilterDisable'][i.isFilter]
                    if i.supported == 0:
                        opType = ['defGeneratorDisable','defFilterDisable'][i.isFilter]
                    elif source == 'output' and not i.isFilter and i.maxInputs == 0 and currFamily == connectTo:
                        opType = ['defGeneratorDisable','defFilterDisable'][i.isFilter]
                    if i.licenseType == 'Pro' and 'Pro' not in license:
                        opType = ['defGeneratorDisable','defFilterDisable'][i.isFilter]
                    elif i.licenseType == 'Commercial' and 'Non-Commercial' in license:
                        opType = ['defGeneratorDisable','defFilterDisable'][i.isFilter]


                    node['isFilter'] = 'layouts/{0}/{1}'.format(family,opType)
                    node['subType'] = getSubType(i.subType)
                    node['minInputs'] = i.minInputs
                    node['maxInputs'] = i.maxInputs
                    node['visibility'] = i.visibleLevel
                    node['ordered'] = i.isMultiInputs
                    node['supported'] = i.supported
                    node['licLevel'] = i.licenseType
                    node['custom'] = i.isCustom
                    node['family'] = family
                    if scriptOp.par.Experimental.eval():
                        allNodes.append(node)
                    elif i.visibleLevel < 2 and scriptOp.par.All.eval():	
                        allNodes.append(node)
                    elif i.visibleLevel < 1 and not scriptOp.par.All.eval():
                        allNodes.append(node)

    if currFamily == 'COMP':
        heading = [['','3D Objects','layouts/COMP/defLabel'],['','Panels','layouts/COMP/defLabel'],['','Other','layouts/COMP/defLabel'],['','Dynamics','layouts/COMP/defLabel']]
        sortedList = sorted(allNodes, key=lambda k: k['subType'])
        count = 0
        currSubType = -1

        for i in sortedList:
            if i['subType'] != currSubType:
                if count > 0:
                    addRows = tableRows-(count%tableRows)
                    for j in range(addRows):
                        scriptOp.appendRow()
                
                currSubType = i['subType']
                scriptOp.appendRow(heading[currSubType])
                count = 1
            scriptOp.appendRow([i['nodeName'],i['nodeLabel'],i['isFilter'],i['subType'],i['minInputs'],i['maxInputs'],i['ordered'],i['visibility'],i['licLevel'],i['supported'],i['score'],i['family'],i['opType']])
            count += 1
        addRows = tableRows-(count%tableRows)

    elif currFamily == 'Custom':
        sortedList = sorted(allNodes, key=lambda k: k['nodeLabel'].lower())
        for i in sortedList:
            if i['custom']:
                scriptOp.appendRow([i['nodeName'],i['nodeLabel'],i['isFilter'],i['subType'],i['minInputs'],i['maxInputs'],i['ordered'],i['visibility'],i['licLevel'],i['supported'],i['score'],i['family'],i['opType']])
        addRows = tableRows-(len(sortedList)%tableRows)

    else:
        sortedList = sorted(allNodes, key=lambda k: k['nodeLabel'].lower())
        for i in sortedList:
            if not i['custom']:
                scriptOp.appendRow([i['nodeName'],i['nodeLabel'],i['isFilter'],i['subType'],i['minInputs'],i['maxInputs'],i['ordered'],i['visibility'],i['licLevel'],i['supported'],i['score'],i['family'],i['opType']])
        addRows = tableRows-(len(sortedList)%tableRows)
    for i in range(addRows):
        scriptOp.appendRow()

    return

def getSubType(subType):
    if subType == 'object':
        return 0
    elif subType == 'panel':
        return 1
    elif subType == 'dynamics':
        return 3
    else:
        return 2