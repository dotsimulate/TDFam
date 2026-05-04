'''Info Header Start
Name : pre_release
Author : Dan@DAN-4090
Saveorigin : opfam-create_dev.64.toe
Saveversion : 2023.12370
Info Header End'''
internal = op('internal_pars')
for _par in internal.customPars:
    _par.val = False
parent().customPages[1].destroy()
me.destroy()
