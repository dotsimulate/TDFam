# Parameter callbacks - checks onPar{name} first, then direct method

def onValueChange(par, val, prev):
	ext = op(me.par.op).ext.OpFamExt
	name = par.name

	handler = f'onPar{name}'
	if hasattr(ext, handler):
		getattr(ext, handler)()
		return

	if len(name) > 1 and name[-1] in 'rgba':
		base_handler = f'onPar{name[:-1]}'
		if hasattr(ext, base_handler):
			getattr(ext, base_handler)()
			return

	if hasattr(ext, name):
		getattr(ext, name)()

def onPulse(par):
	ext = op(me.par.op).ext.OpFamExt

	handler = f'onPar{par.name}'
	if hasattr(ext, handler):
		getattr(ext, handler)()
		return

	if hasattr(ext, par.name):
		getattr(ext, par.name)()

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
