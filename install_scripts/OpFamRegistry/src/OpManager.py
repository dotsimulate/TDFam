import json

class OpManager:
	def __init__(self, ownerComp, registry):
		self.ownerComp = ownerComp
		self.registry = registry


	def manageOpClone(self, family_owner, clone, is_file_based, op_name=None):
		"""
		Modify the placed operator before it is added to the scene.
		"""
		OpInfo, ParRetain, Shortcuts = self._validate_manifest(family_owner, clone, op_name=op_name)

		self._handle_OpInfo(family_owner, clone, OpInfo=OpInfo)
		self._handle_Shortcuts(family_owner, clone, Shortcuts=Shortcuts)
		self._tag_manifest(family_owner, clone, OpInfo)

		self._handle_license(family_owner, clone)
		self._handle_attributes(family_owner, clone, is_file_based)

		return clone

	def _validate_manifest(self, family_owner, _op, op_name=None):
		manifest = _op.op('FamManifest')
		# Create manifest if it doesn't exist
		if not manifest:
			manifest_template = self.ownerComp.op('FamManifest')
			manifest : baseCOMP =  _op.copy(manifest_template)

		OpInfo = self._validate_OpInfo(family_owner, _op, manifest, op_name=op_name)
		ParRetain = self._validate_ParRetain(family_owner, _op, manifest)
		Shortcuts = self._validate_Shortcuts(family_owner, _op, manifest)

		return OpInfo, ParRetain, Shortcuts

	def _validate_OpInfo(self, family_owner, _op, manifest, op_name=None):
		"""
		Check if the operator has a FamManifest and OpInfo, and add them if not.
		"""
		_OpInfo = manifest.op('OpInfo')
		if not _OpInfo:
			_OpInfo = manifest.create(textDAT, 'OpInfo')
			_OpInfo.text = {}

		OpInfo = json.loads(_OpInfo.text)
		if not (_version := OpInfo.get('version', None)):
			_version = _op.par.Version.eval() if _op.par['Version'] is not None else family_owner.par.Version.eval()
			OpInfo['version'] = _version

		if not (_op_fam := OpInfo.get('op_fam', None)):
			_op_fam = family_owner.Properties['family_name']
			OpInfo['op_fam'] = _op_fam

		if not OpInfo.get('op_name', None):
			OpInfo['op_name'] = op_name or _op.name

		if not OpInfo.get('op_type', None):
			OpInfo['op_type'] = 'something' # TODO: determine op type

		_OpInfo.text = json.dumps(OpInfo, indent=4)
		return OpInfo

	def _validate_Shortcuts(self, family_owner, _op, manifest):
		_Shortcuts = manifest.op('Shortcuts')
		# Create Shortcuts if it doesn't exist
		if not _Shortcuts:
			_Shortcuts = manifest.create(textDAT, 'Shortcuts')
			_Shortcuts.text = {}
		return json.loads(_Shortcuts.text)

	def _validate_ParRetain(self, family_owner, _op, manifest):
		_ParRetain = manifest.op('ParRetain')
		# Create ParRetain if it doesn't exist
		if not _ParRetain:
			_ParRetain = manifest.create(textDAT, 'ParRetain')
			_ParRetain.text = {}
		return json.loads(_ParRetain.text)

	def _tag_manifest(self, family_owner, _op, OpInfo):
		manifest = _op.op('FamManifest')
		if not manifest:
			return
		fam_name = OpInfo.get('op_fam', family_owner.Properties['family_name'])
		if fam_name not in manifest.tags:
			manifest.tags.add(fam_name)
		if '<MANIFEST>' not in manifest.tags:
			manifest.tags.add('<MANIFEST>')

	def _handle_OpInfo(self, family_owner, _op, OpInfo = None):
		if not OpInfo:
			OpInfo = json.loads(_op.op('FamManifest').op('OpInfo').text)
		# do stuff with OpInfo
		_op.name = OpInfo['op_name']
		return

	def _handle_Shortcuts(self, family_owner, _op, Shortcuts = None):
		if not Shortcuts:
			Shortcuts = json.loads(_op.op('FamManifest').op('Shortcuts').text)
		# do stuff with Shortcuts
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

	def _handle_attributes(self, family_owner, _op, is_file_based = False):
		# Apply family color to file-based ops if Colorfileops is enabled
		# NOTE: should we do this regardless of the Colorfileops parameter?
		if is_file_based and hasattr(family_owner.par, 'Colorfileops') and family_owner.par.Colorfileops.eval():
			color = family_owner.par.Colorr.eval(), family_owner.par.Colorg.eval(), family_owner.par.Colorb.eval()
			_op.color = color

		_op.allowCooking = True
		_op.bypass = False
		_op.viewer = ui.preferences['network.viewer']