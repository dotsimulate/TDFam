# OpFam Callbacks Template
#
# All callbacks receive an info dict. Pre-action callbacks can:
#   1. Return True/False/None to control flow
#   2. Modify info dict keys to change what gets acted on
#
# Modified info keys are passed through to the caller, so changing
# info['lookupName'] in onPlaceOp will place a different operator.

def onPreInstall(info):
	pass

def onPostInstall(info):
	pass

def onPreUninstall(info):
	pass

def onPostUninstall(info):
	pass

def onPlaceOp(info):
	"""
	Called before placing an operator from the TAB menu.

	info keys:
		lookupName (str) - operator name, MODIFIABLE to swap operator
		panelValue (int) - click position

	Return: True = place, False = cancel+close, None = ActionOp (keep menu)

	Example - swap operator:
		if some_condition:
			info['lookupName'] = 'alternative_operator'
		return True
	"""
	return True

def onPostPlaceOp(info):
	"""
	Called after operator placement.

	info keys:
		clone - the placed operator
	"""
	pass

def onPreStub(info):
	"""
	Called before stubbing an operator.

	info keys:
		comp - the operator to stub, MODIFIABLE

	Return: True = proceed, False = skip this operator
	"""
	return True

def onPostStub(info):
	pass

def onPreReplace(info):
	"""
	Called before replacing a stub with the real operator.

	info keys:
		stub - the stub to replace, MODIFIABLE

	Return: True = proceed, False = skip this stub
	"""
	return True

def onPostReplace(info):
	pass

def onPreUpdate(info):
	"""
	Called before updating an operator to a new version.

	info keys:
		oldComp - the existing operator
		master - the new master to update from, MODIFIABLE

	Return: True = proceed, False = skip this operator
	"""
	return True

def onPostUpdate(info):
	pass

def onPreserveSpecialParams(info):
	"""
	Called during update/replace to preserve custom parameters.

	info keys:
		newComp - the new operator
		source - the old operator or stub
	"""
	pass

def onGetExcludedTags(info):
	return set()

def onGetCategoryTags(info):
	return set()
