from __future__ import annotations
from TDStoreTools import DependDict
from GlobalUIInjector import GlobalUIInjector
from TagManager import TagManager
from StubManager import StubManager
from UpdateManager import UpdateManager
from FileManager import FileManager

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
		self._dev_overwrite_mode = False
		
		run(lambda: self.postInit(), delayFrames=1, delayRef=op.TDResources)

	def postInit(self):
		# Skip if we're a staging copy (used by MockUpdate)
		if self.ownerComp.path == '/sys/quiet':
			return

		# Check if we're post-update
		is_post_update = self.ownerComp.fetch('post_update', False)
		if is_post_update:
			#self.ownerComp.unstore('post_update')
			if hasattr(op, 'FAMREGISTRY') and self.ownerComp == op.FAMREGISTRY:
				# we just update the global registry in place, so we can restore families
				# Restore Registered and Installed families
				restored_registered = self.ownerComp.fetch('RegisteredFams', {})
				restored_installed = self.ownerComp.fetch('InstalledFams', {})

				for _reg_fam in restored_registered:
					self.RegisterFamily(restored_registered[_reg_fam])
				for _inst_fam in restored_installed:
					self.InstallFamily(restored_installed[_inst_fam])
			else:
				# we update a local registry, we need to reconcile with global
				self._reconcile_global_registry()

			self.ownerComp.unstore('post_update')
			self.ownerComp.unstore('RegisteredFams')
			self.ownerComp.unstore('InstalledFams')

			

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
		self.RegisteredFams.setItem(fam_name, family_owner)
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
			del self.RegisteredFams[fam_name]
			debug(f'Unregistered family: {fam_name}')
			self.EventEmitter.Emit('FamilyUnregistered', fam_name)

			# also uninstall if installed
			if fam_name in self.InstalledFams:
				self.UninstallFamily(family_owner_or_name if not isinstance(family_owner_or_name, str) else fam_name)

	def InstallFamily(self, family_owner):
		"""Install a family by owner."""
		fam_name = family_owner.Properties['family_name'] if not isinstance(family_owner, str) else family_owner
		
		# If it's a string, we still need the actual owner for installation logic
		if isinstance(family_owner, str):
			family_owner = self.RegisteredFams.get(fam_name)
			
		if not family_owner:
			raise ValueError(f"Cannot install {fam_name}: not registered.")
		
		self._PreInstall(fam_name)

		self.InstalledFams.setItem(fam_name, family_owner)
		debug(f'Installed family: {fam_name}')
		self.global_ui_injector.install(fam_name, family_owner)
		self.EventEmitter.Emit('FamilyInstalled', fam_name, family_owner)

		self._PostInstall(fam_name)

	def UninstallFamily(self, family_owner):
		"""Uninstall a family by owner."""
		fam_name = family_owner.Properties['family_name'] if not isinstance(family_owner, str) else family_owner
		
		self._PreUninstall(fam_name)

		if fam_name in self.InstalledFams:
			del self.InstalledFams[fam_name]
			debug(f'Uninstalled family: {fam_name}')
			self.global_ui_injector.uninstall(fam_name)
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
			del self.RegisteredFams[old_name]
			self.RegisteredFams.setItem(new_name, family_owner)

		if old_name in self.InstalledFams:
			del self.InstalledFams[old_name]
			self.InstalledFams.setItem(new_name, family_owner)
			
			# Only update global UI if installed
			self.global_ui_injector.update_family_name(old_name, new_name)

		# Update properties and shortcut
		if hasattr(family_owner, 'Properties'):
			family_owner.Properties['family_name'] = new_name
		
		if hasattr(family_owner, 'ShortcutComp'):
			comp = family_owner.ShortcutComp
			if comp:
				comp.par.opshortcut = new_name
		
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

		if fam_name in self.InstalledFams:
			self.global_ui_injector.update_family_color(fam_name, new_color)
		
		return True

	def onRegistryChangeCallback(self, cells, prev):
		"""This checks deletion of family owners for deregistration."""
		for idx, _cell in enumerate(cells):
			_val = _cell.val
			if _val != prev[idx] and _val == 'None':
				self.UnregisterFamily(prev[idx])

# endregion Family Management

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
			return result.get('returnValue', True)
		return True

	def _PostPlaceOp(self, fam_name, clone):
		info = {'clone': clone, 'about': 'Customize the placed operator'}
		return self._dispatch_hook(fam_name, 'onPostPlaceOp', info)

	def _PreStub(self, fam_name, comp):
		info = {'comp': comp, 'about': 'Return False to skip stubbing this operator'}
		result = self._dispatch_hook(fam_name, 'onPreStub', info)
		if result:
			return result.get('returnValue', True)
		return True

	def _PostStub(self, fam_name, stub, original):
		info = {'stub': stub, 'original': original}
		return self._dispatch_hook(fam_name, 'onPostStub', info)

	def _PreReplace(self, fam_name, stub):
		info = {'stub': stub, 'about': 'Return False to skip replacing this stub'}
		result = self._dispatch_hook(fam_name, 'onPreReplace', info)
		if result:
			return result.get('returnValue', True)
		return True

	def _PostReplace(self, fam_name, new_comp, stub):
		info = {'newComp': new_comp, 'stub': stub}
		return self._dispatch_hook(fam_name, 'onPostReplace', info)

	def _PreUpdate(self, fam_name, old_comp, master):
		info = {'oldComp': old_comp, 'master': master, 'about': 'Return False to skip updating this operator'}
		result = self._dispatch_hook(fam_name, 'onPreUpdate', info)
		if result:
			return result.get('returnValue', True)
		return True

	def _PostUpdate(self, fam_name, new_comp):
		info = {'newComp': new_comp}
		return self._dispatch_hook(fam_name, 'onPostUpdate', info)

	def _PreserveSpecialParams(self, fam_name, new_comp, source):
		info = {'newComp': new_comp, 'source': source}
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
		info = {'comp': comp, 'children_data': children_data, 'about': 'Modify children_data in place'}
		return self._dispatch_hook(fam_name, 'onCaptureChildrenParams', info)

# endregion Hook Integration
