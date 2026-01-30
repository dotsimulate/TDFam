def onFamilyRegistered( family_name:str, family_owner:OP ):
	ext.OpFamUIExt.onRegistryFamilyRegistered(family_name, family_owner)
	return

def onFamilyUnregistered( family_name:str ):
	ext.OpFamUIExt.onRegistryFamilyUnregistered(family_name)
	return

def onFamilyInstalled( family_name:str, family_owner:OP ):
	ext.OpFamUIExt.onRegistryFamilyInstalled(family_name, family_owner)
	return

def onFamilyUninstalled( family_name:str ):
	ext.OpFamUIExt.onRegistryFamilyUninstalled(family_name)
	return

def onFamilyRenamed( old_name:str, new_name:str, family_owner:OP ):
	return

