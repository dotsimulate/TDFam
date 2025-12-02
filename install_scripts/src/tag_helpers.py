"""
Tag management helpers for opfam-create.

Provides utilities for ensuring operators in custom_operators have proper tags
for the stub/update/placement systems to work correctly.
"""


def ensure_family_tags(installer, custom_ops_base=None):
    """
    Ensure all operators in custom_operators have the family tag.

    Args:
        installer: The OpFamCreateExt instance
        custom_ops_base: Optional custom operators base.
                         Defaults to installer.ownerComp.op('custom_operators')
    """
    custom_ops = custom_ops_base or installer.ownerComp.op('custom_operators')
    if not custom_ops:
        return

    family = installer.FamilyName.val
    for comp in custom_ops.findChildren(type=COMP, maxDepth=1):
        if family not in comp.tags:
            comp.tags.add(family)


def ensure_type_tags(installer, custom_ops_base=None, pattern='suffix'):
    """
    Ensure all operators have type tags for stub/update matching.

    Args:
        installer: The OpFamCreateExt instance
        custom_ops_base: Optional custom operators base
        pattern: Tag pattern to use:
                 'suffix' - {opname}{Family} (e.g., agentLOP)
                 'name' - just operator name as tag - simpler style
    """
    custom_ops = custom_ops_base or installer.ownerComp.op('custom_operators')
    if not custom_ops:
        return

    family = installer.FamilyName.val
    for comp in custom_ops.findChildren(type=COMP, maxDepth=1):
        if pattern == 'suffix':
            type_tag = f"{comp.name}{family}"
        else:
            type_tag = comp.name

        if type_tag not in comp.tags:
            comp.tags.add(type_tag)


def tag_operators(installer, pattern='suffix'):
    """
    Convenience method to ensure both family and type tags on all operators.

    Call this in wrapper's __init__() or Install() to auto-tag operators.

    Args:
        installer: The OpFamCreateExt instance
        pattern: Tag pattern for type tags ('suffix' or 'name')
    """
    ensure_family_tags(installer)
    ensure_type_tags(installer, pattern=pattern)


def get_operator_type(comp, family_name, category_tags=None):
    """
    Extract operator type from a component's tags.

    Supports two patterns:
    1. {type}{familyName} pattern (e.g., "agentLOP" -> "agent")
    2. Category tag exclusion (find tag that's not a category)

    Args:
        comp: The component to get type for
        family_name: The family name to strip from suffix
        category_tags: Optional set of category tags to exclude

    Returns:
        str: The operator type, or comp.name as fallback
    """
    if category_tags:
        # Find tag that is NOT a category tag
        for tag in comp.tags:
            if tag not in category_tags:
                return tag.lower().replace(' ', '_')
    else:
        # look for {type}{familyName} pattern
        for tag in comp.tags:
            if tag.endswith(family_name) and tag != family_name:
                return tag.removesuffix(family_name)

    # Fallback to component name
    return comp.name


def has_operator_type_tag(comp, family_name, category_tags=None):
    """
    Check if a component has a proper operator type tag.

    Args:
        comp: The component to check
        family_name: The family name
        category_tags: Optional set of category tags

    Returns:
        bool: True if has type tag, False otherwise
    """
    if category_tags:
        return any(tag not in category_tags for tag in comp.tags)
    else:
        return any(
            tag.endswith(family_name) and tag != family_name
            for tag in comp.tags
        )
