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
		1. Type tag (e.g., agentLOP -> agent)
		2. ext0object parameter

		Args:
			family_name: The family name
			comp: The component to find a match for

		Returns:
			tuple: (source_type, source, match_method) or (None, None, 'none')
		"""
		installer = self.registry.GetFamilyExt(family_name)
		if not installer:
			return (None, None, 'none')

		category_tags = self.registry.CallHook(family_name, '_GetCategoryTags') or set()
		
		# Try matching by type tag
		if self.registry.TagManager.has_operator_type_tag(comp, family_name, category_tags):
			comp_type = self.registry.TagManager.get_operator_type(comp, family_name, category_tags)
			source_type, source = self.registry.FileManager.get_operator_source(
				family_name,
				comp_type,
				getattr(installer, 'operators_folder', None),
				getattr(installer, 'dynamic_refresh', False)
			) or (None, None)
			
			if source:
				return (source_type, source, 'type_tag')


		# Try matching by ext0object
		# This is legacy/specific, assumes embedded master currently
		operators_folder = installer.operators_comp
		if operators_folder and hasattr(comp.par, 'ext0object'):
			ext_obj = comp.par.ext0object.eval()
			if ext_obj:
				for master_op in operators_folder.findChildren(type=COMP, maxDepth=1):
					if hasattr(master_op.par, 'ext0object'):
						if master_op.par.ext0object.eval() == ext_obj:
							return ('embedded', master_op, 'ext0object')

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

			# Hook: PreUpdate
			if self.registry.CallHook(family_name, '_PreUpdate', old_comp, master_op) is False:
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

			# Hook: PostUpdate
			self.registry.CallHook(family_name, '_PostUpdate', new_comp)

			return (True, f"Updated {new_comp.path} (matched via {match_method})")

		except Exception as e:
			return (False, f"Error updating {old_comp.path}: {e}")

	def find_family_operators(self, family_name, network=None):
		"""
		Find all operators of this family.

		Args:
			family_name: The family name
			network: Optional network to search in

		Returns:
			list: Family operators (excluding installer)
		"""
		installer = self.registry.GetFamilyExt(family_name)
		if not installer:
			return []

		excluded_tags = self.registry.CallHook(family_name, '_GetExcludedTags') or set()

		search_root = network or op('/')
		depth = 1 if network else None

		return search_root.findChildren(
			type=COMP,
			maxDepth=depth,
			key=lambda o: (
				family_name in o.tags and
				not any(tag in o.tags for tag in excluded_tags) and
				o != installer.ownerComp and
				installer.ownerComp.path not in o.path and
				(not installer.operators_comp or installer.operators_comp.path not in o.path)
			)
		)

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
			return {'without_matches': [], 'updateable': [], 'with_type_tags': [], 'with_ext_object': []}

		operators_folder = installer.operators_comp
		category_tags = self.registry._GetCategoryTags(family_name) or set()

		results = {
			'with_type_tags': [],
			'with_ext_object': [],
			'without_matches': [],
			'updateable': []
		}

		for comp in operators:
			if self.registry.TagManager.has_operator_type_tag(comp, family_name, category_tags):
				results['with_type_tags'].append(comp)
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
