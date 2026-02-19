# example_retention_data = {
# 	"base1/noise1": {
# 		"amp": ["update"],
# 		"harm": ["update", "stub"]
# 	},
# 	"base1/noise2": "exp",
# 	"base1/noise3": ["p1", "p2"] # Example of a list shorthand
# }

# # Example Usage:
# print(get_params_to_retain("base1/noise1", "stub", retention_data))
# # Output: ['harm'] (because 'amp' is only for 'update')
# print(get_params_to_retain("base1/noise2", "stub", retention_data))
# # Output: ['exp'] (shorthand implies all scenarios)

def get_params_to_retain(op_path, current_scenario, retention_data):
	rules = retention_data.get(op_path)
	if not rules:
		return []
		
	params_to_keep = []
	# Case A: It's a dictionary (Per-parameter scenarios)
	if isinstance(rules, dict):
		for par_name, scenarios in rules.items():
			if current_scenario in scenarios:
				params_to_keep.append(par_name)
	# Case B: It's a String or List (Retain in ALL scenarios)
	else:
		# Normalize string to list
		if isinstance(rules, str):
			rules = [rules]
			
		# In this shorthand, we assume we keep them for BOTH update and stub
		params_to_keep.extend(rules)
		
	return params_to_keep

def get_op_type_from_manifest(manifest):
	"""Read op_type from a FamManifest's OpInfo."""
	import json
	op_info_dat = manifest.op('OpInfo')
	if op_info_dat:
		try:
			return json.loads(op_info_dat.text).get('op_type', '')
		except:
			pass
	return ''

def resolve_op_type(comp, family_name, tag_manager=None, category_tags=None):
	"""
	Resolve operator type from manifest first, then fall back to tags.

	Args:
		comp: The component to resolve type for
		family_name: The family name
		tag_manager: Optional TagManager instance for tag-based fallback
		category_tags: Optional set of category tags for tag resolution

	Returns:
		tuple: (op_type, source) where source is 'manifest', 'tags', or 'name'
	"""
	manifest = comp.op('FamManifest')
	if manifest:
		op_type = get_op_type_from_manifest(manifest)
		if op_type:
			return op_type, 'manifest'
	if tag_manager:
		op_type = tag_manager.get_operator_type(comp, family_name, category_tags)
		if op_type:
			return op_type, 'tags'
	return sanitize_name(comp.name), 'name'

def ensure_manifest_tags(target, family_name, op_type=None, is_stub=False, is_manifest=True):
	"""
	Stamp correct FAM/TYPE/MANIFEST/STUB tags on a target comp.
	Works for both manifest comps and bare operators (non-COMP).
	Cleans stale tags before applying current ones.

	Args:
		target: The comp to tag (FamManifest for COMPs, or the op itself for non-COMPs)
		family_name: The family name
		op_type: Optional operator type string
		is_stub: If True, add STUB tag instead of MANIFEST
		is_manifest: If True, add MANIFEST tag (set False for bare ops without manifests)
	"""
	if not target:
		return

	# Clean stale FAM/TYPE tags
	stale_tags = [t for t in target.tags if t.startswith('<FAM:') or t.startswith('<TYPE:')]
	for tag in stale_tags:
		target.tags.remove(tag)

	target.tags.add(f'<FAM:{family_name}>')
	if op_type:
		target.tags.add(f'<TYPE:{op_type}>')

	if not is_manifest:
		# Bare op tagging (non-COMP), no MANIFEST/STUB tags
		return

	if is_stub:
		target.tags.discard('<MANIFEST>')
		target.tags.add('<STUB>')
	else:
		target.tags.discard('<STUB>')
		target.tags.add('<MANIFEST>')

def apply_family_color(family_owner, comp):
	"""
	Apply family color to a component if Colorfileops is enabled.

	Args:
		family_owner: The installer/family owner comp
		comp: The target component to color
	"""
	if hasattr(family_owner.par, 'Colorfileops') and family_owner.par.Colorfileops.eval():
		comp.color = (family_owner.par.Colorr.eval(), family_owner.par.Colorg.eval(), family_owner.par.Colorb.eval())

def sanitize_name(name, base=True):
	if base:
		name = tdu.base(name)

	# Replace spaces with underscores but DO NOT lowercase, to preserve capitalization
	return name.replace(' ', '_')