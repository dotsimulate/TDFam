import json
import re
from RegistryHelpers import sanitize_name, ensure_manifest_tags, apply_family_color, resolve_op_type

class OpManager:
	def __init__(self, ownerComp, registry):
		self.ownerComp = ownerComp
		self.registry = registry


	def _createClone(self, family_owner, display_name, source_info):
		lookup_name = display_name
		normalized_name = lookup_name.replace(' ', '_')
		installer = family_owner
		try:
			prep_place = op.FAMREGISTRY.op('prep')
		except:
			debug("Error: 'prep' operator not found in FAMREGISTRY")
			prep_place = None
		if prep_place is None:
			prep_place = installer.op('OpFamRegistry/prep')

		is_file_based = False


		# TODO X: too many fallbacks to consider ...? need to account for manifest in them? am I just tired?
		if source_info is None:
			# Fallback to original embedded-only behavior
			custom_ops = installer.par.Opcomp.eval() if hasattr(installer.par, 'Opcomp') else None
			if not custom_ops:
				print(f"Error: Operator '{lookup_name}' not found - no operators_comp and no file source")
				return
			masters = custom_ops.findChildren(name=lookup_name, maxDepth=1) # look up using op type manifest first!
			if not masters:
				print(f"Error: Operator '{lookup_name}' not found in custom_operators")
				return
			master = masters[0]
			clone = prep_place.copy(master, name=normalized_name+'1')

		elif source_info[0] == 'file':
			# Load from external .tox file
			tox_path = source_info[1]
			try:
				# loadTox loads .tox as child and returns the loaded op
				clone = prep_place.loadTox(tox_path)
			except Exception as e:
				print(f"Error loading .tox file '{tox_path}': {e}")
				clone = None
				# Fallback to embedded if file load fails AND operators_comp exists
				custom_ops_base = installer.par.Opcomp.eval() if hasattr(installer.par, 'Opcomp') else None
				if custom_ops_base:
					masters = custom_ops_base.findChildren(name=lookup_name, maxDepth=1)
					if masters:
						clone = prep_place.copy(masters[0]
												#, name=normalized_name+'1'
												)

		elif source_info[0] == 'embedded':
			# Use embedded operator (normal path)
			master = source_info[1]
			clone = prep_place.copy(master)

		if clone is None:
			print(f"Error: Could not create operator '{lookup_name}'")
			return

		return clone

	def manageOpClone(self, family_owner, opType, display_name):
		"""
		Modify the placed operator before it is added to the scene.
		"""
		family_name = self.registry.GetFamilyName(family_owner)
		# strip family name from opType
		opType = opType.replace(family_name, '')

		# Get operator source - supports both embedded and file-based loading
		source_info = self.registry.FileManager.get_operator_source(
			family_name, opType
		)



		clone = self._createClone(family_owner, display_name, source_info)
		if not clone:
			debug(f'Failed to create clone {opType} for {family_owner}')
			return
		is_file_based = source_info is not None and source_info[0] == 'file'
		if is_file_based:
			_, tox_file_version = self.registry.FileManager._parse_tox_info(family_owner, source_info[1])
			# Get external manifest data from cache
			folder_cache = family_owner.Properties.get('folder_cache', {})
			cache_entry = folder_cache.get(opType.lower(), {})
			external_manifest = cache_entry.get('manifest')
		else:
			tox_file_version = None
			external_manifest = None

		if clone.family != 'COMP':
			# gather OpInfo without manifest to get defaults
			OpInfo = self._validate_OpInfo(family_owner, clone, None, display_name=display_name)
			# tag normal Op
			self._tag_op(family_owner, clone, OpInfo, is_manifest=False)
			clone.name = sanitize_name(clone.name)
			return clone
		else:
			# Validate manifest (check, or create if necessary)
			OpInfo, ParRetain, Shortcuts = self._validate_manifest(family_owner, clone, tox_file_version=tox_file_version, display_name=display_name, external_manifest=external_manifest)
			self._handle_OpInfo(family_owner, clone, OpInfo=OpInfo)
			self._handle_Shortcuts(family_owner, clone, OpInfo, Shortcuts)
			self._tag_op(family_owner, clone, OpInfo)

			self._handle_license(family_owner, clone)
			self._handle_attributes(family_owner, clone, is_file_based=is_file_based)

		# TODO X: result = op.FAMREGISTRY.CallHook(family, '_PlaceOp', panelValue, lookup_name) ... now that the manifest did its job...?

		return clone

	def _validate_manifest(self, family_owner, _op, tox_file_version=None, display_name=None, external_manifest=None):
		manifest = _op.op('FamManifest')
		# Create manifest if it doesn't exist
		if not manifest:
			manifest_template = self.ownerComp.op('FamManifest')
			manifest : baseCOMP =  _op.copy(manifest_template)

		# External manifest data (from sidecar .json or folder manifest.json)
		ext_opinfo = external_manifest.get('OpInfo', {}) if external_manifest else {}
		ext_parretain = external_manifest.get('ParRetain', {}) if external_manifest else {}
		ext_shortcuts = external_manifest.get('Shortcuts', {}) if external_manifest else {}

		OpInfo = self._validate_OpInfo(family_owner, _op, manifest, tox_file_version=tox_file_version, display_name=display_name, external_opinfo=ext_opinfo)
		ParRetain = self._validate_ParRetain(family_owner, _op, manifest, external_parretain=ext_parretain)
		Shortcuts = self._validate_Shortcuts(family_owner, _op, manifest, external_shortcuts=ext_shortcuts)
		self._validate_StateRetain(family_owner, _op, manifest)

		return OpInfo, ParRetain, Shortcuts

	def GetOpInfo(self, _op, family_owner=None):
		"""
		Get the most complete OpInfo dict possible for an operator.
		Read-only — does not create or modify anything.

		Reads from FamManifest/OpInfo if available, then fills fallbacks
		from par.Version, op name, and family_owner (if provided).

		Args:
			_op: The operator to read from
			family_owner: Optional installer comp for fam_version/op_fam fallbacks

		Returns:
			dict: op_version, fam_version, op_fam, op_type, op_name, op_label
		"""
		OpInfo = {}

		# Read from manifest if COMP with FamManifest
		if isinstance(_op, OP) and _op.isCOMP:
			_manifest = _op.op('FamManifest')
			if _manifest:
				_opInfo_dat = _manifest.op('OpInfo')
				if _opInfo_dat:
					try:
						OpInfo = json.loads(_opInfo_dat.text)
					except:
						pass

		# Fallback: op_version from par.Version, then family version
		if not OpInfo.get('op_version'):
			if hasattr(_op, 'par') and _op.par['Version'] is not None:
				OpInfo['op_version'] = str(_op.par.Version.eval())
			elif family_owner and hasattr(family_owner.par, 'Version'):
				OpInfo['op_version'] = str(family_owner.par.Version.eval())

		# Fallback: fam_version and op_fam from family_owner
		if family_owner:
			if not OpInfo.get('fam_version') and hasattr(family_owner.par, 'Version'):
				OpInfo['fam_version'] = str(family_owner.par.Version.eval())
			if not OpInfo.get('op_fam') and hasattr(family_owner, 'Properties'):
				OpInfo['op_fam'] = family_owner.Properties['family_name']

		# Fallback: op_name, op_type, op_label from op.name
		if not OpInfo.get('op_name'):
			OpInfo['op_name'] = _op.name
		if not OpInfo.get('op_type'):
			OpInfo['op_type'] = _op.name
		if not OpInfo.get('op_label'):
			label = ' '.join(w.capitalize() for w in _op.name.split('_'))
			OpInfo['op_label'] = self._sanitize_label(label)

		return OpInfo

	def _validate_OpInfo(self, family_owner, _op, manifest, tox_file_version=None, display_name=None, external_opinfo=None):
		"""
		Check if the operator has a FamManifest and OpInfo, and add them if not.
		External opinfo (from sidecar/folder manifest) seeds values before internal manifest.
		"""
		# Start from read-only info
		OpInfo = self.GetOpInfo(_op, family_owner)

		# External JSON seeds values that aren't already set by internal manifest
		if external_opinfo:
			for k, v in external_opinfo.items():
				if not OpInfo.get(k):
					OpInfo[k] = v

		# Get or create the DAT for write-back
		_OpInfo = None
		if manifest:
			_OpInfo = manifest.op('OpInfo')
			if not _OpInfo:
				_OpInfo = self._create_manifest_dat(manifest, 'OpInfo')
				_OpInfo.text = "{}"

		# Override op_version with tox_file_version if provided and no manifest version
		if tox_file_version is not None and not OpInfo.get('op_version'):
			OpInfo['op_version'] = tox_file_version

		# Always overwrite fam_version and op_fam
		OpInfo['fam_version'] = str(family_owner.par.Version.eval())
		OpInfo['op_fam'] = family_owner.Properties['family_name']

		# Persist compatible_types: keep per-operator override, else inherit family-level
		if not OpInfo.get('compatible_types'):
			OpInfo['compatible_types'] = list(family_owner.Properties.get('compatible_types', []))

		# Override name/type/label with display_name if provided and field was a fallback
		if display_name:
			# Check what the manifest actually had (without fallbacks)
			raw = {}
			if isinstance(_op, OP) and _op.isCOMP:
				_m = _op.op('FamManifest')
				if _m and _m.op('OpInfo'):
					try:
						raw = json.loads(_m.op('OpInfo').text)
					except:
						pass
			if not raw.get('op_name'):
				OpInfo['op_name'] = display_name
			if not raw.get('op_type'):
				OpInfo['op_type'] = display_name
			if not raw.get('op_label'):
				label = ' '.join(w.capitalize() for w in display_name.split('_'))
				OpInfo['op_label'] = self._sanitize_label(label)

		# sanitize
		OpInfo['op_name'] = sanitize_name(OpInfo['op_name'])
		OpInfo['op_type'] = sanitize_name(OpInfo['op_type'])

		# Ensure consistent key order for readability
		_key_order = ['fam_version', 'op_version', 'op_fam', 'op_type', 'op_name', 'op_label']
		ordered = {k: OpInfo[k] for k in _key_order if k in OpInfo}
		ordered.update({k: v for k, v in OpInfo.items() if k not in _key_order})

		# Unwrap any TD Dependency / DependList values pulled from Properties so json.dumps doesn't loop
		ordered = self._unwrap_for_json(ordered)

		if _OpInfo:
			_OpInfo.text = json.dumps(ordered, indent=4)
		return ordered

	def _validate_Shortcuts(self, family_owner, _op, manifest, external_shortcuts=None):
		_Shortcuts = manifest.op('Shortcuts')
		# Create Shortcuts if it doesn't exist
		if _Shortcuts is None:
			_Shortcuts = manifest.create(textDAT, 'Shortcuts')
			_Shortcuts.text = '{}'
		_dict = json.loads(_Shortcuts.text)
		# External shortcuts fill in keys not already defined internally
		if external_shortcuts:
			for k, v in external_shortcuts.items():
				if k not in _dict:
					_dict[k] = v
			_Shortcuts.text = json.dumps(self._unwrap_for_json(_dict), indent=4)
		return _dict

	def _validate_StateRetain(self, family_owner, _op, manifest):
		_StateRetain = manifest.op('StateRetain')
		if not _StateRetain:
			_StateRetain = manifest.create(textDAT, 'StateRetain')
			_StateRetain.text = '{}'
		return json.loads(_StateRetain.text)

	def _validate_ParRetain(self, family_owner, _op, manifest, external_parretain=None):
		_ParRetain = manifest.op('ParRetain')
		# Create ParRetain if it doesn't exist
		if not _ParRetain:
			_ParRetain = manifest.create(textDAT, 'ParRetain')
			_ParRetain.text = '{}'
		_dict = json.loads(_ParRetain.text)
		# External par retain fills in keys not already defined internally
		if external_parretain:
			for k, v in external_parretain.items():
				if k not in _dict:
					_dict[k] = v
			_ParRetain.text = json.dumps(self._unwrap_for_json(_dict), indent=4)
		return _dict

	def deployManifests(self, family_owner):
		"""Deploy/update FamManifest on all COMPs inside the family's Opcomp, plus on-disk sidecars."""
		family_name = family_owner.Properties['family_name']
		count = 0

		opcomp = family_owner.par.Opcomp.eval() if hasattr(family_owner.par, 'Opcomp') else None
		if opcomp:
			for child in opcomp.findChildren(type=COMP, maxDepth=1):
				OpInfo, ParRetain, Shortcuts = self._validate_manifest(family_owner, child, display_name=child.name)
				self._tag_op(family_owner, child, OpInfo)
				self._clean_manifest_examples(child.op('FamManifest'))
				self.registry.CallHook(family_name, '_DeployManifest', child, OpInfo, ParRetain, Shortcuts)
				count += 1

		count += self.deployManifestsToDisk(family_owner)
		return count

	def _unwrap_for_json(self, obj, seen=None):
		"""Recursively convert TD Dependable/DependList/DependDict to plain Python, with cycle detection."""
		if obj is None or isinstance(obj, (str, int, float, bool)):
			return obj
		if seen is None:
			seen = set()
		if id(obj) in seen:
			return str(obj)
		seen.add(id(obj))
		# Plain dict first (fast path + prevents falling into list branch on failure)
		if isinstance(obj, dict):
			return {str(k): self._unwrap_for_json(v, seen) for k, v in obj.items()}
		if isinstance(obj, (list, tuple)):
			return [self._unwrap_for_json(v, seen) for v in obj]
		# Dependency wrapper — unwrap via .val, but only once and with cycle guard
		if hasattr(obj, 'val'):
			try:
				v = obj.val
				if id(v) not in seen and v is not obj:
					return self._unwrap_for_json(v, seen)
			except Exception:
				pass
		# DependDict-like
		if hasattr(obj, 'items') and callable(getattr(obj, 'items', None)):
			try:
				return {str(k): self._unwrap_for_json(v, seen) for k, v in obj.items()}
			except Exception:
				return str(obj)
		# DependList-like (must come after dict checks so we don't iterate a dict's keys)
		if hasattr(obj, '__iter__'):
			try:
				return [self._unwrap_for_json(v, seen) for v in obj]
			except Exception:
				return str(obj)
		return str(obj)

	def deployManifestsToDisk(self, family_owner):
		"""
		Validate/update per-op manifest definitions on disk. Rules:
		- Never create new files or new entries — only update existing ones.
		- Priority: per-op sidecar JSON (next to .tox) > folder manifest.json (category folder > root).
		- Preserve every field already on disk; only rewrite OpInfo.
		"""
		import os
		family_name = family_owner.Properties['family_name']
		operators_folder = getattr(family_owner, 'operators_folder', None)

		# Make sure folder_cache reflects the current on-disk state before validation
		if operators_folder:
			self.registry.FileManager.refresh_cache(family_name, operators_folder)

		folder_cache = family_owner.Properties.get('folder_cache', {})
		if not folder_cache:
			print(f"deployManifestsToDisk: no folder_cache for {family_name} (operators_folder={operators_folder})")
			return 0

		count = 0
		skipped = 0

		# Batch folder-manifest writes so a file with multiple updated ops is only written once
		folder_writes = {}  # path -> full dict with our updates applied

		for lookup_name, cache_entry in folder_cache.items():
			tox_path = cache_entry.get('path')
			if not tox_path or not os.path.isfile(tox_path):
				skipped += 1
				continue

			existing_manifest = cache_entry.get('manifest') or {}
			validated = self._buildDiskManifest(family_owner, lookup_name, cache_entry, existing_manifest)

			# Priority 1: existing sidecar
			sidecar_path = tox_path[:-4] + '.json'
			if os.path.isfile(sidecar_path):
				try:
					json_str = json.dumps(self._unwrap_for_json(validated), indent=4)
				except Exception as e:
					print(f"deployManifestsToDisk: serialization failed for {lookup_name}: {e}")
					continue
				try:
					with open(sidecar_path, 'w') as f:
						f.write(json_str)
					count += 1
				except Exception as e:
					print(f"deployManifestsToDisk: error writing {sidecar_path}: {e}")
				continue

			# Priority 2: folder manifest.json (category folder, then root) containing this key
			key = lookup_name.lower()
			candidates = []
			tox_dir = os.path.dirname(tox_path)
			candidates.append(os.path.join(tox_dir, 'manifest.json'))
			if operators_folder and os.path.abspath(tox_dir) != os.path.abspath(operators_folder):
				candidates.append(os.path.join(operators_folder, 'manifest.json'))

			for path in candidates:
				if not os.path.isfile(path):
					continue
				if path not in folder_writes:
					try:
						with open(path, 'r') as f:
							folder_writes[path] = json.load(f)
					except Exception as e:
						print(f"deployManifestsToDisk: error reading {path}: {e}")
						continue
				if key in folder_writes[path]:
					folder_writes[path][key] = validated
					count += 1
					break
			# If neither a sidecar nor a matching folder-manifest entry exists, skip silently.

		# Flush batched folder-manifest updates
		for path, data in folder_writes.items():
			try:
				json_str = json.dumps(self._unwrap_for_json(data), indent=4)
			except Exception as e:
				print(f"deployManifestsToDisk: serialization failed for {path}: {e}")
				continue
			try:
				with open(path, 'w') as f:
					f.write(json_str)
			except Exception as e:
				print(f"deployManifestsToDisk: error writing {path}: {e}")

		# Refresh cache so in-memory folder_cache reflects the updated disk state
		if operators_folder and count:
			self.registry.FileManager.refresh_cache(family_name, operators_folder)

		print(f"deployManifestsToDisk[{family_name}]: {count} updated, {skipped} skipped, {len(folder_cache)} in cache")
		return count

	def _buildDiskManifest(self, family_owner, lookup_name, cache_entry, existing_manifest):
		"""
		Compute the validated per-op manifest dict. Preserves every existing
		top-level key; only rewrites OpInfo with current family state.
		"""
		family_name = family_owner.Properties['family_name']
		existing_opinfo = dict(existing_manifest.get('OpInfo', {}))

		# Always overwrite fam_version + op_fam with current family state
		existing_opinfo['fam_version'] = str(family_owner.par.Version.eval())
		existing_opinfo['op_fam'] = family_name

		# Fallback-fill op_name / op_type / op_label from lookup name
		if not existing_opinfo.get('op_name'):
			existing_opinfo['op_name'] = lookup_name
		if not existing_opinfo.get('op_type'):
			existing_opinfo['op_type'] = lookup_name
		if not existing_opinfo.get('op_label'):
			label = ' '.join(w.capitalize() for w in lookup_name.split('_'))
			existing_opinfo['op_label'] = self._sanitize_label(label)

		# op_version: prefer manifest, else version parsed from filename
		if not existing_opinfo.get('op_version') and cache_entry.get('version'):
			existing_opinfo['op_version'] = cache_entry['version']

		# Inherit family-level compatible_types if none set
		if not existing_opinfo.get('compatible_types'):
			existing_opinfo['compatible_types'] = list(family_owner.Properties.get('compatible_types', []))

		existing_opinfo['op_name'] = sanitize_name(existing_opinfo['op_name'])
		existing_opinfo['op_type'] = sanitize_name(existing_opinfo['op_type'])

		_key_order = ['fam_version', 'op_version', 'op_fam', 'op_type', 'op_name', 'op_label']
		ordered_opinfo = {k: existing_opinfo[k] for k in _key_order if k in existing_opinfo}
		ordered_opinfo.update({k: v for k, v in existing_opinfo.items() if k not in _key_order})

		# Preserve all other top-level keys (ParRetain, Shortcuts, or anything user added)
		result = dict(existing_manifest)
		result['OpInfo'] = ordered_opinfo
		return result

	def _clean_manifest_examples(self, manifest):
		"""Clear file/syncfile on example DATs inside a deployed manifest."""
		if not manifest:
			return
		for name in ('OpInfo_example', 'ParRetain_example', 'Shortcuts_example'):
			dat = manifest.op(name)
			if dat and hasattr(dat.par, 'file'):
				dat.par.file = ''
				dat.par.syncfile = False

	def _tag_op(self, family_owner, _op, OpInfo, is_manifest=True):
		fam_name = family_owner.Properties['family_name']
		op_type = OpInfo.get('op_type', "MISSING")

		if is_manifest:
			target = _op.op('FamManifest')
		else:
			target = _op
		ensure_manifest_tags(target, fam_name, op_type=op_type, is_manifest=is_manifest)

	def _handle_OpInfo(self, family_owner, _op, OpInfo = None):
		if not OpInfo:
			OpInfo = json.loads(_op.op('FamManifest').op('OpInfo').text)
			
		# make sure name is valid
		_name = OpInfo['op_name']
		max_tries = 99
		tries = 1
		while tries < max_tries:
			try:
				_op.name = f"{_name}{tries}"
				break
			except:
				tries += 1
		return

	def _handle_Shortcuts(self, family_owner, _op, OpInfo, Shortcuts):
		if not Shortcuts:
			Shortcuts = json.loads(_op.op('FamManifest').op('Shortcuts').text)
		
		fam_name = OpInfo.get('op_fam')
		op_type = OpInfo.get('op_type')
		
		debug(f'about to register {Shortcuts} for {_op}')

		for _shortcut, _parName in Shortcuts.items():
			debug(f'attempting to register shortcut {_shortcut} for {_op}')
			self.registry.ShortcutManager.registerOpShortcut(fam_name, op_type, _shortcut, _parName)

		return

	def _handle_license(self, family_owner, _op):
		"""
		Handle license copying - check clone.family since master may not exist for file-based
		Only copy license if the family_owner has a License op
		"""
		if _op.family == 'COMP' and (license := family_owner.op('License')):
			existing_license = _op.op('License')
			if existing_license:
				try:
					existing_content = existing_license.par.Bodytext.eval()
					current_content = license.par.Bodytext.eval()
					if existing_content != current_content:
						existing_license.destroy()
						_op.copy(license)
				except:
					existing_license.destroy()
					_op.copy(license)
			else:
				_op.copy(license)

	def _handle_attributes(self, family_owner, _op, is_file_based=False):
		if is_file_based:
			apply_family_color(family_owner, _op)

		_op.allowCooking = True
		_op.bypass = False
		_op.viewer = ui.preferences['network.viewer']

# region start helper methods

	def _create_manifest_dat(self, manifest, dat_name):
		"""Create a manifest DAT by copying from the template to preserve position."""
		template_manifest = self.ownerComp.op('FamManifest')
		template_dat = template_manifest.op(dat_name) if template_manifest else None
		if template_dat:
			new_dat = manifest.copy(template_dat)
		else:
			new_dat = manifest.create(textDAT, dat_name)
		return new_dat

	def _sanitize_label(self, label):
		all_families = list(families.keys())
		all_families.extend(self.registry.RegisteredFams.keys())

		if all_families:
			# Escape names and use boundaries that handle non-word characters
			escaped = all_families
			regex = r'(?<!\w)(' + '|'.join(escaped) + r')(?!\w)'
			label = re.sub(regex, lambda m: m.group(1).upper(), label, flags=re.IGNORECASE)

		return label

# endregion