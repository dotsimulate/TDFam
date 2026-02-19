'''Info Header Start
Name : OpFamUIExt
Author : Dan@DAN-4090
Saveorigin : opfam-create_dev.64.toe
Saveversion : 2023.12370
Info Header End'''

from TDStoreTools import DependDict


CustomParHelper: CustomParHelper = next(d for d in me.docked if 'ExtUtils' in d.tags).mod('CustomParHelper').CustomParHelper # import
###

class OpFamUIExt:
	def __init__(self, ownerComp):
		CustomParHelper.Init(self, ownerComp, enable_properties=True, enable_callbacks=True)
		self.ownerComp = ownerComp
		self.fam_menu = self.ownerComp.op('fam_menu')
		self.parameters_ui = self.fam_menu.op('parameter1')
		self.window = self.ownerComp.op('window1')
		run(self.postInit(), delayFrames = 1, delayRef=op.TDResources)

	def postInit(self):
		self.onFamilyTabSelected(next(iter(self.fam_registry.RegisteredFams), None))
		return

	@property
	def fam_registry(self):
		return getattr(op, 'FAMREGISTRY', None) if not (getattr(parent, 'OpFamRegistry', None) and parent.OpFamRegistry.op('internal_pars').par.Dev.eval()) else parent.OpFamRegistry
	
	@property
	def general_settings(self):
		return self.ownerComp.op('general_settings')

# region Registry callbacks
	
	def onRegistryFamilyRegistered(self, fam_name, family_owner):
		self.onFamilyTabSelected(fam_name)
		return

	def onRegistryFamilyUnregistered(self, fam_name):
		# get first registered family and set it as selected
		first_fam = next(iter(self.fam_registry.RegisteredFams), None)
		self.onFamilyTabSelected(first_fam)
		return

	def onRegistryFamilyInstalled(self, fam_name, family_owner):
		self.onFamilyTabSelected(fam_name)
		return

	def onRegistryFamilyUninstalled(self, fam_name):
		return

	def onExistingFamiliesChanged(self, current):
		pass

# endregion Registry callbacks

# region UI callbacks

	def onFamilyTabSelected(self, fam_name):
		if self.fam_registry:
			family_owner = self.fam_registry.RegisteredFams.get(fam_name)
			ui_comp = family_owner.par.Famuicomp.eval() if family_owner and hasattr(family_owner.par, 'Famuicomp') else family_owner
			if not ui_comp:
				ui_comp = family_owner
			self.parameters_ui.par.op = ui_comp
			self.fam_menu.op('buttonSettings').par.value0 = False

	def onButtonClicked(self, panelValue):
		if panelValue.val == 0:
			return

		if panelValue.name == 'lstate':
			self.window.par.winopen.pulse()
		if panelValue.name == 'rstate':
			pass
		if panelValue.name == 'mstate':
			pass

	def onGeneralSettingsClicked(self, panelValue):
		if panelValue.val == 0:
			return

		self.parameters_ui.par.op = self.general_settings
		

# endregion UI callbacks




