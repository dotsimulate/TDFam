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

def resolve_op_type(comp, family_name, tag_manager=None):
	"""
	Resolve operator type from manifest first, then fall back to tags.

	Args:
		comp: The component to resolve type for
		family_name: The family name
		tag_manager: Optional TagManager instance for tag-based fallback

	Returns:
		tuple: (op_type, source) where source is 'manifest', 'tags', or 'name'
	"""
	manifest = comp.op('FamManifest')
	if manifest:
		op_type = get_op_type_from_manifest(manifest)
		if op_type:
			return op_type, 'manifest'
	if tag_manager:
		op_type = tag_manager.get_operator_type(comp, family_name)
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

def _filter_keys_by_rules(available_keys, rules, scenario):
	"""
	Filter a list of string keys using retain rules.
	Same syntax as ParRetain: wildcards, !exclusions, :scenario suffixes.
	Returns the set of keys to retain.
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

		matched = set(tdu.match(entry, list(available_keys)))

		if is_exclude:
			exclusions |= matched
		else:
			inclusions |= matched

	return inclusions - exclusions


def _resolve_targets(comp, comp_path):
	"""
	Resolve a comp-relative path to a list of (resolved_path, target_op) tuples.
	'.' returns the comp itself. Wildcards match immediate children.
	"""
	if comp_path in ('.', ''):
		return [('.', comp)]

	child_names = [c.name for c in comp.findChildren(depth=1)]
	matched = tdu.match(comp_path, child_names)
	return [(name, comp.op(name)) for name in matched if comp.op(name)]


def capture_state_retain(comp, state_retain_data, scenario):
	"""
	Capture non-parameter state from a comp based on StateRetain rules.

	Args:
		comp: The component to capture state from
		state_retain_data: Parsed StateRetain JSON dict
		scenario: 'stub' or 'update'

	Returns:
		dict keyed by resolved comp path with extensions/storage/dats data
	"""
	captured = {}

	for comp_path, rules in state_retain_data.items():
		targets = _resolve_targets(comp, comp_path)

		for resolved_path, target in targets:
			entry = {}

			# Extensions
			ext_rules = rules.get('extensions', {})
			if ext_rules:
				ext_data = {}
				for ext_class, key_rules in ext_rules.items():
					storage_key = ext_class + 'Stored'
					raw_dict = target.fetch(storage_key, None)
					if raw_dict is None:
						continue
					raw = raw_dict.getRaw() if hasattr(raw_dict, 'getRaw') else dict(raw_dict)
					filtered_keys = _filter_keys_by_rules(raw.keys(), key_rules, scenario)
					if filtered_keys:
						ext_data[storage_key] = {k: raw[k] for k in filtered_keys}
				if ext_data:
					entry['extensions'] = ext_data

			# Raw storage
			storage_rules = rules.get('storage', [])
			if storage_rules:
				all_storage_keys = [k for k in target.storage.keys()
									if not k.endswith('Stored')]
				filtered_keys = _filter_keys_by_rules(all_storage_keys, storage_rules, scenario)
				storage_data = {}
				for key in filtered_keys:
					storage_data[key] = target.fetch(key, None)
				if storage_data:
					entry['storage'] = storage_data

			# DATs
			dat_rules = rules.get('dats', [])
			if dat_rules:
				child_names = [c.name for c in target.findChildren(depth=1)]
				filtered_names = _filter_keys_by_rules(child_names, dat_rules, scenario)
				dat_data = {}
				for dat_name in filtered_names:
					dat_op = target.op(dat_name)
					if not dat_op:
						continue
					if dat_op.isTable:
						dat_data[dat_name] = {
							'type': 'table',
							'rows': [[dat_op[r, c].val for c in range(dat_op.numCols)]
									 for r in range(dat_op.numRows)]
						}
					elif dat_op.isText:
						dat_data[dat_name] = {
							'type': 'text',
							'text': dat_op.text
						}
				if dat_data:
					entry['dats'] = dat_data

			if entry:
				captured[resolved_path] = entry

	return captured


def restore_state_retain(comp, captured_data):
	"""
	Restore non-parameter state to a comp from captured StateRetain data.

	Args:
		comp: The component to restore state to
		captured_data: Dict from capture_state_retain()
	"""
	for resolved_path, entry in captured_data.items():
		if resolved_path in ('.', ''):
			target = comp
		else:
			target = comp.op(resolved_path)
		if not target:
			continue

		# Extensions — update existing DependDict rather than replacing it
		for storage_key, filtered_dict in entry.get('extensions', {}).items():
			existing = target.fetch(storage_key, None)
			if existing is not None and hasattr(existing, 'getRaw'):
				for k, v in filtered_dict.items():
					existing[k] = v
			else:
				target.store(storage_key, filtered_dict)

		# Raw storage
		for key, value in entry.get('storage', {}).items():
			target.store(key, value)

		# DATs
		for dat_name, dat_info in entry.get('dats', {}).items():
			dat_op = target.op(dat_name)
			if not dat_op:
				continue
			if dat_info['type'] == 'table' and dat_op.isTable:
				dat_op.clear()
				for row in dat_info['rows']:
					dat_op.appendRow(row)
			elif dat_info['type'] == 'text' and dat_op.isText:
				dat_op.text = dat_info['text']


def sanitize_name(name, base=True):
	if base:
		name = tdu.base(name)

	# Replace spaces with underscores but DO NOT lowercase, to preserve capitalization
	return name.replace(' ', '_')