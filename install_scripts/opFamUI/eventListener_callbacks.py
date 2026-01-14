def onFamilyRegistered( family_name:str, family_owner:OP ):
	ext.OpFamUIExt.onRegistryFamilyRegistered(family_name, family_owner)
	return

def onFamilyUnregistered( family_name:str ):
	ext.OpFamUIExt.onRegistryFamilyUnregistered(family_name)
	return

def onFamilyInstalled( family_name:str, family_owner:OP ):
	return

def onFamilyUninstalled( family_name:str ):
	return

def onFamilyRenamed( old_name:str, new_name:str, family_owner:OP ):
	return

