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
from __future__ import annotations
import time
from TDStoreTools import DependDict

FileLoader = mod('src/file_loader').FileLoader
ConfigManager = mod('src/config_system').ConfigManager


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
                 operators_comp=None, operators_folder=None, dynamic_refresh=False,
                 install_location=None, node_x=0, node_y=0, expose=True):
        """
        Initialize the operator family installer.

        Args:
            ownerComp: The component this extension is attached to
            family_name: Name of the operator family (e.g., 'LOP', 'FAV')
            color: Family color as [r, g, b] or [r, g, b, a]
            compatible_types: List of compatible TD families (e.g., ['COMP', 'TOP'])
            connection_map: Dict mapping (from_family, to_family) -> connector type
            operators_comp: COMP containing embedded operators (optional)
            operators_folder: Path to external .tox folder (optional)
            dynamic_refresh: If True, scan folder on every placement
            install_location: Target parent for installer. Defaults to op('/')
            node_x: X position for installer node
            node_y: Y position for installer node
            expose: Whether to expose the installer
        """
        print(f"Initializing OpFamCreateExt for {family_name}")

        self.ownerComp = ownerComp

        # Single source of truth for family properties
        self.Properties = DependDict({
            'family_name': family_name,
            'color': list(color) if color else [0.5, 0.5, 0.5],
            'index': 0,
            'operators_comp': operators_comp,
            'operators_folder': operators_folder,
            'folder_cache': {},
            'installed': False,
            'dynamic_refresh': dynamic_refresh,
            'compatible_types': compatible_types or [],
            'naming_convention': r'(.+)_v(\d+\.\d+\.\d+)\.tox$',  # Default: name_vX.Y.Z.tox
        })

        # Single source of truth for config (matches JSON import/export structure)
        self.Config = DependDict({
            'group_mapping': {},
            'replace_index': {},
            'os_incompatible': {},
            'relabel_index': {},
            'settings': {},
        })

        # Non-reactive config (not in Properties)
        self.connection_map = connection_map or {}
        self.install_location = install_location if install_location else op('/')
        self.node_x = node_x
        self.node_y = node_y
        self.expose = expose

        # Initialize subsystems (they read from Properties)
        self.file_loader = FileLoader(self)
        self.config = ConfigManager(self)

        # Ensure config tables exist with proper headers
        self.config.ensure_tables_exist()

        # Sync DAT tables to Config DependDict (populates Config from existing tables)
        self.config.sync_tables_to_config()

        # Build initial cache if folder set
        if self.operators_folder and not self.dynamic_refresh:
            self.file_loader.refresh_cache(self.operators_folder)

        # Debouncing for recursive installation prevention
        self.last_install_time = 0
        self.install_cooldown = 2.0

        self.fam_registry = None

        # Run post init actions
        run(lambda: self.postInitInstaller(), endFrame=True, delayRef=op.TDResources)


    def postInitInstaller(self):
        try:
            self.fam_registry : OpFamRegistryExt = self._get_or_create_fam_registry()
        except Exception as e:
            print(f"Failed to create or get fam registry: {e}")

        if self.fam_registry:
            self.fam_registry.RegisterFamily(self.ownerComp)

        # Check for existing installers and set up
        self._initialize_installer()

    # ==================== Property Accessors (Backwards Compatibility) ====================

    @property
    def FamilyName(self):
        """Backwards compatible accessor - returns dependency for expressions."""
        return self.Properties.getDependency('family_name')

    @property
    def color(self):
        """Get family color from Properties."""
        return self.Properties['color']

    @color.setter
    def color(self, value):
        """Set family color in Properties."""
        self.Properties['color'] = list(value) if value else [0.5, 0.5, 0.5]

    @property
    def operators_comp(self):
        """Get operators COMP from Properties."""
        return self.Properties['operators_comp']

    @operators_comp.setter
    def operators_comp(self, value):
        """Set operators COMP in Properties."""
        self.Properties['operators_comp'] = value

    @property
    def operators_folder(self):
        """Get operators folder path from Properties."""
        return self.Properties['operators_folder']

    @operators_folder.setter
    def operators_folder(self, value):
        """Set operators folder path in Properties."""
        self.Properties['operators_folder'] = value

    @property
    def dynamic_refresh(self):
        """Get dynamic refresh setting from Properties."""
        return self.Properties['dynamic_refresh']

    @dynamic_refresh.setter
    def dynamic_refresh(self, value):
        """Set dynamic refresh setting in Properties."""
        self.Properties['dynamic_refresh'] = value

    @property
    def compatible_types(self):
        """Get compatible types from Properties."""
        return self.Properties['compatible_types']

    @compatible_types.setter
    def compatible_types(self, value):
        """Set compatible types in Properties."""
        self.Properties['compatible_types'] = value or []

    @property
    def naming_convention(self):
        """Get naming convention regex from Properties."""
        return self.Properties['naming_convention']

    @naming_convention.setter
    def naming_convention(self, value):
        """Set naming convention regex in Properties."""
        self.Properties['naming_convention'] = value

    @property
    def FolderCache(self):
        """Get folder cache dependency for expressions."""
        return self.Properties.getDependency('folder_cache')

    @property
    def ShortcutComp(self):
        """Get the component that receives the op shortcut. Override in extension."""
        return self.ownerComp

    def get_installer_expr(self, fam_name):
        """Build expression path to installer. Override in extension for custom behavior."""
        return f'op.{fam_name}'

    def _initialize_installer(self):
        """Initialize installer position and check for duplicates."""
        # Check if global shortcut already exists and points to ANOTHER component
        existing = getattr(op, self.FamilyName.val, None)
        if existing is not None and existing != self.ownerComp:
            ui.messageBox(self.FamilyName.val,
                f"{self.FamilyName.val} already exists at {existing.path}!\n\nDisabling this installer.")
            # Turn off Install parameter instead of destroying
            if hasattr(self.ownerComp.par, 'Install'):
                self.ownerComp.par.Install = False
            return

        # Set up this installer
        self.ownerComp.expose = self.expose
        self.ownerComp.nodeX = self.node_x
        self.ownerComp.nodeY = self.node_y
        self.ShortcutComp.par.opshortcut = self.FamilyName.val

        if self.ownerComp.par.Install == 1:
            if not self.fam_registry.IsFamilyInstalled(self.FamilyName.val):
                current_time = time.time()
                if current_time - self.last_install_time >= self.install_cooldown:
                    self.Install()

    def _get_or_create_fam_registry(self, force=False):
        """Get or create the core system fam registry."""
        # Check if already installed at global location
        sys_registry_path = '/sys/OpFamRegistry'
        sys_registry = op(sys_registry_path)
        
        internal = self.ownerComp.op('internal_pars')
        if internal and not force: # caller's force takes precedence
            force = internal.par.Force.eval()

        previous_registered_fams = {}
        previous_installed_fams = {}
        if force and sys_registry:
            # get previous registry elements to be readded later
            previous_registered_fams = sys_registry.RegisteredFams
            previous_installed_fams = sys_registry.InstalledFams
            sys_registry.destroy()
            sys_registry = None

        if not sys_registry:
            # Copy from our template
            template = self.ownerComp.op('OpFamRegistry')

            if template:
                sys = op('/sys')
                if sys:
                    sys_registry = sys.copy(template, name='OpFamRegistry')
                    sys_registry.allowCooking = True
                    sys_registry.nodeX = sys.op('TDDialogs').nodeX
                    sys_registry.nodeY = sys.op('TDDialogs').nodeY - 200

        if sys_registry:
            sys_registry.par.opshortcut = 'FAMREGISTRY'
            for family in previous_registered_fams.values():
                sys_registry.RegisterFamily(family)
            for family in previous_installed_fams.values():
                sys_registry.InstallFamily(family)
            
        return sys_registry

    # ==================== Public API ====================

    def Install(self):
        """Install the operator family into TouchDesigner's UI."""
        self._call_hook('_PreInstall')
        self.last_install_time = time.time()

        if self.operators_folder:
            self.file_loader.refresh_cache(self.operators_folder)
        self.fam_registry.InstallFamily(self.ownerComp)
        self._call_hook('_PostInstall')

    def Uninstall(self):
        """Uninstall the operator family from TouchDesigner's UI."""
        self._call_hook('_PreUninstall')
        self.fam_registry.UninstallFamily(self.ownerComp)
        # TODO: do we check return and only then call the post?
        self._call_hook('_PostUninstall')

    def TagOperators(self, pattern='suffix'):
        """
        Tag all operators in custom_operators with family and type tags.

        Args:
            pattern: Tag pattern for type tags:
                     'suffix' - {opname}{Family} (e.g., agentLOP)
                     'name' - just operator name as tag
        """
        self.fam_registry.TagManager.tag_operators(self, pattern)

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

    # ==================== Setup API ====================

    def Createopcomp(self, name='custom_operators'):
        """
        Create a disabled base COMP at sibling level for embedded operators.

        If par.Opcomp already references a comp, prompts user to:
        - Replace: update par.Opcomp to new comp
        - Keep: keep new comp but don't update parameter
        - Cancel: delete the new comp

        Args:
            name: Base name for the comp (will version if exists)

        Returns:
            The created COMP or None if cancelled
        """
        ui.undo.startBlock('Create Operators COMP')

        parent_comp = self.ownerComp.parent()

        # Version the name if it exists
        final_name = name
        version = 1
        while parent_comp.op(final_name):
            version += 1
            final_name = f"{name}{version}"

        # Create the comp
        ops_comp = parent_comp.create(baseCOMP, final_name)
        ops_comp.nodeX = self.ownerComp.nodeX + 250
        ops_comp.nodeY = self.ownerComp.nodeY
        ops_comp.allowCooking = False  # Disable it

        # Check if Opcomp parameter already has a value
        existing_opcomp = None
        if hasattr(self.ownerComp.par, 'Opcomp'):
            existing_opcomp = self.ownerComp.par.Opcomp.eval()

        if existing_opcomp:
            choice = ui.messageBox(
                'Opcomp Already Set',
                f'par.Opcomp already references:\n{existing_opcomp.path}\n\nWhat would you like to do?',
                buttons=['Replace', 'Keep Both', 'Cancel']
            )

            if choice == 0:  # Replace
                self.ownerComp.par.Opcomp = ops_comp
                self.Properties['operators_comp'] = ops_comp
            elif choice == 1:  # Keep Both
                pass  # Keep new comp but don't update parameter
            else:  # Cancel
                ops_comp.destroy()
                ui.undo.endBlock()
                return None
        else:
            # No existing, just set it
            if hasattr(self.ownerComp.par, 'Opcomp'):
                self.ownerComp.par.Opcomp = ops_comp
            self.Properties['operators_comp'] = ops_comp

        ui.undo.endBlock()
        return ops_comp

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
        category_tags = self._call_hook('_GetCategoryTags') or set()
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
        operators = self.fam_registry.UpdateManager.find_family_operators(self)

        if not operators:
            ui.messageBox("No Operators Found", f"No {self.FamilyName.val} operators found.", buttons=["OK"])
            return

        analysis = self.fam_registry.UpdateManager.analyze_operators(self, operators)

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

        results = self.fam_registry.UpdateManager.update_batch(self, analysis['updateable'])

        summary = f"Updated: {len(results['updated'])}\n"
        summary += f"Skipped: {len(results['skipped'])}\n"
        summary += f"Errors: {len(results['errors'])}"
        ui.messageBox('Update Complete', summary, buttons=["OK"])

    # ==================== Hooks ====================

    def CallHook(self, hook_name, *args):
        """
        Public method for external code to trigger hooks.

        Args:
            hook_name: Name of the hook (e.g., '_PlaceOp')
            *args: Arguments to pass to the hook

        Returns:
            Hook return value, or 'nohook' if hook not defined
        """
        hook = getattr(self, hook_name, None)
        if hook and callable(hook):
            return hook(*args)
        return 'nohook'

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
