# This is a callback system for parameters.
# to use:
#	- create a function in ParCallbacksExt/ParCallbacks
#	  using the same name as the parameter.

def onValueChange(par, val, prev):
	comp = op(me.par.op)
	name = par.name

	# Try exact match first
	if hasattr(comp, name):
		getattr(comp, name)()
		return

	# Try stripping RGB/RGBA suffix (Colorr -> Color)
	if len(name) > 1 and name[-1] in 'rgba':
		base_name = name[:-1]
		if hasattr(comp, base_name):
			getattr(comp, base_name)()
			return

def onPulse(par):
	comp = op(me.par.op)
	if hasattr(comp, par.name):
		getattr(comp, par.name)()

def onExpressionChange(par, val, prev):
	comp = op(me.par.op)
	if hasattr(comp, par.name):
		getattr(comp, par.name)(par, val, prev)

def onExportChange(par, val, prev):
	comp = op(me.par.op)
	if hasattr(comp, par.name):
		getattr(comp, par.name)(par, val, prev)

def onEnableChange(par, val, prev):
	return
	