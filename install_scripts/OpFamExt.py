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
        - Createstuball (pulse): Create stubs for all operators
        - Replacestuball (pulse): Replace all stubs
        - Updateall (pulse): Update all operators
        - Targetop (str): Target operator path
        - Createstubop (pulse): Create stub for target op
        - Replacestubop (pulse): Replace stub for target op
        - Updateop (pulse): Update target operator
        - Targetcomp (str): Target comp path
        - Createstubcomp (pulse): Create stubs in comp
        - Replacestubcomp (pulse): Replace stubs in comp
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

            # Build folder cache now that operators_folder is set from parameters
            if self.operators_folder and not self.dynamic_refresh and self.fam_registry:
                self.fam_registry.FileManager.refresh_cache(self.Properties['family_name'], self.operators_folder)

        run(lambda: self.postInit(), delayFrames = 2)

    def postInit(self):
        self.Install()

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
        if hasattr(inst.par, 'Namingconvention'):
            self.Properties['naming_convention'] = inst.par.Namingconvention.eval()

    @property
    def index(self):
        """Get menu index from Properties registry."""
        return self.Properties['index']

    @index.setter
    def index(self, value):
        """Set menu index in Properties registry."""
        self.Properties['index'] = int(value)

    # ==================== Shortcut Configuration ====================

    @property
    def shortcut_mode(self):
        """Get Shortcutcomp parameter value (strmenu: me, parent(), parent(2))."""
        if hasattr(self._installer.par, 'Shortcutcomp'):
            return self._installer.par.Shortcutcomp.eval()
        return 'me'

    @property
    def ShortcutComp(self):
        """Get the component that receives the op shortcut based on Shortcutcomp parameter."""
        mode = self.shortcut_mode
        if mode == 'me':
            return self.ownerComp
        elif mode == 'parent()':
            return self.ownerComp.parent()
        elif mode == 'parent(2)':
            return self.ownerComp.parent().parent()
        return self.ownerComp

    def get_installer_expr(self, fam_name):
        """
        Build expression path from shortcut target back to installer.

        Args:
            fam_name: Family name to use in expression

        Returns:
            Expression string like 'op.{family}' or 'op.{family}.op('{installer}')'
        """
        mode = self.shortcut_mode

        if mode == 'me':
            return f'op.{fam_name}'
        elif mode == 'parent()':
            return f"op.{fam_name}.op('{self.ownerComp.name}')"
        elif mode == 'parent(2)':
            parent_name = self.ownerComp.parent().name
            return f"op.{fam_name}.op('{parent_name}').op('{self.ownerComp.name}')"
        return f'op.{fam_name}' 

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

    def Family(self, name=None):
        """
        Update the family name and all associated UI elements.

        Args:
            name: New family name. If None, uses Family parameter value.
        """
        if name is None:
            name = self._installer.par.Family.eval()

        # Get old name before updating
        old_name = self.Properties['family_name']

        # Skip if no change
        if old_name == name:
            return

        # Update registry
        if self.fam_registry:
            self.fam_registry.UpdateFamilyName(old_name, name)
        
        self.Properties['family_name'] = name

    def Color(self, r=None, g=None, b=None):
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

        if self.fam_registry:
            self.fam_registry.UpdateFamilyColor(self.Properties['family_name'], self.Properties['color'])


    def Namingconvention(self, pattern=None):
        """
        Set the .tox filename naming convention pattern.

        Args:
            pattern: Regex pattern for parsing version from filename.
                     If None, uses Namingconvention parameter value.
                     Empty string means no versioning.
        """
        if pattern is None:
            pattern = self._installer.par.Namingconvention.eval()

        self.Properties['naming_convention'] = pattern

        # Refresh folder cache with new naming convention
        if self.operators_folder:
            self.fam_registry.FileManager.refresh_cache(self.Properties['family_name'], self.operators_folder)

    # --- Stub for single operator ---

    def Createstubop(self, target=None):
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
        if isinstance(target, str):
            target = op(target)
        return super().CreateStubFor(target)

    def Replacestubop(self, stub=None):
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
        if isinstance(stub, str):
            stub = op(stub)
        return super().ReplaceStubFor(stub)

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
        if isinstance(target, str):
            target = op(target)
        return super().Updateop(target)

    # --- Stubs for comp/network ---

    def Createstubscomp(self, comp=None):
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
        if isinstance(comp, str):
            comp = op(comp)

        if isinstance(comp, str):
            comp = op(comp)

        # Use refined base method with scope
        return super().CreateStubs(comp)

    def Replacestubcomp(self, comp=None):
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
        if isinstance(comp, str):
            comp = op(comp)
            
        if isinstance(comp, str):
            comp = op(comp)
            
        # Use refined base method with scope
        return super().ReplaceStubs(comp)

    def Updatecomp(self, comp=None):
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
        if isinstance(comp, str):
            comp = op(comp)

        if isinstance(comp, str):
            comp = op(comp)

        # Use refined base method with scope
        return super().UpdateOperators(comp)

    # --- Stubs for ALL ---

    def Createstuball(self):
        """
        Create stubs for ALL family operators in the project.

        Returns:
            List of created stubs
        """
        return super().CreateStubs()

    def Replacestuball(self):
        """
        Replace ALL stubs in the project with full operators.

        Returns:
            List of replaced COMPs
        """
        return super().ReplaceStubs()

    def Updateall(self):
        """
        Update ALL family operators in the project.

        Returns:
            List of updated COMPs
        """
        return super().Updateall()

    def Tagoperators(self, pattern=None):
        """
        Tag all operators in Opcomp with family and type tags.
        Exposed as pulse parameter.

        Args:
            pattern: Tag pattern ('suffix' or 'name'). If None, uses 'suffix'.
        """
        if pattern is None:
            pattern = 'suffix'
        return super().TagOperators(pattern)

    def Createcallbacks(self):
        """
        Create a callbacks DAT from template if not already set.
        Sets the Callbackdat parameter to the created DAT.

        Returns:
            The created callbacks DAT, or None if already exists
        """
        template = self._installer.op('callback_template')
        callbacks_dat = self.CreateCallbackDat(self._installer, template)

        if callbacks_dat:
            self._installer.par.Callbackdat = callbacks_dat

        return callbacks_dat
