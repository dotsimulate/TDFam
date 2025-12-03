'''Info Header Start
Name : OpFamUIExt
Author : root
Saveorigin : opfam-create_dev.43.toe
Saveversion : 2023.12370
Info Header End'''

from TDStoreTools import DependDict


CustomParHelper: CustomParHelper = next(d for d in me.docked if 'ExtUtils' in d.tags).mod('CustomParHelper').CustomParHelper # import
###

class OpFamUIExt:
	def __init__(self, ownerComp):
		CustomParHelper.Init(self, ownerComp, enable_properties=True, enable_callbacks=True)
		self.ownerComp = ownerComp
		self.parameters_ui = self.ownerComp.op('fam_menu/parameter1')
		self.RegisteredFams = DependDict()
		self.window = self.ownerComp.op('window1')
		
# region local registry

	def RegisterFamily(self, family_owner):
		# TODO: error handling
		if family_owner.Properties['family_name'] in self.RegisteredFams:
			return
		fam_name = family_owner.Properties['family_name']
		self.RegisteredFams.setItem(fam_name, family_owner)

	def UnregisterFamily(self, fam_name):
		if fam_name in self.RegisteredFams:
			del self.RegisteredFams[fam_name]

	def UpdateFamilyName(self, old_name, new_name):
		if old_name in self.RegisteredFams:
			family_owner = self.RegisteredFams[old_name]
			del self.RegisteredFams[old_name]
			self.RegisteredFams.setItem(new_name, family_owner)

# endregion local registry

# region Registry callbacks
	
	def onRegistryRegisteredFamily(self, fam_name, family_owner):
		# even though we should have already registered the family on init, we do it just in case on install
		self.RegisterFamily(family_owner)

	def onRegistryUnregisteredFamily(self, fam_name):
		return

	def onExistingFamiliesChanged(self, current):
		pass

# endregion Registry callbacks

# region UI callbacks

	def onFamilyTabSelected(self, fam_name):
		self.parameters_ui.par.op = self.RegisteredFams.get(fam_name)

	def onButtonClicked(self, panelValue):
		if panelValue.val == 0:
			return

		if panelValue.name == 'lstate':
			self.window.par.winopen.pulse()
		if panelValue.name == 'rstate':
			pass
		if panelValue.name == 'mstate':
			pass

# endregion UI callbacks




