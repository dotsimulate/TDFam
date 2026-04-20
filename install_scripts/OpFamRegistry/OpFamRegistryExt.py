from __future__ import annotations
from TDStoreTools import DependDict
from GlobalUIInjector import GlobalUIInjector
from TagManager import TagManager
from StubManager import StubManager
from UpdateManager import UpdateManager
from FileManager import FileManager
from OpManager import OpManager
from ShortcutManager import ShortcutManager
from RegistryHelpers import get_op_type_from_manifest

class OpFamRegistryExt:
	def __init__(self, ownerComp):
		self.ownerComp = ownerComp
		self.RegisteredFams = DependDict({})
		self.InstalledFams = DependDict({})
		self.EventEmitter = self.ownerComp.op('eventEmitter')
		self.global_ui_injector = GlobalUIInjector(self.ownerComp, self)
		
		# Initialize Helper Systems
		self.TagManager = TagManager(self.ownerComp, self)
		self.StubManager = StubManager(self.ownerComp, self)
		self.UpdateManager = UpdateManager(self.ownerComp, self)
		self.FileManager = FileManager(self.ownerComp, self)
		self.OpManager = OpManager(self.ownerComp, self)
		self.ShortcutManager = ShortcutManager(self.ownerComp, self)

		self._dev_overwrite_mode = False
		
		run(lambda: self.postInit(), delayFrames=1, delayRef=op.TDResources)

	def postInit(self):
		# Skip if we're a staging copy (used by MockUpdate)
		if self.ownerComp.path == '/sys/quiet':
			return
		
		if hasattr(op, 'FAMREGISTRY') and self.ownerComp == op.FAMREGISTRY:
			# we just update the global registry in place, so we can restore families
			# Restore Registered and Installed families
			restored_registered = self.ownerComp.fetch('RegisteredFams', {})
			restored_installed = self.ownerComp.fetch('InstalledFams', {})

			for _reg_fam in restored_registered:
				self.RegisterFamily(restored_registered[_reg_fam])
			for _inst_fam in restored_installed:
				self.InstallFamily(restored_installed[_inst_fam])

			self.ShortcutManager.restore()
			self.ShortcutManager.enableShortcutDat()
		else:
			# Check if we're post-update
			is_post_update = self.ownerComp.fetch('post_update', False)
			if is_post_update:
				# we update a local registry, we need to reconcile with global
				self._reconcile_global_registry()
				self.ownerComp.unstore('post_update')

			

	def _reconcile_global_registry(self):
		"""
		Check for existing global registry and handle version reconciliation.

		If we ARE the global registry (op.FAMREGISTRY), do nothing.
		If another registry exists:
			- Compare versions
			- Replace it if we're newer
			- Destroy ourselves if it's newer or equal
		If no global registry exists, become the global registry.
		"""
		
		global_registry = op.FAMREGISTRY if hasattr(op, 'FAMREGISTRY') else None
		if not global_registry:
			# No existing global registry - become it
			debug('OpFamRegistry: No existing global registry found. Becoming global registry.')
			self._become_global_registry()
			return

		# Another registry exists - compare versions
		should_keep_existing = self._check_version_against(global_registry)

		if should_keep_existing:
			# Existing registry is same or newer
			debug(f'OpFamRegistry: Existing registry at {global_registry.path} is same or newer.')
			# Transfer any families we might have to the existing registry
			# self._transfer_families_to(global_registry)
		else:
			# We are newer - replace the existing registry
			debug(f'OpFamRegistry: We are newer than existing registry at {global_registry.path}. Replacing it.')
			self._replace_global_registry(global_registry)

	def _become_global_registry(self):
		"""
		Become the global registry at /sys/OpFamRegistry.

		If already at /sys/OpFamRegistry, just sets the shortcut.
		Otherwise, copies ourselves to /sys, positions relative to TDDialogs,
		transfers families, and destroys the original.

		Follows installer.py's _get_or_create_fam_registry pattern.
		"""
		sys_registry_path = '/sys/OpFamRegistry'

		# If we're already at /sys/OpFamRegistry, just set the shortcut
		if self.ownerComp.path == sys_registry_path:
			self.ownerComp.par.opshortcut = 'FAMREGISTRY'
			return

		# We need to copy ourselves to /sys (same as installer.py)
		sys_comp = op('/sys')
		if not sys_comp:
			debug('OpFamRegistry: /sys not found, cannot become global registry.')
			return

		# Copy ourselves to /sys
		new_registry = sys_comp.copy(self.ownerComp, name='OpFamRegistry')
		new_registry.allowCooking = True
		new_registry.op('internal_pars').par.Dev = False
		new_registry.op('internal_pars').par.Force = False

		# Position relative to TDDialogs (same as installer.py)
		td_dialogs = sys_comp.op('TDDialogs')
		if td_dialogs:
			new_registry.nodeX = td_dialogs.nodeX
			new_registry.nodeY = td_dialogs.nodeY - 200

		# Set the shortcut
		new_registry.par.opshortcut = 'FAMREGISTRY'

		# Store families for new registry to restore in postInit
		new_registry.store('post_update', True)
		new_registry.store('RegisteredFams', dict(self.ownerComp.fetch('RegisteredFams', {})))
		new_registry.store('InstalledFams', dict(self.ownerComp.fetch('InstalledFams', {})))
		new_registry.store('ShortcutDict', self.ownerComp.fetch('ShortcutDict', {}))

		debug(f'OpFamRegistry: Copied to {new_registry.path}.')

		# Destroy ourselves
		# run(lambda: self.ownerComp.destroy(), delayFrames=1, delayRef=op.TDResources)
		return new_registry

	def _transfer_families_to(self, target_registry):
		"""
		Transfer our registered/installed families to another registry.

		Args:
			target_registry: The registry to transfer families to.
		"""
		if not target_registry or not hasattr(target_registry, 'RegisterFamily'):
			return

		for fam_name, fam_owner in self.RegisteredFams.items():
			if fam_name not in target_registry.RegisteredFams:
				target_registry.RegisterFamily(fam_owner)

		for fam_name, fam_owner in self.InstalledFams.items():
			if fam_name not in target_registry.InstalledFams:
				target_registry.InstallFamily(fam_owner)

	def _replace_global_registry(self, old_registry):
		"""
		Replace the existing global registry with ourselves.

		Follows installer.py's _get_or_create_fam_registry pattern:
		1. Capture families from old registry
		2. Destroy old registry
		3. Set ourselves as global registry
		4. Re-register all families

		Args:
			old_registry: The existing registry to replace.
		"""
		# Capture families from old registry
		previous_registered_fams = old_registry.RegisteredFams if hasattr(old_registry, 'RegisteredFams') else {}
		previous_installed_fams = old_registry.InstalledFams if hasattr(old_registry, 'InstalledFams') else {}

		# Destroy the old registry
		old_registry.destroy()

		# Become the global registry
		new_global = self._become_global_registry()

		

	def _check_version_against(self, other_registry):
		"""
		Compare our version against another registry.

		Args:
			other_registry: The registry to compare against.

		Returns:
			bool: True if other_registry should be kept (is >= our version),
			      False if we should replace it (we are newer).
		"""
		our_version = self._parse_version(self._get_version(self.ownerComp))
		their_version = self._parse_version(self._get_version(other_registry))

		# If we can't determine versions, keep existing
		if our_version is None:
			return True
		if their_version is None:
			return False  # We have a version, they don't - replace them

		# Check for major version difference
		if our_version[0] != their_version[0]:
			our_str = '.'.join(str(x) for x in our_version)
			their_str = '.'.join(str(x) for x in their_version)
			choice = ui.messageBox(
				'Registry Version Conflict',
				f'Multiple OpFamRegistry versions detected.\n\n'
				f'Existing: v{their_str} at {other_registry.path}\n'
				f'New: v{our_str} at {self.ownerComp.path}\n\n'
				f'Which version should be used?',
				buttons=['Use New', 'Keep Existing']
			)
			return choice != 0  # 0 = Use New (return False), 1 = Keep Existing (return True)

		# Keep existing if their version >= our version
		return their_version >= our_version

	def _get_version(self, comp):
		"""Get version string from a component."""
		if comp and hasattr(comp.par, 'Version'):
			return str(comp.par.Version.eval())
		return None

	def _parse_version(self, ver_string):
		"""
		Parse version string to tuple for comparison.

		Args:
			ver_string: Version string like '1.2.3' or 'v1.2.3'

		Returns:
			tuple: (1, 2, 3) or None if invalid.
		"""
		if not ver_string:
			return None
		try:
			ver_string = ver_string.lstrip('vV')
			return tuple(int(x) for x in ver_string.split('.'))
		except:
			return None

# region Properties

	@property
	def NumFamiliesRegistered(self):
		return len(self.RegisteredFams)

	@property
	def NumFamiliesInstalled(self):
		return len(self.InstalledFams)

# endregion Properties

# region Family Housekeeping

	def IsFamilyInstalled(self, fam_name):
		"""Public API to check if a family is installed."""
		return fam_name in self.InstalledFams

	def IsFamilyUIInstalled(self, fam_name):
		"""Public API to check if a family's UI is installed."""
		return self.global_ui_injector.is_family_installed(fam_name)

	def GetFamilyName(self, family_owner):
		"""
		Get family name by owner.
		Checks installed families first, then registered.
		"""
		return family_owner.Properties['family_name']

	def GetFamilyOwner(self, fam_name):
		"""
		Get family owner by name.
		Checks installed families first, then registered.
		"""
		if fam_name in self.InstalledFams:
			return self.InstalledFams[fam_name]
		if fam_name in self.RegisteredFams:
			return self.RegisteredFams[fam_name]
		else:
			raise ValueError(f'Family {fam_name} not found in Registry')

	def GetFamilyExt(self, fam_name):
		"""
		Get family owner (OpFamExt) by name.
		Checks installed families first, then registered.
		"""
		try:
			family_owner = self.GetFamilyOwner(fam_name)
			if family_owner and hasattr(family_owner, 'ext') and hasattr(family_owner.ext, 'OpFamExt'):
				return family_owner.ext.OpFamExt
		except:
			pass
		return None

	def ValidateFamilyOwner(self, fam_name, family_owner):
		"""
		Check if family owner from argument is the same as the registered one.
		Returns True if they match or if family_owner is None (for internal calls), 
		False if they don't match.
		"""
		if family_owner is None:
			return False
		
		actual_owner = self.RegisteredFams.get(fam_name, None)
		if not actual_owner:
			return True # If family doesn't exist, we don't have an owner to compare against
			
		return actual_owner == family_owner

# endregion Family Housekeeping

# region Family Management

	def RegisterFamily(self, family_owner : OpFamCreateExt):
		fam_name = family_owner.Properties['family_name']
		if fam_name in self.RegisteredFams and not self._is_overwrite(fam_name, family_owner):
			debug(f'Family {fam_name} already registered. Skipping registration.')
			return False
		self._add_fam_tag(family_owner)
		self._setFamilyDict(self.RegisteredFams, fam_name, family_owner)
		debug(f'Registered family: {fam_name}')
		self.EventEmitter.Emit('FamilyRegistered', fam_name, family_owner)
		return True

	def UnregisterFamily(self, family_owner_or_name):
		"""Unregister a family by name or owner instance."""
		if hasattr(family_owner_or_name, 'Properties'):
			fam_name = family_owner_or_name.Properties['family_name']
		else:
			fam_name = family_owner_or_name

		if fam_name in self.RegisteredFams:
			self._deleteItemFromFamilyDict(self.RegisteredFams, fam_name)
			debug(f'Unregistered family: {fam_name}')
			self.EventEmitter.Emit('FamilyUnregistered', fam_name)

			# also uninstall if installed
			if fam_name in self.InstalledFams:
				debug(f'Also uninstalling family {fam_name} as part of unregistration.')
				self.UninstallFamily(family_owner_or_name if not isinstance(family_owner_or_name, str) else fam_name)

	def InstallFamily(self, family_owner):
		"""Install a family by owner."""
		fam_name = family_owner.Properties['family_name'] if not isinstance(family_owner, str) else family_owner
		if not self.ValidateFamilyOwner(fam_name, family_owner):
			return False
		# If it's a string, we still need the actual owner for installation logic
		if isinstance(family_owner, str):
			family_owner = self.RegisteredFams.get(fam_name)
			
		if not family_owner:
			raise ValueError(f"Cannot install {fam_name}: not registered.")
		
		self._PreInstall(fam_name)

		self._setFamilyDict(self.InstalledFams, fam_name, family_owner)
		debug(f'Installed family: {fam_name}')
		self.global_ui_injector.install(fam_name, family_owner)
		self.EventEmitter.Emit('FamilyInstalled', fam_name, family_owner)

		self._PostInstall(fam_name)

	def UninstallFamily(self, family_owner):
		"""Uninstall a family by owner."""
		fam_name = family_owner.Properties['family_name'] if not isinstance(family_owner, str) else family_owner
		if not self.ValidateFamilyOwner(fam_name, family_owner):
			return False
		
		self._PreUninstall(fam_name)

		if fam_name in self.InstalledFams:
			self._deleteItemFromFamilyDict(self.InstalledFams, fam_name)
			debug(f'Uninstalled family: {fam_name}')
			self.global_ui_injector.uninstall(fam_name)
			self.ShortcutManager.unregisterOpShortcutsForFamily(fam_name)
			self.EventEmitter.Emit('FamilyUninstalled', fam_name)
			
			self._PostUninstall(fam_name)
			return True
		return False

	def UpdateFamilyName(self, family_owner, new_name):
		# Capture old name from owner before it's updated elsewhere
		old_name = family_owner.Properties['family_name']
		
		if old_name == new_name:
			return True

		# Validate owner
		if not self.ValidateFamilyOwner(old_name, family_owner):
			debug(f'UpdateFamilyName ignored: owner mismatch for {old_name}')
			return False

		# Update registry storage
		if old_name in self.RegisteredFams:
			self._deleteItemFromFamilyDict(self.RegisteredFams, old_name)
			self._setFamilyDict(self.RegisteredFams, new_name, family_owner)

		if old_name in self.InstalledFams:
			self._deleteItemFromFamilyDict(self.InstalledFams, old_name)
			self._setFamilyDict(self.InstalledFams, new_name, family_owner)

			# Only update global UI if installed
			self.global_ui_injector.update_family_name(old_name, new_name)

		# Update properties and shortcut
		if hasattr(family_owner, 'Properties'):
			family_owner.Properties['family_name'] = new_name
		
		# send event now that we actually succeeded
		self.EventEmitter.Emit('FamilyRenamed', old_name, new_name, family_owner)
		debug(f'Family renamed: {old_name} -> {new_name}')
		
		return True
	
	def UpdateFamilyColor(self, family_owner, new_color):
		"""Update family color in UI elements."""
		fam_name = family_owner.Properties['family_name']
		
		# Validate owner
		if not self.ValidateFamilyOwner(fam_name, family_owner):
			debug(f'UpdateFamilyColor ignored: owner mismatch for {fam_name}')
			return False

		if fam_name in self.RegisteredFams:
			self.global_ui_injector.update_family_color(fam_name, new_color)
		
		return True

	def UpdateFamilyIndexOrder(self, family_name, family_owner):
		if not self.ValidateFamilyOwner(family_name, family_owner):
			debug(f'UpdateFamilyIndexOrder ignored: owner mismatch for {family_name}')
			return False
		self.global_ui_injector.update_family_evals()
		return True

	def UpdateCompatibleTable(self, family_name, family_owner):
		if not self.ValidateFamilyOwner(family_name, family_owner):
			debug(f'updateCompatibleTable ignored: owner mismatch for {family_name}')
			return False
		self.global_ui_injector.update_compatible_table(family_name, family_owner)
		return True

	def onRegistryChangeCallback(self, cells, prev):
		"""This checks deletion of family owners for deregistration."""
		for idx, _cell in enumerate(cells):
			_val = _cell.val
			if _val != prev[idx] and _val == 'None':
				self.UnregisterFamily(prev[idx])

# endregion Family Management

# region Operator Management

	def manageOpClone(self, fam_name, opType, display_name):
		"""
		Modify the placed operator before it is added to the scene.
		"""
		family_owner = self.GetFamilyOwner(fam_name)
		clone = self.OpManager.manageOpClone(family_owner, opType, display_name)
		return clone

	def FindOps(self, family_name,
			   type=None, name=None, path=None,
			   depth=None, maxDepth=None,
			   tags=[], allTags=False,
			   parValue=None, parExpr=None, parName=None,
			   key=None,
			   include_stubs=True, network=None):
		"""
		Find placed operators of a family. Mirrors TD's findChildren API.

		Phase 1: Find all FamManifest COMPs tagged <FAM:name> + <MANIFEST>.
		Phase 2: Post-filter parent operators with findChildren-style params.

		Args:
			family_name: The family name to search for
			type: Filter by TD OP type (e.g. COMP, TOP)
			name: Filter by name pattern (fnmatch, e.g. 'agent*')
			path: Filter by path pattern (fnmatch)
			depth: Exact depth relative to network root
			maxDepth: Maximum depth relative to network root
			tags: Additional tag filters (checked on operator AND manifest)
			allTags: If True, require all tags to match
			parValue: Filter ops with a parameter matching this value
			parExpr: Filter ops with a parameter matching this expression
			parName: Parameter name to check for parValue/parExpr filters
			key: Custom filter function â€” key(op) must return True to include
			include_stubs: If True, include stubbed operators in results
			network: Root component to search from (defaults to /)

		Returns:
			list: Matching placed family operators
		"""
		import fnmatch as _fnmatch

		installer = self.GetFamilyExt(family_name)
		if not installer:
			return []

		search_root = network or op('/')

		# Phase 1: Find all manifests for this family
		manifests = search_root.findChildren(
			type=COMP,
			tags=[f'<FAM:{family_name}>', '<MANIFEST>'],
			allTags=True,
		)

		# Collect parent operators with standard exclusions
		operators = []
		for m in manifests:
			parent_op = m.parent()
			if not parent_op:
				continue
			if not include_stubs and '<STUB>' in m.tags:
				continue
			if parent_op == installer.ownerComp:
				continue
			if installer.ownerComp.path in parent_op.path:
				continue
			if installer.operators_comp and installer.operators_comp.path in parent_op.path:
				continue
			operators.append((parent_op, m))

		# Phase 2: Apply findChildren-style filters
		results = []
		root_depth = search_root.path.rstrip('/').count('/')

		for o, manifest in operators:
			if type is not None and not isinstance(o, type):
				continue

			if name is not None and not _fnmatch.fnmatch(o.name, name):
				continue

			if path is not None and not _fnmatch.fnmatch(o.path, path):
				continue

			if depth is not None or maxDepth is not None:
				op_depth = o.path.rstrip('/').count('/') - root_depth
				if depth is not None and op_depth != depth:
					continue
				if maxDepth is not None and op_depth > maxDepth:
					continue

			if tags:
				combined_tags = set(o.tags) | set(manifest.tags)
				if allTags:
					if not all(t in combined_tags for t in tags):
						continue
				else:
					if not any(t in combined_tags for t in tags):
						continue

			if parName is not None:
				if not hasattr(o.par, parName):
					continue
				if parValue is not None and getattr(o.par, parName).eval() != parValue:
					continue
				if parExpr is not None and getattr(o.par, parName).expr != parExpr:
					continue

			if key is not None and not key(o):
				continue

			results.append(o)

		return results

	def GetOperators(self, family_name):
		"""
		Get all available operators in a family with full metadata.

		Enumerates embedded operators (from operators_comp) and file-based
		operators (from folder_cache), reads OpInfo manifests, and merges
		with Config data (groups, OS compat, label replacements).

		Args:
			family_name: The family name to query

		Returns:
			dict: Keyed by op_type. Each value contains:
				op_type, op_name, op_label, op_version, fam_version,
				op_fam, group, source, os_compatible
		"""
		installer = self.GetFamilyExt(family_name)
		if not installer:
			return {}

		# Config data
		config = installer.Config
		group_mapping = config.get('group_mapping', {})
		label_replacements = config.get('label_replacements', {})
		os_incompatible = config.get('os_incompatible', {})
		# Build lookup indexes from config
		group_index = {}
		for group_name, operators in group_mapping.items():
			for op_name in operators:
				group_index[op_name.lower().replace(' ', '_')] = group_name

		os_index = {}
		for op_name, os_data in os_incompatible.items():
			normalized = op_name.lower().replace(' ', '_')
			os_index[normalized] = {
				'windows': os_data.get('windows', 1),
				'mac': os_data.get('mac', 1),
				'exclude': os_data.get('exclude', 0),
			}

		# fam_version for file-based ops (no TD operator to read from)
		fam_version = None
		if hasattr(installer.ownerComp.par, 'Version'):
			fam_version = str(installer.ownerComp.par.Version.eval())

		result = {}

		# Collect all operator names from both sources
		all_op_names = set()
		embedded_ops = {}
		custom_ops = installer.operators_comp
		if custom_ops:
			for _op in custom_ops.findChildren(maxDepth=1):
				if hasattr(_op, 'par') and hasattr(_op.par, 'parentshortcut') and _op.par.parentshortcut.eval() == 'Annotate':
					continue
				embedded_ops[_op.name.lower()] = _op
				all_op_names.add(_op.name.lower())

		folder_cache = installer.Properties.get('folder_cache', {})
		if folder_cache:
			for name in folder_cache:
				all_op_names.add(name.lower())

		# Resolve each operator once via get_operator_source
		for lookup_name in all_op_names:
			source = self.FileManager.get_operator_source(family_name, lookup_name)
			if not source:
				continue

			normalized = lookup_name.replace(' ', '_')

			if source[0] == 'embedded':
				_op = source[1]
				op_info = self.OpManager.GetOpInfo(_op, installer.ownerComp)

				op_label = op_info.get('op_label', _op.name)
				for old, new in label_replacements.items():
					op_label = op_label.replace(old, new)

				op_type = op_info.get('op_type', lookup_name)
				result[op_type] = {
					'op_type': op_type,
					'op_name': op_info.get('op_name', _op.name),
					'op_label': op_label,
					'op_version': op_info.get('op_version'),
					'fam_version': op_info.get('fam_version'),
					'op_fam': op_info.get('op_fam', family_name),
					'group': op_info.get('op_group') or group_index.get(normalized) or None,
					'source': source,
					'os_compatible': os_index.get(normalized, {'windows': 1, 'mac': 1, 'exclude': 0}),
				}

			elif source[0] == 'file':
				file_info = folder_cache.get(lookup_name, {})
				ext_manifest = file_info.get('manifest') or {}
				ext_opinfo = ext_manifest.get('OpInfo', {})

				op_label = ext_opinfo.get('op_label') or ' '.join(w.capitalize() for w in lookup_name.split('_'))
				op_label = self.OpManager._sanitize_label(op_label)
				for old, new in label_replacements.items():
					op_label = op_label.replace(old, new)

				group = ext_opinfo.get('op_group') or group_index.get(normalized)
				if group is None and file_info.get('category'):
					group = file_info['category']

				result[lookup_name] = {
					'op_type': ext_opinfo.get('op_type') or lookup_name,
					'op_name': ext_opinfo.get('op_name') or lookup_name,
					'op_label': op_label,
					'op_version': ext_opinfo.get('op_version') or file_info.get('version'),
					'fam_version': fam_version,
					'op_fam': family_name,
					'group': group,
					'source': source,
					'os_compatible': os_index.get(normalized, {'windows': 1, 'mac': 1, 'exclude': 0}),
					'compatible_types': ext_opinfo.get('compatible_types', []),
				}

		return result

	def PlaceOp(self, family_name, target, op_type, name=None, x=None, y=None):
		"""
		Programmatically place an operator into a target COMP.
		Runs the full manifest + callback chain identical to the OP Create Dialog path.

		Args:
			family_name: The family name.
			target: The COMP to place into (OP or path string).
			op_type: Operator type name (as shown in OP Create menu).
			name: (Optional) Custom name for the placed operator.

		Returns:
			OP: The placed operator, or None if cancelled/failed.
		"""
		if isinstance(target, str):
			target = op(target)
		if not target or not target.isCOMP:
			debug(f'PlaceOp: target must be a COMP, got {target}')
			return None

		if family_name not in self.InstalledFams:
			debug(f'PlaceOp: family {family_name} is not installed')
			return None

		# Normalize lookup name
		lookup_name = op_type.lower().replace(' ', '_')
		display_name = op_type

		# 1. Run onPlaceOp callback
		result = self._PlaceOp(family_name, None, lookup_name)
		if isinstance(result, dict):
			should_place = result.get('returnValue', True)
			lookup_name = result.get('lookupName', lookup_name)
		else:
			should_place = True

		if should_place is False or should_place is None:
			return None

		# 2. Create clone in staging area via manageOpClone
		clone = self.manageOpClone(family_name, lookup_name, display_name)
		if not clone:
			debug(f'PlaceOp: failed to create clone for {op_type}')
			return None

		# 3. Copy clone into target COMP
		placed = target.copy(clone, name=name)

		# 3b. Set position if provided
		if x is not None:
			placed.nodeX = x
		if y is not None:
			placed.nodeY = y

		# 4. Clean up staging
		clone.destroy()

		# 5. Run onPostPlaceOp callback
		self._PostPlaceOp(family_name, placed)

		return placed

# endregion Operator Management

# region Internal Helpers

	def _add_fam_tag(self, family_owner):
		if '<FAM>' not in family_owner.tags:
			family_owner.tags.add('<FAM>')

	def _is_overwrite(self, fam_name, family_owner = None):
		"""
		Check if new family can be overwritten.
		# TODO: for the future we should compare version numbers and warn if lower
		"""
		is_reinit = (fam_name in self.RegisteredFams and self.RegisteredFams[fam_name] == family_owner)
		return self._dev_overwrite_mode or is_reinit
	
	def _setFamilyDict(self, _dict, fam_name, family_owner):
		_dict.setItem(fam_name, family_owner)
		self.ownerComp.store('RegisteredFams' if _dict is self.RegisteredFams else 'InstalledFams', dict(_dict))

	def _deleteItemFromFamilyDict(self, _dict, fam_name):
		if fam_name in _dict:
			del _dict[fam_name]
			self.ownerComp.store('RegisteredFams' if _dict is self.RegisteredFams else 'InstalledFams', dict(_dict))

# endregion Internal Helpers

# region Hook Integration

	def CallHook(self, fam_name, hook_name, *args):
		"""
		Public entry point to call a specific family hook.
		Maps the external hook name (e.g. '_PlaceOp') to the internal registry helper.
		"""
		# We check if the registry has an internal helper method for this hook
		method = getattr(self, hook_name, None)
		if method and callable(method):
			return method(fam_name, *args)
		return 'nohook'

	def _dispatch_hook(self, fam_name, hook_name, info):
		"""
		Internal dispatcher for all family hooks.
		"""
		installer = self.GetFamilyExt(fam_name)
		if not installer or not hasattr(installer, 'DoCallback'):
			return None

		return installer.DoCallback(hook_name, info)

	def _get_op_type(self, comp):
		"""Read op_type from a comp's FamManifest, or return None."""
		if comp:
			manifest = comp.op('FamManifest')
			if manifest:
				return get_op_type_from_manifest(manifest)
		return None

	def _PreInstall(self, fam_name):
		info = {'about': 'Called before installation'}
		return self._dispatch_hook(fam_name, 'onPreInstall', info)

	def _PostInstall(self, fam_name):
		info = {'about': 'Called after installation'}
		return self._dispatch_hook(fam_name, 'onPostInstall', info)

	def _PreUninstall(self, fam_name):
		info = {'about': 'Called before uninstallation'}
		return self._dispatch_hook(fam_name, 'onPreUninstall', info)

	def _PostUninstall(self, fam_name):
		info = {'about': 'Called after uninstallation'}
		return self._dispatch_hook(fam_name, 'onPostUninstall', info)

	def _PlaceOp(self, fam_name, panelValue, lookup_name):
		info = {
			'panelValue': panelValue,
			'lookupName': lookup_name,
			'about': 'Return True to place, False to cancel+close, None for ActionOp'
		}
		result = self._dispatch_hook(fam_name, 'onPlaceOp', info)
		if result:
			result.setdefault('returnValue', True)
			return result
		return {'returnValue': True, 'panelValue': panelValue, 'lookupName': lookup_name}

	def _PostPlaceOp(self, fam_name, clone):
		info = {'clone': clone, 'about': 'Customize the placed operator'}
		return self._dispatch_hook(fam_name, 'onPostPlaceOp', info)

	def _PreStub(self, fam_name, comp):
		info = {'comp': comp, 'opType': self._get_op_type(comp), 'about': 'Return False to skip stubbing this operator'}
		result = self._dispatch_hook(fam_name, 'onPreStub', info)
		if result:
			result.setdefault('returnValue', True)
			return result
		return {'returnValue': True, 'comp': comp}

	def _PostStub(self, fam_name, stub, original):
		info = {'stub': stub, 'original': original, 'opType': self._get_op_type(stub)}
		return self._dispatch_hook(fam_name, 'onPostStub', info)

	def _PreReplace(self, fam_name, stub):
		info = {'stub': stub, 'opType': self._get_op_type(stub), 'about': 'Return False to skip replacing this stub'}
		result = self._dispatch_hook(fam_name, 'onPreReplace', info)
		if result:
			result.setdefault('returnValue', True)
			return result
		return {'returnValue': True, 'stub': stub}

	def _PostReplace(self, fam_name, new_comp, stub, extra_info):
		info = {'newComp': new_comp, 'stub': stub, 'extraInfo': extra_info, 'opType': self._get_op_type(new_comp)}
		return self._dispatch_hook(fam_name, 'onPostReplace', info)

	def _CaptureExtraInfo(self, fam_name, comp, scenario):
		info = {'comp': comp, 'scenario': scenario, 'opType': self._get_op_type(comp), 'about': 'Return a dict of arbitrary data to preserve across stub/update'}
		result = self._dispatch_hook(fam_name, 'onCaptureExtraInfo', info)
		if result and result.get('returnValue') is not None:
			return result
		return {'returnValue': {}}

	def _PreUpdate(self, fam_name, old_comp, master):
		info = {'oldComp': old_comp, 'master': master, 'opType': self._get_op_type(old_comp), 'about': 'Return False to skip updating this operator'}
		result = self._dispatch_hook(fam_name, 'onPreUpdate', info)
		if result:
			result.setdefault('returnValue', True)
			return result
		return {'returnValue': True, 'oldComp': old_comp, 'master': master}

	def _PostUpdate(self, fam_name, new_comp, extra_info):
		info = {'newComp': new_comp, 'extraInfo': extra_info, 'opType': self._get_op_type(new_comp)}
		return self._dispatch_hook(fam_name, 'onPostUpdate', info)

	def _PreserveSpecialParams(self, fam_name, new_comp, source):
		info = {'newComp': new_comp, 'source': source, 'opType': self._get_op_type(new_comp)}
		return self._dispatch_hook(fam_name, 'onPreserveSpecialParams', info)

	def _GetExcludedTags(self, fam_name):
		info = {'about': 'Return a set of tag names to exclude'}
		result = self._dispatch_hook(fam_name, 'onGetExcludedTags', info)
		if result and result.get('returnValue') is not None:
			return result['returnValue']
		return set()

	def _GetCategoryTags(self, fam_name):
		info = {'about': 'Return a set of category tag names'}
		result = self._dispatch_hook(fam_name, 'onGetCategoryTags', info)
		if result and result.get('returnValue') is not None:
			return result['returnValue']
		return set()

	def _CaptureChildrenParams(self, fam_name, comp, children_data):
		info = {'comp': comp, 'children_data': children_data, 'opType': self._get_op_type(comp), 'about': 'Modify children_data in place'}
		return self._dispatch_hook(fam_name, 'onCaptureChildrenParams', info)

	def _DeployManifest(self, fam_name, comp, OpInfo, ParRetain, Shortcuts):
		info = {'comp': comp, 'opType': OpInfo.get('op_type'), 'OpInfo': OpInfo, 'ParRetain': ParRetain, 'Shortcuts': Shortcuts}
		return self._dispatch_hook(fam_name, 'onDeployManifest', info)

# endregion Hook Integration
