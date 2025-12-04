'''Info Header Start
Name : OpFamUIExt
Author : root
Saveorigin : opfam-create_dev.47.toe
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
		self.window = self.ownerComp.op('window1')

	@property
	def fam_registry(self):
		return getattr(op, 'FAMREGISTRY', None)
	
# region Registry callbacks
	
	def onRegistryRegisteredFamily(self, fam_name, family_owner):
		self.onFamilyTabSelected(fam_name)
		return

	def onRegistryUnregisteredFamily(self, fam_name):
		# get first registered family and set it as selected
		first_fam = next(iter(self.fam_registry.RegisteredFams), None)
		self.onFamilyTabSelected(first_fam)
		return

	def onExistingFamiliesChanged(self, current):
		pass

# endregion Registry callbacks

# region UI callbacks

	def onFamilyTabSelected(self, fam_name):
		if self.fam_registry:
			self.parameters_ui.par.op = self.fam_registry.RegisteredFams.get(fam_name)

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




