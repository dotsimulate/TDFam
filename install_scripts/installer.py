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
            'replace_index': {},
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

    @property
    def ShortcutComp(self):
        return self.ownerComp

    def get_installer_expr(self, fam_name):
        return f'op.{fam_name}'

    # endregion

    # region Initialization

    def _initialize_installer(self):
        existing = getattr(op, self.FamilyName.val, None)
        if existing is not None and existing != self.ownerComp:
            if hasattr(self.ownerComp.par, 'Install'):
                self.ownerComp.par.Install = False
            return (False, f"{self.FamilyName.val} already exists at {existing.path}")

        self.ownerComp.expose = self.expose
        self.ownerComp.nodeX = self.node_x
        self.ownerComp.nodeY = self.node_y
        self.ShortcutComp.par.opshortcut = self.FamilyName.val

        if self.ownerComp.par.Install == 1:
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

        previous_registered_fams = {}
        previous_installed_fams = {}
        if force and sys_registry:
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
            self.FamilyName.val,
            lookup_name,
            self.operators_folder,
            self.dynamic_refresh
        )

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
        return self.fam_registry.StubManager.find_family_operators(self.FamilyName.val, scope)

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

        if self.FamilyName.val not in comp.tags:
            return None

        if f"{self.FamilyName.val}stub" in str(comp.tags):
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
