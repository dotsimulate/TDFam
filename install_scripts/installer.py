"""
OpFamCreate - Core library for operator family installation in TouchDesigner.

Properties/Config management and core methods.
No UI (messageBox) - that belongs in OpFamExt.

MIT License - Based on work by Josef Pelz
"""
from __future__ import annotations
import time
from TDStoreTools import DependDict


ConfigManager = mod('src/config_system').ConfigManager


class OpFamCreateExt:

    def __init__(self, ownerComp, family_name, color,
                 compatible_types=None, connection_map=None,
                 operators_comp=None, operators_folder=None, dynamic_refresh=False,
                 install_location=None, node_x=0, node_y=0, expose=True):
        self.ownerComp = ownerComp

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
            'naming_convention': r'(.+)_v(\d+\.\d+\.\d+)\.tox$',
        })

        self.Config = DependDict({
            'group_mapping': {},
            'label_replacements': {},
            'os_incompatible': {},
            'relabel_index': {},
            'settings': {},
        })

        self.connection_map = connection_map or {}
        self.install_location = install_location if install_location else op('/')
        self.node_x = node_x
        self.node_y = node_y
        self.expose = expose

        self.config = ConfigManager(self)
        self.config.ensure_tables_exist()
        self.config.sync_tables_to_config()

        self.last_install_time = 0
        self.install_cooldown = 2.0
        self.fam_registry = None

        run(lambda: self._post_init(), endFrame=True, delayRef=op.TDResources)

    def _post_init(self):
        try:
            self.fam_registry = self._get_or_create_fam_registry()
        except Exception as e:
            print(f"Failed to create or get fam registry: {e}")

        if self.fam_registry:
            if self.fam_registry.RegisterFamily(self.ownerComp):
                if self.operators_folder and not self.dynamic_refresh:
                    self.fam_registry.FileManager.refresh_cache(self.FamilyName.val, self.operators_folder)

                self._initialize_installer()
            else:
                self.ownerComp.par.Install = False
                ui.messageBox("Already Registered", f"Family {self.FamilyName.val} already registered from {self.fam_registry.RegisteredFams[self.FamilyName.val].path}.", buttons=['OK'])

    # region Properties

    @property
    def FamilyName(self):
        return self.Properties.getDependency('family_name')

    @property
    def color(self):
        return self.Properties['color']

    @color.setter
    def color(self, value):
        self.Properties['color'] = list(value) if value else [0.5, 0.5, 0.5]

    @property
    def operators_comp(self):
        return self.Properties['operators_comp']

    @operators_comp.setter
    def operators_comp(self, value):
        self.Properties['operators_comp'] = value

    @property
    def operators_folder(self):
        return self.Properties['operators_folder']

    @operators_folder.setter
    def operators_folder(self, value):
        self.Properties['operators_folder'] = value

    @property
    def dynamic_refresh(self):
        return self.Properties['dynamic_refresh']

    @dynamic_refresh.setter
    def dynamic_refresh(self, value):
        self.Properties['dynamic_refresh'] = value

    @property
    def compatible_types(self):
        return self.Properties['compatible_types']

    @compatible_types.setter
    def compatible_types(self, value):
        self.Properties['compatible_types'] = value or []

    @property
    def naming_convention(self):
        return self.Properties['naming_convention']

    @naming_convention.setter
    def naming_convention(self, value):
        self.Properties['naming_convention'] = value

    @property
    def FolderCache(self):
        return self.Properties.getDependency('folder_cache')

    # endregion

    # region Initialization

    def _initialize_installer(self):
        if not self.fam_registry.ValidateFamilyOwner(self.FamilyName.val, self.ownerComp):
            if hasattr(self.ownerComp.par, 'Install'):
                self.ownerComp.par.Install = False
            return (False, f"{self.FamilyName.val} already exists at {self.fam_registry.GetFamilyOwner(self.FamilyName.val).path}.")

        self.ownerComp.expose = self.expose

        if self.ownerComp.par.Install.eval():
            if not self.fam_registry.IsFamilyInstalled(self.FamilyName.val):
                current_time = time.time()
                if current_time - self.last_install_time >= self.install_cooldown:
                    self._do_install()

        return (True, None)

    def _get_or_create_fam_registry(self, force=False):
        sys_registry_path = '/sys/OpFamRegistry'
        sys_registry = op(sys_registry_path)

        internal = self.ownerComp.op('internal_pars')
        if internal and not force:
            force = internal.par.Force.eval()

        # If registry exists and has equal or greater version (and force is not set), keep it
        if sys_registry and not force and self._check_version(sys_registry):
            return sys_registry

        # If we get here with a registry, it needs to be replaced (force=True or template is newer)
        previous_registered_fams = {}
        previous_installed_fams = {}
        if sys_registry:
            previous_registered_fams = sys_registry.RegisteredFams
            previous_installed_fams = sys_registry.InstalledFams
            sys_registry.destroy()
            sys_registry = None

        if not sys_registry:
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
            for fam_name in previous_installed_fams.keys():
                sys_registry.InstallFamily(fam_name)

        return sys_registry

    def _check_version(self, comp_check_against):
        """
        Compare version of existing registry with template version.

        Args:
            comp_check_against: The existing registry component to check

        Returns:
            bool: True if existing version >= template version (keep existing),
                  False if template version is greater (should update)
        """

        def _parse_version(ver_string):
            """
            Parse version string to tuple for comparison.

            Args:
                ver_string: Version string like "1.2.3" or "v1.2.3"

            Returns:
                tuple: (1, 2, 3) or None if invalid
            """
            if not ver_string:
                return None
            try:
                ver_string = ver_string.lstrip('vV')
                return tuple(int(x) for x in ver_string.split('.'))
            except:
                return None
            
        template = self.ownerComp.op('OpFamRegistry')
        if not template:
            return True  # No template, keep existing

        # Get existing version
        existing_version = None
        if hasattr(comp_check_against.par, 'Version'):
            existing_version = _parse_version(str(comp_check_against.par.Version.eval()))

        # Get template version
        template_version = None
        if hasattr(template.par, 'Version'):
            template_version = _parse_version(str(template.par.Version.eval()))

        # If existing has no version but template does, force overwrite
        if existing_version is None and template_version is not None:
            return False

        # If template has no version, keep existing
        if template_version is None:
            return True

        # If major version differs, prompt user
        if existing_version[0] != template_version[0]:
            existing_str = '.'.join(str(x) for x in existing_version)
            template_str = '.'.join(str(x) for x in template_version)
            choice = ui.messageBox(
                'Major Version Change',
                f'Registry major version change detected.\n\nExisting: v{existing_str}\nNew: v{template_str}\n\nProceed with update?',
                buttons=['Update', 'Keep Existing']
            )
            return choice != 0  # 0 = Update (return False), 1 = Keep Existing (return True)

        # Keep existing if version is >= template version
        return existing_version >= template_version




    # endregion

    # region Core

    def _do_install(self):
        self.last_install_time = time.time()

        if self.operators_folder:
            self.fam_registry.FileManager.refresh_cache(self.FamilyName.val, self.operators_folder)

        self.fam_registry.InstallFamily(self.ownerComp)

    def _do_uninstall(self):
        self.fam_registry.UninstallFamily(self.ownerComp)

    def _tag_operators(self, pattern='suffix'):
        self.fam_registry.TagManager.tag_operators(self.FamilyName.val, pattern)

    def _get_operator_source(self, lookup_name):
        return self.fam_registry.FileManager.get_operator_source(
            self.FamilyName.val, lookup_name
        )

    def _get_operators(self):
        return self.fam_registry.GetOperators(self.FamilyName.val)

    def _refresh_folder(self):
        self.fam_registry.FileManager.refresh_cache(self.FamilyName.val, self.operators_folder)

        op_fam = self.ownerComp.op('OP_fam')
        if op_fam:
            op_fam.cook(force=True)

    def _create_opcomp(self, name='custom_operators'):
        ui.undo.startBlock('Create Operators COMP')

        parent_comp = self.ownerComp.parent()

        final_name = name
        version = 1
        while parent_comp.op(final_name):
            version += 1
            final_name = f"{name}{version}"

        ops_comp = parent_comp.create(baseCOMP, final_name)
        ops_comp.nodeX = self.ownerComp.nodeX + 250
        ops_comp.nodeY = self.ownerComp.nodeY
        ops_comp.allowCooking = False

        existing_opcomp = None
        if hasattr(self.ownerComp.par, 'Opcomp'):
            existing_opcomp = self.ownerComp.par.Opcomp.eval()

        ui.undo.endBlock()
        return (ops_comp, existing_opcomp)

    def _self_destroy(self):
        self.ownerComp.destroy()

    # endregion

    # region Config

    def _import_config(self, source):
        return self.config.import_config(source)

    def _export_config(self, path=None):
        return self.config.export_config(path)

    # endregion

    # region Stubs

    def _find_family_operators(self, scope=None):
        return self.fam_registry.FindOps(self.FamilyName.val, network=scope)

    def _find_ops(self, **kwargs):
        return self.fam_registry.FindOps(self.FamilyName.val, **kwargs)

    def _find_stubs(self, scope=None):
        return self.fam_registry.StubManager.find_stubs(self.FamilyName.val, scope)

    def _check_missing_tags(self, operators):
        category_tags = self.fam_registry.CallHook(self.FamilyName.val, '_GetCategoryTags') or set()
        return [
            c for c in operators
            if not self.fam_registry.TagManager.has_operator_type_tag(c, self.FamilyName.val, category_tags)
        ]

    def _create_stub(self, comp):
        if isinstance(comp, str):
            comp = op(comp)
        if not comp:
            return None

        ui.undo.startBlock(f'Create Stub for {comp.name}')
        stub = self.fam_registry.StubManager.create_stub(self.FamilyName.val, comp)
        ui.undo.endBlock()

        return stub

    def _replace_stub(self, stub):
        if isinstance(stub, str):
            stub = op(stub)
        if not stub:
            return None

        ui.undo.startBlock(f'Replace Stub {stub.name}')
        new_comp = self.fam_registry.StubManager.replace_stub(self.FamilyName.val, stub)
        ui.undo.endBlock()

        return new_comp

    def _create_stubs_batch(self, operators):
        return self.fam_registry.StubManager.create_stubs_batch(self.FamilyName.val, operators)

    def _replace_stubs_batch(self, stubs):
        return self.fam_registry.StubManager.replace_stubs_batch(self.FamilyName.val, stubs)

    # endregion

    # region Updates

    def _analyze_for_update(self, operators):
        return self.fam_registry.UpdateManager.analyze_operators(self.FamilyName.val, operators)

    def _update_operator(self, comp):
        if isinstance(comp, str):
            comp = op(comp)
        if not comp:
            return (False, "No operator specified")

        return self.fam_registry.UpdateManager.update_operator(self.FamilyName.val, comp)

    def _update_batch(self, operators):
        return self.fam_registry.UpdateManager.update_batch(self.FamilyName.val, operators)

    # endregion
