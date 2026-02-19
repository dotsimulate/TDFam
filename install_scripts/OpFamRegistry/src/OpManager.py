import json
import re
from RegistryHelpers import sanitize_name

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

	def _validate_OpInfo(self, family_owner, _op, manifest, tox_file_version=None, display_name=None):
		"""
		Check if the operator has a FamManifest and OpInfo, and add them if not.
		"""
		if manifest:
			_OpInfo = manifest.op('OpInfo')
			if not _OpInfo:
				_OpInfo = manifest.create(textDAT, 'OpInfo')
				_OpInfo.text = "{}"

			OpInfo = json.loads(_OpInfo.text)
		else:
			# at this point we are most likely dealing with a non-COMP operator edge case
			OpInfo = {}
			_OpInfo = None

		if not (_version := OpInfo.get('op_version', None)):
			_version = family_owner.par.Version.eval() 
			if (_parVersion := _op.par['Version']) is not None:
				_version = _parVersion
			elif tox_file_version is not None:
				_version = tox_file_version

			OpInfo['op_version'] = _version

		# always overwrite fam_version
		_fam_version = family_owner.par.Version.eval()
		OpInfo['fam_version'] = _fam_version

		# always overwrite op_fam
		_op_fam = family_owner.Properties['family_name']
		OpInfo['op_fam'] = _op_fam

		if not OpInfo.get('op_name', None):
			OpInfo['op_name'] = display_name or _op.name

		if not OpInfo.get('op_type', None):
			OpInfo['op_type'] = display_name or _op.name

		if not OpInfo.get('op_label', None):
			# we only force sanitization if we're creating the label
			label = self._sanitize_label(display_name or _op.name)
			OpInfo['op_label'] = label
		
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
		if not is_manifest:
			_op_to_tag = _op
		else:
			_op_to_tag = _op.op('FamManifest')
			if not _op_to_tag:
				return
			
			#fam_name = OpInfo.get('op_fam', family_owner.Properties['family_name'])
		fam_name = family_owner.Properties['family_name'] # NOTE: we ignore op_fam manifest value for now
		op_type = OpInfo.get('op_type', "MISSING") # TODO: have a fallback for this (based on probably display name which needs then to be passed here)

		# remove any tag starting with <FAM: or <TYPE: cause we're gonna add the actual current one if it's not already there
		stale_tags = [tag for tag in _op_to_tag.tags if tag.startswith('<FAM:') or tag.startswith('<TYPE:')]
		for tag in stale_tags:
			_op_to_tag.tags.remove(tag)

		if f'<FAM:{fam_name}>' not in _op_to_tag.tags:
			_op_to_tag.tags.add(f'<FAM:{fam_name}>')
		if f'<TYPE:{op_type}>' not in _op_to_tag.tags:
			_op_to_tag.tags.add(f'<TYPE:{op_type}>')
		if is_manifest:
			if '<MANIFEST>' not in _op_to_tag.tags:
				_op_to_tag.tags.add('<MANIFEST>')

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
		# Apply family color to file-based ops if Colorfileops is enabled
		# NOTE: should we do this regardless of the Colorfileops parameter?
		if is_file_based and hasattr(family_owner.par, 'Colorfileops') and family_owner.par.Colorfileops.eval():
			color = family_owner.par.Colorr.eval(), family_owner.par.Colorg.eval(), family_owner.par.Colorb.eval()
			_op.color = color

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