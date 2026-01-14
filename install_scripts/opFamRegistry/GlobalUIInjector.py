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
		print(f"Installing UI for family: {family_name}")
		try:
			# 1. Per-family (Incremental)
			self._create_inject_script(family_name, family_owner)
			self._deploy_panel_execute(family_name, family_owner)
			self._update_compatible_table(family_name, family_owner)
			self._update_colors_table(family_name, family_owner)
			self._set_owner_colors(family_owner)
			
			# 2. Global (Rebuild/Refresh)
			self._update_family_eval(self.menu_op.op('eval2'))
			self._update_family_eval(self.nodeTable.op('eval4'))
			self._setup_last_node_type()
			self._modify_launch_menu()
			self._modify_create_node()
			self._modify_search_exec()
			
		except Exception as e:
			debug(f'Error installing UI for family {family_name}: {e}')
			import traceback
			debug(traceback.format_exc())

	def uninstall(self, family_name):
		"""Uninstall UI injections for a specific family"""
		print(f"Uninstalling UI for family: {family_name}")
		try:
			menuOp = self.menu_op
			nodeTable = self.nodeTable

			# 1. Per-family cleanup
			
			if nodeTable.op(f'inject_{family_name}_fam'):
				nodeTable.op(f'inject_{family_name}_fam').destroy()
			
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
			self._update_family_eval(self.menu_op.op('eval2'))
			self._update_family_eval(self.nodeTable.op('eval4'))
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


	def _update_family_eval(self, op_to_update):
		"""Update eval expression to include all installed families."""
		if not op_to_update:
			return

		_expr = "[x for x in families.keys()]"
		if self.owner.InstalledFams:
			_expr += " + ["
			for fam_name in self.owner.InstalledFams.keys():
				_expr += f"'{fam_name}', "
			_expr += "]"

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

		# Collect all compatible types and build checks
		fam_checks = []
		all_compatible_types = set()
		for fam_name, fam_owner in self.owner.InstalledFams.items():
			fam_checks.append(f"if ('{fam_name}' in lastnode.tags):\n\t\ttype = '{fam_name}'")
			for t in fam_owner.Properties.get('compatible_types', []):
				all_compatible_types.add(t)

		compatible_check = ' or '.join([f"menu_type=='{t}'" for t in all_compatible_types]) or "False"
		
		# Build per-family mouse pos checks
		mouse_checks = []
		for fam_name in self.owner.InstalledFams.keys():
			mouse_checks.append(f"if('{fam_name}' in child.tags):\n\t\t\t\ttype = '{fam_name}'")

		fam_check_str = "\n\tel".join(fam_checks)
		mouse_check_str = "\n\t\t\tel".join(mouse_checks)

		script = f'''varTable = op('local/set_variables')
lastnode = op(varTable['nodepath',1])
source = varTable['source',1].val
menu_type = varTable['menu_type',1].val
if(lastnode and source == 'output'):
	type = lastnode.family
	{fam_check_str}
	varTable['lasttype',1] = type
elif(source == 'input' and ({compatible_check})):
	pane = ui.panes.current
	zoom = pane.zoom
	currentParent = pane.owner
	mousePos = [varTable['xpos',1],varTable['ypos',1]]
	type = menu_type
	for child in currentParent.findChildren(maxDepth=1):
		if (-5<(mousePos[0]-child.nodeX)*zoom<15 and child.nodeY+child.nodeHeight>mousePos[1] and mousePos[1]>child.nodeY):
			{mouse_check_str}
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

	def _create_inject_script(self, family_name, family_owner):
		"""Create inject script in nodetable."""
		nodeTable = self.nodeTable
		inject_op_name = f'inject_{family_name}_fam'
		families_op = nodeTable.op('families')

		if not families_op or nodeTable.op(inject_op_name):
			return

		families_op.bypass = False
		fam_owner_expr = f"op('{family_owner.path}')"

		original_input = families_op.inputs[0] if families_op.inputs else None
		inject_op = nodeTable.copy(families_op, name=inject_op_name, includeDocked=True)
		inject_op.par.callbacks.expr = f"{fam_owner_expr}.op('fam_script_callbacks')"
		inject_op.nodeX = families_op.nodeX + 150
		inject_op.nodeY = families_op.nodeY

		if original_input:
			original_input.outputConnectors[0].disconnect()
			original_input.outputConnectors[0].connect(inject_op)
			inject_op.outputConnectors[0].connect(families_op)

		families_op.cook(force=True)
		inject_op.cook(force=True)

	def _deploy_panel_execute(self, family_name, family_owner):
		"""Deploy fam_panel_execute to menu_op."""
		panel_execute_path = f'{family_name}_panel_execute'
		if self.menu_op.op(panel_execute_path):
			return

		source = family_owner.op('fam_panel_execute')
		if not source:
			return
 
		panel_execute = self.menu_op.copy(source, name=panel_execute_path)
		panel_execute.nodeX = self.menu_op.op('node_script').nodeX
		panel_execute.nodeY = self.menu_op.op('node_script').nodeY + 100
		panel_execute.par.syncfile = ''

	def _update_compatible_table(self, family_name, family_owner):
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

		# Add row and column
		if not compatibleTable.rows(family_name):
			compatibleTable.appendRow(row_entry)
		if not compatibleTable.cols(family_name):
			compatibleTable.appendCol(col_entry)

		# Set self-compatibility
		try:
			# Find row in first column
			row_cells = compatibleTable.findCells(family_name, cols=[0])
			# Find col in first row
			col_cells = compatibleTable.findCells(family_name, rows=[0])
			
			if row_cells and col_cells:
				row_idx = row_cells[0].row
				col_idx = col_cells[0].col
				compatibleTable[row_idx, col_idx] = 'x'
		except Exception as e:
			debug(f"Error setting self-compatibility: {e}")

	def _set_owner_colors(self, family_owner):
		"""Set color on all family owner children."""
		color = family_owner.Properties.get('color', [0.5, 0.5, 0.5])
		color_val = list(color)
		if len(color_val) < 4:
			color_val = color_val + [1.0] * (4 - len(color_val))

		# Operator .color expects 3 elements (RGB)
		rgb_color = color_val[:3]

		# Operator .color expects 3 elements (RGB)
		rgb_color = color_val[:3]

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


	def update_family_name(self, old_name, new_name):
		"""
		Update family name in UI elements.
		Rebuilds global scripts and renames per-family elements.
		"""
		print(f"Updating UI for family name change: {old_name} -> {new_name}")
		try:
			menuOp = self.menu_op
			nodeTable = self.nodeTable

			# 1. Rename per-family elements
			old_inject = nodeTable.op(f'inject_{old_name}_fam')
			if old_inject:
				old_inject.name = f'inject_{new_name}_fam'

			old_panel = menuOp.op(f'{old_name}_panel_execute')
			if old_panel:
				old_panel.name = f'{new_name}_panel_execute'

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
			self._update_family_eval(self.menu_op.op('eval2'))
			self._update_family_eval(self.nodeTable.op('eval4'))
			self._update_colors_table()
			self._setup_last_node_type()
			self._modify_create_node()
			self._modify_search_exec()

		except Exception as e:
			debug(f'Error updating UI for family name change: {e}')

	def update_family_color(self, family_name, new_color):
		"""
		Update family color in UI elements.
		Updates the colors table and family owner children.
		"""
		print(f"Updating UI color for family: {family_name}")
		try:
			# 1. Update colors table (global rebuild is easiest to keep in sync)
			self._update_colors_table()

			# 2. Update owner colors
			family_owner = self.owner.InstalledFams.get(family_name)
			if family_owner:
				self._set_owner_colors(family_owner)
				
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