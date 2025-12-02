"""
Update system for opfam-create.

Handles updating operators to newer versions while preserving
connections and parameter values.
"""

get_operator_type = mod('tag_helpers').get_operator_type
has_operator_type_tag = mod('tag_helpers').has_operator_type_tag


class UpdateManager:
    """
    Manages operator updates for an operator family.

    Updates replace an operator's internals with the latest version
    while preserving connections, position, and parameter values.
    """

    def __init__(self, installer):
        """
        Initialize the update manager.

        Args:
            installer: The OpFamCreateExt instance
        """
        self.installer = installer
        self.ownerComp = installer.ownerComp
        self.family_name = installer.FamilyName.val

    def _call_hook(self, hook_name, *args):
        """Call a hook on the installer if it exists."""
        hook = getattr(self.installer, hook_name, None)
        if hook and callable(hook):
            return hook(*args)
        return None

    def find_matching_master(self, comp):
        """
        Find a matching master operator for a component.

        Matching methods:
        1. Type tag (e.g., agentLOP -> agent)
        2. ext0object parameter

        Args:
            comp: The component to find a match for

        Returns:
            tuple: (master_op, match_method) or (None, 'none')
        """
        operators_folder = self.ownerComp.op('custom_operators')
        if not operators_folder:
            return (None, 'none')

        category_tags = self._call_hook('GetCategoryTags') or set()

        # Try matching by type tag
        if has_operator_type_tag(comp, self.family_name, category_tags):
            comp_type = get_operator_type(comp, self.family_name, category_tags)
            master_ops = operators_folder.findChildren(name=comp_type, maxDepth=1)
            if master_ops:
                return (master_ops[0], 'type_tag')

        # Try matching by ext0object
        if hasattr(comp.par, 'ext0object'):
            ext_obj = comp.par.ext0object.eval()
            if ext_obj:
                for master_op in operators_folder.findChildren(type=COMP, maxDepth=1):
                    if hasattr(master_op.par, 'ext0object'):
                        if master_op.par.ext0object.eval() == ext_obj:
                            return (master_op, 'ext0object')

        return (None, 'none')

    def copy_par(self, dest_par, source_par):
        """
        Copy parameter value from source to destination.

        Handles regular and sequence parameters.

        Args:
            dest_par: Destination parameter
            source_par: Source parameter
        """
        # Sequence parameters
        if (hasattr(dest_par, 'sequence') and dest_par.sequence and
            hasattr(source_par, 'sequence') and source_par.sequence):

            seq_dest = dest_par.sequence
            seq_source = source_par.sequence

            if seq_dest.numBlocks != seq_source.numBlocks:
                seq_dest.numBlocks = seq_source.numBlocks

            common_par_names = [
                'name', 'label', 'value', 'index', 'enable', 'display',
                'top', 'dat', 'text', 'op', 'ops', 'mode', 'active',
                'parameters', 'pages', 'info', 'shortcut'
            ]

            for i in range(min(seq_source.numBlocks, seq_dest.numBlocks)):
                try:
                    source_block = seq_source.blocks[i]
                    dest_block = seq_dest.blocks[i]

                    for name in common_par_names:
                        try:
                            if hasattr(source_block.par, name) and hasattr(dest_block.par, name):
                                self._copy_simple_par(
                                    dest_block.par[name],
                                    source_block.par[name]
                                )
                        except:
                            pass
                except Exception as e:
                    print(f"Error copying sequence block {i}: {e}")

            return

        # Regular parameters
        self._copy_simple_par(dest_par, source_par)

    def _copy_simple_par(self, dest_par, source_par):
        """Copy a simple (non-sequence) parameter."""
        dest_par.mode = source_par.mode

        if source_par.mode == ParMode.CONSTANT:
            dest_par.val = source_par.val
        elif source_par.mode == ParMode.EXPRESSION:
            dest_par.expr = source_par.expr
        elif source_par.mode == ParMode.BIND:
            dest_par.bindExpr = source_par.bindExpr

    def update_operator(self, old_comp):
        """
        Update a single operator to the newest version.

        Args:
            old_comp: The component to update

        Returns:
            tuple: (success, message)
        """
        operators_folder = self.ownerComp.op('custom_operators')
        if not operators_folder:
            return (False, "Error: 'custom_operators' folder not found")

        master_comp, match_method = self.find_matching_master(old_comp)
        if not master_comp:
            return (False, f"Couldn't update {old_comp.path}, no matching master found")

        # Hook: PreUpdate
        if self._call_hook('PreUpdate', old_comp, master_comp) is False:
            return (False, f"Update cancelled by PreUpdate hook for {old_comp.path}")

        try:
            new_comp = old_comp.parent().copy(master_comp)
            old_name = old_comp.name

            # Preserve attributes
            new_comp.nodeX = old_comp.nodeX
            new_comp.nodeY = old_comp.nodeY
            new_comp.nodeWidth = old_comp.nodeWidth
            new_comp.nodeHeight = old_comp.nodeHeight
            new_comp.allowCooking = old_comp.allowCooking
            new_comp.bypass = old_comp.bypass
            new_comp.activeViewer = old_comp.activeViewer
            new_comp.viewer = old_comp.viewer

            # Copy parameters (skip certain ones)
            skip_pars = {'Version', 'Copyright'}
            for p in new_comp.pars():
                if p.name in skip_pars:
                    continue
                if hasattr(p, 'sequence') and p.sequence and p.sequence.name == 'ext':
                    continue

                old_pars = old_comp.pars(p.name)
                if old_pars:
                    self.copy_par(p, old_pars[0])

            # Hook: PreserveSpecialParams
            self._call_hook('PreserveSpecialParams', new_comp, old_comp)

            # Restore connections
            for i in range(min(len(new_comp.inputConnectors), len(old_comp.inputConnectors))):
                old_in = old_comp.inputConnectors[i]
                if old_in.connections:
                    try:
                        new_comp.inputConnectors[i].connect(old_in.connections[0])
                    except:
                        pass

            for o in range(min(len(new_comp.outputConnectors), len(old_comp.outputConnectors))):
                old_out = old_comp.outputConnectors[o]
                for conn in old_out.connections:
                    try:
                        new_comp.outputConnectors[o].connect(conn)
                    except:
                        pass

            old_comp.destroy()
            new_comp.name = old_name

            # Hook: PostUpdate
            self._call_hook('PostUpdate', new_comp)

            return (True, f"Updated {new_comp.path} (matched via {match_method})")

        except Exception as e:
            return (False, f"Error updating {old_comp.path}: {e}")

    def find_family_operators(self, network=None):
        """
        Find all operators of this family.

        Args:
            network: Optional network to search in

        Returns:
            list: Family operators (excluding installer)
        """
        excluded_tags = self._call_hook('GetExcludedTags') or set()

        search_root = network or op('/')
        depth = 1 if network else None

        return search_root.findChildren(
            type=COMP,
            maxDepth=depth,
            key=lambda o: (
                self.family_name in o.tags and
                not any(tag in o.tags for tag in excluded_tags) and
                o != self.ownerComp and
                self.ownerComp.path not in o.path
            )
        )

    def analyze_operators(self, operators):
        """
        Analyze operators for update compatibility.

        Args:
            operators: List of operators to analyze

        Returns:
            dict: Analysis results
        """
        operators_folder = self.ownerComp.op('custom_operators')
        category_tags = self._call_hook('GetCategoryTags') or set()

        results = {
            'with_type_tags': [],
            'with_ext_object': [],
            'without_matches': [],
            'updateable': []
        }

        for comp in operators:
            if has_operator_type_tag(comp, self.family_name, category_tags):
                results['with_type_tags'].append(comp)
                results['updateable'].append(comp)
            elif hasattr(comp.par, 'ext0object') and comp.par.ext0object.eval():
                results['with_ext_object'].append(comp)
                results['updateable'].append(comp)
            else:
                master, _ = self.find_matching_master(comp)
                if master:
                    results['updateable'].append(comp)
                else:
                    results['without_matches'].append(comp)

        return results

    def update_batch(self, operators):
        """
        Update multiple operators.

        Args:
            operators: List of operators to update

        Returns:
            dict: Results with updated, skipped, errors lists
        """
        ui.undo.startBlock(f'Update {self.family_name} operators')

        results = {
            'updated': [],
            'skipped': [],
            'errors': []
        }

        for op_comp in operators:
            try:
                success, message = self.update_operator(op_comp)
                if success:
                    results['updated'].append(message)
                else:
                    if 'no matching master' in message.lower():
                        results['skipped'].append(message)
                    else:
                        results['errors'].append(message)
            except Exception as e:
                results['errors'].append(f"Error with {op_comp.path}: {e}")

        ui.undo.endBlock()

        return results
