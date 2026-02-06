"""
Update system for opfam-create.

Handles updating operators to newer versions while preserving
connections and parameter values.
"""

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

		Matching methods:
		1. FamManifest OpInfo op_type
		2. ext0object parameter (legacy fallback)

		Returns:
			tuple: (source_type, source, match_method) or (None, None, 'none')
		"""
		installer = self.registry.GetFamilyExt(family_name)
		if not installer:
			return (None, None, 'none')

		# Try matching by manifest op_name
		manifest = comp.op('FamManifest')
		if manifest:
			comp_type = self._get_op_type_from_manifest(manifest)
			if comp_type:
				source_type, source = self.registry.FileManager.get_operator_source(
					family_name,
					comp_type,
					getattr(installer, 'operators_folder', None),
					getattr(installer, 'dynamic_refresh', False)
				) or (None, None)

				if source:
					return (source_type, source, 'manifest')

		# Legacy fallback: ext0object
		operators_folder = installer.operators_comp
		if operators_folder and hasattr(comp.par, 'ext0object'):
			ext_obj = comp.par.ext0object.eval()
			if ext_obj:
				for master_op in operators_folder.findChildren(type=COMP, maxDepth=1):
					if hasattr(master_op.par, 'ext0object'):
						if master_op.par.ext0object.eval() == ext_obj:
							return ('embedded', master_op, 'ext0object')

		return (None, None, 'none')

	def _get_op_type_from_manifest(self, manifest):
		"""Read op_name from a FamManifest's OpInfo."""
		import json
		op_info_dat = manifest.op('OpInfo')
		if op_info_dat:
			try:
				return json.loads(op_info_dat.text).get('op_type', '')
			except:
				pass
		return ''

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

			# 1. Synchronize sequences first
			processed_seqs = set()
			skip_seqs = {'ext', 'iop'}
			
			for p in new_comp.pars():
				if hasattr(p, 'sequence') and p.sequence:
					seq_name = p.sequence.name
					if seq_name in skip_seqs or seq_name in processed_seqs:
						continue
					processed_seqs.add(seq_name)
					
					# Find matching sequence in old_comp
					# We can't access sequences by name easily on op, so check param
					old_pars = old_comp.pars(p.name)
					if old_pars and hasattr(old_pars[0], 'sequence'):
						p.sequence.numBlocks = old_pars[0].sequence.numBlocks

			# 2. Copy all parameters (now that sequences are sized)
			skip_pars = {'Version', 'Copyright', 'opshortcut', 'parentshortcut'}
			for p in new_comp.pars():
				if p.name in skip_pars:
					continue
				if hasattr(p, 'sequence') and p.sequence and p.sequence.name in skip_seqs:
					continue

				old_pars = old_comp.pars(p.name)
				if old_pars:
					self._copy_par(p, old_pars[0])

			# Ensure manifest exists on new comp
			new_manifest = new_comp.op('FamManifest')
			if not new_manifest:
				old_manifest = old_comp.op('FamManifest')
				if old_manifest:
					new_manifest = new_comp.copy(old_manifest)
			if new_manifest:
				if f'<FAM:{family_name}>' not in new_manifest.tags:
					new_manifest.tags.add(f'<FAM:{family_name}>')
				if '<MANIFEST>' not in new_manifest.tags:
					new_manifest.tags.add('<MANIFEST>')

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
				fam_owner = installer.ownerComp
				if hasattr(fam_owner.par, 'Colorfileops') and fam_owner.par.Colorfileops.eval():
					new_comp.color = (fam_owner.par.Colorr.eval(), fam_owner.par.Colorg.eval(), fam_owner.par.Colorb.eval())

			# Hook: PostUpdate
			self.registry.CallHook(family_name, '_PostUpdate', new_comp)

			return (True, f"Updated {new_comp.path} (matched via {match_method})")

		except Exception as e:
			return (False, f"Error updating {old_comp.path}: {e}")

	def find_family_operators(self, family_name, network=None):
		"""
		Find all operators of this family via their FamManifest tags.

		Returns:
			list: Family operators (excluding installer and operators_comp)
		"""
		installer = self.registry.GetFamilyExt(family_name)
		if not installer:
			return []

		search_root = network or op('/')
		manifests = search_root.findChildren(
			type=COMP,
			tags=[f'<FAM:{family_name}>', '<MANIFEST>'],
		)

		operators = []
		for m in manifests:
			parent_op = m.parent()
			if not parent_op:
				continue
			if '<STUB>' in m.tags:
				continue
			if parent_op == installer.ownerComp:
				continue
			if installer.ownerComp.path in parent_op.path:
				continue
			if installer.operators_comp and installer.operators_comp.path in parent_op.path:
				continue
			operators.append(parent_op)
		return operators

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
			if manifest and self._get_op_type_from_manifest(manifest):
				results['with_manifest'].append(comp)
				results['updateable'].append(comp)
			elif hasattr(comp.par, 'ext0object') and comp.par.ext0object.eval():
				results['with_ext_object'].append(comp)
				results['updateable'].append(comp)
			else:
				source_type, _, _ = self.find_matching_master(family_name, comp)
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
