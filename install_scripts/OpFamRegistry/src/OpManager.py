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
		else:
			tox_file_version = None

		if clone.family != 'COMP':
			# gather OpInfo without manifest to get defaults
			OpInfo = self._validate_OpInfo(family_owner, clone, None, display_name=display_name)
			# tag normal Op
			self._tag_op(family_owner, clone, OpInfo, is_manifest=False)
			clone.name = sanitize_name(clone.name)
			return clone
		else:
			# Validate manifest (check, or create if necessary)
			OpInfo, ParRetain, Shortcuts = self._validate_manifest(family_owner, clone, tox_file_version=tox_file_version, display_name=display_name)
			self._handle_OpInfo(family_owner, clone, OpInfo=OpInfo)
			self._handle_Shortcuts(family_owner, clone, OpInfo, Shortcuts)
			self._tag_op(family_owner, clone, OpInfo)

			self._handle_license(family_owner, clone)
			self._handle_attributes(family_owner, clone, is_file_based=is_file_based)

		# TODO X: result = op.FAMREGISTRY.CallHook(family, '_PlaceOp', panelValue, lookup_name) ... now that the manifest did its job...?

		return clone

	def _validate_manifest(self, family_owner, _op, tox_file_version=None, display_name=None):
		manifest = _op.op('FamManifest')
		# Create manifest if it doesn't exist
		if not manifest:
			manifest_template = self.ownerComp.op('FamManifest')
			manifest : baseCOMP =  _op.copy(manifest_template)

		OpInfo = self._validate_OpInfo(family_owner, _op, manifest, tox_file_version=tox_file_version, display_name=display_name)
		ParRetain = self._validate_ParRetain(family_owner, _op, manifest)
		Shortcuts = self._validate_Shortcuts(family_owner, _op, manifest)

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

		# Fallback: op_version from par.Version
		if not OpInfo.get('op_version'):
			if hasattr(_op, 'par') and _op.par['Version'] is not None:
				OpInfo['op_version'] = str(_op.par.Version.eval())

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

	def _validate_OpInfo(self, family_owner, _op, manifest, tox_file_version=None, display_name=None):
		"""
		Check if the operator has a FamManifest and OpInfo, and add them if not.
		"""
		# Start from read-only info
		OpInfo = self.GetOpInfo(_op, family_owner)

		# Get or create the DAT for write-back
		_OpInfo = None
		if manifest:
			_OpInfo = manifest.op('OpInfo')
			if not _OpInfo:
				_OpInfo = manifest.create(textDAT, 'OpInfo')
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
				OpInfo['op_label'] = self._sanitize_label(display_name)

		# sanitize
		OpInfo['op_name'] = sanitize_name(OpInfo['op_name'])
		OpInfo['op_type'] = sanitize_name(OpInfo['op_type'])

		if _OpInfo:
			_OpInfo.text = json.dumps(OpInfo, indent=4)
		return OpInfo

	def _validate_Shortcuts(self, family_owner, _op, manifest):
		_Shortcuts = manifest.op('Shortcuts')
		# Create Shortcuts if it doesn't exist
		if _Shortcuts is None:
			_Shortcuts = manifest.create(textDAT, 'Shortcuts')
			_Shortcuts.text = {}
		_dict = json.loads(_Shortcuts.text)
		return _dict

	def _validate_ParRetain(self, family_owner, _op, manifest):
		_ParRetain = manifest.op('ParRetain')
		# Create ParRetain if it doesn't exist
		if not _ParRetain:
			_ParRetain = manifest.create(textDAT, 'ParRetain')
			_ParRetain.text = {}
		return json.loads(_ParRetain.text)

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