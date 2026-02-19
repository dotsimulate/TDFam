import re
from RegistryHelpers import sanitize_name

class TagManager:
	def __init__(self, ownerComp, registry):
		self.ownerComp = ownerComp
		self.registry = registry

	def ensure_family_tags(self, family_name, custom_ops_base=None):
		"""
		Ensure all operators in operators_comp have the family tag.

		Args:
			family_name: The family name
			custom_ops_base: Optional custom operators base.
		"""
		installer = self.registry.GetFamilyExt(family_name)
		if not installer:
			return

		custom_ops = custom_ops_base or installer.Properties['operators_comp']
		if not custom_ops:
			return

		family = family_name
		for comp in custom_ops.findChildren(type=COMP, maxDepth=1):
			if family not in comp.tags:
				comp.tags.add(family)
			if '<FAM>' not in comp.tags:
				comp.tags.add('<FAM>')


	def ensure_type_tags(self, family_name, custom_ops_base=None, pattern='suffix'):
		"""
		Ensure all operators have type tags for stub/update matching.

		Args:
			family_name: The family name
			custom_ops_base: Optional custom operators base
			pattern: Tag pattern ('suffix' or 'name')
		"""
		installer = self.registry.GetFamilyExt(family_name)
		if not installer:
			return

		custom_ops = custom_ops_base or installer.Properties['operators_comp']
		if not custom_ops:
			return

		family = family_name
		for comp in custom_ops.findChildren(type=COMP, maxDepth=1):
			if pattern == 'suffix':
				type_tag = f"{comp.name}{family}"
			else:
				type_tag = comp.name

			if type_tag not in comp.tags:
				comp.tags.add(type_tag)


	def tag_operators(self, family_name, pattern='suffix'):
		# TODO X: remove
		"""
		Convenience method to ensure both family and type tags on all operators.

		Args:
			family_name: The family name
			pattern: Tag pattern ('suffix' or 'name')
		"""
		self.ensure_family_tags(family_name)
		self.ensure_type_tags(family_name, pattern=pattern)


	def get_operator_type(self, comp, family_name, category_tags=None):
		"""
		Check if a component has a proper operator type tag and return it.

		Args:
			comp: The component to check
			family_name: The family name
			category_tags: Optional set of category tags

		Returns:
			str: The operator type string if found, None otherwise
		"""
		type_regex = re.compile(r'<TYPE:(.*)>')

		# Check for new <TYPE:...> tag format on manifest
		manifest = comp.op('FamManifest')
		if manifest:
			for tag in manifest.tags:
				if match := type_regex.match(tag):
					return match.group(1)
			
		# Check for tags on the component itself (e.g. for non-COMP or file-based overrides)
		if f'<FAM:{family_name}>' in comp.tags:
			for tag in comp.tags:
				if match := type_regex.match(tag):
					return match.group(1)

		if category_tags:
			for tag in comp.tags:
				if tag not in category_tags:
					return tag
		else:
			for tag in comp.tags:
				if tag.endswith(family_name) and tag != family_name:
					return tag.removesuffix(family_name)
		
		return sanitize_name(comp.name)
