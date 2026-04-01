import re

# example_retention_data = {
# 	".": ["!Period:stub", "!<About>:update", "Help"],  # self: default all custom, with exclusions
# 	"noise1": ["<Noise>", "!harm:stub"],               # child: include Noise page, but not harm on stub
# 	"noise2": "exp",                                   # child: just retain exp in all scenarios
# }

def _parse_retain_rules(rules, scenario, comp, custom_only=False):
	"""
	Parse a list of retain rule strings into (inclusions, exclusions) sets.

	Rule syntax:
	  "Par"           — include Par in all scenarios
	  "Par:update"    — include Par in update scenario only
	  "<Page>"        — include all pars on Page (requires comp)
	  "!Par:stub"     — exclude Par in stub scenario only
	  "!<Page>"       — exclude all pars on Page in all scenarios
	"""
	if isinstance(rules, str):
		rules = [rules]

	inclusions = set()
	exclusions = set()

	for item in rules:
		is_exclude = item.startswith('!')
		entry = item[1:] if is_exclude else item

		entry_scenario = None
		if ':' in entry:
			entry, entry_scenario = entry.split(':', 1)

		if entry_scenario is not None and entry_scenario != scenario:
			continue

		page_match = re.match(r'^<(.+)>$', entry)
		if page_match and comp is not None:
			page_name = page_match.group(1)
			par_source = comp.customPars if custom_only else comp.pars()
			matched = {p.name for p in par_source if p.page is not None and p.page.name == page_name}
		elif comp is not None:
			par_source = comp.customPars if custom_only else comp.pars()
			all_names = [p.name for p in par_source if p.page is not None]
			matched = set(tdu.match(entry, all_names))
		else:
			matched = {entry}

		if is_exclude:
			exclusions |= matched
		else:
			inclusions |= matched

	return inclusions, exclusions


def get_self_pars_to_retain(comp, scenario, rules):
	"""
	Retain rules for the self (.) entry.
	Default: all custom pars. Explicit inclusions override exclusions.
	"""
	all_custom = {p.name for p in comp.customPars if p.page is not None}
	inclusions, exclusions = _parse_retain_rules(rules, scenario, comp, custom_only=True)
	return list((all_custom - exclusions) | (inclusions & all_custom))

def find_retain_key(comp_path, retention_data):
	"""
	Find the matching key in retention_data for a comp.
	Tries '.' and '' as self-reference aliases before the absolute path.

	Returns:
		The matched key string, or None if no entry exists.
	"""
	for candidate in ['.', '', comp_path]:
		if candidate in retention_data:
			return candidate
	return None

def get_params_to_retain(op_path, current_scenario, retention_data, comp=None):
	"""
	Retain rules for child op entries.
	Default: nothing. Inclusions define what to keep, exclusions carve out exceptions.
	"""
	rules = retention_data.get(op_path)
	if not rules:
		return []
	inclusions, exclusions = _parse_retain_rules(rules, current_scenario, comp)
	return list(inclusions - exclusions)

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