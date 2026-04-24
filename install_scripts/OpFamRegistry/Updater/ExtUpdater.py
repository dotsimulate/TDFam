import os
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
		self._set_status_message(self.IsUpdatable.val)
		#

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

		if parent.OpFamRegistry == (op.FAMREGISTRY if hasattr(op, 'FAMREGISTRY') else None):
			self._set_update_indicator(self.IsUpdatable.val)
			self._set_status_message(self.IsUpdatable.val)

		if hasattr(parent.OpFamRegistry.parent().par, 'Devmode'):
			if parent.OpFamRegistry.parent().par.Devmode.eval() and self.IsUpdatable.val:
				# Auto-fetch in dev mode for testing
				#release_notes = iop.GitHub.FetchReleaseNotes()
				#debug(f'Latest release notes:\n{release_notes}')
				self.PromptUpdate()


	def _get_ui_manager(self):
		global_registry = getattr(op, 'FAMREGISTRY', None)
		if global_registry:
			return global_registry.op('OpFamUI') or op('/ui/dialogs/mainmenu/OpFamUI')
		return op('/ui/dialogs/mainmenu/OpFamUI')

	def _set_update_indicator(self, has_update):
		alpha = 0.5 if has_update else 0
		ui_manager = self._get_ui_manager()
		if ui_manager:
			toggle_text = ui_manager.op('fam_toggle/text')
			if toggle_text and hasattr(toggle_text.par, 'borderbalpha'):
				toggle_text.par.borderbalpha = alpha

	def _set_status_message(self, has_update):
		status = 'Update available!' if has_update else 'https://github.com/dotsimulate/TDFam'
		label = 'UPDATE' if has_update else 'Repo'
		global_registry = getattr(op, 'FAMREGISTRY', None)
		if global_registry:
			settings = global_registry.op('OpFamUI/general_settings')
			if settings and hasattr(settings.par, 'Status'):
				settings.par.Status = status
				settings.par.Status.label = label


	def _set_family_update_indicators(self):
		target = self.target_comp.parent()
		if not target or not hasattr(target, 'Properties'):
			return
		fam_name = target.Properties.get('family_name')
		if not fam_name:
			return
		ui_manager = self._get_ui_manager()
		if not ui_manager:
			return
		folder_tabs = ui_manager.op('fam_menu/folderTabs/folderTabs')
		if not folder_tabs:
			return
		global_registry = getattr(op, 'FAMREGISTRY', None)
		global_updater = global_registry.op('UPDATER') if global_registry else None
		both_updatable = self.IsUpdatable.val and bool(getattr(global_updater, 'IsUpdatable', tdu.Dependency(False)).val)
		for tab in folder_tabs.ops('tab*'):
			off_comp = tab.op('off')
			if not off_comp:
				continue
			if off_comp.par.text.eval().lstrip('!') != fam_name:
				continue
			if both_updatable:
				off_comp.par.text.expr = "'!' + op('../menuOptions')[parent().digits + 1, 'label']"
			else:
				off_comp.par.text.expr = "op('../menuOptions')[parent().digits + 1, 'label']"
			break

	def PromptUpdate(self):
		"""
		Display a confirmation dialog before updating.

		Shows a message box with the new version number and asks user
		to confirm. If confirmed, calls Update() to begin download.
		"""
		name = self.component_name
		ret = ui.messageBox(
			f'Hello TDFam Developer!',
			f'This TDFam has an outdated internal registry component.\n'
			f'We want to update it for you to ensure you and your users have the latest features and fixes.\n\n'
			f'It will not overwrite any existing data of yours. Thanks.',
			buttons=['Yes']
		)
		if ret == 0:
			self.Update()
		else:
			return

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
		debug(f'Downloaded file info: {fp}')
		# rename file, append version
		if fp.exists:
			new_name = f"{self.palette_folder}_{self.newTag}.tox"
			new_path = fp.dir + '/' + new_name
			if not tdu.FileInfo(new_path).exists:
				os.rename(fp.path, new_path)
				debug(f'Renamed downloaded file to: {new_path}')
			else:
				debug(f'File with name {new_name} already exists, skipping rename')
		else:
			debug(f'FileInfo for downloaded path does not exist: {callbackInfo["path"]}')

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

		# Grab version and families from old comp before any destruction
		self.newTag = parent.OpFamRegistry.parent().fetch('new_tdfamregistry_version', '0.0.0')

		prev_reg = dict(getattr(oldComp, 'RegisteredFams', {}))
		prev_inst = dict(getattr(oldComp, 'InstalledFams', {}))
		prev_shortcuts = {}
		if (_sm := getattr(oldComp, 'ShortcutManager', None)):
			prev_shortcuts = _sm.shortcutDict.getRaw()
		node_x, node_y = oldComp.nodeX, oldComp.nodeY

		# Rename old comp out of the way so /sys/TDFamRegistry is free
		oldComp.name = 'TDFamRegistry_old'

		# Copy new comp into /sys/ with the canonical name
		sys_root = op('/sys')
		new_global = sys_root.copy(newComp, name='TDFamRegistry')
		new_global.allowCooking = True
		new_global.nodeX = node_x
		new_global.nodeY = node_y

		# Set version and shortcut immediately
		if hasattr(new_global.par, 'Version'):
			new_global.par.Version = self.newTag
		new_global.par.opshortcut = 'FAMREGISTRY'

		# Store families so the new tox's postInit can restore them if it has that logic
		new_global.store('RegisteredFams', prev_reg)
		new_global.store('InstalledFams', prev_inst)
		new_global.store('ShortcutDict', prev_shortcuts)

		# Let each family owner re-register itself with the new registry
		for family in prev_inst.values():
			run('args[0].ext.OpFamExt._post_init()', family, delayFrames=3, delayRef=op.TDResources)

		# Notify user
		self._post_update_notify()

		# Defer destroy of old comp (we are running inside it, can't destroy synchronously)
		run('args[0].destroy()', oldComp, delayFrames=1, delayRef=op.TDResources)
		# Destroy the /sys/quiet temp copy now
		newComp.destroy()


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
			target = self.ownerComp
			if target and hasattr(target.par, 'Repository'):
				repo_url = target.par.Repository.eval()
				if repo_url:
					ui.viewFile(f'{repo_url}/releases/latest')
