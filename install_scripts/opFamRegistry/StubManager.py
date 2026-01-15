"""
Stub system for opfam-create.

Handles creating lightweight stubs from operators and replacing them
back with full operators. Used for performance optimization.
"""
import re

class StubManager:
	"""
	Manages stub creation and replacement for an operator family.

	Stubs are lightweight placeholders that preserve:
	- Position and size
	- Connections (inputs/outputs)
	- Parameter values (including sequences)
	- Operator type info
	"""

	def __init__(self, ownerComp, registry):
		"""
		Initialize the stub manager.

		Args:
			ownerComp: The component that owns this extension
			registry: The OpFamRegistryExt instance
		"""
		self.ownerComp = ownerComp
		self.registry = registry

	def _call_hook(self, installer, hook_name, *args):
		"""Call a hook on the installer if it exists."""
		hook = getattr(installer, hook_name, None)
		if hook and callable(hook):
			return hook(*args)
		return None

	def get_family_name(self, installer):
		return installer.Properties['family_name']

	def _get_first_element(self, s):
		"""Returns the first element of a set/list or None if empty."""
		for e in s:
			return e
		return None

	def create_stub(self, installer, comp):
		"""
		Create a lightweight stub of a component.

		Preserves connections, parameters, position, and type info.

		Args:
			installer: The OpFamCreateExt instance
			comp: The component to create a stub from

		Returns:
			The stub component, or None if skipped
		"""
		# Hook: PreStub - can return False to skip
		if self._call_hook(installer, '_PreStub', comp) is False:
			print(f"createStub: Skipped {comp.path} by PreStub hook")
			return None

		name = comp.name
		family_name = self.get_family_name(installer)
		category_tags = self._call_hook(installer, '_GetCategoryTags') or set()
		op_type = self.registry.TagManager.get_operator_type(comp, family_name, category_tags)

		print(f"createStub: Creating stub for {comp.path} with type '{op_type}'")

		print(f"createStub: Creating stub for {comp.path} with type '{op_type}'")
		
		# Capture children params before destruction
		children_params = self._capture_children_params(comp)
		comp.store('children_params', children_params)

		# Remove all children except ins and outs
		children = comp.findChildren(depth=1)
		input_ops = [_input.inOP for _input in comp.inputConnectors]
		output_ops = [_output.outOP for _output in comp.outputConnectors]
		while children:
			if children[-1] in input_ops or children[-1] in output_ops:
				children = children[:-1]
				continue
			if children[-1]:
				children[-1].destroy()
			else:
				children = children[:-1]

		# Store tags
		comp.store('tags', comp.tags)

		# Set stub tag and store type
		comp.store('op_type', op_type)
		comp.tags.add('<STUB>')
		comp.tags.add(f"{op_type}{family_name}stub")
		comp.name = f"{name}"

		# Store state
		comp.store('cooking', comp.allowCooking)
		comp.store('bypass', comp.bypass)

		# Store input connections
		inputs = []
		for i in comp.inputConnectors:
			conns = []
			for conn in i.connections:
				conns.append((comp.relativePath(conn.owner), conn.index))
			inputs.append(conns)
		comp.store('inputs', inputs)

		# Store output connections
		outputs = []
		for o in comp.outputConnectors:
			conns = []
			for conn in o.connections:
				conns.append((comp.relativePath(conn.owner), conn.index))
			outputs.append(conns)
		comp.store('outputs', outputs)

		# Store parameters
		# Store parameters
		params, sequences = self._capture_params(comp)
		# debug(params)
		# debug(sequences)
		comp.store('params', params)
		comp.store('sequences', sequences)

		# Uncook
		comp.allowCooking = False

		# Hook: PostStub
		self._call_hook(installer, '_PostStub', comp, comp)

		return comp

	def _capture_children_params(self, comp):
		"""
		Capture parameters for all children of a component.
		"""
		children_data = {}
		for child in comp.findChildren():
			try:
				rel_path = comp.relativePath(child)
				params, sequences = self._capture_params(child)
				if params or sequences:
					children_data[rel_path] = {'params': params, 'sequences': sequences}
			except:
				pass
		return children_data

	def _restore_children_params(self, comp, children_data):
		"""
		Restore parameters for children.
		"""
		for rel_path, data in children_data.items():
			try:
				target = comp.op(rel_path)
				if target:
					self._restore_params(target, data.get('params', {}), data.get('sequences', {}))
			except:
				pass

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

		discovered_sequences = {}
		for p in comp.pars():
			if hasattr(p, 'sequence') and p.sequence:
				# Sequence parameter
				if p.sequence.name not in discovered_sequences:
					discovered_sequences[p.sequence.name] = []
				match = re.match(r'(.+?)(\d+)(.+)', p.name)
				if match:
					_, _, par_basename = match.groups()
					debug(par_basename)
					if p.isCustom:
						par_basename = par_basename.capitalize()
					if par_basename not in discovered_sequences[p.sequence.name]:
						discovered_sequences[p.sequence.name].append(par_basename)
				
			else:
				# Regular parameter
				params[p.name] = self._get_par_info(p)

		all_sequence_data = {}
		debug(discovered_sequences)
		for _sequence, par_names in discovered_sequences.items():
			all_sequence_data[_sequence] = {}
			for _block_idx, _block in enumerate(comp.seq[_sequence]):
				all_sequence_data[_sequence][_block_idx] = {}
				for _par_name in par_names:
					all_sequence_data[_sequence][_block_idx][_par_name] = self._get_par_info(_block.par[_par_name])
						

		return params, all_sequence_data

	def _get_par_value(self, par):
		"""Get parameter value with mode info."""
		if par.mode == ParMode.CONSTANT:
			return par.val
		elif par.mode == ParMode.EXPRESSION:
			return {'mode': 'expr', 'expr': par.expr}
		elif par.mode == ParMode.BIND:
			return {'mode': 'bind', 'expr': par.bindExpr}
		return par.val

	def _get_par_info(self, par):
		"""Get parameter info."""
		return {
			'mode': par.mode,
			'val': par.val,
			'expr': par.expr,
			'bindExpr': par.bindExpr
		}

	def _restore_par_value(self, dest_par, value):
		"""Restore parameter value from stored value."""
		if isinstance(value, dict):
			mode = value.get('mode')
			if mode == ParMode.EXPRESSION:
				dest_par.mode = ParMode.EXPRESSION
				dest_par.expr = value.get('expr', '')
			elif mode == ParMode.BIND:
				dest_par.mode = ParMode.BIND
				dest_par.bindExpr = value.get('bindExpr', '')
			elif mode == ParMode.CONSTANT:
				dest_par.mode = ParMode.CONSTANT
				dest_par.val = value.get('val')
			else:
				# Fallback for old style or default
				dest_par.val = value.get('val')
		else:
			dest_par.mode = ParMode.CONSTANT
			dest_par.val = value

	def replace_stub(self, installer, stub):
		"""
		Replace a single stub with a full operator.

		Args:
			installer: The installer component
			stub: The stub component

		Returns:
			The new full component, or None if failed
		"""
		family_name = self.get_family_name(installer)
		if not family_name in stub.tags:
			print(f"replaceStub: Invalid stub tag on {stub.path}")
			return None
		
		# Hook: PreReplace
		if self._call_hook(installer, '_PreReplace', stub) is False:
			print(f"replaceStub: Skipped {stub.path} by PreReplace hook")
			return None

		# Get operator type
		op_type = stub.fetch('op_type', None)
		if not op_type:
			for tag in stub.tags:
				if tag.endswith(f"{family_name}stub"):
					op_type = tag.removesuffix(f"{family_name}stub")
					break
			if not op_type:
				print(f"replaceStub: Invalid stub tag on {stub.path}")
				return None

		# Find master
		target_parent = stub.parent()
		master_op, is_file_based = installer.file_loader.get_master_for_type(
			op_type, target_parent,
			getattr(installer, 'operators_folder', None),
			getattr(installer, 'dynamic_refresh', False)
		)

		if not master_op:
			print(f"replaceStub: No master found for type '{op_type}'")
			return None

		# Rename stub to avoid name conflict
		if not stub.name.endswith('_stub'):
			stub.name = stub.name + '_stub'

		# Create new component
		if is_file_based:
			new_comp = master_op
		else:
			new_comp = target_parent.copy(master_op)

		if not new_comp:
			raise Exception(f"replaceStub: Failed to create new component for {stub.path}")

		

		# Merge tags with new_comp and restored tags
		new_comp.tags = list(set(new_comp.tags) | set(stub.fetch('tags', [])))
		new_comp.tags.remove('<STUB>')
		new_comp.tags.remove(f"{op_type}{family_name}stub")
		
		# Restore position/size
		new_comp.nodeX = stub.nodeX
		new_comp.nodeY = stub.nodeY
		new_comp.nodeWidth = stub.nodeWidth
		new_comp.nodeHeight = stub.nodeHeight
		if stub.name.endswith('_stub'):
			new_comp.name = stub.name.removesuffix('_stub')

		try:
			# Restore parameters
			params = stub.fetch('params', {})
			sequences = stub.fetch('sequences', {})
			self._restore_params(new_comp, params, sequences)

			# Restore children params
			children_data = stub.fetch('children_params', {})
			# self._restore_children_params(new_comp, children_data)

			# Hook: PreserveSpecialParams
			# self._call_hook(installer, '_PreserveSpecialParams', new_comp, params)

			# Restore connections
			self._restore_connections(new_comp, stub)

			# Restore state
			new_comp.allowCooking = stub.fetch('cooking', 1)
			new_comp.bypass = stub.fetch('bypass', False)

			# Hook: PostReplace
			self._call_hook(installer, '_PostReplace', new_comp, stub)
		except:
			print(f"replaceStub: Failed to replace {stub.path}")
		finally:
			# Remove stub
			stub.destroy()

		return new_comp

	def _restore_params(self, new_comp, params, sequences):
		"""Restore parameters to a component from stored values."""
		# Restore regular parameters
		for name, value in params.items():
			dest_pars = new_comp.pars(name)
			if dest_pars:
				self._restore_par_value(dest_pars[0], value)

		# Restore sequences
		for seq_name, seq_blocks in sequences.items():
			if not hasattr(new_comp, 'seq'):
				continue
				
			try:
				dest_seq = new_comp.seq[seq_name]
			except:
				continue

			# Ensure enough blocks exists
			if dest_seq.numBlocks < len(seq_blocks):
				dest_seq.numBlocks = len(seq_blocks)

			# Restore block parameters
			for block_idx_str, block_data in seq_blocks.items():
				block_idx = int(block_idx_str)
				if block_idx < dest_seq.numBlocks:
					dest_block = dest_seq.blocks[block_idx]
					for par_name, par_info in block_data.items():
						if hasattr(dest_block.par, par_name):
							self._restore_par_value(dest_block.par[par_name], par_info)

	def _restore_connections(self, new_comp, stub):
		"""Restore input/output connections from stub."""
		# Inputs
		stored_inputs = stub.fetch('inputs', [])
		for i, conns in enumerate(stored_inputs):
			if i >= len(new_comp.inputConnectors):
				break
			for path, index in conns:
				target = new_comp.parent().op(path)
				if target and index < len(target.outputConnectors):
					try:
						new_comp.inputConnectors[i].connect(target.outputConnectors[index])
					except:
						pass

		# Outputs
		stored_outputs = stub.fetch('outputs', [])
		for i, conns in enumerate(stored_outputs):
			if i >= len(new_comp.outputConnectors):
				break
			for path, index in conns:
				target = new_comp.parent().op(path)
				if target and index < len(target.inputConnectors):
					try:
						new_comp.outputConnectors[i].connect(target.inputConnectors[index])
					except:
						pass

	# ==================== Batch Operations ====================

	def find_family_operators(self, installer, network=None, max_depth=None):
		"""
		Find all operators of this family.

		Args:
			installer: The installer component
			network: Optional network to search in. Defaults to root.
			max_depth: Maximum search depth. None for unlimited.

		Returns:
			list: Family operators (excluding installer and stubs)
		"""
		family_name = self.get_family_name(installer)
		excluded_tags = self._call_hook(installer, '_GetExcludedTags') or set()

		search_root = network or op('/')
		depth = 1 if network else None
		
		return search_root.findChildren(
			type=COMP,
			maxDepth=depth,
			key=lambda o: (
				family_name in o.tags and
				not any(tag in o.tags for tag in excluded_tags) and
				f"{family_name}stub" not in str(o.tags) and
				f"{family_name}stub" not in str(o.tags) and
				o != installer.ownerComp and
				installer.ownerComp.path not in o.path and
				(not installer.operators_comp or installer.operators_comp.path not in o.path)
			)
		)

	def find_stubs(self, installer, network=None):
		"""
		Find all stubs of this family.

		Args:
			installer: The installer component
			network: Optional network to search in. Defaults to root.

		Returns:
			list: Stub operators
		"""
		family_name = self.get_family_name(installer)
		excluded_tags = self._call_hook(installer, '_GetExcludedTags') or set()
		excluded_lower = {t.lower() for t in excluded_tags}

		search_root = network or op('/')
		depth = 1 if network else None

		all_stubs = search_root.findChildren(
			type=COMP,
			maxDepth=depth,
			tags=['<STUB>']
		)

		# Filter by current family
		all_stubs = [s for s in all_stubs if family_name in s.tags]

		# Filter by op_type
		return [s for s in all_stubs if s.fetch('op_type', '').lower() not in excluded_lower]

	def create_stubs_batch(self, installer, operators):
		"""
		Create stubs for multiple operators.

		Args:
			installer: The installer component
			operators: List of operators to stub

		Returns:
			list: Created stubs
		"""
		family_name = self.get_family_name(installer)
		ui.undo.startBlock(f'Create {family_name} Stubs')

		stubs = []
		for comp in operators:
			try:
				stub = self.create_stub(installer, comp)
				if stub:
					stubs.append(stub)
			except Exception as e:
				print(f"Error creating stub for {comp.path}: {e}")


		ui.undo.endBlock()

		return stubs

	def replace_stubs_batch(self, installer, stubs):
		"""
		Replace multiple stubs with full operators.

		Args:
			installer: The installer component
			stubs: List of stubs to replace

		Returns:
			list: Regenerated operators
		"""
		family_name = self.get_family_name(installer)
		ui.undo.startBlock(f'Replace {family_name} Stubs')

		regenerated = []
		for stub in stubs:
			try:
				new_comp = self.replace_stub(installer, stub)
				if new_comp:
					regenerated.append(new_comp)
			except Exception as e:
				print(f"Error replacing stub {stub.path}: {e}")

		ui.undo.endBlock()

		return regenerated
