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

            run('args[0]._update_compatible_types_menu()', self, delayFrames=1)

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
        if hasattr(p, 'Compatibletypes'):
            self.Properties['compatible_types'] = self._parse_compatible_types(p.Compatibletypes.eval())

    # region Properties

    @property
    def index(self):
        return self.Properties['index']

    @index.setter
    def index(self, value):
        self.Properties['index'] = int(value)

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
            debug(f'Uninstalling family... from {self.ownerComp.path}')
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

    def GetOperators(self):
        """
        Get all available operators in this family with full metadata.

        Returns:
            dict: Keyed by op_type. Each value contains:
                op_type, op_name, op_label, op_version, fam_version,
                op_fam, group, source (tuple), os_compatible
        """
        return self._get_operators()

    def PlaceOp(self, target, op_type, name=None, x=None, y=None):
        """
        Programmatically place an operator into a target COMP.
        Triggers the full FamManifest + callback chain (onPlaceOp, onPostPlaceOp).

        Args:
            target: The COMP to place the operator into (OP or path string).
            op_type: Operator type name (as shown in the OP Create menu).
            name: (Optional) Name for the placed operator.
            x: (Optional) Node X position in the target network.
            y: (Optional) Node Y position in the target network.

        Returns:
            OP: The placed operator, or None if placement was cancelled/failed.
        """
        if not self.fam_registry:
            debug(f'PlaceOp: No registry available for {self.FamilyName.val}')
            return None
        return self.fam_registry.PlaceOp(self.FamilyName.val, target, op_type, name=name, x=x, y=y)

    def FindOps(self, type=None, name=None, path=None,
                depth=None, maxDepth=None,
                tags=[], allTags=False,
                parValue=None, parExpr=None, parName=None,
                key=None,
                include_stubs=False, network=None):
        """
        Find placed operators of this family. Mirrors TD's findChildren API.

        Examples:
            installer.FindOps(name='agent*')
            installer.FindOps(type=COMP, key=lambda o: o.par.Version.eval() > '1.0')
            installer.FindOps(parName='Version', parValue='2.0.0')
            installer.FindOps(network=op('/project1'), maxDepth=2)

        Returns:
            list: Matching placed family operators
        """
        return self._find_ops(
            type=type, name=name, path=path,
            depth=depth, maxDepth=maxDepth,
            tags=tags, allTags=allTags,
            parValue=parValue, parExpr=parExpr, parName=parName,
            key=key, include_stubs=include_stubs, network=network
        )

    def StubOp(self, comp):
        """Create a lightweight stub from a placed operator.

        Args:
            comp: The operator to stub (OP or path string)

        Returns:
            The stub component, or None if skipped
        """
        return self._create_stub(comp)

    def UpdateOp(self, comp):
        """Update a single operator to the newest version.

        Args:
            comp: The operator to update (OP or path string)

        Returns:
            tuple: (success, message)
        """
        return self._update_operator(comp)

    # endregion

    # region Parameter Handlers

    def onParInstall(self):
        self.Install()

    def onParFamily(self):
        new_name = self.ownerComp.par.Family.eval()
        if self.fam_registry:
            # The registry handles updating self.Properties['family_name'] and other logic
            if not self.fam_registry.UpdateFamilyName(self.ownerComp, new_name):
                # Revert parameter if registry rejected the update, try to reinit/register with new name
                self.ownerComp.par.reinitextensions.pulse()
                # 

    def onParColor(self):
        p = self.ownerComp.par
        color = [p.Colorr.eval(), p.Colorg.eval(), p.Colorb.eval()]
        if self.fam_registry:
            # The registry handles updating global UI, we update local property
            if not self.fam_registry.UpdateFamilyColor(self.ownerComp, color):
                # Revert parameters if registry rejected the update
                old_color = self.Properties['color']
                p.Colorr, p.Colorg, p.Colorb = old_color
                ui.messageBox('Update Failed', f'Registry rejected color change for {self.ownerComp.name}. Check for owner mismatch.', buttons=['OK'])
                return
        
        self.Properties['color'] = color

    def onParIndex(self):
        self.Properties['index'] = int(self.ownerComp.par.Index.eval())

    def onParOpcomp(self):
        self.Properties['operators_comp'] = self.ownerComp.par.Opcomp.eval()

    def onParOpfolder(self):
        self.Properties['operators_folder'] = self.ownerComp.par.Opfolder.eval()
        self._refresh_folder()

    def onParNamingconvention(self):
        self.Properties['naming_convention'] = self.ownerComp.par.Namingconvention.eval()
        self._refresh_folder()

    def onParColorfileops(self):
        pass

    def onParCompatibletypes(self):
        self.Properties['compatible_types'] = self._parse_compatible_types(
            self.ownerComp.par.Compatibletypes.eval()
        )

    def _parse_compatible_types(self, value):
        """Parse space or comma-separated compatible types string into list."""
        if not value:
            return []
        # Support both space-separated (StrMenu) and comma-separated
        if ',' in value:
            items = value.split(',')
        else:
            items = value.split()
        return [t.strip() for t in items if t.strip()]

    def _update_compatible_types_menu(self):
        """Update Compatibletypes parameter menu with TD families + registered custom families."""
        if not hasattr(self.ownerComp.par, 'Compatibletypes'):
            return
        td = [x for x in families.keys()]
        custom = [x for x in self.fam_registry.GetAllFamilies().keys()] if self.fam_registry else []
        menu = td + custom
        self.ownerComp.par.Compatibletypes.menuNames = menu
        self.ownerComp.par.Compatibletypes.menuLabels = menu

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
        # TODO X: remove
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

    def onParDeploymanifests(self):
        if not self.fam_registry:
            debug('Deploy Manifests: Family not registered')
            return
        count = self.fam_registry.OpManager.deployManifests(self.ownerComp)
        print(f'Deploy Manifests: Deployed to {count} operator(s)')

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
