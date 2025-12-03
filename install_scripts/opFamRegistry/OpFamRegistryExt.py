from __future__ import annotations
from TDStoreTools import DependDict

class OpFamRegistryExt:
	def __init__(self, ownerComp):
		self.ownerComp = ownerComp
		self.RegisteredFams = DependDict({})
		self.InstalledFams = DependDict({})
		self.EventEmitter = self.ownerComp.op('eventEmitter')

	def RegisterFamily(self, family_owner : OpFamCreateExt):
		fam_name = family_owner.Properties['family_name']
		self._add_fam_tag(family_owner)
		self.RegisteredFams.setItem(fam_name, family_owner)
		self.EventEmitter.Emit('FamilyRegistered', fam_name, family_owner)

	def UnregisterFamily(self, fam_name):
		if fam_name in self.RegisteredFams:
			del self.RegisteredFams[fam_name]
			self.EventEmitter.Emit('FamilyUnregistered', fam_name)

	def UpdateFamilyName(self, old_name, new_name):
		if old_name in self.RegisteredFams:
			family_owner = self.RegisteredFams[old_name]
			del self.RegisteredFams[old_name]
			self.RegisteredFams.setItem(new_name, family_owner)

	def _add_fam_tag(self, family_owner):
		if 'FAM' not in family_owner.tags:
			family_owner.tags.add('FAM')

	@property
	def NumFamilies(self):
		return len(self.RegisteredFams)