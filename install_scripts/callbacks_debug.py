# Debug Callbacks - prints all callback activity to textport

def onPreInstall(info):
    debug("[onPreInstall]")
    debug(info)

def onPostInstall(info):
    debug("[onPostInstall]")
    debug(info)

def onPreUninstall(info):
    debug("[onPreUninstall]")
    debug(info)

def onPostUninstall(info):
    debug("[onPostUninstall]")
    debug(info)

def onPlaceOp(info):
    debug(f"[onPlaceOp] {info['lookupName']}")
    debug(info)
    return True

def onPostPlaceOp(info):
    debug(f"[onPostPlaceOp] {info['clone']}")
    debug(info)

def onPreStub(info):
    debug(f"[onPreStub] {info['comp']}")
    debug(info)
    return True

def onPostStub(info):
    debug(f"[onPostStub] stub={info['stub']} original={info['original']}")
    debug(info)

def onPreReplace(info):
    debug(f"[onPreReplace] {info['stub']}")
    debug(info)
    return True

def onPostReplace(info):
    debug(f"[onPostReplace] newComp={info['newComp']}")
    debug(info)

def onPreUpdate(info):
    debug(f"[onPreUpdate] old={info['oldComp']} master={info['master']}")
    debug(info)
    return True

def onPostUpdate(info):
    debug(f"[onPostUpdate] {info['newComp']}")
    debug(info)

def onPreserveSpecialParams(info):
    debug(f"[onPreserveSpecialParams] newComp={info['newComp']} source={info['source']}")
    debug(info)

def onGetExcludedTags(info):
    debug("[onGetExcludedTags]")
    debug(info)
    return set()

def onGetCategoryTags(info):
    debug("[onGetCategoryTags]")
    debug(info)
    return set()
