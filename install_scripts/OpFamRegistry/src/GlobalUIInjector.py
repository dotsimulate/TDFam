from __future__ import annotations

class GlobalUIInjector:
	"""Global UI injector for OpFamRegistry."""
	def __init__(self, ownerComp, owner : OpFamRegistryExt):
		self.ownerComp = ownerComp
		self.owner = owner
		
		self.menu_op = op('/ui/dialogs/menu_op')
		self.nodeTable = self.menu_op.op('nodetable') if self.menu_op else None
		
		run(lambda: self.post_init(), endFrame=True, delayRef=op.TDResources)

	def post_init(self):
		self.famui_manager = self.get_or_create_famui_manager()

	def install(self, family_name, family_owner):
		"""Install all required UI injections for a new family"""
		try:
			# 1. Per-family (Incremental)
			self.update_compatible_table(family_name, family_owner)
			self._update_colors_table(family_name, family_owner)
			self._set_owner_colors(family_owner)
			
			# 2. Global (Rebuild/Refresh)
			self._setup_global_inject_script()
			self._setup_global_panel_execute()
			self.update_family_evals()
			self._setup_last_node_type()
			self._modify_launch_menu()
			self._modify_create_node()
			self._modify_search_exec()
			self._setup_popmenu_callbacks()
			self._setup_helptext_chain()

		except Exception as e:
			debug(f'Error installing UI for family {family_name}: {e}')
			import traceback
			debug(traceback.format_exc())

	def uninstall(self, family_name):
		"""Uninstall UI injections for a specific family"""
		try:
			menuOp = self.menu_op
			nodeTable = self.nodeTable

			# 1. Per-family cleanup
			if not self.owner.InstalledFams:
				if nodeTable.op('inject_opfam_registry'):
					nodeTable.op('inject_opfam_registry').destroy()
				if menuOp.op('opfam_panel_execute'):
					menuOp.op('opfam_panel_execute').destroy()
				self._cleanup_popmenu_callbacks()
				self._cleanup_helptext_chain()

			families_op = nodeTable.op('families')
			if families_op:
				menuOp.op('families/family').click(0,0)
				families_op.bypass = False

			if menuOp.op(f'{family_name}_panel_execute'):
				menuOp.op(f'{family_name}_panel_execute').destroy()
			
			# Remove from colors table
			colors_table = menuOp.op('colors')
			if colors_table:
				for i in range(colors_table.numRows):
					if colors_table[i, 0].val == f"'{family_name}'":
						colors_table.deleteRow(i)
						break

			# Remove from compatible table
			compatibleTable = menuOp.op('compatible')
			if compatibleTable:
				if compatibleTable.rows(family_name):
					compatibleTable.deleteRow(family_name)
				if compatibleTable.cols(family_name):
					compatibleTable.deleteCol(family_name)

			# 2. Global Refresh (rebuilds scripts without this family)
			self.update_family_evals()
			self._update_colors_table()

			# Update and cleanup global scripts
			self._modify_launch_menu()
			self._modify_create_node()
			self._modify_search_exec()
			
			# Check if any custom families remain for specific cleanup
			if not self.owner.InstalledFams:
				if menuOp.op('set_last_node_type'):
					menuOp.op('set_last_node_type').destroy()
			else:
				# If families remain, just update the script
				self._setup_last_node_type()

		except Exception as e:
			debug(f'Error uninstalling UI for family {family_name}: {e}')

	# ==================== Global Rebuild Methods ====================
	
	def is_family_installed(self, family_name):
		"""
		Check if installation is actually needed by verifying if family-specific components are already in place.
		"""
		try:
			# 1. Check if inject operation exists for this family
			# TODO: this could be illegitimate check when updating to new version?
			nodeTable = self.nodeTable
			if nodeTable:
				inject_op_name = f'inject_{family_name}_fam'
				if nodeTable.op(inject_op_name):
					return True
			
			# 2. Check if this family is in the eval4 expression
			if nodeTable:
				eval4 = nodeTable.op('eval4')
				if eval4:
					current_expr = eval4.par.expr.eval()
					if current_expr and family_name in current_expr:
						return True
			
			# 3. Check if bookmark bar toggle exists
			toggle_path = f"/ui/dialogs/bookmark_bar/{family_name}_toggle"
			if op(toggle_path):
				return True

			return False
			
		except Exception as e:
			debug(f"Error checking if family {family_name} is installed: {e}")
			return False

	def update_family_evals(self):
		self._update_family_eval(self.menu_op.op('eval2'))
		self._update_family_eval(self.nodeTable.op('eval4'))

	def refresh_after_deploy(self, family_name=None):
		"""
		Rebuild UI state that reflects manifest contents (op labels, search words,
		compatible table, family evals). Call after deployManifests so the
		op-create dialog, search, etc. pick up fresh OpInfo values.
		"""
		try:
			# Refresh family eval DATs (drives op-create families list)
			self.update_family_evals()

			# Force-cook the central inject script so its output reflects fresh labels
			inject_op = self.nodeTable.op('inject_opfam_registry')
			if inject_op:
				inject_op.cook(force=True)
			families_op = self.nodeTable.op('families')
			if families_op:
				families_op.cook(force=True)

			# Per-family refresh
			if family_name and family_name in self.owner.InstalledFams:
				family_owner = self.owner.InstalledFams[family_name]
				self.update_compatible_table(family_name, family_owner)
				self._update_colors_table(family_name, family_owner)
		except Exception as e:
			debug(f'refresh_after_deploy error: {e}')

	def _update_family_eval(self, op_to_update):
		"""Update eval expression to include all installed families."""
		if not op_to_update:
			return

		_expr = "[n for _, n, _ in sorted([(i, k, True) for i, k in enumerate(families.keys())]"
		if self.owner.InstalledFams:
			_expr += " + ["
			for fam_name, fam_owner in self.owner.InstalledFams.items():
				idx = fam_owner.Properties['index']
				_expr += f"({idx}, '{fam_name}', False), "
			_expr += "]"
		_expr += ", key=lambda x: (x[0], x[2], x[1]))]"

		op_to_update.par.expr = _expr

	def _update_colors_table(self, family_name=None, family_owner=None):
		"""
		Update colors table with family color.
		Ensures family-specific colors are updated or appended without clearing the table.
		"""
		colors_table = self.menu_op.op('colors')
		if not colors_table:
			return

		# If arguments provided, update/add that specific family
		if family_name and family_owner:
			color = family_owner.Properties['color']
			family_exists = False
			for i in range(colors_table.numRows):
				if colors_table[i, 0].val == f"'{family_name}'":
					for j in range(min(len(color), colors_table.numCols - 1)):
						colors_table[i, j + 1] = color[j]
					family_exists = True
					break
			if not family_exists:
				new_row = [f"'{family_name}'"] + list(color)
				colors_table.appendRow(new_row)
		else:
			# If no arguments, ensure all currently installed families are present/updated
			for fam_name, fam_owner in self.owner.InstalledFams.items():
				color = fam_owner.Properties['color']
				family_exists = False
				for i in range(colors_table.numRows):
					if colors_table[i, 0].val == f"'{fam_name}'":
						for j in range(min(len(color), colors_table.numCols - 1)):
							colors_table[i, j + 1] = color[j]
						family_exists = True
						break
				if not family_exists:
					new_row = [f"'{fam_name}'"] + list(color)
					colors_table.appendRow(new_row)

	def _setup_last_node_type(self):
		"""Create/update set_last_node_type script for all families."""
		setLastNodeType = self.menu_op.op('set_last_node_type')
		if not setLastNodeType:
			setLastNodeType = self.menu_op.create(textDAT, 'set_last_node_type')
			launch_menu = self.menu_op.op('launch_menu_op')
			if launch_menu:
				setLastNodeType.nodeX = launch_menu.nodeX - 200
				setLastNodeType.nodeY = launch_menu.nodeY

		if not self.owner.InstalledFams:
			setLastNodeType.text = ""
			return

		# Collect all compatible types and build checks (manifest-based detection)
		fam_checks = []
		all_compatible_types = set()
		for fam_name, fam_owner in self.owner.InstalledFams.items():
			fam_checks.append(f"if manifest and '<MANIFEST>' in manifest.tags and '<FAM:{fam_name}>' in manifest.tags:\n\t\ttype = '{fam_name}'")
			for t in fam_owner.Properties.get('compatible_types', []):
				all_compatible_types.add(t)

		compatible_check = ' or '.join([f"menu_type=='{t}'" for t in all_compatible_types]) or "False"

		# Build per-family mouse pos checks (manifest-based detection)
		mouse_checks = []
		for fam_name in self.owner.InstalledFams.keys():
			mouse_checks.append(f"if child_manifest and '<MANIFEST>' in child_manifest.tags and '<FAM:{fam_name}>' in child_manifest.tags:\n\t\t\t\ttype = '{fam_name}'")

		fam_check_str = "\n\tel".join(fam_checks)
		mouse_check_str = "\n\t\t\tel".join(mouse_checks)

		script = f'''import json
varTable = op('local/set_variables')
lastnode = op(varTable['nodepath',1])
source = varTable['source',1].val
menu_type = varTable['menu_type',1].val
varTable['lasttype',1] = menu_type
if(lastnode and source == 'output'):
	type = lastnode.family
	pane_owner = ui.panes.current.owner
	parent_comp = lastnode.parent() if lastnode else None
	manifest = parent_comp.op('FamManifest') if (parent_comp and parent_comp != pane_owner) else None
	{fam_check_str}
	if manifest:
		_opinfo_dat = manifest.op('OpInfo')
		if _opinfo_dat:
			try:
				_opinfo = json.loads(_opinfo_dat.text)
				_compat = _opinfo.get('compatible_types', [])
				if isinstance(_compat, str):
					_compat = [t.strip() for t in (_compat.split(',') if ',' in _compat else _compat.split()) if t.strip()]
				if _compat:
					_ctable = op('compatible')
					if _ctable and _ctable.row(type):
						for _ci in range(1, _ctable.numCols):
							_col_type = _ctable[0, _ci].val
							if _col_type in _compat or _col_type == type or _col_type == 'COMP':
								_ctable[type, _ci] = 'x'
							else:
								_ctable[type, _ci] = ''
				if _compat and menu_type not in _compat:
					type = menu_type
			except:
				pass
	varTable['lasttype',1] = type
elif(source == 'input' and ({compatible_check})):
	pane = ui.panes.current
	zoom = pane.zoom
	currentParent = pane.owner
	mousePos = [varTable['xpos',1],varTable['ypos',1]]
	type = menu_type
	for child in currentParent.findChildren(maxDepth=1):
		if (-5<(mousePos[0]-child.nodeX)*zoom<15 and child.nodeY+child.nodeHeight>mousePos[1] and mousePos[1]>child.nodeY):
			child_manifest = child.op('FamManifest')
			{mouse_check_str}
			# Per-operator compatible_types override from manifest OpInfo
			if type != menu_type and child_manifest:
				_opinfo_dat = child_manifest.op('OpInfo')
				if _opinfo_dat:
					try:
						_opinfo = json.loads(_opinfo_dat.text)
						_compat = _opinfo.get('compatible_types', [])
						if _compat and menu_type not in _compat:
							type = menu_type
					except:
						pass
			if type != menu_type:
				varTable['lastnode',1] = child.name
				varTable['nodepath',1] = child.path
				break
	varTable['lasttype',1] = type'''

		setLastNodeType.text = script

	def _modify_launch_menu(self):
		"""Modify launch_menu_op script to use set_last_node_type."""
		launch_menu_op = self.menu_op.op('launch_menu_op')
		if not launch_menu_op:
			return

		code = launch_menu_op.text
		key = 'if($type != "none")'
		
		# 1. Clean up marker block if exists
		import re
		if '# OPFAM_START' in code and '# OPFAM_END' in code:
			# Remove the block AND the preceding newline we likely added
			# The injection adds: \n\t# OPFAM_START...
			pattern = r"\n\s*# OPFAM_START\n.*?\n\s*# OPFAM_END"
			code = re.sub(pattern, "", code, flags=re.DOTALL)

		# 2. Inject if we have families
		if self.owner.InstalledFams:
			if key in code and '# OPFAM_START' not in code:
				replacement = f"{key}\n\t# OPFAM_START\n\tcvar menu_type=$type\n\trun set_last_node_type\n\tset type = $lasttype\n\t# OPFAM_END"
				code = code.replace(key, replacement)
		
		launch_menu_op.text = code

	def _modify_create_node(self):
		"""Modify create_node script to skip creation for custom families (handled by inject scripts)."""
		createNode = self.menu_op.op('create_node')
		if not createNode:
			return

		text = createNode.text
		
		# 1. Clean up legacy injections (regex)
		import re
		text = re.sub(r"if\(\$type=='[^']+'\)\s+exit\s+endif\n?", "", text)

		# 2. Handle Marker-based injection
		insertion_key = 'set type = `tab("current",0,0)`\n'
		start_marker = "# OPFAM_START\n"
		end_marker = "# OPFAM_END\n"

		# Remove existing marker block
		if start_marker in text and end_marker in text:
			pattern = re.escape(start_marker) + r".*?" + re.escape(end_marker)
			# Here we might need similar logic, but let's check validation first.
			# Previous logic: re.sub(pattern, "", text)
			# If pattern includes newline at end, and we replace with "", we effectively remove the block.
			# But if we want to be safe:
			text = re.sub(pattern, "", text, flags=re.DOTALL)

		# Build new block
		new_block = ""
		if self.owner.InstalledFams:
			new_block = start_marker
			for fam_name in self.owner.InstalledFams.keys():
				new_block += f"if($type=='{fam_name}')\n\texit\nendif\n"
			new_block += end_marker

		# Insert new block
		if new_block:
			if insertion_key in text:
				index = text.index(insertion_key)
				createNode.text = (
					text[:index + len(insertion_key)]
					+ new_block
					+ text[index + len(insertion_key):]
				)
		else:
			createNode.text = text


	def _modify_search_exec(self):
		"""Modify search panel exec to handle custom families."""
		searchExec = self.menu_op.op('search/panelexec1')
		if not searchExec:
			return

		text = searchExec.text
		import re

		# 1. Clean up legacy injections (regex)
		pattern_legacy = r"\t\t\tif\(op\('/ui/dialogs/menu_op/current'\)\[0,0\]\.val=='[^']+'\):\n\t\t\t\tparent\.OPCREATE\.op\('nodetable'\)\.clickID\(-?\d+\)\n\t\t\t\treturn\n"
		text = re.sub(pattern_legacy, "", text)

		# 2. Handle Marker-based injection
		key = "if parent.OPCREATE.op('nodetable/destil').numRows > 1:\n"
		start_marker = "\t\t\t# OPFAM_START\n"
		end_marker = "\t\t\t# OPFAM_END\n"

		# Remove existing marker block
		if "# OPFAM_START" in text and "# OPFAM_END" in text:
			# Use flexible regex for marker removal to account for indentation
			pattern_marker = r"\s*# OPFAM_START\n.*?\s*# OPFAM_END\n"
			# Replace with a single newline to preserve spacing logic?
			# Actually if we used \s* it might have eaten the newline before the block.
			# Let's replace with empty string but be careful about the regex.
			# If we use \s+ it eats the preceding newline.
			# If we look at the result 'AB' from 'A\n\tB', it means we lost the newline.
			# So we should probably replace with nothing BUT ensure regex only matches from start of line?
			# Or easier: replace with "\n" if we consumed the newline.
			text = re.sub(pattern_marker, "\n", text, flags=re.DOTALL)

		# Build new block
		new_block = ""
		if self.owner.InstalledFams:
			fam_names = list(self.owner.InstalledFams.keys())
			fam_list_str = str(fam_names)
			
			new_block = (
				f"{start_marker}"
				f"\t\t\tif(op('{self.menu_op.path}/current')[0,0].val in {fam_list_str}):\n"
				f"\t\t\t\tparent.OPCREATE.op('nodetable').clickID(-8358)\n"
				f"\t\t\t\treturn\n"
				f"{end_marker}"
			)

		# Insert new block
		# Insert new block
		if new_block:
			# More robust regex search for the key line
			# matches "if parent...numRows > 1:" with any whitespace
			match = re.search(r"if\s+parent\.OPCREATE\.op\('nodetable/destil'\)\.numRows\s*>\s*1:", text)
			
			if match:
				end_idx = match.end()
				# Check if there is a newline after match, if not, careful
				if end_idx < len(text) and text[end_idx] == '\n':
					end_idx += 1 # Include the newline
				elif end_idx < len(text) and text[end_idx] == '\r': # Handle CRLF potentially
					if end_idx+1 < len(text) and text[end_idx+1] == '\n':
						end_idx += 2
					else:
						end_idx += 1
				
				searchExec.text = (
					text[:end_idx]
					+ new_block
					+ text[end_idx:]
				)
		else:
			# If no new block (no families), just save the cleaned text
			searchExec.text = text

	def _setup_global_inject_script(self):
		"""Create/Update the central inject script in nodetable."""
		nodeTable = self.nodeTable
		inject_op_name = 'inject_opfam_registry'
		families_op = nodeTable.op('families')

		if not families_op:
			return

		families_op.bypass = False
		
		inject_op = nodeTable.op(inject_op_name)
		if not inject_op:
			original_input = families_op.inputs[0] if families_op.inputs else None
			inject_op = nodeTable.copy(families_op, name=inject_op_name, includeDocked=True)
			
			if original_input:
				# Insert into chain: input -> inject_op -> families_op
				original_input.outputConnectors[0].disconnect()
				original_input.outputConnectors[0].connect(inject_op)
				inject_op.outputConnectors[0].connect(families_op)
		
		# Always ensure central registry callbacks are pointed to
		inject_op.par.callbacks.expr = "op.FAMREGISTRY.op('fam_script_callbacks')"
		
		inject_op.nodeX = families_op.nodeX - 150
		inject_op.nodeY = families_op.nodeY

		families_op.cook(force=True)
		inject_op.cook(force=True)

	def _setup_global_panel_execute(self, force=True):
		"""Deploy single opfam_panel_execute to menu_op."""
		panel_execute_path = 'opfam_panel_execute'
		existing = self.menu_op.op(panel_execute_path)
		if existing and not force:
			# Already exists
			return

		if existing and force:
			existing.destroy()

		source = self.ownerComp.op('fam_panel_execute')
		if not source:
			return
 
		panel_execute = self.menu_op.copy(source, name=panel_execute_path)
		panel_execute.nodeX = self.menu_op.op('node_script').nodeX
		panel_execute.nodeY = self.menu_op.op('node_script').nodeY + 100
		panel_execute.par.syncfile = ''
		panel_execute.par.file = ''
		
		# Ensure it listens to the correct panel (likely /ui/dialogs/menu_op)
		# Usually it watches its parent.

	def _setup_popmenu_callbacks(self):
		"""Deploy opfam_popMenuCallbacks to nodetable and set expression on popMenu.par.Callbackdat."""
		nodeTable = self.nodeTable
		if not nodeTable:
			debug('[_setup_popmenu_callbacks] nodeTable is None, aborting')
			return

		cb_name = 'opfam_popMenuCallbacks'
		existing = nodeTable.op(cb_name)
		debug(f'[_setup_popmenu_callbacks] existing={existing}')

		# Create the callback DAT if it doesn't exist
		if not existing:
			source = self.ownerComp.op(cb_name)
			debug(f'[_setup_popmenu_callbacks] source DAT in registry={source}')
			if source:
				existing = nodeTable.copy(source, name=cb_name)
				debug(f'[_setup_popmenu_callbacks] copied from registry source, len={len(existing.text)}')
			else:
				existing = nodeTable.create(textDAT, cb_name)
				import os
				tox_path = self.ownerComp.par.externaltox.eval() or ''
				cb_file = os.path.join(os.path.dirname(tox_path), 'src', 'opfam_popMenuCallbacks.py')
				debug(f'[_setup_popmenu_callbacks] no source DAT, trying file: {cb_file} exists={os.path.exists(cb_file)} tox_path={tox_path}')
				if os.path.exists(cb_file):
					with open(cb_file, 'r') as f:
						existing.text = f.read()
					debug(f'[_setup_popmenu_callbacks] loaded from file, len={len(existing.text)}')
				else:
					debug(f'[_setup_popmenu_callbacks] FILE NOT FOUND: {cb_file}')

			# Position next to inject_opfam_registry
			inject_op = nodeTable.op('inject_opfam_registry')
			if inject_op:
				existing.nodeX = inject_op.nodeX
				existing.nodeY = inject_op.nodeY - 120
			else:
				existing.nodeX = nodeTable.op('popMenuCallbacks').nodeX + 200 if nodeTable.op('popMenuCallbacks') else 0
				existing.nodeY = nodeTable.op('popMenuCallbacks').nodeY if nodeTable.op('popMenuCallbacks') else 0

		debug(f'[_setup_popmenu_callbacks] deployed DAT len={len(existing.text) if existing else "None"}')

		# Set expression on popMenu.par.Callbackdat to auto-swap
		popMenu = nodeTable.op('popMenu')
		if popMenu:
			fam_names = list(self.owner.InstalledFams.keys())
			fam_list_str = str(fam_names)
			popMenu.par.Callbackdat.expr = (
				f"op('opfam_popMenuCallbacks') "
				f"if op('/ui/dialogs/menu_op/current')[0,0].val in {fam_list_str} "
				f"else op('popMenuCallbacks')"
			)
			debug(f'[_setup_popmenu_callbacks] popMenu.Callbackdat expr set for families={fam_list_str}')

		self._inject_panelexec3()

	def _inject_panelexec3(self):
		"""Inject OPFAM markers into panelexec3 to set custom Items for custom families."""
		nodeTable = self.nodeTable
		if not nodeTable:
			return

		pe3 = nodeTable.op('panelexec3')
		if not pe3:
			return

		text = pe3.text
		import re

		# Remove existing marker block
		if '# OPFAM_POPMENU_START' in text and '# OPFAM_POPMENU_END' in text:
			pattern = r"\n?\t\t\t# OPFAM_POPMENU_START\n.*?\t\t\t# OPFAM_POPMENU_END\n"
			text = re.sub(pattern, "\n", text, flags=re.DOTALL)

		# Build injection block
		if self.owner.InstalledFams:
			fam_names = list(self.owner.InstalledFams.keys())
			fam_list_str = str(fam_names)

			injection = (
				f"\t\t\t# OPFAM_POPMENU_START\n"
				f"\t\t\tif family in {fam_list_str}:\n"
				f"\t\t\t\tselectedOp = op('selectedOp')\n"
				f"\t\t\t\t_registry = getattr(op, 'FAMREGISTRY', None)\n"
				f"\t\t\t\t_items = ['Documentation']\n"
				f"\t\t\t\t_disabled = []\n"
				f"\t\t\t\t_dividers = []\n"
				f"\t\t\t\tif _registry:\n"
				f"\t\t\t\t\t_installer = _registry.InstalledFams.get(family)\n"
				f"\t\t\t\t\tif _installer:\n"
				f"\t\t\t\t\t\t_manifest_items = _registry.ext.OpFamRegistryExt.getPopMenuItems(family, opType)\n"
				f"\t\t\t\t\t\tif _manifest_items:\n"
				f"\t\t\t\t\t\t\t_dividers.append(_items[-1])\n"
				f"\t\t\t\t\t\t\tfor _mi in _manifest_items:\n"
				f"\t\t\t\t\t\t\t\t_items.append(_mi.get('label', ''))\n"
				f"\t\t\t\t\t\t\t\tif _mi.get('disabled', False):\n"
				f"\t\t\t\t\t\t\t\t\t_disabled.append(_mi.get('label', ''))\n"
				f"\t\t\t\t\t\t_doc_url = _registry.ext.OpFamRegistryExt.getDocUrl(family, opType)\n"
				f"\t\t\t\t\t\tif not _doc_url:\n"
				f"\t\t\t\t\t\t\t_disabled.append('Documentation')\n"
				f"\t\t\t\tpopMenu.par.Items = str(_items)\n"
				f"\t\t\t\tpopMenu.par.Disableditems = str(_disabled)\n"
				f"\t\t\t\tpopMenu.par.Dividersafteritems = str(_dividers)\n"
				f"\t\t\t\tselectedOp['help',1] = label\n"
				f"\t\t\t\tselectedOp['pythonHelp',1] = opType\n"
				f"\t\t\t\tpanel = panelValue.owner\n"
				f"\t\t\t\tmouseLoc = panel.locateMouse()\n"
				f"\t\t\t\tpopMenu.par.x = min(mouseLoc[0]-5, panel.width-popMenu.width)\n"
				f"\t\t\t\tif mouseLoc[1] - popMenu.height + 5 < 0:\n"
				f"\t\t\t\t\tpopMenu.par.y = mouseLoc[1]\n"
				f"\t\t\t\telse:\n"
				f"\t\t\t\t\tpopMenu.par.y = mouseLoc[1] - popMenu.height + 5\n"
				f"\t\t\t\trun('args[0].par.display = True', popMenu, delayFrames=1, delayRef=op.TDResources)\n"
				f"\t\t\t\treturn\n"
				f"\t\t\telse:\n"
				f"\t\t\t\tpopMenu.par.Items = str(['Help', 'Python Help', 'Operator Snippets', 'Edit Templates...'])\n"
				f"\t\t\t\tpopMenu.par.Dividersafteritems = str([])\n"
				f"\t\t\t# OPFAM_POPMENU_END\n"
			)

			# Insert after: family = detailOp[panelValue+1,'family'].val
			insert_key = "family = detailOp[panelValue+1,'family'].val"
			if insert_key in text:
				idx = text.index(insert_key) + len(insert_key)
				# Find end of that line
				nl = text.index('\n', idx)
				text = text[:nl + 1] + injection + text[nl + 1:]

		pe3.text = text

	def _cleanup_panelexec3(self):
		"""Remove OPFAM markers from panelexec3."""
		nodeTable = self.nodeTable
		if not nodeTable:
			return

		pe3 = nodeTable.op('panelexec3')
		if not pe3:
			return

		text = pe3.text
		import re
		if '# OPFAM_POPMENU_START' in text and '# OPFAM_POPMENU_END' in text:
			pattern = r"\n?\t\t\t# OPFAM_POPMENU_START\n.*?\t\t\t# OPFAM_POPMENU_END\n"
			text = re.sub(pattern, "\n", text, flags=re.DOTALL)
			pe3.text = text

	def _cleanup_popmenu_callbacks(self):
		"""Remove opfam_popMenuCallbacks, restore original Callbackdat, clean panelexec3."""
		nodeTable = self.nodeTable
		if not nodeTable:
			return

		# Restore Callbackdat to original constant value
		popMenu = nodeTable.op('popMenu')
		if popMenu:
			original_cb = nodeTable.op('popMenuCallbacks')
			popMenu.par.Callbackdat.expr = ''
			popMenu.par.Callbackdat.val = original_cb if original_cb else ''

			# Restore original Items
			popMenu.par.Items = str(['Help', 'Python Help', 'Operator Snippets', 'Edit Templates...'])
			popMenu.par.Disableditems = str([])
			popMenu.par.Dividersafteritems = str([])

		# Remove our callback DAT
		cb = nodeTable.op('opfam_popMenuCallbacks')
		if cb:
			cb.destroy()

		# Clean panelexec3
		self._cleanup_panelexec3()

	def _setup_helptext_chain(self):
		"""Wire the helptext merge chain in menu_op so custom family summaries appear."""
		menuOp = self.menu_op
		if not menuOp:
			return

		summaries_null = menuOp.op('summaries')
		if not summaries_null:
			return

		# Ensure summaries tableDAT exists in registry
		if not self.ownerComp.op('summaries'):
			self.ownerComp.create(tableDAT, 'summaries')

		# Rebuild summaries from manifests
		self.owner.rebuildSummaries()

		merge_name = 'merge_opfam_summaries'
		select_src_name = 'select_sumFromParGrabber'
		select_opfam_name = 'select_opfam_help'

		# If chain already exists, just rebuild summaries data
		if menuOp.op(merge_name):
			return

		# Find original input to summaries (the parGrabber null_summaries)
		original_input = summaries_null.inputs[0] if summaries_null.inputs else None
		if not original_input:
			return

		# Create select for original summaries source
		select_src = menuOp.create(selectDAT, select_src_name)
		select_src.par.dat.mode = ParMode.EXPRESSION
		select_src.par.dat.expr = f"op('{original_input.path}')"

		# Create select for opfam summaries
		select_opfam = menuOp.create(selectDAT, select_opfam_name)
		select_opfam.par.dat.mode = ParMode.EXPRESSION
		select_opfam.par.dat.expr = "op.FAMREGISTRY.op('summaries')"

		# Create merge
		merge = menuOp.create(mergeDAT, merge_name)

		# Wire: select_src + select_opfam -> merge -> summaries
		select_src.outputConnectors[0].connect(merge)
		select_opfam.outputConnectors[0].connect(merge)

		# Disconnect original input from summaries, wire merge instead
		original_input.outputConnectors[0].disconnect()
		merge.outputConnectors[0].connect(summaries_null)

		# Position near summaries
		select_src.nodeX = summaries_null.nodeX - 300
		select_src.nodeY = summaries_null.nodeY + 80
		select_opfam.nodeX = summaries_null.nodeX - 300
		select_opfam.nodeY = summaries_null.nodeY - 80
		merge.nodeX = summaries_null.nodeX - 150
		merge.nodeY = summaries_null.nodeY

	def _cleanup_helptext_chain(self):
		"""Remove the helptext merge chain and restore original wiring."""
		menuOp = self.menu_op
		if not menuOp:
			return

		merge = menuOp.op('merge_opfam_summaries')
		select_src = menuOp.op('select_sumFromParGrabber')
		select_opfam = menuOp.op('select_opfam_help')
		summaries_null = menuOp.op('summaries')

		if merge and summaries_null:
			# Find the original source (what select_src points to)
			original_path = None
			if select_src:
				try:
					original_path = select_src.par.dat.eval().path if select_src.par.dat.eval() else None
				except:
					pass

			# Disconnect merge from summaries
			merge.outputConnectors[0].disconnect()

			# Reconnect original source to summaries
			if original_path:
				original_op = op(original_path)
				if original_op:
					original_op.outputConnectors[0].connect(summaries_null)

		# Destroy our ops
		for o in [merge, select_src, select_opfam]:
			if o:
				o.destroy()

		# Clear registry summaries
		reg_summ = self.ownerComp.op('summaries')
		if reg_summ:
			reg_summ.clear()

	def update_compatible_table(self, family_name, family_owner):
		"""Update compatible table with family entries."""
		compatibleTable = self.menu_op.op('compatible')
		if not compatibleTable:
			return

		connection_map = family_owner.connection_map if hasattr(family_owner, 'connection_map') else {}
		compatible_types = family_owner.Properties.get('compatible_types', [])

		# Build row entry
		row_entry = [family_name]
		for index in range(1, compatibleTable.numCols):
			col_type = compatibleTable[0, index].val
			connection_key = (family_name, col_type)
			if connection_key in connection_map:
				row_entry.append(connection_map[connection_key])
			elif col_type in compatible_types:
				row_entry.append('x')
			elif col_type == 'COMP':
				row_entry.append('x')
			else:
				row_entry.append('')

		# Build col entry
		col_entry = [family_name]
		for row in compatibleTable.rows()[1:]:
			row_type = row[0].val
			connection_key = (row_type, family_name)
			if connection_key in connection_map:
				col_entry.append(connection_map[connection_key])
			elif row_type in compatible_types:
				col_entry.append('x')
			else:
				col_entry.append('')

		# Add or update row
		existing_rows = compatibleTable.rows(family_name)
		if existing_rows:
			row_idx = existing_rows[0][0].row
			for col_idx, val in enumerate(row_entry):
				compatibleTable[row_idx, col_idx] = val
		else:
			compatibleTable.appendRow(row_entry)

		# Add or update column
		existing_cols = compatibleTable.cols(family_name)
		if existing_cols:
			col_idx = existing_cols[0][0].col
			for row_idx, val in enumerate(col_entry):
				compatibleTable[row_idx, col_idx] = val
		else:
			compatibleTable.appendCol(col_entry)

		# Set self-compatibility
		try:
			row_cells = compatibleTable.findCells(family_name, cols=[0])
			col_cells = compatibleTable.findCells(family_name, rows=[0])
			if row_cells and col_cells:
				compatibleTable[row_cells[0].row, col_cells[0].col] = 'x'
		except Exception as e:
			debug(f"Error setting self-compatibility: {e}")

	def _set_owner_colors(self, family_owner, old_color=None):
		"""Set color on all family owner children."""
		color = family_owner.Properties.get('color', [0.5, 0.5, 0.5])
		color_val = list(color)
		if len(color_val) < 4:
			color_val = color_val + [1.0] * (4 - len(color_val))

		rgb_color = color_val[:3]
		old_rgb = tuple(old_color[:3]) if old_color and len(old_color) >= 3 else None

		try:
			family_owner.color = rgb_color
		except:
			pass

		# Update Opcomp (custom operators container) if it exists
		if hasattr(family_owner.par, 'Opcomp'):
			custom_ops = family_owner.par.Opcomp.eval()
			if custom_ops:
				try:
					custom_ops.color = rgb_color
					# Update children of custom_ops (excluding annotate)
					for comp in custom_ops.findChildren(type=COMP, maxDepth=1):
						if comp.OPType != 'annotateCOMP':
							comp.color = rgb_color
				except:
					pass

		# Find all placed operators via their manifest tags and update color
		family_name = family_owner.Properties.get('family_name')
		for manifest in root.findChildren(type=COMP, tags=[f'<FAM:{family_name}>', '<MANIFEST>'], allTags=True):
			parent_op = manifest.parent()
			if parent_op:
				op_color = None
				_opinfo_dat = manifest.op('OpInfo')
				if _opinfo_dat:
					try:
						import json
						_oi = json.loads(_opinfo_dat.text)
						op_color = _oi.get('op_color')
					except:
						pass
				expected = tuple(op_color[:3]) if op_color and len(op_color) >= 3 else tuple(rgb_color)
				current = tuple(parent_op.color[:3])
				is_default = all(abs(c - 0.545) < 0.002 for c in current)
				is_family = all(abs(current[i] - rgb_color[i]) < 0.002 for i in range(3))
				is_expected = all(abs(current[i] - expected[i]) < 0.002 for i in range(3))
				is_old = old_rgb is not None and all(abs(current[i] - old_rgb[i]) < 0.002 for i in range(3))
				debug(f"[_set_owner_colors] op={parent_op.path} op_color={op_color} expected={expected} current={current} is_default={is_default} is_family={is_family} is_expected={is_expected} is_old={is_old} old_rgb={old_rgb}")
				if not is_default and not is_family and not is_expected and not is_old:
					debug(f"[_set_owner_colors] SKIPPED op={parent_op.path} — custom color detected")
					continue
				debug(f"[_set_owner_colors] APPLYING color {expected} to {parent_op.path}")
				parent_op.color = expected


	def update_family_name(self, old_name, new_name):
		"""
		Update family name in UI elements.
		Rebuilds global scripts and renames per-family elements.
		"""
		try:
			menuOp = self.menu_op
			nodeTable = self.nodeTable

			# 1. Rename per-family elements
			# (Inject script is now global, no renaming needed)
			# (Panel execute is now global, no renaming needed)

			# 2. Update compatible table
			compatibleTable = menuOp.op('compatible')
			if compatibleTable:
				# Update row header
				for i in range(compatibleTable.numRows):
					if compatibleTable[i, 0].val == old_name:
						compatibleTable[i, 0] = new_name
						break
				# Update column header
				for i in range(compatibleTable.numCols):
					if compatibleTable[0, i].val == old_name:
						compatibleTable[0, i] = new_name
						break

			# 3. Global Refresh (rebuilds scripts with new name)
			self.update_family_evals()
			self._update_colors_table()
			self._setup_last_node_type()
			self._modify_create_node()
			self._modify_search_exec()

		except Exception as e:
			debug(f'Error updating UI for family name change: {e}')

	def update_family_color(self, family_name, new_color, old_color=None):
		"""
		Update family color in UI elements.
		Updates the colors table and family owner children.
		"""
		try:
			family_owner = self.owner.RegisteredFams.get(family_name)
			debug(f'Updating UI color for family {family_name} to {new_color} (old={old_color})')
			# 1. Update colors table (global rebuild is easiest to keep in sync)
			self._update_colors_table()

			# 2. Update owner colors
			if family_owner:
				self._set_owner_colors(family_owner, old_color=old_color)
				
		except Exception as e:
			debug(f'Error updating UI color for family {family_name}: {e}')

# region famui_manager

	def get_or_create_famui_manager(self, force=False):
		"""Get or create the central OpFamUI manager."""
		# Check if already installed at global location
		ui_manager_path = '/ui/dialogs/mainmenu/OpFamUI'
		ui_manager = op(ui_manager_path)
		
		internal = self.ownerComp.op('internal_pars')
		if internal:
			force = force or internal.par.Force.eval() # callers force takes precedence
			local_dev = internal.par.Dev.eval()
		else:
			local_dev = False

		if (force or local_dev) and ui_manager:
			ui_manager.destroy()
			ui_manager = None

		if not ui_manager:
			# Copy from our template
			template = self.ownerComp.op('OpFamUI')
			
			if local_dev:
				template = self.ownerComp.op('OpFamUI/OpFamUI')

			if template:
				mainmenu = op('/ui/dialogs/mainmenu')
				if mainmenu:
					ui_manager = mainmenu.copy(template, name='OpFamUI')
					ui_manager.allowCooking = True

					# Wire up to emptypanel in mainmenu
					emptypanel = mainmenu.op('emptypanel')
					if emptypanel and ui_manager.inputCOMPConnectors:
						ui_manager.inputCOMPConnectors[0].connect(emptypanel)

					if local_dev:
						ui_manager.par.enable = True
						ui_manager.par.display = True
						ui_manager.par.selectpanel = self.ownerComp.op('OpFamUI')

		return ui_manager if not local_dev else self.ownerComp.op('OpFamUI')

# endregion