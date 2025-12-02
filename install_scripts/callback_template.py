"""
OpFam Callback Template

Copy this file and reference it in the Callbackdat parameter.
Uncomment and implement the callbacks you need.

All callbacks receive an 'info' dict containing:
    - ownerComp: The installer COMP
    - callbackName: Name of this callback
    - (plus hook-specific data)

Return values:
    - Most hooks: return value is ignored
    - onPlaceOp: return True (place), False (cancel+close), None (ActionOp - keep menu)
    - onPre* hooks: return False to skip the operation
    - onGetExcludedTags/onGetCategoryTags: return a set of tag names
"""


# ==================== Install/Uninstall Hooks ====================

# def onPreInstall(info):
#     """Called before installation."""
#     pass

# def onPostInstall(info):
#     """Called after installation."""
#     pass

# def onPreUninstall(info):
#     """Called before uninstallation."""
#     pass

# def onPostUninstall(info):
#     """Called after uninstallation."""
#     pass


# ==================== Placement Hooks ====================

# def onPlaceOp(info):
#     """
#     Called before operator placement from TAB menu.
#
#     info keys:
#         panelValue: Raw panel click value
#         lookupName: Lowercase operator name
#
#     Returns:
#         True  - proceed with normal placement
#         False - cancel placement, close menu
#         None  - cancel placement, keep menu open (ActionOp pattern)
#     """
#     lookup_name = info['lookupName']
#     # Example: ActionOp that changes theme instead of placing
#     # if lookup_name == 'dark':
#     #     info['ownerComp'].SetColor(0.1, 0.1, 0.15)
#     #     return None  # keep menu open
#     return True


# def onPostPlaceOp(info):
#     """
#     Called after operator is placed.
#
#     info keys:
#         clone: The newly placed operator
#     """
#     clone = info['clone']
#     # Example: set a parameter on placed operator
#     # if hasattr(clone.par, 'Mypar'):
#     #     clone.par.Mypar = 'value'
#     pass


# ==================== Stub Hooks ====================

# def onPreStub(info):
#     """
#     Called before stub creation.
#
#     info keys:
#         comp: The component about to be stubbed
#
#     Returns:
#         False to skip stubbing this operator
#     """
#     comp = info['comp']
#     # Example: skip certain operators
#     # if 'neverStub' in comp.tags:
#     #     return False
#     return True


# def onPostStub(info):
#     """
#     Called after stub is created.
#
#     info keys:
#         stub: The created stub
#         original: The original component (still exists at this point)
#     """
#     pass


# def onPreReplace(info):
#     """
#     Called before stub replacement.
#
#     info keys:
#         stub: The stub about to be replaced
#
#     Returns:
#         False to skip replacing this stub
#     """
#     return True


# def onPostReplace(info):
#     """
#     Called after stub is replaced with full operator.
#
#     info keys:
#         newComp: The new full operator
#         stub: The stub (about to be destroyed)
#     """
#     pass


# ==================== Update Hooks ====================

# def onPreUpdate(info):
#     """
#     Called before operator update.
#
#     info keys:
#         oldComp: The operator being updated
#         master: The master operator it will update from
#
#     Returns:
#         False to skip updating this operator
#     """
#     return True


# def onPostUpdate(info):
#     """
#     Called after operator is updated.
#
#     info keys:
#         newComp: The updated operator
#     """
#     pass


# def onPreserveSpecialParams(info):
#     """
#     Called during stub replacement and update to preserve special parameters.
#
#     info keys:
#         newComp: The new operator
#         source: The source (stub or old operator)
#     """
#     # Example: preserve a custom parameter
#     # new_comp = info['newComp']
#     # source = info['source']
#     # if hasattr(source.par, 'Myspecialpar') and hasattr(new_comp.par, 'Myspecialpar'):
#     #     new_comp.par.Myspecialpar = source.par.Myspecialpar.eval()
#     pass


# ==================== Tag Hooks ====================

# def onGetExcludedTags(info):
#     """
#     Return tags to exclude from batch operations (stubs, updates).
#
#     Returns:
#         set of tag names to exclude
#     """
#     # Example: exclude action operators from stubbing
#     # return {'actionMYFAM', 'internal'}
#     return set()


# def onGetCategoryTags(info):
#     """
#     Return category tags for operator type detection.
#
#     Returns:
#         set of category tag names
#     """
#     # Example: category tags that shouldn't be used for type matching
#     # return {'actionMYFAM', 'settings'}
#     return set()
