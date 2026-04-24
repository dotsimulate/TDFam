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
			prep_place = installer.op('TDFamRegistry/prep')

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
			self._handle_attributes(family_owner, clone, is_file_based=is_file_based, OpInfo=OpInfo)

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
		ext_stateretain = external_manifest.get('StateRetain', {}) if external_manifest else {}

		OpInfo = self._validate_OpInfo(family_owner, _op, manifest, tox_file_version=tox_file_version, display_name=display_name, external_opinfo=ext_opinfo)
		ParRetain = self._validate_ParRetain(family_owner, _op, manifest, external_parretain=ext_parretain)
		Shortcuts = self._validate_Shortcuts(family_owner, _op, manifest, external_shortcuts=ext_shortcuts)
		self._validate_StateRetain(family_owner, _op, manifest, external_stateretain=ext_stateretain)

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

	def _apply_opinfo_rules(self, opinfo, family_owner, fallback_name=None, tox_file_version=None):
		"""
		Canonical OpInfo validation rules, shared by in-TD (_validate_OpInfo) and on-disk
		(_buildDiskManifest) code paths.
		- `fam_version` and `op_fam`: always overwritten from family_owner (authoritative).
		- `op_version`: filled from `tox_file_version` only if missing.
		- `compatible_types`: filled from family only if missing.
		- `op_name` / `op_type` / `op_label`: filled from `fallback_name` only if missing.
		  `op_name`/`op_type` are sanitized when generated from the fallback; existing user
		  values are left untouched.
		Returns the opinfo dict with keys in canonical order.
		"""
		opinfo['fam_version'] = str(family_owner.par.Version.eval())
		opinfo['op_fam'] = family_owner.Properties['family_name']

		if 'op_version' not in opinfo and tox_file_version is not None:
			opinfo['op_version'] = tox_file_version
		if fallback_name:
			if 'op_name' not in opinfo:
				opinfo['op_name'] = sanitize_name(fallback_name)
			if 'op_type' not in opinfo:
				opinfo['op_type'] = sanitize_name(fallback_name)
			if 'op_label' not in opinfo:
				label = ' '.join(w.capitalize() for w in fallback_name.split('_'))
				opinfo['op_label'] = self._sanitize_label(label)

		_key_order = ['fam_version', 'op_version', 'op_fam', 'op_type', 'op_name', 'op_label']
		ordered = {k: opinfo[k] for k in _key_order if k in opinfo}
		ordered.update({k: v for k, v in opinfo.items() if k not in _key_order})
		return ordered

	def _validate_OpInfo(self, family_owner, _op, manifest, tox_file_version=None, display_name=None, external_opinfo=None):
		"""
		Persist OpInfo for an in-TD op. The manifest DAT's current text is the source
		of truth — every existing field (including custom ones like search_words) is
		preserved. Only `fam_version` / `op_fam` are overwritten, and missing required
		fields are filled from fallbacks.
		"""
		# 1. Manifest DAT for write-back — ensure it exists
		_OpInfo = None
		if manifest:
			_OpInfo = manifest.op('OpInfo')
			if not _OpInfo:
				_OpInfo = self._create_manifest_dat(manifest, 'OpInfo')
				_OpInfo.text = "{}"

		# 2. Current on-manifest values are the source of truth for existing fields
		current = {}
		if _OpInfo:
			try:
				current = json.loads(_OpInfo.text)
				if not isinstance(current, dict):
					current = {}
			except Exception as e:
				print(f"_validate_OpInfo[{_op.path}]: OpInfo DAT text failed to parse as JSON ({e}); starting from empty. Raw text:\n{_OpInfo.text[:300]}")
				current = {}

		# 3. External seeds only fill values NOT already present in the manifest
		if external_opinfo:
			for k, v in external_opinfo.items():
				if k not in current:
					current[k] = v

		# 4. Sync op_version from par.Version: fill if absent, or bump if par.Version is higher.
		if hasattr(_op, 'par') and _op.par['Version'] is not None:
			par_ver_str = str(_op.par.Version.eval())
			if 'op_version' not in current:
				current['op_version'] = par_ver_str
			else:
				_parse = self.registry.FileManager._parse_version
				par_v = _parse(par_ver_str)
				cur_v = _parse(current.get('op_version'))
				if par_v and cur_v and par_v > cur_v:
					current['op_version'] = par_ver_str
		elif 'op_version' not in current and hasattr(family_owner.par, 'Version'):
			current['op_version'] = str(family_owner.par.Version.eval())

		# 5. Canonical validation rules (overwrites fam_version/op_fam, fills missing)
		ordered = self._apply_opinfo_rules(
			current, family_owner,
			fallback_name=display_name or _op.name,
			tox_file_version=tox_file_version,
		)

		# 6. In-TD forces sanitized op_name/op_type (strict for TD naming)
		ordered['op_name'] = sanitize_name(ordered['op_name'])
		ordered['op_type'] = sanitize_name(ordered['op_type'], base=False)

		# 7. Unwrap TD Dependency / DependList so json.dumps doesn't loop
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

	def _validate_StateRetain(self, family_owner, _op, manifest, external_stateretain=None):
		_StateRetain = manifest.op('StateRetain')
		if not _StateRetain:
			_StateRetain = manifest.create(textDAT, 'StateRetain')
			_StateRetain.text = '{}'
			_StateRetain.nodeX = manifest.op('Shortcuts').nodeX
			_StateRetain.nodeY = manifest.op('Shortcuts').nodeY - 150
		_dict = json.loads(_StateRetain.text)
		if external_stateretain:
			for k, v in external_stateretain.items():
				if k not in _dict:
					_dict[k] = v
			_StateRetain.text = json.dumps(_dict, indent=4)
		return _dict

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

		# Re-read external manifest JSONs (sidecars + folder manifests) so edits
		# made on disk are picked up. refresh_cache rebuilds the search-words
		# cache at the end; fall back to embedded-only rebuild if no folder.
		operators_folder = family_owner.Properties.get('operators_folder')
		if not operators_folder and hasattr(family_owner.par, 'Opfolder'):
			operators_folder = family_owner.par.Opfolder.eval()
		import os
		if operators_folder and os.path.isdir(operators_folder):
			self.registry.FileManager.refresh_cache(family_name, operators_folder)
		else:
			self.registry.FileManager.refresh_search_words_cache(family_name)

		# Force-cook fam_create so OP_fam rebuilds from fresh manifest data (labels, types, etc.)
		fam_create = family_owner.op('fam_create')
		if fam_create:
			fam_create.cook(force=True)

		# Let the op-create dialog / menu / search pick up fresh labels & metadata
		self.registry.global_ui_injector.refresh_after_deploy(family_name)
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
		Reads disk state fresh on every call — does NOT rely on folder_cache in Properties
		(which can contain stale values between edits and the next refresh).
		"""
		import os
		family_name = family_owner.Properties['family_name']
		operators_folder = None

		if not operators_folder:
			operators_folder = family_owner.Properties.get('operators_folder')
		if not operators_folder and hasattr(family_owner.par, 'Opfolder'):
			operators_folder = family_owner.par.Opfolder.eval()
		if not operators_folder or not os.path.isdir(operators_folder):
			# No Opfolder set, or it doesn't exist — family has no file-based ops. Normal.
			return 0

		fm = self.registry.FileManager
		pattern_name_parser = fm._parse_tox_info

		# Discover every .tox in the folder tree (one level of category subdirs, like refresh_cache)
		tox_entries = []  # list of (lookup_name, tox_path, version, tox_dir)
		for item in os.listdir(operators_folder):
			item_path = os.path.join(operators_folder, item)
			if os.path.isdir(item_path):
				for f in os.listdir(item_path):
					if f.endswith('.tox'):
						name, version = pattern_name_parser(family_owner, f)
						if name:
							tox_entries.append((name.lower(), os.path.join(item_path, f), version, item_path))
			elif item.endswith('.tox'):
				name, version = pattern_name_parser(family_owner, item)
				if name:
					tox_entries.append((name.lower(), os.path.join(operators_folder, item), version, operators_folder))

		if not tox_entries:
			print(f"deployManifestsToDisk: no .tox files under {operators_folder}")
			return 0

		count = 0
		skipped = 0

		# Batch folder-manifest writes so a file with multiple updated ops is only written once
		folder_writes = {}  # path -> full dict (loaded fresh from disk)

		for lookup_name, tox_path, version, tox_dir in tox_entries:
			cache_entry = {'version': version}

			# Priority 1: existing sidecar — load fresh, update, write back
			sidecar_path = tox_path[:-4] + '.json'
			if os.path.isfile(sidecar_path):
				try:
					with open(sidecar_path, 'r') as f:
						existing_manifest = json.load(f)
				except Exception as e:
					print(f"deployManifestsToDisk: error reading {sidecar_path}: {e}")
					skipped += 1
					continue
				validated = self._buildDiskManifest(family_owner, lookup_name, cache_entry, existing_manifest)
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
			candidates = [os.path.join(tox_dir, 'manifest.json')]
			if os.path.abspath(tox_dir) != os.path.abspath(operators_folder):
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
					# Use the just-loaded entry (fresh) as the existing_manifest source
					entry_manifest = folder_writes[path][key] if isinstance(folder_writes[path][key], dict) else {}
					validated = self._buildDiskManifest(family_owner, lookup_name, cache_entry, entry_manifest)
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

		# Refresh in-memory cache so downstream readers see the updated disk state
		if count:
			self.registry.FileManager.refresh_cache(family_name, operators_folder)

		return count

	def _buildDiskManifest(self, family_owner, lookup_name, cache_entry, existing_manifest):
		"""
		Build the validated per-op manifest dict for on-disk writes.
		Applies the shared OpInfo rules, preserving every other top-level key
		(ParRetain, Shortcuts, any user-added fields) untouched.
		"""
		existing_opinfo = dict(existing_manifest.get('OpInfo', {}))
		ordered_opinfo = self._apply_opinfo_rules(
			existing_opinfo, family_owner,
			fallback_name=lookup_name,
			tox_file_version=cache_entry.get('version'),
		)
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

	def _handle_attributes(self, family_owner, _op, is_file_based=False, OpInfo=None):
		op_color = OpInfo.get('op_color') if OpInfo else None
		debug(f"[_handle_attributes] op={_op.path} is_file_based={is_file_based} op_color={op_color} OpInfo_keys={list(OpInfo.keys()) if OpInfo else None} color_before={_op.color}")
		if is_file_based or op_color:
			apply_family_color(family_owner, _op, op_color=op_color)
			debug(f"[_handle_attributes] color_after_apply={_op.color}")
		else:
			debug(f"[_handle_attributes] SKIPPED apply_family_color — not file_based and no op_color")

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