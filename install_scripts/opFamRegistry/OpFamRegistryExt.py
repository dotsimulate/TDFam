from __future__ import annotations
from TDStoreTools import DependDict
from GlobalUIInjector import GlobalUIInjector

class OpFamRegistryExt:
	def __init__(self, ownerComp):
		self.ownerComp = ownerComp
		self.RegisteredFams = DependDict({})
		self.InstalledFams = DependDict({})
		self.EventEmitter = self.ownerComp.op('eventEmitter')
		self.global_ui_injector = GlobalUIInjector(self.ownerComp, self)
#
	def RegisterFamily(self, family_owner : OpFamCreateExt):
		fam_name = family_owner.Properties['family_name']
		self._add_fam_tag(family_owner)
		self.RegisteredFams.setItem(fam_name, family_owner)
		debug(f'Registered family: {fam_name}')
		self.EventEmitter.Emit('FamilyRegistered', fam_name, family_owner)

	def UnregisterFamily(self, fam_name):
		# TODO: discrepancy where this is the only high level function taking the name
		# --- due to how we're checking deleted families that need to be unregistered 
		# --- via eval and DAT callbacks
		if fam_name in self.RegisteredFams:
			del self.RegisteredFams[fam_name]
			debug(f'Unregistered family: {fam_name}')
			self.EventEmitter.Emit('FamilyUnregistered', fam_name)

			# also uninstall if installed
			if fam_name in self.InstalledFams:
				family_owner = self.InstalledFams[fam_name]
				self.UninstallFamily(family_owner)

	def InstallFamily(self, family_owner : OpFamCreateExt):
		fam_name = family_owner.Properties['family_name']
		if fam_name not in self.RegisteredFams:
			self.RegisterFamily(family_owner)
		
		self.InstalledFams.setItem(fam_name, family_owner)
		debug(f'Installed family: {fam_name}')
		self.global_ui_injector.install(fam_name, family_owner)
		self.EventEmitter.Emit('FamilyInstalled', fam_name, family_owner)

	def UninstallFamily(self, family_owner : OpFamCreateExt):
		fam_name = family_owner.Properties['family_name']
		if fam_name in self.InstalledFams:
			del self.InstalledFams[fam_name]
			debug(f'Uninstalled family: {fam_name}')
			self.global_ui_injector.uninstall(fam_name)
			self.EventEmitter.Emit('FamilyUninstalled', fam_name)
			return True
		return False

	def IsFamilyInstalled(self, fam_name):
		"""Public API to check if a family's UI is installed."""
		return self.global_ui_injector.is_family_installed(fam_name)

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