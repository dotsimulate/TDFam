'''Info Header Start
Name : pre_release
Author : Dan@DAN-4090
Saveorigin : opfam-create_dev.64.toe
Saveversion : 2023.12370
Info Header End'''

internal = op('internal_pars')
for _par in internal.customPars:
    _par.reset()

parent().par.Targettype = ''
parent().par.Targetop = ''
parent().par.Targetcomp = ''
parent().par.Opfolder = ''
parent().par.Opcomp = ''
parent().par.Compatibletypes = ''
parent().par.Callbackdat = op('default_callbacks')
parent().customPages[4].destroy()
parent().currentPage = 'Family'
parent().par.Famuicomp.expr = 'me'
parent().par.Famuicomp.mode = ParMode.EXPRESSION