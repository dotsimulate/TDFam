"""
Stub system for opfam-create.

Handles creating lightweight stubs from operators and replacing them
back with full operators. Used for performance optimization.
"""
import re
import json
from RegistryHelpers import get_op_type_from_manifest, resolve_op_type, ensure_manifest_tags, apply_family_color, get_params_to_retain, get_self_pars_to_retain, capture_state_retain, restore_state_retain

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


	def _get_first_element(self, s):
		"""Returns the first element of a set/list or None if empty."""
		for e in s:
			return e
		return None

	def create_stub(self, family_name, comp):
		"""
		Create a lightweight stub of a component.

		Preserves connections, parameters, position, and type info.

		Args:
			family_name: The family name
			comp: The component to create a stub from

		Returns:
			The stub component, or None if skipped
		"""
		installer = self.registry.GetFamilyExt(family_name)
		if not installer:
			print(f"createStub: Family {family_name} not found")
			return None

		# Hook: PreStub - can return False to skip, or modify comp
		pre_stub = self.registry.CallHook(family_name, '_PreStub', comp)
		if isinstance(pre_stub, dict):
			if pre_stub.get('returnValue') is False:
				print(f"createStub: Skipped {comp.path} by PreStub hook")
				return None
			comp = pre_stub.get('comp', comp)
		elif pre_stub is False:
			print(f"createStub: Skipped {comp.path} by PreStub hook")
			return None

		name = comp.name
		manifest = comp.op('FamManifest')
		op_type, _ = resolve_op_type(comp, family_name, self.registry.TagManager)

		print(f"createStub: Creating stub for {comp.path} with type '{op_type}'")

		# Capture children params before destruction
		children_params = self._capture_children_params(comp)

		# Hook: CaptureChildrenParams
		self.registry.CallHook(family_name, '_CaptureChildrenParams', comp, children_params)

		# Hook: CaptureExtraInfo — developer returns a dict of arbitrary data to preserve
		extra_info_result = self.registry.CallHook(family_name, '_CaptureExtraInfo', comp, 'stub')
		extra_info = extra_info_result.get('returnValue', {}) if isinstance(extra_info_result, dict) else {}

		# Capture StateRetain data before children are destroyed
		state_retain_captured = {}
		if manifest:
			_state_retain_dat = manifest.op('StateRetain')
			if _state_retain_dat:
				try:
					state_retain_data = json.loads(_state_retain_dat.text)
					if state_retain_data:
						state_retain_captured = capture_state_retain(comp, state_retain_data, 'stub')
				except:
					pass

		# Remove all children except ins, outs, and FamManifest
		children = comp.findChildren(depth=1)
		input_ops = [_input.inOP for _input in comp.inputConnectors]
		output_ops = [_output.outOP for _output in comp.outputConnectors]
		while children:
			child = children[-1]
			if child in input_ops or child in output_ops or child == manifest:
				children = children[:-1]
				continue
			if child:
				child.destroy()
			else:
				children = children[:-1]

		# Tag manifest as stub
		comp.store('op_type', op_type)
		if manifest:
			manifest.tags.add('<STUB>')
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
		params, sequences = self._capture_params(comp)
		comp.store('params', params)
		comp.store('sequences', sequences)
		comp.store('children_params', children_params)
		comp.store('extra_info', extra_info)
		comp.store('state_retain_data', state_retain_captured)

		# Uncook
		comp.allowCooking = False

		# Hook: PostStub
		self.registry.CallHook(family_name, '_PostStub', comp, comp)

		return comp

	def _capture_children_params(self, comp):
		"""
		Capture parameters for all children of a component.
		"""
		children_data = {}
		for child in comp.findChildren():
			try:
				rel_path = comp.relativePath(child)
				if rel_path.startswith('./'):
					rel_path = rel_path[2:]
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
					if p.isCustom:
						par_basename = par_basename.capitalize()
					if par_basename not in discovered_sequences[p.sequence.name]:
						discovered_sequences[p.sequence.name].append(par_basename)
				
			else:
				# Regular parameter
				params[p.name] = self._get_par_info(p)

		all_sequence_data = {}
		
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

	def replace_stub(self, family_name, stub):
		"""
		Replace a single stub with a full operator.

		Args:
			family_name: The family name
			stub: The stub component

		Returns:
			The new full component, or None if failed
		"""
		installer = self.registry.GetFamilyExt(family_name)
		if not installer:
			print(f"replaceStub: Family {family_name} not found")
			return None

		stub_manifest = stub.op('FamManifest')
		if not stub_manifest or f'<FAM:{family_name}>' not in stub_manifest.tags:
			print(f"replaceStub: No valid manifest on {stub.path}")
			return None

		# Hook: PreReplace - can return False to skip, or modify stub
		pre_replace = self.registry.CallHook(family_name, '_PreReplace', stub)
		if isinstance(pre_replace, dict):
			if pre_replace.get('returnValue') is False:
				print(f"replaceStub: Skipped {stub.path} by PreReplace hook")
				return None
			stub = pre_replace.get('stub', stub)
		elif pre_replace is False:
			print(f"replaceStub: Skipped {stub.path} by PreReplace hook")
			return None

		# Get operator type from manifest
		op_type = get_op_type_from_manifest(stub_manifest)
		if not op_type:
			op_type = stub.fetch('op_type', None)
		if not op_type:
			print(f"replaceStub: No op_type found for {stub.path}")
			return None

		# Find master
		# Find master
		target_parent = stub.parent()
		source_type, source = self.registry.FileManager.get_operator_source(
			family_name, op_type
		) or (None, None)

		if not source:
			print(f"replaceStub: No master found for type '{op_type}'")
			return None

		# Read ParRetain before rename
		par_retain_data = {}
		_par_retain_dat = stub_manifest.op('ParRetain') if stub_manifest else None
		if _par_retain_dat:
			try:
				par_retain_data = json.loads(_par_retain_dat.text)
			except:
				pass
			
		# Rename stub to avoid name conflict
		if not stub.name.endswith('_stub'):
			stub.name = stub.name + '_stub'

		# Create new component
		new_comp = None
		if source_type == 'embedded':
			new_comp = target_parent.copy(source)
		elif source_type == 'file':
			try:
				new_comp = target_parent.loadTox(source)
			except Exception as e:
				print(f"replaceStub: Error loading tox {source}: {e}")
				return None

		if not new_comp:
			raise Exception(f"replaceStub: Failed to create new component for {stub.path}")

		# Ensure manifest exists on new comp
		new_manifest = new_comp.op('FamManifest')
		if not new_manifest:
			stub_manifest_copy = stub.op('FamManifest')
			if stub_manifest_copy:
				new_manifest = new_comp.copy(stub_manifest_copy)
		ensure_manifest_tags(new_manifest, family_name, op_type=op_type)
		
		# Restore position/size
		new_comp.nodeX = stub.nodeX
		new_comp.nodeY = stub.nodeY
		new_comp.nodeWidth = stub.nodeWidth
		new_comp.nodeHeight = stub.nodeHeight
		if stub.name.endswith('_stub'):
			new_comp.name = stub.name.removesuffix('_stub')

		try:
			params = stub.fetch('params', {})
			sequences = stub.fetch('sequences', {})
			children_data = stub.fetch('children_params', {})
			extra_info = stub.fetch('extra_info', {})

			# Self params: default = all custom pars, filtered by '.' rules if present
			self_key = next((k for k in ['.', ''] if k in par_retain_data), None)
			if self_key is not None:
				pars_to_retain = get_self_pars_to_retain(new_comp, 'stub', par_retain_data[self_key])
			else:
				pars_to_retain = {p.name for p in new_comp.customPars if p.page is not None}
			filtered_params = {k: v for k, v in params.items() if k in pars_to_retain}
			filtered_seqs = {k: v for k, v in sequences.items() if k in pars_to_retain}
			self._restore_params(new_comp, filtered_params, filtered_seqs)

			# Child params: only what's explicitly listed per key
			all_child_paths = list(children_data.keys())
			for key, _ in par_retain_data.items():
				if key in ('.', ''):
					continue
				for child_path in tdu.match(key, all_child_paths):
					target = new_comp.op(child_path)
					child_stored = children_data.get(child_path, {})
					if not target or not child_stored:
						continue
					child_pars_to_retain = get_params_to_retain(key, 'stub', par_retain_data, comp=target)
					child_params = {k: v for k, v in child_stored.get('params', {}).items() if k in child_pars_to_retain}
					child_seqs = {k: v for k, v in child_stored.get('sequences', {}).items() if k in child_pars_to_retain}
					self._restore_params(target, child_params, child_seqs)

			# Restore StateRetain data
			state_retain_captured = stub.fetch('state_retain_data', {})
			if state_retain_captured:
				restore_state_retain(new_comp, state_retain_captured)

			# Hook: PreserveSpecialParams
			self.registry.CallHook(family_name, '_PreserveSpecialParams', new_comp, params)

			# Restore connections
			self._restore_connections(new_comp, stub)

			# Restore state
			new_comp.allowCooking = stub.fetch('cooking', 1)
			new_comp.bypass = stub.fetch('bypass', False)

			# Apply family color for file-based ops
			if source_type == 'file' and hasattr(installer, 'ownerComp'):
				op_color = None
				_m = new_comp.op('FamManifest')
				if _m and _m.op('OpInfo'):
					try:
						_oi = json.loads(_m.op('OpInfo').text)
						op_color = _oi.get('op_color')
					except:
						pass
				apply_family_color(installer.ownerComp, new_comp, op_color=op_color)

			# Hook: PostReplace
			self.registry.CallHook(family_name, '_PostReplace', new_comp, stub, extra_info)
		except Exception as e:
			print(f"replaceStub: Failed to replace {stub.path}: {e}")
			#raise
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

	def find_stubs(self, family_name, network=None):
		"""
		Find all stubs of this family via their FamManifest tags.

		Returns:
			list: Stub operators
		"""
		installer = self.registry.GetFamilyExt(family_name)
		if not installer:
			return []

		search_root = network or op('/')
		manifests = search_root.findChildren(
			type=COMP,
			tags=[f'<FAM:{family_name}>', '<MANIFEST>', '<STUB>'],
			allTags=True,
		)

		stubs = []
		for m in manifests:
			parent_op = m.parent()
			if not parent_op:
				continue
			stubs.append(parent_op)
		return stubs

	def create_stubs_batch(self, family_name, operators):
		"""
		Create stubs for multiple operators.

		Args:
			family_name: The family name
			operators: List of operators to stub

		Returns:
			list: Created stubs
		"""
		ui.undo.startBlock(f'Create {family_name} Stubs')

		stubs = []
		for comp in operators:
			try:
				stub = self.create_stub(family_name, comp)
				if stub:
					stubs.append(stub)
			except Exception as e:
				print(f"Error creating stub for {comp.path}: {e}")


		ui.undo.endBlock()

		return stubs

	def replace_stubs_batch(self, family_name, stubs):
		"""
		Replace multiple stubs with full operators.

		Args:
			family_name: The family name
			stubs: List of stubs to replace

		Returns:
			list: Regenerated operators
		"""
		ui.undo.startBlock(f'Replace {family_name} Stubs')

		regenerated = []
		for stub in stubs:
			# try:
			new_comp = self.replace_stub(family_name, stub)
			if new_comp:
				regenerated.append(new_comp)
			# except Exception as e:
			# 	print(f"Error replacing stub {stub.path}: {e}")

		ui.undo.endBlock()

		return regenerated
