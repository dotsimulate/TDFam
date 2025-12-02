"""
OpFamExt - Middle class extension for opfam-create with integrated callbacks.

This extension lives on the install_scripts COMP and provides:
- Chained callback system (extension + DAT both called)
- Clean public API with exposed methods
- Parameter binding to existing parameters on install_scripts

Expected parameters on install_scripts:
    Family page:
        - Family (str): Family name
        - Install (toggle): Install/uninstall toggle
        - Color (rgb): Family color
        - Index (int): Menu index position
        - Opcomp (COMP): Embedded operators container
        - Opfolder (folder): Path to external .tox files

    Stubs page:
        - Createstubsforall (pulse): Create stubs for all operators
        - Replacestubsforall (pulse): Replace all stubs
        - Updateall (pulse): Update all operators
        - Targetop (str): Target operator path
        - Createstubforop (pulse): Create stub for target op
        - Replacestubforop (pulse): Replace stub for target op
        - Updateop (pulse): Update target operator
        - Targetcomp (str): Target comp path
        - Createstubsincomp (pulse): Create stubs in comp
        - Replacestubsincomp (pulse): Replace stubs in comp
        - Updateopsincomp (pulse): Update ops in comp

Usage:
    # No-code: just use parameters + callback DAT on install_scripts
    # Light wrapper: subclass OpFamExt, call super().__init__(ownerComp)
    # Expert: use SetAssignedCallback('onPlaceOp', self._my_handler) for programmatic callbacks
"""

OpFamCreateExt = mod('installer').OpFamCreateExt
ChainedCallbacksExt = mod('src/chained_callbacks').ChainedCallbacksExt


class OpFamExt(ChainedCallbacksExt, OpFamCreateExt):
    """
    Middle class extension providing callbacks and API for operator families.

    Inherits core logic from OpFamCreateExt and adds:
    - Chained callback system (both assigned + DAT callbacks run)
    - Clean exposed API bound to parameters
    """

    def __init__(self, ownerComp, auto_init=True):
        """
        Initialize OpFamExt.

        Args:
            ownerComp: The install_scripts COMP
            auto_init: If True, read from parameters and call super().__init__
                       If False, skip for manual initialization by subclass
        """
        self.ownerComp = ownerComp

        # install_scripts IS where the parameters live
        self._installer = ownerComp

        if auto_init:
            # Initialize ChainedCallbacksExt (provides callback system)
            ChainedCallbacksExt.__init__(self, self._installer)

            # Initialize OpFamCreateExt with minimal defaults
            # _sync_parameters() will update Properties from actual parameters
            OpFamCreateExt.__init__(
                self,
                ownerComp=self._installer,
                family_name=self._installer.par.Family.eval(),
                color=[0.5, 0.5, 0.5],  # Placeholder, updated by _sync_parameters
                install_location=self._installer.parent()
            )

            # Sync all parameters to Properties registry (the real initialization)
            self._sync_parameters()

            # Auto-tag operators in custom_operators
            self.TagOperators()

    def _sync_parameters(self):
        """Read parameters and update Properties registry."""
        inst = self._installer

        # Family page
        if hasattr(inst.par, 'Family'):
            self.Properties['family_name'] = inst.par.Family.eval()
        if hasattr(inst.par, 'Colorr'):
            self.Properties['color'] = [
                inst.par.Colorr.eval(),
                inst.par.Colorg.eval(),
                inst.par.Colorb.eval()
            ]
        if hasattr(inst.par, 'Index'):
            self.Properties['index'] = int(inst.par.Index.eval())
        if hasattr(inst.par, 'Opcomp'):
            self.Properties['operators_comp'] = inst.par.Opcomp.eval()
        if hasattr(inst.par, 'Opfolder'):
            self.Properties['operators_folder'] = inst.par.Opfolder.eval()
        if hasattr(inst.par, 'Dynamicrefresh'):
            self.Properties['dynamic_refresh'] = bool(inst.par.Dynamicrefresh.eval())
        if hasattr(inst.par, 'Compatibletypes') and inst.par.Compatibletypes.eval():
            types_str = inst.par.Compatibletypes.eval()
            self.Properties['compatible_types'] = [t.strip() for t in types_str.split(',') if t.strip()]

    @property
    def index(self):
        """Get menu index from Properties registry."""
        return self.Properties['index']

    @index.setter
    def index(self, value):
        """Set menu index in Properties registry."""
        self.Properties['index'] = int(value)

    # ==================== Hook Integration (private) ====================

    def _PreInstall(self):
        info = {'about': 'Called before installation'}
        self.DoCallback('onPreInstall', info)

    def _PostInstall(self):
        info = {'about': 'Called after installation'}
        self.DoCallback('onPostInstall', info)

    def _PreUninstall(self):
        info = {'about': 'Called before uninstallation'}
        self.DoCallback('onPreUninstall', info)

    def _PostUninstall(self):
        info = {'about': 'Called after uninstallation'}
        self.DoCallback('onPostUninstall', info)

    def _PlaceOp(self, panelValue, lookup_name):
        info = {
            'panelValue': panelValue,
            'lookupName': lookup_name,
            'about': 'Return True to place, False to cancel+close, None for ActionOp'
        }
        result = self.DoCallback('onPlaceOp', info)
        if result:
            return result.get('returnValue', True)
        return True

    def _PostPlaceOp(self, clone):
        info = {'clone': clone, 'about': 'Customize the placed operator'}
        self.DoCallback('onPostPlaceOp', info)

    def _PreStub(self, comp):
        info = {'comp': comp, 'about': 'Return False to skip stubbing this operator'}
        result = self.DoCallback('onPreStub', info)
        if result:
            return result.get('returnValue', True)
        return True

    def _PostStub(self, stub, original):
        info = {'stub': stub, 'original': original}
        self.DoCallback('onPostStub', info)

    def _PreReplace(self, stub):
        info = {'stub': stub, 'about': 'Return False to skip replacing this stub'}
        result = self.DoCallback('onPreReplace', info)
        if result:
            return result.get('returnValue', True)
        return True

    def _PostReplace(self, new_comp, stub):
        info = {'newComp': new_comp, 'stub': stub}
        self.DoCallback('onPostReplace', info)

    def _PreUpdate(self, old_comp, master):
        info = {'oldComp': old_comp, 'master': master, 'about': 'Return False to skip updating this operator'}
        result = self.DoCallback('onPreUpdate', info)
        if result:
            return result.get('returnValue', True)
        return True

    def _PostUpdate(self, new_comp):
        info = {'newComp': new_comp}
        self.DoCallback('onPostUpdate', info)

    def _PreserveSpecialParams(self, new_comp, source):
        info = {'newComp': new_comp, 'source': source}
        self.DoCallback('onPreserveSpecialParams', info)

    def _GetExcludedTags(self):
        info = {'about': 'Return a set of tag names to exclude'}
        result = self.DoCallback('onGetExcludedTags', info)
        if result and result.get('returnValue'):
            return result['returnValue']
        return set()

    def _GetCategoryTags(self):
        info = {'about': 'Return a set of category tag names'}
        result = self.DoCallback('onGetCategoryTags', info)
        if result and result.get('returnValue'):
            return result['returnValue']
        return set()

    # ==================== Public API (Exposed Methods) ====================
    # All methods accept optional args; if None, use parameter value

    def Install(self, install=None):
        """
        Toggle installation based on Install parameter or argument.

        Args:
            install: If None, uses Install parameter. If bool, installs/uninstalls.
        """
        if install is None:
            install = self._installer.par.Install.eval()
        if install:
            super().Install()
        else:
            super().Uninstall()

    def SetColor(self, r=None, g=None, b=None):
        """
        Set family color and update UI.

        Args:
            r, g, b: Color values 0-1. If None, uses Color parameter values.
        """
        if r is None:
            r = self._installer.par.Colorr.eval()
        if g is None:
            g = self._installer.par.Colorg.eval()
        if b is None:
            b = self._installer.par.Colorb.eval()

        # Update registry - this triggers all dependent expressions
        self.Properties['color'] = [r, g, b]

        # Also update parameters
        self._installer.par.Colorr = r
        self._installer.par.Colorg = g
        self._installer.par.Colorb = b

        if hasattr(self, 'ui') and self.ui:
            self.ui.update_family_color(self.Properties['color'])

    # --- Stub for single operator ---

    def Createstubforop(self, target=None):
        """
        Create stub for a target operator.

        Args:
            target: Operator or path. If None, uses Targetop parameter.

        Returns:
            Created stub COMP or None
        """
        if target is None:
            target = self._installer.par.Targetop.eval()
        if not target:
            print("Createstubforop: No target operator specified")
            return None
        if isinstance(target, str):
            target = op(target)
        return self.stubs.create_stub(target)

    def Replacestubforop(self, stub=None):
        """
        Replace a stub with the full operator.

        Args:
            stub: Stub COMP or path. If None, uses Targetop parameter.

        Returns:
            Replaced COMP or None
        """
        if stub is None:
            stub = self._installer.par.Targetop.eval()
        if not stub:
            print("Replacestubforop: No stub specified")
            return None
        if isinstance(stub, str):
            stub = op(stub)
        return self.stubs.replace_stub(stub)

    def Updateop(self, target=None):
        """
        Update a single operator to latest version.

        Args:
            target: Operator or path. If None, uses Targetop parameter.

        Returns:
            Updated COMP or None
        """
        if target is None:
            target = self._installer.par.Targetop.eval()
        if not target:
            print("Updateop: No target operator specified")
            return None
        if isinstance(target, str):
            target = op(target)
        return self.stubs.update_operator(target)

    # --- Stubs for comp/network ---

    def Createstubsincomp(self, comp=None):
        """
        Create stubs for all family operators in a comp.

        Args:
            comp: Target COMP or path. If None, uses Targetcomp parameter.

        Returns:
            List of created stubs
        """
        if comp is None:
            comp = self._installer.par.Targetcomp.eval()
        if not comp:
            print("Createstubsincomp: No comp specified")
            return []
        if isinstance(comp, str):
            comp = op(comp)
        operators = self.stubs.find_family_operators(comp)
        return self.stubs.create_stubs_batch(operators)

    def Replacestubsincomp(self, comp=None):
        """
        Replace all stubs in a comp with full operators.

        Args:
            comp: Target COMP or path. If None, uses Targetcomp parameter.

        Returns:
            List of replaced COMPs
        """
        if comp is None:
            comp = self._installer.par.Targetcomp.eval()
        if not comp:
            print("Replacestubsincomp: No comp specified")
            return []
        if isinstance(comp, str):
            comp = op(comp)
        stubs = self.stubs.find_stubs(comp)
        return self.stubs.replace_stubs_batch(stubs)

    def Updateopsincomp(self, comp=None):
        """
        Update all family operators in a comp.

        Args:
            comp: Target COMP or path. If None, uses Targetcomp parameter.

        Returns:
            List of updated COMPs
        """
        if comp is None:
            comp = self._installer.par.Targetcomp.eval()
        if not comp:
            print("Updateopsincomp: No comp specified")
            return []
        if isinstance(comp, str):
            comp = op(comp)
        operators = self.stubs.find_family_operators(comp)
        return self.stubs.update_batch(operators)

    # --- Stubs for ALL ---

    def Createstubsforall(self):
        """
        Create stubs for ALL family operators in the project.

        Returns:
            List of created stubs
        """
        operators = self.stubs.find_all_family_operators()
        return self.stubs.create_stubs_batch(operators)

    def Replacestubsforall(self):
        """
        Replace ALL stubs in the project with full operators.

        Returns:
            List of replaced COMPs
        """
        stubs = self.stubs.find_all_stubs()
        return self.stubs.replace_stubs_batch(stubs)

    def Updateall(self):
        """
        Update ALL family operators in the project.

        Returns:
            List of updated COMPs
        """
        return super().Updateall()
