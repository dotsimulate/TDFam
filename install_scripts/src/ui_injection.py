"""
UI injection system for opfam-create.

Handles installing and uninstalling operator families into
TouchDesigner's UI system (menu_op, bookmark_bar, etc).
"""


class UIInjector:
    """
    Manages installation and uninstallation of operator families.

    Injects into:
    - /ui/dialogs/menu_op (TAB menu)
    - /ui/dialogs/bookmark_bar (toggle button)
    """

    def __init__(self, installer):
        """
        Initialize the UI injector.

        Args:
            installer: The OpFamCreateExt instance
        """
        self.installer = installer
        self.ownerComp = installer.ownerComp
        self.connection_map = installer.connection_map

    @property
    def family_name(self):
        """Get family name from Properties registry."""
        return self.installer.Properties['family_name']

    @property
    def color(self):
        """Get color from Properties registry."""
        return self.installer.Properties['color']

    @color.setter
    def color(self, value):
        """Set color in Properties registry."""
        self.installer.Properties['color'] = value

    @property
    def compatible_types(self):
        """Get compatible types from Properties registry."""
        return self.installer.Properties['compatible_types']

    @property
    def shortcut_comp(self):
        """Get the component that receives the op shortcut (from installer)."""
        return self.installer.shortcut_comp

    @property
    def installer_expr(self):
        """Get expression path to installer (from installer)."""
        return self.installer.get_installer_expr(self.family_name)

    def _build_installer_expr(self, fam_name):
        """Build expression path for a given family name."""
        return self.installer.get_installer_expr(fam_name)

    def is_installation_needed(self):
        """
        Check if installation is needed.

        Returns:
            bool: True if installation needed, False if already installed
        """
        try:
            # Check inject operation in nodetable
            nodeTable = op('/ui/dialogs/menu_op/nodetable')
            if nodeTable:
                inject_op_name = f'inject_{self.family_name}_fam'
                if nodeTable.op(inject_op_name):
                    return False

                # Check eval4 expression
                eval4 = nodeTable.op('eval4')
                if eval4:
                    current_expr = eval4.par.expr.eval()
                    if current_expr and self.family_name in current_expr:
                        return False

            return True

        except Exception as e:
            return True

    def count_installed_families(self):
        """
        Count how many families are currently installed.

        Returns:
            int: Number of installed families
        """
        try:
            nodeTable = op('/ui/dialogs/menu_op/nodetable')
            if nodeTable:
                inject_ops = [o for o in nodeTable.ops('inject_*_fam') if o.valid]
                return len(inject_ops)
            return 0
        except:
            return 999  # Err on safe side

    def _undo_install_callback(self, isUndo, info):
        """
        Callback to sync Install parameter on undo/redo of install.

        Args:
            isUndo: True if undoing, False if redoing
            info: Dict with 'ownerComp' reference
        """
        owner = info.get('ownerComp')
        if owner and hasattr(owner.par, 'Install'):
            # On undo of install -> set to 0, on redo of install -> set to 1
            owner.par.Install = 0 if isUndo else 1

    def _undo_uninstall_callback(self, isUndo, info):
        """
        Callback to sync Install parameter on undo/redo of uninstall.

        Args:
            isUndo: True if undoing, False if redoing
            info: Dict with 'ownerComp' reference
        """
        owner = info.get('ownerComp')
        if owner and hasattr(owner.par, 'Install'):
            # On undo of uninstall -> set to 1, on redo of uninstall -> set to 0
            owner.par.Install = 1 if isUndo else 0

    def install(self):
        """
        Install the operator family into TouchDesigner's UI.

        Modifies:
        - bookmark_bar: Adds toggle button
        - menu_op: Adds family to TAB menu
        - nodetable: Adds inject script
        - colors: Adds family color
        - compatible: Adds compatibility entries
        """
        ui.undo.startBlock(f'Install {self.family_name} Operator Family')
        try:
            # Add callback to sync Install parameter on undo/redo
            ui.undo.addCallback(self._undo_install_callback, {'ownerComp': self.ownerComp})

            print(f"Installing {self.family_name}")
            self.ownerComp.par.Install = 1

            menuOp = op('/ui/dialogs/menu_op')
            nodeTable = op('/ui/dialogs/menu_op/nodetable')

            # Get or create UI manager
            self._get_or_create_ui_manager()

            # Create family insert DAT
            self._create_family_insert(menuOp)

            # Update colors table
            self._update_colors_table(menuOp)

            # Create/update set_last_node_type script
            self._setup_last_node_type(menuOp)

            # Modify launch_menu_op
            self._modify_launch_menu(menuOp)

            # Set colors on installer children
            self._set_child_colors()

            # Create inject script in nodetable
            self._create_inject_script(nodeTable)

            # Update eval4 expression
            self._update_eval4(nodeTable)

            # Modify create_node script
            self._modify_create_node(menuOp)

            # Modify search panel exec
            self._modify_search_exec(menuOp)

            # Deploy fam_panel_execute
            self._deploy_panel_execute(menuOp)

            # Update compatible table
            self._update_compatible_table(menuOp)

            print(f"{self.family_name} installation complete")
        finally:
            ui.undo.endBlock()

    def uninstall(self):
        """
        Uninstall the operator family from TouchDesigner's UI.
        """
        ui.undo.startBlock(f'Uninstall {self.family_name} Operator Family')
        try:
            # Add callback to sync Install parameter on undo/redo
            ui.undo.addCallback(self._undo_uninstall_callback, {'ownerComp': self.ownerComp})

            print(f"Beginning uninstall of {self.family_name}")
            self.ownerComp.par.Install = 0

            # -Unregister from central UI manager-
            # ! Do not unregister from GUI (top right button), this is managed by event system
            # self._unregister_from_ui_manager() 

            menuOp = op('/ui/dialogs/menu_op')
            nodeTable = op('/ui/dialogs/menu_op/nodetable')

            # Remove family insert DAT
            if menuOp.op(f'{self.family_name}_insert'):
                menuOp.op(f'{self.family_name}_insert').destroy()

            # Remove from colors table
            colors_table = menuOp.op('colors')
            if colors_table:
                for i in range(colors_table.numRows):
                    if colors_table[i, 0].val == f"'{self.family_name}'":
                        colors_table.deleteRow(i)
                        break

            # Remove inject script
            inject_op_name = f'inject_{self.family_name}_fam'
            if nodeTable.op(inject_op_name):
                nodeTable.op(inject_op_name).destroy()

            families_op = nodeTable.op('families')
            if families_op:
                families_op.bypass = False

            # Remove panel execute
            panel_execute_path = f'{self.family_name}_panel_execute'
            if menuOp.op(panel_execute_path):
                menuOp.op(panel_execute_path).destroy()

            # Only remove shared components if last family
            if self.count_installed_families() <= 1:
                launch_menu_op = menuOp.op('launch_menu_op')
                if launch_menu_op:
                    code = launch_menu_op.text
                    key = "if($type != \"none\")\n\tcvar menu_type=$type\n\trun set_last_node_type\n\tset type = $lasttype"
                    replacement = 'if($type != "none")'
                    launch_menu_op.text = code.replace(key, replacement)

                if menuOp.op('set_last_node_type'):
                    menuOp.op('set_last_node_type').destroy()

            # Remove from compatible table
            compatibleTable = menuOp.op('compatible')
            if compatibleTable:
                if compatibleTable.rows(self.family_name):
                    compatibleTable.deleteRow(self.family_name)
                if compatibleTable.cols(self.family_name):
                    compatibleTable.deleteCol(self.family_name)

            print(f"{self.family_name} uninstallation complete")
        finally:
            ui.undo.endBlock()

    # ==================== Private Install Helpers ====================

    def _get_or_create_ui_manager(self, force=False):
        """Get or create the central OpFamUI manager."""
        # Check if already installed at global location
        ui_manager_path = '/ui/dialogs/mainmenu/OpFamUI'
        ui_manager = op(ui_manager_path)
        
        internal = self.ownerComp.op('internal_pars')
        if internal:
            force = force or internal.par.Force.eval() # callers force takes precedence
            local_dev = internal.par.Dev.eval()
        else:
            local_dev = False

        if (force or local_dev) and ui_manager:
            ui_manager.destroy()
            ui_manager = None

        if not ui_manager:
            # Copy from our template
            template = self.ownerComp.op('OpFamUI')
            
            if local_dev:
                template = self.ownerComp.op('OpFamUI/OpFamUI')

            if template:
                mainmenu = op('/ui/dialogs/mainmenu')
                if mainmenu:
                    debug(f'copying {template.path} to {mainmenu.path}')
                    ui_manager = mainmenu.copy(template, name='OpFamUI')
                    ui_manager.allowCooking = True

                    # Wire up to emptypanel in mainmenu
                    emptypanel = mainmenu.op('emptypanel')
                    if emptypanel and ui_manager.inputCOMPConnectors:
                        ui_manager.inputCOMPConnectors[0].connect(emptypanel)

                    if local_dev:
                        ui_manager.par.enable = True
                        ui_manager.par.display = True
                        ui_manager.par.selectpanel = self.ownerComp.op('OpFamUI')

        return ui_manager if not local_dev else self.ownerComp.op('OpFamUI')

    def _create_family_insert(self, menuOp):
        """Create family insert DAT in menu_op."""
        if menuOp.op(f'{self.family_name}_insert'):
            return

        familyInsert = menuOp.create(insertDAT, f'{self.family_name}_insert')
        familyInsert.par.insert = 'col'
        familyInsert.par.at = 'index'

        default_index = 10
        if hasattr(self.ownerComp.par, 'Index'):
            default_index = self.ownerComp.par.Index.eval()
            familyInsert.par.index.expr = f'{self.installer_expr}.par.Index'
        else:
            familyInsert.par.index = default_index

        familyInsert.par.contents = self.family_name

        # Insert into chain
        insert1 = menuOp.op('insert1')
        current_output = insert1.outputs[0]
        insert1.outputConnectors[0].disconnect()
        insert1.outputConnectors[0].connect(familyInsert)
        familyInsert.outputConnectors[0].connect(current_output)
        familyInsert.nodeX = insert1.nodeX + 150
        familyInsert.nodeY = insert1.nodeY

    def _update_colors_table(self, menuOp):
        """Update colors table with family color."""
        colors_table = menuOp.op('colors')
        if not colors_table:
            return

        # Check if exists
        family_exists = False
        for i in range(colors_table.numRows):
            if colors_table[i, 0].val == f"'{self.family_name}'":
                # Update existing
                for j in range(min(len(self.color), colors_table.numCols - 1)):
                    colors_table[i, j + 1] = self.color[j]
                family_exists = True
                break

        if not family_exists:
            new_row = [f"'{self.family_name}'"] + list(self.color)
            colors_table.appendRow(new_row)

    def _setup_last_node_type(self, menuOp):
        """Create/update set_last_node_type script."""
        setLastNodeType = menuOp.op('set_last_node_type')
        if not setLastNodeType:
            setLastNodeType = menuOp.create(textDAT, 'set_last_node_type')
            launch_menu = menuOp.op('launch_menu_op')
            if launch_menu:
                setLastNodeType.nodeX = launch_menu.nodeX - 200
                setLastNodeType.nodeY = launch_menu.nodeY

        # Update script content
        compatible_check = ' or '.join([f"menu_type=='{t}'" for t in self.compatible_types])
        script = f'''varTable = op('local/set_variables')
lastnode = op(varTable['nodepath',1])
source = varTable['source',1].val
menu_type = varTable['menu_type',1].val
if(lastnode and source == 'output'):
    type = lastnode.family
    if ('{self.family_name}' in lastnode.tags):
        type = '{self.family_name}'
    varTable['lasttype',1] = type
elif(source == 'input' and ({compatible_check})):
    pane = ui.panes.current
    zoom = pane.zoom
    currentParent = pane.owner
    mousePos = [varTable['xpos',1],varTable['ypos',1]]
    type = menu_type
    for child in currentParent.findChildren(maxDepth=1):
        if (-5<(mousePos[0]-child.nodeX)*zoom<15 and child.nodeY+child.nodeHeight>mousePos[1] and mousePos[1]>child.nodeY):
            if('{self.family_name}' in child.tags):
                type = '{self.family_name}'
                varTable['lastnode',1] = child.name
                varTable['nodepath',1] = child.path
                break
    varTable['lasttype',1] = type'''

        if setLastNodeType:
            setLastNodeType.text = script

    def _modify_launch_menu(self, menuOp):
        """Modify launch_menu_op script."""
        launch_menu_op = menuOp.op('launch_menu_op')
        if not launch_menu_op:
            return

        code = launch_menu_op.text
        key = 'if($type != "none")'
        replacement = f"{key}\n\tcvar menu_type=$type\n\trun set_last_node_type\n\tset type = $lasttype"

        if 'run set_last_node_type' not in code:
            launch_menu_op.text = code.replace(key, replacement)

    def _set_child_colors(self):
        """Set color on all installer children."""
        color_val = list(self.color) if self.color else [0.5, 0.5, 0.5, 1.0]
        if len(color_val) < 4:
            color_val = color_val + [1.0] * (4 - len(color_val))

        for o in self.ownerComp.findChildren():
            if 'License' not in o.name and o.OPType != 'annotateCOMP':
                try:
                    o.color = color_val
                except:
                    pass

        try:
            self.ownerComp.color = color_val
        except:
            pass

    def _create_inject_script(self, nodeTable):
        """Create inject script in nodetable."""
        inject_op_name = f'inject_{self.family_name}_fam'
        families_op = nodeTable.op('families')

        if not families_op:
            return

        families_op.bypass = False

        if nodeTable.op(inject_op_name):
            return

        original_input = families_op.inputs[0] if families_op.inputs else None
        inject_op = nodeTable.copy(families_op, name=inject_op_name, includeDocked=True)
        inject_op.par.callbacks.expr = f"{self.installer_expr}.op('fam_script_callbacks')"
        inject_op.nodeX = families_op.nodeX + 150
        inject_op.nodeY = families_op.nodeY

        if original_input:
            original_input.outputConnectors[0].disconnect()
            original_input.outputConnectors[0].connect(inject_op)
            inject_op.outputConnectors[0].connect(families_op)

        families_op.cook(force=True)
        inject_op.cook(force=True)

    def _update_eval4(self, nodeTable):
        """Update eval4 expression to include family."""
        eval4 = nodeTable.op('eval4')
        if not eval4:
            return

        # Get the raw expression STRING, not the evaluated result
        current_expr = eval4.par.expr.expr

        if current_expr:
            if current_expr != "[x for x in families.keys()]":
                if self.family_name not in current_expr:
                    eval4.par.expr = f"{current_expr[:-1]}, '{self.family_name}']"
            else:
                eval4.par.expr = f"[x for x in families.keys()] + ['{self.family_name}']"
        else:
            eval4.par.expr = f"[x for x in families.keys()] + ['{self.family_name}']"

    def _modify_create_node(self, menuOp):
        """Modify create_node script."""
        createNode = menuOp.op('create_node')
        if not createNode:
            return

        if f"if($type=='{self.family_name}')" in createNode.text:
            return

        insertion_key = 'set type = `tab("current",0,0)`\n'
        insert_code = f"if($type=='{self.family_name}')\n\texit\nendif\n"

        try:
            index = createNode.text.index(insertion_key)
            createNode.text = (
                createNode.text[:index + len(insertion_key)]
                + insert_code
                + createNode.text[index + len(insertion_key):]
            )
        except ValueError:
            pass

    def _modify_search_exec(self, menuOp):
        """Modify search panel exec."""
        searchExec = menuOp.op('search/panelexec1')
        if not searchExec:
            return

        if self.family_name in searchExec.text:
            return

        key = "if parent.OPCREATE.op('nodetable/destil').numRows > 1:\n"
        unique_id = -abs(hash(self.family_name) % 10000)
        insert_code = (
            f"\t\t\tif(op('/ui/dialogs/menu_op/current')[0,0].val=='{self.family_name}'):\n"
            f"\t\t\t\tparent.OPCREATE.op('nodetable').clickID({unique_id})\n"
            f"\t\t\t\treturn\n"
        )

        try:
            index = searchExec.text.index(key)
            searchExec.text = (
                searchExec.text[:index + len(key)]
                + insert_code
                + searchExec.text[index + len(key):]
            )
        except ValueError:
            pass

    def _deploy_panel_execute(self, menuOp):
        """Deploy fam_panel_execute to menu_op."""
        panel_execute_path = f'{self.family_name}_panel_execute'
        if menuOp.op(panel_execute_path):
            return

        source = self.ownerComp.op('fam_panel_execute')
        if not source:
            return

        panel_execute = menuOp.copy(source, name=panel_execute_path)
        panel_execute.nodeX = menuOp.op('node_script').nodeX
        panel_execute.nodeY = menuOp.op('node_script').nodeY + 100

        # Disable sync on deployed copy to prevent corruption
        panel_execute.par.syncfile = ''

    def _update_compatible_table(self, menuOp):
        """Update compatible table with family entries."""
        compatibleTable = menuOp.op('compatible')
        if not compatibleTable:
            return

        # Build row entry
        row_entry = [self.family_name]
        for index in range(1, compatibleTable.numCols):
            col_type = compatibleTable[0, index].val
            connection_key = (self.family_name, col_type)
            if connection_key in self.connection_map:
                row_entry.append(self.connection_map[connection_key])
            elif col_type in self.compatible_types:
                row_entry.append('x')
            else:
                row_entry.append('')

        # Build col entry
        col_entry = [self.family_name]
        for row in compatibleTable.rows()[1:]:
            row_type = row[0].val
            connection_key = (row_type, self.family_name)
            if connection_key in self.connection_map:
                col_entry.append(self.connection_map[connection_key])
            elif row_type in self.compatible_types:
                col_entry.append('x')
            else:
                col_entry.append('')

        # Add row and column
        if not compatibleTable.rows(self.family_name):
            compatibleTable.appendRow(row_entry)
        if not compatibleTable.cols(self.family_name):
            compatibleTable.appendCol(col_entry)

        # Set self-compatibility
        try:
            row_index = None
            col_index = None

            for i in range(compatibleTable.numRows):
                if compatibleTable[i, 0].val == self.family_name:
                    row_index = i
                    break

            for i in range(compatibleTable.numCols):
                if compatibleTable[0, i].val == self.family_name:
                    col_index = i
                    break

            if row_index is not None and col_index is not None:
                compatibleTable[row_index, col_index] = 'x'
        except Exception as e:
            print(f"Error setting self-compatibility: {e}")

    # ==================== Dynamic Update Methods ====================

    def update_family_color(self, new_color):
        """
        Update family color without full reinstall.

        Useful for ActionOp theme switching.

        Args:
            new_color: New color as [r, g, b] or [r, g, b, a]
        """
        self.color = new_color
        self.installer.color = new_color

        menuOp = op('/ui/dialogs/menu_op')
        if not menuOp:
            return

        # Update colors table
        colors_table = menuOp.op('colors')
        if colors_table:
            for i in range(colors_table.numRows):
                if colors_table[i, 0].val == f"'{self.family_name}'":
                    for j in range(min(len(new_color), colors_table.numCols - 1)):
                        colors_table[i, j + 1] = new_color[j]
                    break

        # Update installer child colors
        self._set_child_colors()

        # Update operators_comp and ownerComp colors
        color_val = list(new_color) if new_color else [0.5, 0.5, 0.5]
        color_tuple = (color_val[0], color_val[1], color_val[2])

        # Get operators_comp from parameter
        custom_ops = self.ownerComp.par.Opcomp.eval() if hasattr(self.ownerComp.par, 'Opcomp') else None
        if custom_ops:
            # Update the Opcomp container itself
            custom_ops.color = color_tuple
            # Update all operators inside
            for comp in custom_ops.findChildren(type=COMP, maxDepth=1):
                comp.color = color_tuple

        self.ownerComp.color = color_tuple

    def update_family_name(self, old_name, new_name):
        """
        Update family name without full reinstall.

        Renames all UI elements if currently installed.

        Args:
            old_name: Previous family name
            new_name: New family name
        """
        # Update Properties registry
        self.installer.Properties['family_name'] = new_name

        # Update op shortcut on the correct component
        self.shortcut_comp.par.opshortcut = new_name

        # If not installed, nothing else to update
        if not self.ownerComp.par.Install.eval():
            return

        menuOp = op('/ui/dialogs/menu_op')
        nodeTable = op('/ui/dialogs/menu_op/nodetable')
        if not menuOp:
            return

        # 1. Update in central registry 
        # # TODO: should not be done here since it's not UI related only
        ui_manager = self.installer.fam_registry
        ui_manager.UpdateFamilyName(old_name, new_name)

        # 2. Rename family insert DAT
        old_insert = menuOp.op(f'{old_name}_insert')
        if old_insert:
            old_insert.name = f'{new_name}_insert'
            old_insert.par.contents = new_name
            if hasattr(self.ownerComp.par, 'Index'):
                old_insert.par.index.expr = f'{self._build_installer_expr(new_name)}.par.Index'

        # 3. Update colors table
        colors_table = menuOp.op('colors')
        if colors_table:
            for i in range(colors_table.numRows):
                if colors_table[i, 0].val == f"'{old_name}'":
                    colors_table[i, 0] = f"'{new_name}'"
                    break

        # 4. Update set_last_node_type script
        setLastNodeType = menuOp.op('set_last_node_type')
        if setLastNodeType:
            setLastNodeType.text = setLastNodeType.text.replace(
                f"'{old_name}'", f"'{new_name}'"
            )

        # 5. Rename inject script in nodetable
        old_inject = nodeTable.op(f'inject_{old_name}_fam')
        if old_inject:
            old_inject.name = f'inject_{new_name}_fam'
            old_inject.par.callbacks.expr = f"{self._build_installer_expr(new_name)}.op('fam_script_callbacks')"

        # 6. Update eval4 expression
        eval4 = nodeTable.op('eval4')
        if eval4:
            current_expr = eval4.par.expr.expr
            if current_expr and old_name in current_expr:
                eval4.par.expr = current_expr.replace(f"'{old_name}'", f"'{new_name}'")

        # 7. Update create_node script
        createNode = menuOp.op('create_node')
        if createNode and old_name in createNode.text:
            createNode.text = createNode.text.replace(
                f"'{old_name}'", f"'{new_name}'"
            )

        # 8. Update search panel exec
        searchExec = menuOp.op('search/panelexec1')
        if searchExec and old_name in searchExec.text:
            searchExec.text = searchExec.text.replace(
                f"'{old_name}'", f"'{new_name}'"
            )

        # 9. Rename panel execute
        old_panel = menuOp.op(f'{old_name}_panel_execute')
        if old_panel:
            old_panel.name = f'{new_name}_panel_execute'

        # 10. Update compatible table
        compatibleTable = menuOp.op('compatible')
        if compatibleTable:
            # Update row header
            for i in range(compatibleTable.numRows):
                if compatibleTable[i, 0].val == old_name:
                    compatibleTable[i, 0] = new_name
                    break
            # Update column header
            for i in range(compatibleTable.numCols):
                if compatibleTable[0, i].val == old_name:
                    compatibleTable[0, i] = new_name
                    break

        print(f"Family name updated from '{old_name}' to '{new_name}'")
