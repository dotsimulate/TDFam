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
#
	def RegisterFamily(self, family_owner : OpFamCreateExt):
		fam_name = family_owner.Properties['family_name']
		self._add_fam_tag(family_owner)
		self.RegisteredFams.setItem(fam_name, family_owner)
		debug(f'Registered family: {fam_name}')
		self.EventEmitter.Emit('FamilyRegistered', fam_name, family_owner)

	def UnregisterFamily(self, fam_name):
		"""Unregister a family by name."""
		if fam_name in self.RegisteredFams:
			del self.RegisteredFams[fam_name]
			debug(f'Unregistered family: {fam_name}')
			self.EventEmitter.Emit('FamilyUnregistered', fam_name)

			# also uninstall if installed
			if fam_name in self.InstalledFams:
				self.UninstallFamily(fam_name)

	def InstallFamily(self, fam_name):
		"""Install a family by name."""
		family_owner = self.RegisteredFams.get(fam_name)
		if not family_owner:
			raise ValueError(f"Cannot install {fam_name}: not registered.")
		
		self._PreInstall(fam_name)

		self.InstalledFams.setItem(fam_name, family_owner)
		debug(f'Installed family: {fam_name}')
		self.global_ui_injector.install(fam_name, family_owner)
		self.EventEmitter.Emit('FamilyInstalled', fam_name, family_owner)

		self._PostInstall(fam_name)

	def UninstallFamily(self, fam_name):
		"""Uninstall a family by name."""
		self._PreUninstall(fam_name)

		if fam_name in self.InstalledFams:
			del self.InstalledFams[fam_name]
			debug(f'Uninstalled family: {fam_name}')
			self.global_ui_injector.uninstall(fam_name)
			self.EventEmitter.Emit('FamilyUninstalled', fam_name)
			
			self._PostUninstall(fam_name)
			return True
		return False

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


	def UpdateFamilyName(self, old_name, new_name):
		# send event if indeed renamed
		if old_name in self.RegisteredFams or old_name in self.InstalledFams:
			family_owner = self.RegisteredFams.get(old_name) or self.InstalledFams.get(old_name)
			self.EventEmitter.Emit('FamilyRenamed', old_name, new_name, family_owner)
			debug(f'Family renamed: {old_name} -> {new_name}')

		# Collect family owner from either list
		family_owner = None
		if old_name in self.RegisteredFams:
			family_owner = self.RegisteredFams[old_name]
			del self.RegisteredFams[old_name]
			self.RegisteredFams.setItem(new_name, family_owner)

		if old_name in self.InstalledFams:
			family_owner = self.InstalledFams[old_name] # Should be same object
			del self.InstalledFams[old_name]
			self.InstalledFams.setItem(new_name, family_owner)
			
			# Only update global UI if installed
			self.global_ui_injector.update_family_name(old_name, new_name)

		# Update properties and shortcut if we found the family owner (installed or not)
		if family_owner:
			if hasattr(family_owner, 'Properties'):
				family_owner.Properties['family_name'] = new_name
			
			if hasattr(family_owner, 'ShortcutComp'):
				comp = family_owner.ShortcutComp
				if comp:
					comp.par.opshortcut = new_name
	
	def UpdateFamilyColor(self, fam_name, new_color):
		"""Update family color in UI elements."""
		if fam_name in self.InstalledFams:
			# Update local property first (if not already done by caller)
			family_owner = self.InstalledFams[fam_name]
			# The caller (OpFamExt) usually updates its own property, but we ensure consistency here if needed.
			# But typically caller calls this AFTER updating property.
			
			self.global_ui_injector.update_family_color(fam_name, new_color)

	def onRegistryChangeCallback(self, cells, prev):
		for idx, _cell in enumerate(cells):
			_val = _cell.val
			if _val != prev[idx] and _val == 'None':
				self.UnregisterFamily(prev[idx])

	def _add_fam_tag(self, family_owner):
		if '<FAM>' not in family_owner.tags:
			family_owner.tags.add('<FAM>')

	@property
	def NumFamiliesRegistered(self):
		return len(self.RegisteredFams)

	@property
	def NumFamiliesInstalled(self):
		return len(self.InstalledFams)


	# ==================== Hook Integration ====================

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
