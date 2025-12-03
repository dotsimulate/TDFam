"""
Generic manager for opfam-create.
Handles installing and uninstalling operator families into

"""


class FamManager:
    """
    Manages installation and uninstallation of operator families.

    Injects into:
    - /sys/
    as opFamManager
    """

    def __init__(self, installer):
        """
        Initialize the FamManager.

        Args:
            installer: The OpFamCreateExt instance
        """
        self.installer = installer
        self.ownerComp = installer.ownerComp
        self.connection_map = installer.connection_map

    def install(self):
        """
        Install the operator family into TouchDesigner's /sys.
        """
        fam_registry = self._get_or_create_fam_registry()
        if fam_registry and hasattr(fam_registry, 'RegisterFamily'):
            fam_registry.RegisterFamily(self.ownerComp)

    def uninstall(self):
        """
        Uninstall the operator family from TouchDesigner's UI.
        """
        fam_registry = self._get_or_create_fam_registry()
        if fam_registry and hasattr(fam_registry, 'UnregisterFamily'):
            fam_registry.UnregisterFamily(self.ownerComp)

    # ==================== Private Install Helpers ====================

    def _get_or_create_fam_registry(self, force=False):
        """Get or create the central opFamUI manager."""
        # Check if already installed at global location
        sys_registry_path = '/sys/opFamRegistry'
        sys_registry = op(sys_registry_path)
        
        internal = self.ownerComp.op('internal_pars')
        if internal and not force: # caller's force takes precedence
            force = internal.par.Force.eval()

        if force and sys_registry:
            sys_registry.destroy()
            sys_registry = None

        if not sys_registry:
            # Copy from our template
            template = self.ownerComp.op('opFamRegistry')

            if template:
                sys = op('/sys')
                if sys:
                    sys_registry = sys.copy(template, name='opFamRegistry')
                    sys_registry.allowCooking = True
                    sys_registry.nodeX = sys.op('TDDialogs').nodeX
                    sys_registry.nodeY = sys.op('TDDialogs').nodeY - 200

        if sys_registry:
            sys_registry.par.opshortcut = 'FAMREGISTRY'

        return sys_registry

    # ==================== Dynamic Update Methods ====================

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

        # 1. Update registration in central UI manager
        ui_manager = op('/ui/dialogs/mainmenu/opFamUI')
        if ui_manager and hasattr(ui_manager, 'UpdateFamilyName'):
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
