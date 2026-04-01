"""
Update system for opfam-create.

Handles updating operators to newer versions while preserving
connections and parameter values.
"""
import json
from RegistryHelpers import get_op_type_from_manifest, resolve_op_type, ensure_manifest_tags, apply_family_color, get_params_to_retain, get_self_pars_to_retain

class UpdateManager:
	"""
	Manages operator updates for an operator family.

	Updates replace an operator's internals with the latest version
	while preserving connections, position, and parameter values.
	"""

	def __init__(self, ownerComp, registry):
		"""
		Initialize the update manager.

		Args:
			ownerComp: The component that owns this extension
			registry: The OpFamRegistryExt instance
		"""
		self.ownerComp = ownerComp
		self.registry = registry



	def find_matching_master(self, family_name, comp):
		"""
		Find a matching master operator for a component.

		Uses resolve_op_type to check manifest first, then tags.

		Returns:
			tuple: (source_type, source, match_method) or (None, None, 'none')
		"""
		installer = self.registry.GetFamilyExt(family_name)
		if not installer:
			return (None, None, 'none')

		category_tags = self.registry._GetCategoryTags(family_name) or set()
		comp_type, info_type = resolve_op_type(comp, family_name, self.registry.TagManager, category_tags)

		if comp_type:
			result = self.registry.FileManager.get_operator_source(
				family_name, comp_type
			)
			if result:
				source_type, source = result
				return (source_type, source, info_type)

		return (None, None, 'none')

	def _copy_par(self, dest_par, source_par):
		"""Copy parameter value/mode from source to destination."""
		dest_par.mode = source_par.mode
		if source_par.mode == ParMode.CONSTANT:
			dest_par.val = source_par.val
		elif source_par.mode == ParMode.EXPRESSION:
			dest_par.expr = source_par.expr
		elif source_par.mode == ParMode.BIND:
			dest_par.bindExpr = source_par.bindExpr

	def update_operator(self, family_name, old_comp):
		"""
		Update a single operator to the newest version.

		Args:
			family_name: The family name
			old_comp: The component to update

		Returns:
			tuple: (success, message)
		"""
		installer = self.registry.GetFamilyExt(family_name)
		if not installer:
			return (False, f"Family {family_name} not found")

		source_type, source, match_method = self.find_matching_master(family_name, old_comp)
		if not source:
			return (False, f"Couldn't update {old_comp.path}, no matching master found")

		# Prepare master_op for hook and update
		master_op = None
		is_file_loaded = False

		try:
			if source_type == 'embedded':
				master_op = source
			elif source_type == 'file':
				try:
					master_op = old_comp.parent().loadTox(source)
					is_file_loaded = True
				except Exception as e:
					return (False, f"Error loading tox {source}: {e}")

			# Hook: PreUpdate - can return False to skip, or modify master
			pre_update = self.registry.CallHook(family_name, '_PreUpdate', old_comp, master_op)
			if isinstance(pre_update, dict):
				if pre_update.get('returnValue') is False:
					if is_file_loaded and master_op:
						master_op.destroy()
					return (False, f"Update cancelled by PreUpdate hook for {old_comp.path}")
				master_op = pre_update.get('master', master_op)
			elif pre_update is False:
				if is_file_loaded and master_op:
					master_op.destroy()
				return (False, f"Update cancelled by PreUpdate hook for {old_comp.path}")

			# Create new_comp (or use loaded)
			new_comp = None
			if is_file_loaded:
				new_comp = master_op
			else:
				new_comp = old_comp.parent().copy(master_op)
			
			if not new_comp:
				if is_file_loaded and master_op:
					master_op.destroy()
				return (False, "Failed to create new component")

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

			# Read ParRetain for update scenario
			par_retain_data = {}
			old_manifest = old_comp.op('FamManifest')
			if old_manifest:
				_par_retain_dat = old_manifest.op('ParRetain')
				if _par_retain_dat:
					try:
						par_retain_data = json.loads(_par_retain_dat.text)
					except:
						pass

			# Determine which top-level params to retain (None = retain all)
			self_key = next((k for k in ['.', ''] if k in par_retain_data), None)
			pars_to_retain = get_self_pars_to_retain(new_comp, 'update', par_retain_data[self_key]) if self_key is not None else None

# 1. Synchronize sequences first
			processed_seqs = set()
			skip_seqs = {'ext', 'iop'}

			for p in new_comp.pars():
				if hasattr(p, 'sequence') and p.sequence:
					seq_name = p.sequence.name
					if seq_name in skip_seqs or seq_name in processed_seqs:
						continue
					if pars_to_retain is not None and seq_name not in pars_to_retain:
						continue
					processed_seqs.add(seq_name)

					old_pars = old_comp.pars(p.name)
					if old_pars and hasattr(old_pars[0], 'sequence'):
						p.sequence.numBlocks = old_pars[0].sequence.numBlocks

			# 2. Copy top-level parameters (now that sequences are sized)
			skip_pars = {'Version', 'Copyright', 'opshortcut', 'parentshortcut'}
			for p in new_comp.pars():
				if p.name in skip_pars:
					continue
				if hasattr(p, 'sequence') and p.sequence and p.sequence.name in skip_seqs:
					continue
				if pars_to_retain is not None and p.name not in pars_to_retain:
					continue

				old_pars = old_comp.pars(p.name)
				if old_pars:
					self._copy_par(p, old_pars[0])

			# 3. Copy retained params for each child path in ParRetain
			all_new_children = [c.name for c in new_comp.findChildren(depth=1)]
			for key, _ in par_retain_data.items():
				if key in ('.', ''):
					continue
				for child_path in tdu.match(key, all_new_children):
					target_old = old_comp.op(child_path)
					target_new = new_comp.op(child_path)
					if not target_old or not target_new:
						continue
					child_pars = get_params_to_retain(key, 'update', par_retain_data, comp=target_new)
					for p in target_new.pars():
						if p.name not in child_pars:
							continue
						old_pars = target_old.pars(p.name)
						if old_pars:
							self._copy_par(p, old_pars[0])

			# Ensure manifest exists on new comp (handles edge case where old op
			# was non-COMP with no manifest but new master is a COMP)
			if new_comp.isCOMP:
				OpInfo, _, _ = self.registry.OpManager._validate_manifest(
					installer.ownerComp, new_comp,
					tox_file_version=None, display_name=old_name
				)
				self.registry.OpManager._tag_op(installer.ownerComp, new_comp, OpInfo)
			else:
				ensure_manifest_tags(new_comp, family_name, is_manifest=False)

			# Hook: PreserveSpecialParams
			self.registry.CallHook(family_name, '_PreserveSpecialParams', new_comp, old_comp)

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

			# Apply family color for file-based ops
			if is_file_loaded and hasattr(installer, 'ownerComp'):
				apply_family_color(installer.ownerComp, new_comp)

			# Hook: PostUpdate
			self.registry.CallHook(family_name, '_PostUpdate', new_comp)

			return (True, f"Updated {new_comp.path} (matched via {match_method})")

		except Exception as e:
			return (False, f"Error updating {old_comp.path}: {e}")

	def analyze_operators(self, family_name, operators):
		"""
		Analyze operators for update compatibility.

		Args:
			family_name: The family name
			operators: List of operators to analyze

		Returns:
			dict: Analysis results
		"""
		installer = self.registry.GetFamilyExt(family_name)
		if not installer:
			return {'without_matches': [], 'updateable': [], 'with_manifest': [], 'with_ext_object': []}

		results = {
			'with_manifest': [],
			'with_ext_object': [],
			'without_matches': [],
			'updateable': []
		}

		for comp in operators:
			manifest = comp.op('FamManifest')
			if manifest and get_op_type_from_manifest(manifest):
				results['with_manifest'].append(comp)
				results['updateable'].append(comp)
			else:
				# source_type: from file or comp
				# info_type: from manifest or tag
				source_type, _, info_type = self.find_matching_master(family_name, comp)
				if info_type == 'manifest':
					results['with_manifest'].append(comp)

				if source_type:
					results['updateable'].append(comp)
				else:
					results['without_matches'].append(comp)

		return results

	def update_batch(self, family_name, operators):
		"""
		Update multiple operators.

		Args:
			family_name: The family name
			operators: List of operators to update

		Returns:
			dict: Results with updated, skipped, errors lists
		"""
		ui.undo.startBlock(f'Update {family_name} operators')

		results = {
			'updated': [],
			'skipped': [],
			'errors': []
		}

		for op_comp in operators:
			try:
				success, message = self.update_operator(family_name, op_comp)
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
