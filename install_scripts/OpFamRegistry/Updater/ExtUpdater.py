import TDFunctions as TDF


class ExtUpdater:
	"""
	Generic updater extension for TouchDesigner components.

	This extension polls a GitHub repository for new releases and manages
	the download and replacement process for updating a target component.

	Flow:
		1. Check() triggers async polling via iop.GitHub.PollLatestTag()
		2. GitHub extension calls OnPolledLatestTag() with the latest tag
		3. Version comparison sets IsUpdatable dependency
		4. UI can bind to IsUpdatable to show update button
		5. PromptUpdate() or Update() initiates download via iop.Downloader
		6. OnFileDownloaded() handles component replacement

	Required Parameters on ownerComp:
		- Target: Reference to the component to update
		- Enabled: Toggle to enable/disable update checking
		- Componentname (optional): Display name for UI messages
		- Palettefolder (optional): Folder name in userPaletteFolder for externaltox

	Required Internal Operators:
		- iop.GitHub: GitHub remote extension for polling tags
		- iop.Downloader: FileDownloader extension for downloading files
		- iop.TDAsyncIO: Async IO handler

	Attributes:
		IsUpdatable (tdu.Dependency): Reactive flag indicating update availability.
		newTag (str): The latest tag retrieved from GitHub.
	"""

	def __init__(self, ownerComp):
		"""
		Initialize the ExtUpdater extension.

		Args:
			ownerComp: The component this extension is attached to.
		"""
		self.ownerComp = ownerComp
		self.IsUpdatable = tdu.Dependency(False)
		self.newTag = None
		self.isMajorUpdateAllowed = True

	@property
	def target_comp(self):
		"""
		The component to be updated.

		Returns:
			COMP or None: The target component from the Target parameter.
		"""
		return self.ownerComp.par.Target.eval()

	@property
	def component_name(self):
		"""
		Display name for the component being updated.

		Used in UI dialogs and debug messages. Falls back to target
		component's name if Componentname parameter is not set.

		Returns:
			str: Component display name.
		"""
		if hasattr(self.ownerComp.par, 'Componentname'):
			name = self.ownerComp.par.Componentname.eval()
			if name:
				return name
		target = self.target_comp
		return target.name if target else 'Component'

	@property
	def palette_folder(self):
		"""
		Folder name within userPaletteFolder for storing the .tox file.

		Used to construct the externaltox expression. Falls back to
		component_name if Palettefolder parameter is not set.

		Returns:
			str: Palette folder name.
		"""
		if hasattr(self.ownerComp.par, 'Palettefolder'):
			folder = self.ownerComp.par.Palettefolder.eval()
			if folder:
				return folder
		return self.component_name

	@property
	def current_version(self):
		"""
		Current version string from the target component.

		Reads the Version parameter from target_comp and strips any 'v' prefix.

		Returns:
			str: Version string (e.g., '1.2.3') or '0.0.0' if unavailable.
		"""
		target = self.target_comp
		if target and hasattr(target.par, 'Version'):
			return target.par.Version.eval().strip('v')
		return '0.0.0'

	def Check(self, _=None):
		"""
		Check for available updates asynchronously.

		Only runs if the Enabled parameter is True. Triggers the GitHub
		extension to poll for the latest release tag.

		Args:
			_: Unused parameter (allows binding to par callbacks).
		"""
		if self.ownerComp.par.Enabled.eval():
			iop.TDAsyncIO.Run([self._doDaCheck()])

	async def _doDaCheck(self):
		"""
		Async coroutine that triggers the GitHub tag poll.

		Called by Check() via TDAsyncIO. The result arrives via
		OnPolledLatestTag() callback.
		"""
		iop.GitHub.PollLatestTag()

	def OnPolledLatestTag(self, new_tag):
		"""
		Callback invoked when GitHub returns the latest release tag.

		Compares the new tag against current_version to determine if an
		update is available. Sets IsUpdatable accordingly.

		Version Comparison Logic:
			- Strips 'v' prefix from both versions for comparison
			- Parses semantic version (major.minor.patch)
			- Major version jumps are blocked unless tag ends with 'f' flag
			  (e.g., '2.0.0f' forces update from 1.x.x to 2.x.x)
			- Falls back to string comparison if parsing fails

		Args:
			new_tag: The latest tag string from GitHub (e.g., 'v1.2.3').
					 Can include optional 'f' suffix to force major updates.

		Side Effects:
			- Sets self.newTag to the received tag
			- Sets self.IsUpdatable.val to True/False
		"""
		if not new_tag:
			self.IsUpdatable.val = False
			return

		debug(f'ExtUpdater: Polled latest tag: {new_tag}')
		new_tag_clean = new_tag.strip('v')
		self.newTag = new_tag_clean

		parent.OpFamRegistry.parent().store('new_tdfamregistry_version', new_tag_clean)

		current = self.current_version

		try:
			new_parts = new_tag_clean.split('.')
			current_parts = current.split('.')

			new_major = int(new_parts[0]) if new_parts else 0
			current_major = int(current_parts[0]) if current_parts else 0

			# Check for flag suffix (e.g., 'f' for force update)
			tag_flag = new_tag_clean[-1] if new_tag_clean else ''

			# Skip major version jumps unless flagged
			if not self.isMajorUpdateAllowed and new_major > current_major and tag_flag != 'f':
				self.IsUpdatable.val = False
			else:
				self.IsUpdatable.val = (current != new_tag_clean)
		except (ValueError, IndexError):
			# If version parsing fails, compare as strings
			self.IsUpdatable.val = (current != new_tag_clean)

	def PromptUpdate(self):
		"""
		Display a confirmation dialog before updating.

		Shows a message box with the new version number and asks user
		to confirm. If confirmed, calls Update() to begin download.
		"""
		name = self.component_name
		ret = ui.messageBox(
			f'{name} update available',
			f'A new version ({self.newTag}) is available.\nWould you like to update {name}?',
			buttons=['No', 'Yes']
		)
		if ret:
			self.Update()

	def Update(self, _=None):
		"""
		Begin the update download process.

		Calls _pre_update_save() for any cleanup, then pulses the
		Downloader to fetch the new version. The download completion
		is handled by OnFileDownloaded().

		Args:
			_: Unused parameter (allows binding to par callbacks).
		"""
		self._PreRemoteDownload()
		#self.MockUpdate()
		iop.Downloader.par.Download.pulse()

	def MockUpdate(self, source_path='/TDFamRegistry'):
		"""
		Mock update for testing - bypasses GitHub download.

		Copies the source component to /sys/quiet and then calls
		OnFileDownloaded with mock callbackInfo, letting the normal
		update flow handle everything.

		Args:
			source_path: Path to component to use as update source.
						 Defaults to '/TDFamRegistry'.
		"""
		source_comp = op(source_path)
		if not source_comp:
			debug(f'MockUpdate: Source component not found at {source_path}')
			return

		# Copy source to /sys/quiet (simulating download/load)
		sys_comp = op('/sys/quiet')
		if not sys_comp:
			debug(f'MockUpdate: /sys not found')
			return

		# Clean up any existing mock comp
		existing = sys_comp.op('TDFamRegistry')
		if existing:
			existing.destroy()
		newComp = sys_comp.copy(source_comp, name='TDFamRegistry')
		if not newComp:
			debug(f'MockUpdate: Failed to copy source component to /sys/quiet')
			return

		# Call OnFileDownloaded with mock callbackInfo
		self.OnFileDownloaded({
			'compPath': newComp.path,
			'path': f'{source_path}.tox'  # mock file path
		})

	def _PreRemoteDownload(self):
		"""
		Hook called before downloading an update.
		"""
		self.ownerComp.DoCallback("PreRemoteDownload")
		pass

	def _PostRemoteDownload(self, oldComp, newComp):
		"""
		Hook called after downloading a new component but before replacement.

		Override this method in a subclass to transfer settings or state
		from the old component to the new one."""
		self.ownerComp.DoCallback("PostRemoteDownload", callbackInfo={
                    "oldComp": oldComp,
                    "newComp": newComp,
                })

	def OnFileDownloaded(self, callbackInfo):
		"""
		Callback invoked when the FileDownloader completes the download.

		Performs the component replacement process:
			1. Validates the downloaded component
			2. Preserves docked operators (undocks them temporarily)
			3. Configures the new component (externaltox, Version, etc.)
			4. Replaces old component using TDF.replaceOp()
			5. Restores docked operators to the new component
			6. Calls _post_update_notify() to inform user

		Args:
			callbackInfo: Dictionary from FileDownloader containing:
				- 'compPath': Path to the loaded component in project
				- 'path': File path of the downloaded .tox file

		Note:
			The new component stores 'post_update' = True, which can be
			checked on initialization to run post-update migrations.
		"""
		name = self.component_name
		debug(f'{name} update downloaded: {callbackInfo}')
		comp_path = callbackInfo.get('compPath')
		newComp = op(comp_path) if comp_path else None

		if not newComp:
			debug(f'{name} update failed: could not load new component')
			return

		fp = tdu.FileInfo(str(callbackInfo['path']))
		oldComp = self.target_comp

		if not oldComp:
			debug(f'{name} update failed: target component not found')
			newComp.destroy()
			return
		
		# Call post-download callbacks
		self._PostRemoteDownload( oldComp, newComp )


		# Store docked operators information before replacement
		docked_ops = []
		for docked_op in oldComp.docked:
			docked_info = {
				'op': docked_op,
				'pos': (docked_op.nodeX, docked_op.nodeY),
			}
			docked_ops.append(docked_info)
			# Undock the operator before replacement
			docked_op.dock = None

		# Configure the new component
		folder = self.palette_folder
		
		self.newTag = parent.OpFamRegistry.parent().fetch('new_tdfamregistry_version','0.0.0')
		debug(f'Setting version to {self.newTag} on new component')
		if hasattr(newComp.par, 'Version'):
			newComp.par.Version = self.newTag
			

		newComp.store('post_update', True)

		global_registry = op.FAMREGISTRY if hasattr(op, 'FAMREGISTRY') else None
		if global_registry:
			if (_registered_fams := getattr(global_registry, 'RegisteredFams', None)):
				newComp.store('RegisteredFams', _registered_fams)

			if (_installed_fams := getattr(global_registry, 'InstalledFams', None)):
				newComp.store('InstalledFams', _installed_fams)

			if (_sm := getattr(global_registry, 'ShortcutManager', None)):
				newComp.store('ShortcutDict', _sm.shortcutDict.getRaw())

		old_path = oldComp.path
		new_path = newComp.path
		old_version = oldComp.par.Version.eval()
		new_version = newComp.par.Version.eval()
		# Replace the old component
		TDF.replaceOp(oldComp, newComp)


	def _post_update_notify(self):
		"""
		Hook called after successful component replacement.

		Default implementation shows a message box asking if user wants
		to view the changelog. Override to customize post-update behavior.

		Example:
			def _post_update_notify(self):
				# Run migrations
				self._run_migrations()
				# Then call parent
				super()._post_update_notify()
		"""
		name = self.component_name
		ret = ui.messageBox(
			f'{name} updated',
			f'Successfully updated to version {self.newTag}.\nWould you like to see the changelog?',
			buttons=['No', 'Yes']
		)
		if ret:
			# Open the releases page in browser
			target = self.target_comp
			if target and hasattr(target.par, 'Repository'):
				repo_url = target.par.Repository.eval()
				if repo_url:
					ui.viewFile(f'{repo_url}/releases/latest')
