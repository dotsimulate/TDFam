'''Info Header Start
Name : pre_release
Author : DotSimulate@DOTOFFICE
Saveorigin : opfam-create_dev.107.toe
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