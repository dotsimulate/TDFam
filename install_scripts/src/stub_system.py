"""
Stub system for opfam-create.

Handles creating lightweight stubs from operators and replacing them
back with full operators. Used for performance optimization.
"""

get_operator_type = mod('tag_helpers').get_operator_type
has_operator_type_tag = mod('tag_helpers').has_operator_type_tag


class StubManager:
    """
    Manages stub creation and replacement for an operator family.

    Stubs are lightweight placeholders that preserve:
    - Position and size
    - Connections (inputs/outputs)
    - Parameter values (including sequences)
    - Operator type info
    """

    def __init__(self, installer):
        """
        Initialize the stub manager.

        Args:
            installer: The OpFamCreateExt instance
        """
        self.installer = installer
        self.ownerComp = installer.ownerComp
        self.family_name = installer.FamilyName.val

    def _get_first_element(self, s):
        """Returns the first element of a set/list or None if empty."""
        for e in s:
            return e
        return None

    def _call_hook(self, hook_name, *args):
        """Call a hook on the installer if it exists."""
        hook = getattr(self.installer, hook_name, None)
        if hook and callable(hook):
            return hook(*args)
        return None

    def create_stub(self, comp):
        """
        Create a lightweight stub of a component.

        Preserves connections, parameters, position, and type info.

        Args:
            comp: The component to create a stub from

        Returns:
            The stub component, or None if skipped
        """
        # Hook: PreStub - can return False to skip
        if self._call_hook('_PreStub', comp) is False:
            print(f"createStub: Skipped {comp.path} by PreStub hook")
            return None

        name = comp.name
        category_tags = self._call_hook('_GetCategoryTags') or set()
        op_type = get_operator_type(comp, self.family_name, category_tags)

        print(f"createStub: Creating stub for {comp.path} with type '{op_type}'")

        # Copy and strip
        copy = comp.parent().copy(comp)
        copy.allowCooking = False

        # Preserve position/size
        copy.nodeX = comp.nodeX
        copy.nodeY = comp.nodeY
        copy.nodeWidth = comp.nodeWidth
        copy.nodeHeight = comp.nodeHeight

        # Remove all children
        children = copy.findChildren(depth=1)
        while children:
            if children[-1]:
                children[-1].destroy()
            else:
                children = children[:-1]

        # Set stub tag and store type
        stub_tag = f"{op_type}{self.family_name}stub"
        copy.tags = [stub_tag]
        copy.store('op_type', op_type)
        copy.name = f"{name}_stub"

        # Store state
        copy.store('cooking', comp.allowCooking)
        copy.store('bypass', comp.bypass)

        # Store input connections
        inputs = []
        for i in comp.inputConnectors:
            if i.connections:
                conn = i.connections[0]
                if conn.owner.isCOMP:
                    inputs.append(conn.outOP)
                else:
                    inputs.append(conn.owner)
            else:
                inputs.append(None)
        copy.store('inputs', inputs)

        # Store output connections
        outputs = []
        for o in comp.outputConnectors:
            outputs.append([(con.owner, con.index) for con in o.connections])
        copy.store('outputs', outputs)

        # Store parameters
        params = self._capture_params(comp)
        copy.store('params', params)

        # Hook: PostStub
        self._call_hook('_PostStub', copy, comp)

        return copy

    def _capture_params(self, comp):
        """
        Capture all parameter values from a component.

        Handles regular params and sequence params.

        Args:
            comp: The component

        Returns:
            dict: Parameter name -> value mapping
        """
        params = {}

        for p in comp.pars():
            if hasattr(p, 'sequence') and p.sequence:
                # Sequence parameter
                seq = p.sequence
                seq_data = {
                    'name': seq.name if hasattr(seq, 'name') else '',
                    'numBlocks': seq.numBlocks,
                    'blocks': []
                }

                common_par_names = [
                    'name', 'label', 'value', 'index', 'enable', 'display',
                    'top', 'dat', 'text', 'op', 'ops', 'mode', 'active',
                    'parameters', 'pages', 'info', 'shortcut'
                ]

                for i in range(seq.numBlocks):
                    block = seq.blocks[i]
                    block_data = {}

                    for par_name in common_par_names:
                        try:
                            if hasattr(block.par, par_name):
                                par = block.par[par_name]
                                block_data[par_name] = self._get_par_value(par)
                        except:
                            pass

                    seq_data['blocks'].append(block_data)

                params[p.name] = {'type': 'sequence', 'data': seq_data}
            else:
                # Regular parameter
                params[p.name] = self._get_par_value(p)

        return params

    def _get_par_value(self, par):
        """Get parameter value with mode info."""
        if par.mode == ParMode.CONSTANT:
            return par.val
        elif par.mode == ParMode.EXPRESSION:
            return {'mode': 'expr', 'expr': par.expr}
        elif par.mode == ParMode.BIND:
            return {'mode': 'bind', 'expr': par.bindExpr}
        return par.val

    def _restore_par_value(self, dest_par, value):
        """Restore parameter value from stored value."""
        if isinstance(value, dict):
            if value.get('mode') == 'expr':
                dest_par.mode = ParMode.EXPRESSION
                dest_par.expr = value.get('expr', '')
            elif value.get('mode') == 'bind':
                dest_par.mode = ParMode.BIND
                dest_par.bindExpr = value.get('expr', '')
        else:
            dest_par.mode = ParMode.CONSTANT
            dest_par.val = value

    def replace_stub(self, stub):
        """
        Replace a single stub with a full operator.

        Args:
            stub: The stub component

        Returns:
            The new full component, or None if failed
        """
        # Hook: PreReplace
        if self._call_hook('_PreReplace', stub) is False:
            print(f"replaceStub: Skipped {stub.path} by PreReplace hook")
            return None

        # Get operator type
        op_type = stub.fetch('op_type', None)
        if not op_type:
            tag = self._get_first_element(stub.tags)
            if not tag or not tag.endswith(f"{self.family_name}stub"):
                print(f"replaceStub: Invalid stub tag on {stub.path}")
                return None
            op_type = tag.removesuffix(f"{self.family_name}stub")

        # Find master
        target_parent = stub.parent()
        master_op, is_file_based = self.installer.file_loader.get_master_for_type(
            op_type, target_parent,
            getattr(self.installer, 'operators_folder', None),
            getattr(self.installer, 'dynamic_refresh', False)
        )

        if not master_op:
            print(f"replaceStub: No master found for type '{op_type}'")
            return None

        # Create new component
        if is_file_based:
            new_comp = master_op
        else:
            new_comp = target_parent.copy(master_op)

        # Restore position/size
        new_comp.nodeX = stub.nodeX
        new_comp.nodeY = stub.nodeY
        new_comp.nodeWidth = stub.nodeWidth
        new_comp.nodeHeight = stub.nodeHeight
        new_comp.name = stub.name.removesuffix('_stub')

        # Restore parameters
        params = stub.fetch('params', {})
        self._restore_params(new_comp, params)

        # Hook: PreserveSpecialParams
        self._call_hook('_PreserveSpecialParams', new_comp, params)

        # Restore connections
        self._restore_connections(new_comp, stub)

        # Restore state
        new_comp.allowCooking = stub.fetch('cooking', 1)
        new_comp.bypass = stub.fetch('bypass', False)

        # Hook: PostReplace
        self._call_hook('_PostReplace', new_comp, stub)

        # Remove stub
        stub.destroy()

        return new_comp

    def _restore_params(self, new_comp, params):
        """Restore parameters to a component from stored values."""
        for name, value in params.items():
            dest_pars = new_comp.pars(name)
            if not dest_pars:
                continue

            dest_par = dest_pars[0]

            if isinstance(value, dict) and value.get('type') == 'sequence':
                # Sequence parameter
                seq_data = value.get('data', {})
                if hasattr(dest_par, 'sequence') and dest_par.sequence:
                    seq_dest = dest_par.sequence

                    if seq_dest.numBlocks != seq_data.get('numBlocks', 0):
                        seq_dest.numBlocks = seq_data.get('numBlocks', 0)

                    blocks_data = seq_data.get('blocks', [])
                    for i, block_data in enumerate(blocks_data):
                        if i < seq_dest.numBlocks:
                            dest_block = seq_dest.blocks[i]
                            for par_name, par_value in block_data.items():
                                try:
                                    if hasattr(dest_block.par, par_name):
                                        self._restore_par_value(
                                            dest_block.par[par_name],
                                            par_value
                                        )
                                except:
                                    pass
            else:
                self._restore_par_value(dest_par, value)

    def _restore_connections(self, new_comp, stub):
        """Restore input/output connections from stub."""
        # Inputs
        stored_inputs = stub.fetch('inputs')
        if stored_inputs:
            for i, input_op in enumerate(stored_inputs):
                if i < len(new_comp.inputConnectors) and input_op:
                    try:
                        new_comp.inputConnectors[i].connect(input_op)
                    except:
                        pass

        # Outputs
        stored_outputs = stub.fetch('outputs')
        if stored_outputs:
            for o_idx, connections in enumerate(stored_outputs):
                if o_idx < len(new_comp.outputConnectors):
                    for con in connections:
                        try:
                            target_op = con[0].op() if hasattr(con[0], 'op') else con[0]
                            if target_op and con[1] < len(target_op.inputConnectors):
                                new_comp.outputConnectors[o_idx].connect(
                                    target_op.inputConnectors[con[1]]
                                )
                        except:
                            pass

    # ==================== Batch Operations ====================

    def find_family_operators(self, network=None, max_depth=None):
        """
        Find all operators of this family.

        Args:
            network: Optional network to search in. Defaults to root.
            max_depth: Maximum search depth. None for unlimited.

        Returns:
            list: Family operators (excluding installer and stubs)
        """
        excluded_tags = self._call_hook('_GetExcludedTags') or set()

        search_root = network or op('/')
        depth = 1 if network else None

        return search_root.findChildren(
            type=COMP,
            maxDepth=depth,
            key=lambda o: (
                self.family_name in o.tags and
                not any(tag in o.tags for tag in excluded_tags) and
                f"{self.family_name}stub" not in str(o.tags) and
                o != self.ownerComp and
                self.ownerComp.path not in o.path
            )
        )

    def find_stubs(self, network=None):
        """
        Find all stubs of this family.

        Args:
            network: Optional network to search in. Defaults to root.

        Returns:
            list: Stub operators
        """
        excluded_tags = self._call_hook('_GetExcludedTags') or set()
        excluded_lower = {t.lower() for t in excluded_tags}

        search_root = network or op('/')
        depth = 1 if network else None

        all_stubs = search_root.findChildren(
            type=COMP,
            maxDepth=depth,
            key=lambda o: (
                len(o.tags) == 1 and
                f"{self.family_name}stub" in self._get_first_element(o.tags)
            )
        )

        # Filter by op_type
        return [s for s in all_stubs if s.fetch('op_type', '').lower() not in excluded_lower]

    def create_stubs_batch(self, operators):
        """
        Create stubs for multiple operators.

        Args:
            operators: List of operators to stub

        Returns:
            list: Created stubs
        """
        ui.undo.startBlock(f'Create {self.family_name} Stubs')

        stubs = []
        for comp in operators:
            try:
                stub = self.create_stub(comp)
                if stub:
                    stubs.append(stub)
            except Exception as e:
                print(f"Error creating stub for {comp.path}: {e}")

        # Destroy originals
        for comp in operators:
            try:
                comp.destroy()
            except Exception as e:
                print(f"Error destroying {comp.path}: {e}")

        ui.undo.endBlock()

        return stubs

    def replace_stubs_batch(self, stubs):
        """
        Replace multiple stubs with full operators.

        Args:
            stubs: List of stubs to replace

        Returns:
            list: Regenerated operators
        """
        ui.undo.startBlock(f'Replace {self.family_name} Stubs')

        regenerated = []
        for stub in stubs:
            try:
                new_comp = self.replace_stub(stub)
                if new_comp:
                    regenerated.append(new_comp)
            except Exception as e:
                print(f"Error replacing stub {stub.path}: {e}")

        ui.undo.endBlock()

        return regenerated
