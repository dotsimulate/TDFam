"""
OpFamCreate - Flexible operator family installer for TouchDesigner.

This module provides OpFamCreateExt, a base class for creating custom
operator families that integrate with TouchDesigner's TAB menu system.

Usage:
    OpFamCreateExt = mod('install_scripts/installer').OpFamCreateExt

    class MyFamilyEXT(OpFamCreateExt):
        def __init__(self, ownerComp):
            super().__init__(
                ownerComp,
                family_name='MYFAM',
                color=[0.3, 0.5, 0.7]
            )

MIT License - Based on work by Josef Pelz
"""

import time

FileLoader = mod('src/file_loader').FileLoader
ConfigManager = mod('src/config_system').ConfigManager
StubManager = mod('src/stub_system').StubManager
UpdateManager = mod('src/update_system').UpdateManager
UIInjector = mod('src/ui_injection').UIInjector


class OpFamCreateExt:
    """
    Base class for creating custom operator families in TouchDesigner.

    Features:
    - TAB menu integration
    - File-based and embedded operator loading
    - Stub system for performance optimization
    - Operator updates
    - JSON config import/export
    - Hook system for wrapper customization

    Subclass this and override hooks as needed.
    """

    def __init__(self, ownerComp, family_name, color,
                 compatible_types=None, connection_map=None,
                 operators_folder=None, dynamic_refresh=False,
                 install_location=None, node_x=0, node_y=0, expose=True):
        """
        Initialize the operator family installer.

        Args:
            ownerComp: The component this extension is attached to
            family_name: Name of the operator family (e.g., 'LOP', 'FAV')
            color: Family color as [r, g, b] or [r, g, b, a]
            compatible_types: List of compatible TD families (e.g., ['COMP', 'TOP'])
            connection_map: Dict mapping (from_family, to_family) -> connector type
            operators_folder: Path to external .tox folder (optional)
            dynamic_refresh: If True, scan folder on every placement
            install_location: Target parent for installer. Defaults to op('/')
            node_x: X position for installer node
            node_y: Y position for installer node
            expose: Whether to expose the installer
        """
        print(f"Initializing OpFamCreateExt for {family_name}")

        self.ownerComp = ownerComp
        # Capitalized for promotion - accessible via comp.FamilyName
        self.FamilyName = tdu.Dependency(family_name)
        self.color = color
        self.compatible_types = compatible_types or []
        self.connection_map = connection_map or {}

        # Installer placement config
        self.install_location = install_location if install_location else op('/')
        self.node_x = node_x
        self.node_y = node_y
        self.expose = expose

        # File-based loading config
        self.operators_folder = operators_folder
        self.dynamic_refresh = dynamic_refresh

        # Initialize subsystems
        self.file_loader = FileLoader(self)
        self.config = ConfigManager(self)
        self.stubs = StubManager(self)
        self.updates = UpdateManager(self)
        self.ui = UIInjector(self)

        # Expose FolderCache for fam_create_callback compatibility
        self.FolderCache = self.file_loader.cache

        # Build initial cache if folder set
        if self.operators_folder and not self.dynamic_refresh:
            self.file_loader.refresh_cache(self.operators_folder)

        # Debouncing for recursive installation prevention
        self.last_install_time = 0
        self.install_cooldown = 2.0

        # Check for existing installers and set up
        self._initialize_installer()

    def _initialize_installer(self):
        """Initialize installer position and check for duplicates."""
        self.ownerComp.par.opshortcut = ''

        if hasattr(op, self.FamilyName.val):
            ui.messageBox(self.FamilyName.val, f"{self.FamilyName.val} exists already!")
            run("args[0].selfDestroy()", self, endFrame=True, delayRef=op.TDResources)
            return

        if self.ownerComp.parent() != self.install_location:
            newInstaller = self.install_location.copy(self.ownerComp)
            newInstaller.cook(force=True)
            run("args[0].selfDestroy()", self, endFrame=True, delayRef=op.TDResources)
            return

        self.ownerComp.expose = self.expose
        self.ownerComp.nodeX = self.node_x
        self.ownerComp.nodeY = self.node_y
        self.ownerComp.par.opshortcut = self.FamilyName.val

        if self.ownerComp.par.Install == 1:
            if self.ui.is_installation_needed():
                current_time = time.time()
                if current_time - self.last_install_time >= self.install_cooldown:
                    self.Install()

    # ==================== Public API ====================

    def Install(self):
        """Install the operator family into TouchDesigner's UI."""
        self.last_install_time = time.time()

        if self.operators_folder:
            self.file_loader.refresh_cache(self.operators_folder)

        self.ui.install()

    def Uninstall(self):
        """Uninstall the operator family from TouchDesigner's UI."""
        self.ui.uninstall()

    def selfDestroy(self):
        """Destroy the installer component."""
        print(f"Destroying {self.FamilyName.val} installer component")
        self.ownerComp.destroy()

    # ==================== File Loading API ====================

    def Getoperatorsource(self, lookup_name):
        """
        Get operator source - embedded or file-based.

        Args:
            lookup_name: Operator name to find (lowercase)

        Returns:
            tuple: ('embedded', op) or ('file', path) or None
        """
        return self.file_loader.get_operator_source(
            lookup_name,
            self.operators_folder,
            self.dynamic_refresh
        )

    def Refreshfolder(self):
        """Rescan external operators folder."""
        self.file_loader.refresh_cache(self.operators_folder)

        op_fam = self.ownerComp.op('OP_fam')
        if op_fam:
            op_fam.cook(force=True)

    # ==================== Config API ====================

    def ImportConfig(self, source):
        """
        Import JSON config.

        Args:
            source: File path, JSON string, or dict

        Returns:
            tuple: (success, message)
        """
        return self.config.import_config(source)

    def ExportConfig(self, path=None):
        """
        Export config to JSON.

        Args:
            path: Output file path (optional)

        Returns:
            If path: (success, message)
            If no path: config dict
        """
        return self.config.export_config(path)

    # ==================== Stub API ====================

    def Createstubs(self):
        """Create stubs for all family operators (with UI confirmation)."""
        operators = self.stubs.find_family_operators()

        if not operators:
            ui.messageBox(
                f"No {self.FamilyName.val} Operators Found",
                f"No {self.FamilyName.val} operators found to create stubs.",
                buttons=["OK"]
            )
            return

        # Check for missing type tags
        has_operator_type_tag = mod('src/tag_helpers').has_operator_type_tag
        category_tags = self._call_hook('GetCategoryTags') or set()
        ops_without_tags = [
            c for c in operators
            if not has_operator_type_tag(c, self.FamilyName.val, category_tags)
        ]

        if ops_without_tags:
            warning = f"WARNING: {len(ops_without_tags)} operators lack proper type tags.\n\n"
            warning += "They may not restore correctly. Proceed anyway?"
            choice = ui.messageBox('Missing Type Tags', warning, buttons=['Proceed', 'Cancel'])
            if choice != 0:
                return

        message = f"Create stubs for {len(operators)} operator(s)?"
        choice = ui.messageBox(f'Create {self.FamilyName.val} Stubs', message, buttons=['Create', 'Cancel'])
        if choice != 0:
            return

        stubs = self.stubs.create_stubs_batch(operators)
        ui.messageBox('Stubs Created', f"Created {len(stubs)} stub(s).", buttons=["OK"])

    def Replacestubs(self):
        """Replace all stubs with full operators (with UI confirmation)."""
        stubs = self.stubs.find_stubs()

        if not stubs:
            ui.messageBox(
                f"No {self.FamilyName.val} Stubs Found",
                f"No {self.FamilyName.val} stubs found.",
                buttons=["OK"]
            )
            return

        message = f"Regenerate {len(stubs)} operator(s) from stubs?"
        choice = ui.messageBox(f'Regenerate {self.FamilyName.val}', message, buttons=['Regenerate', 'Cancel'])
        if choice != 0:
            return

        regenerated = self.stubs.replace_stubs_batch(stubs)
        ui.messageBox('Regeneration Complete', f"Regenerated {len(regenerated)} operator(s).", buttons=["OK"])

    def CreatestubFor(self, operator_path):
        """Create stub for a single operator."""
        comp = op(operator_path)
        if not comp:
            return None

        if self.FamilyName.val not in comp.tags:
            return None

        if f"{self.FamilyName.val}stub" in str(comp.tags):
            return None

        ui.undo.startBlock(f'Create Stub for {comp.name}')
        stub = self.stubs.create_stub(comp)
        comp.destroy()
        ui.undo.endBlock()

        return stub

    def ReplacestubFor(self, stub_path):
        """Replace a single stub with full operator."""
        stub = op(stub_path)
        if not stub:
            return None

        ui.undo.startBlock(f'Replace Stub {stub.name}')
        new_comp = self.stubs.replace_stub(stub)
        ui.undo.endBlock()

        return new_comp

    # ==================== Update API ====================

    def Updateall(self):
        """Update all family operators (with UI confirmation)."""
        operators = self.updates.find_family_operators()

        if not operators:
            ui.messageBox("No Operators Found", f"No {self.FamilyName.val} operators found.", buttons=["OK"])
            return

        analysis = self.updates.analyze_operators(operators)

        if analysis['without_matches']:
            warning = f"{len(analysis['without_matches'])} operators cannot be matched.\n"
            warning += "They will be skipped. Continue?"
            choice = ui.messageBox('Missing Matches', warning, buttons=['Continue', 'Cancel'])
            if choice != 0:
                return

        updateable = len(analysis['updateable'])
        message = f"Update {updateable} operator(s)?"
        choice = ui.messageBox(f'Update {self.FamilyName.val}', message, buttons=['Update', 'Cancel'])
        if choice != 0:
            return

        results = self.updates.update_batch(analysis['updateable'])

        summary = f"Updated: {len(results['updated'])}\n"
        summary += f"Skipped: {len(results['skipped'])}\n"
        summary += f"Errors: {len(results['errors'])}"
        ui.messageBox('Update Complete', summary, buttons=["OK"])

    # ==================== Hooks ====================

    def _call_hook(self, hook_name, *args):
        """
        Call a hook method if defined on this instance.

        Hooks allow wrappers to customize behavior without modifying base code.
        """
        hook = getattr(self, hook_name, None)
        if hook and callable(hook):
            return hook(*args)
        return None

    # Override these in your wrapper as needed:
    #
    # def PlaceOp(self, panelValue, lookup_name):
    #     """Called before operator placement. Return True/False/None."""
    #     return True
    #
    # def PostPlaceOp(self, clone):
    #     """Called after operator is placed."""
    #     pass
    #
    # def PreStub(self, comp):
    #     """Called before creating stub. Return False to skip."""
    #     return True
    #
    # def PostStub(self, stub, original):
    #     """Called after stub created."""
    #     pass
    #
    # def PreReplace(self, stub):
    #     """Called before replacing stub. Return False to skip."""
    #     return True
    #
    # def PostReplace(self, new_comp, stub):
    #     """Called after stub replaced."""
    #     pass
    #
    # def PreUpdate(self, old_comp, master):
    #     """Called before update. Return False to skip."""
    #     return True
    #
    # def PostUpdate(self, new_comp):
    #     """Called after update."""
    #     pass
    #
    # def PreserveSpecialParams(self, new_comp, source):
    #     """Called to preserve special parameters (ramps, etc)."""
    #     pass
    #
    # def GetExcludedTags(self):
    #     """Return set of tags to exclude from batch operations."""
    #     return set()
    #
    # def GetCategoryTags(self):
    #     """Return set of category tags for type detection."""
    #     return set()
