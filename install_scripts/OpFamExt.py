"""
OpFamExt - Main extension for operator family installers.

This is the primary extension class for opfam-create operator families.
It manages parameter bindings, UI confirmations, and callback orchestration.

For developers creating custom operator families:
    - This file is relatively safe to edit for advanced customization
    - However, callbacks are the preferred way to inject custom logic
    - Implement callbacks in the DAT referenced by par.Callbackdat
    - Other opfam-create code (installer.py, OpFamRegistry, etc.) should be left untouched

Available Callbacks (implement in par.Callbackdat):
    Installation:   onPreInstall, onPostInstall, onPreUninstall, onPostUninstall
    Placement:      onPlaceOp, onPostPlaceOp
    Stubs:          onPreStub, onPostStub, onPreReplace, onPostReplace
    Updates:        onPreUpdate, onPostUpdate, onPreserveSpecialParams
    Configuration:  onGetExcludedTags, onGetCategoryTags, onCaptureChildrenParams
"""

OpFamCreateExt = mod('installer').OpFamCreateExt
ChainedCallbacksExt = mod('src/chained_callbacks').ChainedCallbacksExt


class OpFamExt(ChainedCallbacksExt, OpFamCreateExt):

    def __init__(self, ownerComp, auto_init=True):
        self.ownerComp = ownerComp

        if auto_init:
            ChainedCallbacksExt.__init__(self, ownerComp)

            OpFamCreateExt.__init__(
                self,
                ownerComp=ownerComp,
                family_name=ownerComp.par.Family.eval(),
                color=[0.5, 0.5, 0.5],
                install_location=ownerComp.parent()
            )

            self._sync_parameters()

            if self.operators_folder and not self.dynamic_refresh and self.fam_registry:
                self.fam_registry.FileManager.refresh_cache(self.Properties['family_name'], self.operators_folder)

        run(lambda: self._post_init_ext(), delayFrames=2)

    def _post_init_ext(self):
        if self.ownerComp.par.Install.eval():
            self._do_install()

    def _sync_parameters(self):
        p = self.ownerComp.par

        if hasattr(p, 'Family'):
            self.Properties['family_name'] = p.Family.eval()
        if hasattr(p, 'Colorr'):
            self.Properties['color'] = [p.Colorr.eval(), p.Colorg.eval(), p.Colorb.eval()]
        if hasattr(p, 'Index'):
            self.Properties['index'] = int(p.Index.eval())
        if hasattr(p, 'Opcomp'):
            self.Properties['operators_comp'] = p.Opcomp.eval()
        if hasattr(p, 'Opfolder'):
            self.Properties['operators_folder'] = p.Opfolder.eval()
        if hasattr(p, 'Namingconvention'):
            self.Properties['naming_convention'] = p.Namingconvention.eval()

    # region Properties

    @property
    def index(self):
        return self.Properties['index']

    @index.setter
    def index(self, value):
        self.Properties['index'] = int(value)

    @property
    def shortcut_mode(self):
        if hasattr(self.ownerComp.par, 'Shortcutcomp'):
            return self.ownerComp.par.Shortcutcomp.eval()
        return 'me'

    @property
    def ShortcutComp(self):
        mode = self.shortcut_mode
        if mode == 'me':
            return self.ownerComp
        elif mode == 'parent()':
            return self.ownerComp.parent()
        elif mode == 'parent(2)':
            return self.ownerComp.parent().parent()
        return self.ownerComp

    def get_installer_expr(self, fam_name):
        mode = self.shortcut_mode
        if mode == 'me':
            return f'op.{fam_name}'
        elif mode == 'parent()':
            return f"op.{fam_name}.op('{self.ownerComp.name}')"
        elif mode == 'parent(2)':
            parent_name = self.ownerComp.parent().name
            return f"op.{fam_name}.op('{parent_name}').op('{self.ownerComp.name}')"
        return f'op.{fam_name}'

    # endregion

    # region Exposed API

    def Install(self, install: bool = None):
        """
        Install or uninstall the family.

        Args:
            install: If None, uses Install parameter. If bool, installs/uninstalls.
        """
        if install is None:
            install = self.ownerComp.par.Install.eval()
        if install:
            self._do_install()
        else:
            self._do_uninstall()

    def ExportConfig(self, path: str = None):
        """
        Export config to JSON.

        Args:
            path: Output file path. If None, returns config dict.

        Returns:
            dict if no path, else (success, message)
        """
        config = self._export_config(path)
        return config

    def ImportConfig(self, source: str | dict):
        """
        Import config from JSON.

        Args:
            source: File path, JSON string, or dict

        Returns:
            (success, message)
        """
        success, message = self._import_config(source)
        return success, message

    def GetOperatorSource(self, lookup_name: str):
        """
        Get operator source for a given name.

        Args:
            lookup_name: Operator name (lowercase)

        Returns:
            ('embedded', op) or ('file', path) or None
        """
        return self._get_operator_source(lookup_name)

    # endregion

    # region Parameter Handlers

    def onParInstall(self):
        if self.ownerComp.par.Install.eval():
            self._do_install()
        else:
            self._do_uninstall()

    def onParFamily(self):
        old_name = self.Properties['family_name']
        new_name = self.ownerComp.par.Family.eval()
        if old_name != new_name:
            if self.fam_registry:
                self.fam_registry.UpdateFamilyName(old_name, new_name)
            self.Properties['family_name'] = new_name

    def onParColor(self):
        p = self.ownerComp.par
        color = [p.Colorr.eval(), p.Colorg.eval(), p.Colorb.eval()]
        self.Properties['color'] = color
        if self.fam_registry:
            self.fam_registry.UpdateFamilyColor(self.Properties['family_name'], color)

    def onParIndex(self):
        self.Properties['index'] = int(self.ownerComp.par.Index.eval())

    def onParOpcomp(self):
        self.Properties['operators_comp'] = self.ownerComp.par.Opcomp.eval()

    def onParOpfolder(self):
        self.Properties['operators_folder'] = self.ownerComp.par.Opfolder.eval()
        self._refresh_folder()

    def onParShortcutcomp(self):
        self.ShortcutComp.par.opshortcut = self.FamilyName.val

    def onParNamingconvention(self):
        self.Properties['naming_convention'] = self.ownerComp.par.Namingconvention.eval()
        self._refresh_folder()

    def onParColorfileops(self):
        pass

    def onParCreateopcomp(self):
        comp, existing = self._create_opcomp()
        if existing:
            choice = ui.messageBox('Opcomp Exists',
                f'par.Opcomp already references:\n{existing.path}\n\nReplace?',
                buttons=['Replace', 'Keep Both', 'Cancel'])
            if choice == 0:
                self.ownerComp.par.Opcomp = comp
                self.Properties['operators_comp'] = comp
            elif choice == 2:
                comp.destroy()
                return
        else:
            if hasattr(self.ownerComp.par, 'Opcomp'):
                self.ownerComp.par.Opcomp = comp
            self.Properties['operators_comp'] = comp

    def onParTagoperators(self):
        self._tag_operators()

    def onParCreatestubop(self):
        target = self.ownerComp.par.Targetop.eval()
        if target:
            self._create_stub(target)

    def onParReplacestubop(self):
        target = self.ownerComp.par.Targetop.eval()
        if target:
            self._replace_stub(target)

    def onParUpdateop(self):
        target = self.ownerComp.par.Targetop.eval()
        if target:
            self._update_operator(target)

    def onParCreatestubscomp(self):
        comp = self.ownerComp.par.Targetcomp.eval()
        if not comp:
            return
        operators = self._find_family_operators(comp)
        if not operators:
            ui.messageBox('No Operators', f'No {self.FamilyName.val} operators found.', buttons=['OK'])
            return
        self._create_stubs_batch(operators)

    def onParReplacestubcomp(self):
        comp = self.ownerComp.par.Targetcomp.eval()
        if not comp:
            return
        stubs = self._find_stubs(comp)
        if not stubs:
            ui.messageBox('No Stubs', f'No {self.FamilyName.val} stubs found.', buttons=['OK'])
            return
        self._replace_stubs_batch(stubs)

    def onParUpdatecomp(self):
        comp = self.ownerComp.par.Targetcomp.eval()
        if not comp:
            return
        operators = self._find_family_operators(comp)
        if not operators:
            ui.messageBox('No Operators', f'No {self.FamilyName.val} operators found.', buttons=['OK'])
            return
        self._update_with_ui(operators)

    def onParCreatestuball(self):
        operators = self._find_family_operators()
        if not operators:
            ui.messageBox('No Operators', f'No {self.FamilyName.val} operators found.', buttons=['OK'])
            return

        untagged = self._check_missing_tags(operators)
        if untagged:
            choice = ui.messageBox('Missing Tags',
                f'{len(untagged)} operators lack type tags. Proceed anyway?',
                buttons=['Proceed', 'Cancel'])
            if choice != 0:
                return

        choice = ui.messageBox('Create Stubs',
            f'Create stubs for {len(operators)} operator(s)?',
            buttons=['Create', 'Cancel'])
        if choice != 0:
            return

        stubs = self._create_stubs_batch(operators)
        ui.messageBox('Done', f'Created {len(stubs)} stub(s).', buttons=['OK'])

    def onParReplacestuball(self):
        stubs = self._find_stubs()
        if not stubs:
            ui.messageBox('No Stubs', f'No {self.FamilyName.val} stubs found.', buttons=['OK'])
            return

        choice = ui.messageBox('Replace Stubs',
            f'Regenerate {len(stubs)} operator(s)?',
            buttons=['Regenerate', 'Cancel'])
        if choice != 0:
            return

        regenerated = self._replace_stubs_batch(stubs)
        ui.messageBox('Done', f'Regenerated {len(regenerated)} operator(s).', buttons=['OK'])

    def onParUpdateall(self):
        operators = self._find_family_operators()
        if not operators:
            ui.messageBox('No Operators', f'No {self.FamilyName.val} operators found.', buttons=['OK'])
            return
        self._update_with_ui(operators)

    def onParCreatecallbacks(self):
        template = self.ownerComp.op('callback_template')
        callbacks_dat = self.CreateCallbackDat(self.ownerComp, template)
        if callbacks_dat and hasattr(self.ownerComp.par, 'Callbackdat'):
            self.ownerComp.par.Callbackdat = callbacks_dat

    # endregion

    # region Helpers

    def _update_with_ui(self, operators):
        analysis = self._analyze_for_update(operators)

        if analysis['without_matches']:
            choice = ui.messageBox('Missing Matches',
                f"{len(analysis['without_matches'])} operators can't be matched. Skip them?",
                buttons=['Continue', 'Cancel'])
            if choice != 0:
                return

        updateable = len(analysis['updateable'])
        choice = ui.messageBox('Update',
            f'Update {updateable} operator(s)?',
            buttons=['Update', 'Cancel'])
        if choice != 0:
            return

        results = self._update_batch(analysis['updateable'])

        summary = f"Updated: {len(results['updated'])}\n"
        summary += f"Skipped: {len(results['skipped'])}\n"
        summary += f"Errors: {len(results['errors'])}"
        ui.messageBox('Done', summary, buttons=['OK'])

    # endregion
