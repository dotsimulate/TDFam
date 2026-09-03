"""
File-based operator loading for opfam-create.

Handles loading operators from external .tox files, with caching and
version comparison against embedded operators.
"""

import os
import re
import json

class FileManager:
	"""
	Manages loading operators from external .tox files.

	Supports:
	- Folder scanning and caching
	- Version parsing from filenames
	- Resolution between embedded and file-based operators
	"""

	def __init__(self, ownerComp, registry):
		"""
		Initialize the file manager.

		Args:
			ownerComp: The component that owns this extension
			registry: The OpFamRegistryExt instance
		"""
		self.ownerComp = ownerComp
		self.registry = registry
		self._search_words_cache = {}  # {family_name: {op_type_lower: [words]}}
		self._manifest_index_cache = {}  # {family_name: {op_type_lower: [master_op, ...]}}

	def refresh_cache(self, family_name, operators_folder):
		"""
		Scan external folder and build cache of available operators.
		Also loads external manifest data from per-op .json sidecars
		and folder-level manifest.json files.

		Args:
			family_name: The family name
			operators_folder: Path to folder containing .tox files
		"""
		installer = self.registry.GetFamilyExt(family_name)
		if not installer:
			return

		new_cache = {}

		if not operators_folder or not os.path.isdir(operators_folder):
			installer.Properties['folder_cache'] = new_cache
			return

		# Load root-level manifest.json (covers all ops as fallback)
		root_manifest = self._load_folder_manifest(operators_folder)

		for item in os.listdir(operators_folder):
			item_path = os.path.join(operators_folder, item)

			if os.path.isdir(item_path):
				# Subfolder = category
				category_name = item
				cat_manifest = self._load_folder_manifest(item_path)
				for f in os.listdir(item_path):
					if f.endswith('.tox'):
						name, version = self._parse_tox_info(installer, f)
						if name:
							key = name.lower()
							sidecar = self._load_sidecar_json(item_path, f)
							manifest_data = sidecar or cat_manifest.get(key) or root_manifest.get(key)
							entry = {
								'path': os.path.join(item_path, f),
								'version': version,
								'category': category_name,
								'manifest': manifest_data
							}
							optype_key = (((manifest_data or {}).get('OpInfo') or {}).get('op_type') or '').lower()
							new_cache[optype_key if optype_key else key] = entry

			elif item.endswith('.tox'):
				# Loose file = no category
				name, version = self._parse_tox_info(installer, item)
				if name:
					key = name.lower()
					sidecar = self._load_sidecar_json(operators_folder, item)
					manifest_data = sidecar or root_manifest.get(key)
					entry = {
						'path': os.path.join(operators_folder, item),
						'version': version,
						'category': None,
						'manifest': manifest_data
					}
					optype_key = (((manifest_data or {}).get('OpInfo') or {}).get('op_type') or '').lower()
					new_cache[optype_key if optype_key else key] = entry

		installer.Properties['folder_cache'] = new_cache
		self.refresh_search_words_cache(family_name, folder_cache_override=new_cache)

	def refresh_search_words_cache(self, family_name, folder_cache_override=None):
		"""
		Build {op_type_lower: [search_words]} from folder_cache manifests and
		embedded op FamManifest/OpInfo. Stored on self._search_words_cache
		under family_name.
		"""
		installer = self.registry.GetFamilyExt(family_name)
		if not installer:
			return

		search_words = {}

		def _merge(op_type, words):
			"""Union-merge preserving order; skips no-ops."""
			if not op_type or not words:
				return
			key = op_type.lower()
			existing = search_words.setdefault(key, [])
			for w in words:
				if w not in existing:
					existing.append(w)

		folder_cache = folder_cache_override if folder_cache_override is not None \
			else installer.Properties.get('folder_cache', {})
		for key, entry in (folder_cache or {}).items():
			opinfo = (entry.get('manifest') or {}).get('OpInfo', {})
			words = self._normalize_search_words(opinfo.get('search_words'))
			_merge(opinfo.get('op_type') or key, words)

		custom_ops = installer.operators_comp
		if custom_ops:
			for manifest in custom_ops.findChildren(tags=['<MANIFEST>'], maxDepth=2):
				opinfo_dat = manifest.op('OpInfo')
				if not opinfo_dat:
					continue
				try:
					opinfo = json.loads(opinfo_dat.text)
				except Exception:
					continue
				words = self._normalize_search_words(opinfo.get('search_words'))
				_merge(opinfo.get('op_type') or manifest.parent().name, words)

		self._search_words_cache[family_name] = search_words

	def GetSearchWords(self, family_name):
		"""Return {op_type_lower: [words]} for the family (empty dict if none)."""
		return self._search_words_cache.get(family_name, {})

	def _normalize_search_words(self, raw):
		"""Accept list or comma/space-separated string; return lowercased list."""
		if not raw:
			return []
		if isinstance(raw, str):
			parts = re.split(r'[,\s]+', raw)
		elif isinstance(raw, (list, tuple)):
			parts = raw
		else:
			return []
		return [str(p).strip().lower() for p in parts if str(p).strip()]

	def _load_folder_manifest(self, folder_path):
		"""
		Load a manifest.json from a folder. Keys are normalized op names.

		Returns:
			dict: keyed by op name, values are {OpInfo, ParRetain, Shortcuts}
		"""
		manifest_path = os.path.join(folder_path, 'manifest.json')
		if os.path.isfile(manifest_path):
			try:
				with open(manifest_path, 'r') as f:
					return json.load(f)
			except Exception as e:
				print(f"Error loading {manifest_path}: {e}")
		return {}

	def _load_sidecar_json(self, folder_path, tox_filename):
		"""
		Load a per-op sidecar JSON file matching a .tox filename.
		e.g. cook_bar_v0.1.1.tox -> cook_bar_v0.1.1.json

		Returns:
			dict: {OpInfo, ParRetain, Shortcuts} or None
		"""
		json_filename = tox_filename[:-4] + '.json'
		json_path = os.path.join(folder_path, json_filename)
		if os.path.isfile(json_path):
			try:
				with open(json_path, 'r') as f:
					return json.load(f)
			except Exception as e:
				print(f"Error loading sidecar {json_path}: {e}")
		return None

	def _parse_tox_info(self, installer, filename):
		"""
		Parse operator name and version from .tox filename.

		Uses configurable naming_convention regex from Properties.
		Pattern should have two capture groups: (name, version)

		Args:
			installer: The OpFamCreateExt instance
			filename: The .tox filename

		Returns:
			tuple: (name, version) or (None, None) if invalid
		"""
		# Get configurable pattern from Properties
		pattern = installer.Properties.get('naming_convention', r'(.+)_v(\d+\.\d+\.\d+)\.tox$')

		if pattern:
			match = re.match(pattern, filename)
			if match:
				return (match.group(1), match.group(2))

		if filename.endswith('.tox'):
			return (filename[:-4], None)

		return (None, None)

	def _parse_version(self, ver_string):
		"""
		Parse version string to tuple for comparison.

		Args:
			ver_string: Version string like "1.2.3"

		Returns:
			tuple: (1, 2, 3) or None if invalid
		"""
		if not ver_string:
			return None
		try:
			return tuple(int(x) for x in ver_string.split('.'))
		except:
			return None

	def _get_manifest_index(self, family_name):
		"""Return {op_type_lower: [master_op, ...]} for the family's embedded masters.

		One pass over operators_comp, cached per family. Replaces the per-lookup deep
		manifest scan in get_operator_source(), which parsed every manifest for every
		lookup and was therefore O(masters^2) in JSON parses per cook.
		"""
		cached = self._manifest_index_cache.get(family_name)
		if cached is not None:
			return cached

		index = {}
		installer = self.registry.GetFamilyExt(family_name)
		custom_ops = installer.operators_comp if installer else None
		if custom_ops:
			type_regex = re.compile(r'<TYPE:(.*)>')
			for manifest in custom_ops.findChildren(tags=['<MANIFEST>'], maxDepth=2):
				master = manifest.parent()
				if not master or master == custom_ops:
					continue
				op_type = None
				if opinfo_dat := manifest.op('OpInfo'):
					try:
						op_type = json.loads(opinfo_dat.text).get('op_type')
					except Exception:
						op_type = None
				if op_type:
					op_type = op_type.replace(family_name, '')
				else:
					for tag in manifest.tags:
						if match := type_regex.match(tag):
							op_type = match.group(1)
							break
				if not op_type:
					continue
				index.setdefault(op_type.strip().lower(), []).append(master)

		self._manifest_index_cache[family_name] = index
		return index

	def invalidate_manifest_index(self, family_name=None):
		"""Drop the cached manifest index for a family (or all families)."""
		if family_name is None:
			self._manifest_index_cache.clear()
		else:
			self._manifest_index_cache.pop(family_name, None)

	def get_operator_source(self, family_name, lookup_name):
		"""
		Get operator source - embedded or file-based.
		Reads operators_folder and dynamic_refresh from the installer internally.

		Args:
			family_name: The family name
			lookup_name: Operator name to find (lowercase)

		Returns:
			tuple: ('embedded', op) or ('file', path) or None
		"""
		installer = self.registry.GetFamilyExt(family_name)
		if not installer:
			return None

		operators_folder = getattr(installer, 'operators_folder', None)
		dynamic_refresh = getattr(installer, 'dynamic_refresh', False)

		# Find embedded operator from operators_comp
		custom_ops = installer.operators_comp
		embedded = None
		if custom_ops:
			def _pick_highest(ops):
				"""Return the op with the highest op_version; trailing number breaks ties."""
				def _score(c):
					trailing = int(m.group(1)) if (m := re.search(r'(\d+)$', c.name)) else 0
					version = (0, 0, 0)
					manifest = c.op('FamManifest')
					if manifest:
						opinfo_dat = manifest.op('OpInfo')
						if opinfo_dat:
							try:
								parsed = self._parse_version(json.loads(opinfo_dat.text).get('op_version'))
								if parsed:
									version = parsed
							except:
								pass
					return (version, trailing)
				return max(ops, key=_score) if ops else None

			# Indexed manifest lookup — built once per family, reused for every lookup
			# in the cook. May return multiple masters with the same op_type; pick highest.
			manifested_ops = self._get_manifest_index(family_name).get(lookup_name.strip().lower(), [])
			manifested = _pick_highest(manifested_ops) if manifested_ops else None

			if not manifested:
				# Name-based fallback — also covers masters named 'foo1' for op_type 'foo'.
				embedded_ops = custom_ops.findChildren(name=lookup_name, maxDepth=1)
				if not embedded_ops:
					embedded_ops = [c for c in custom_ops.findChildren(maxDepth=1)
					                if tdu.base(c.name).lower() == lookup_name.lower()]
				embedded = _pick_highest(embedded_ops) if embedded_ops else None
			else:
				embedded = manifested

		# Find external .tox
		external_info = None
		if dynamic_refresh and operators_folder:
			# Live scan
			if os.path.isdir(operators_folder):
				for f in os.listdir(operators_folder):
					if not f.endswith('.tox'):
						continue
					name, version = self._parse_tox_info(installer, f)
					if name and name.lower() == lookup_name:
						external_info = {
							'path': os.path.join(operators_folder, f),
							'version': version
						}
						break
		else:
			# Use cache from Properties
			folder_cache = installer.Properties['folder_cache']
			if folder_cache:
				external_info = folder_cache.get(lookup_name)

		# Resolution logic
		if external_info and not embedded:
			return ('file', external_info['path'])

		if embedded and not external_info:
			return ('embedded', embedded)

		if not embedded and not external_info:
			return None

		# Both exist - check versioning
		external_version = external_info.get('version') if external_info else None

		if external_version is None:
			# External has no version -> embedded wins
			return ('embedded', embedded)

		# External has version - compare
		embedded_version = None
		if hasattr(embedded.par, 'Version'):
			embedded_version = self._parse_version(str(embedded.par.Version.eval()))

		external_ver_tuple = self._parse_version(external_version)

		if embedded_version is None:
			# Embedded unversioned, external versioned -> use external
			return ('file', external_info['path'])

		# Both versioned - higher wins, tie goes to embedded
		if external_ver_tuple and external_ver_tuple > embedded_version:
			return ('file', external_info['path'])

		return ('embedded', embedded)
