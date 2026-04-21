"""
OpFam Pop Menu Callbacks — deployed to /ui/dialogs/menu_op/nodetable/
Swapped in via expression on popMenu.par.Callbackdat when a custom family is active.
"""

import json
import webbrowser

def _close_opcreate():
	menu_op = op('/ui/dialogs/menu_op')
	if menu_op:
		menu_op.par.winclose.pulse()

def _get_context():
	"""Get the current right-click context from nodetable."""
	registry = getattr(op, 'FAMREGISTRY', None)
	current_family = op('/ui/dialogs/menu_op/current')[0,0].val if op('/ui/dialogs/menu_op/current') else ''
	installer = registry.InstalledFams.get(current_family) if registry else None

	selected_op = op('/ui/dialogs/menu_op/nodetable/selectedOp')
	op_type = selected_op['pythonHelp', 1].val if selected_op else ''
	op_label = selected_op['help', 1].val if selected_op else ''

	return {
		'registry': registry,
		'family': current_family,
		'installer': installer,
		'op_type': op_type,
		'op_label': op_label,
	}

def _get_manifest_popmenu(installer, op_type):
	"""Get pop_menu items from manifest OpInfo for this operator."""
	if not installer:
		return []

	op_comp = installer.par.Opcomp.eval() if hasattr(installer.par, 'Opcomp') else None
	if not op_comp:
		return []

	# Find the operator's manifest
	op_name = op_type.replace(installer.Properties.get('family_name', ''), '')
	for child in op_comp.findChildren(maxDepth=1):
		manifest = child.op('FamManifest')
		if manifest and manifest.op('OpInfo'):
			try:
				opinfo = json.loads(manifest.op('OpInfo').text)
				if opinfo.get('op_type', '') == op_name or child.name == op_name:
					return opinfo.get('pop_menu', [])
			except:
				pass
	return []


def onSelect(info):
	pass

def onRollover(info):
	pass

def onOpen(info):
	"""Set custom items for the current family operator."""
	ctx = _get_context()
	popMenu = op('/ui/dialogs/menu_op/nodetable/popMenu')
	if not popMenu:
		return

	items = []
	disabled = []
	dividers = []

	# -- Built-in items for custom families --

	# Documentation (from manifest doc_url)
	items.append('Documentation')
	doc_url = _get_doc_url(ctx)
	if not doc_url:
		disabled.append('Documentation')

	# -- Manifest-defined custom items --
	manifest_items = _get_manifest_popmenu(ctx.get('installer'), ctx.get('op_type', ''))
	if manifest_items:
		dividers.append(items[-1])
		for entry in manifest_items:
			label = entry.get('label', '')
			if label:
				items.append(label)
				if entry.get('disabled', False):
					disabled.append(label)

	popMenu.par.Items = str(items)
	popMenu.par.Disableditems = str(disabled)
	popMenu.par.Dividersafteritems = str(dividers)

def onClose(info):
	pass

def onMouseDown(info):
	pass

def onMouseUp(info):
	pass

def onClick(info):
	"""Handle click on a custom family pop menu item."""
	ctx = _get_context()
	item_label = info.get('item', '')

	if item_label == 'Documentation':
		doc_url = _get_doc_url(ctx)
		if doc_url:
			if not doc_url.startswith(('http://', 'https://')):
				doc_url = 'https://' + doc_url
			_close_opcreate()
			webbrowser.open(doc_url)
		return

	# Manifest-defined custom items — dispatch via CallHook
	registry = ctx.get('registry')
	family = ctx.get('family')
	if registry and family:
		manifest_items = _get_manifest_popmenu(ctx.get('installer'), ctx.get('op_type', ''))
		for entry in manifest_items:
			if entry.get('label') == item_label:
				callback_name = entry.get('callback', '')
				if callback_name:
					_close_opcreate()
					registry.CallHook(family, callback_name, info)
				return

def onLostFocus(info):
	pass


# -- Helpers --

def _get_doc_url(ctx):
	"""Extract doc_url from manifest for the current operator."""
	installer = ctx.get('installer')
	if not installer:
		return None

	op_type = ctx.get('op_type', '')

	op_comp = installer.par.Opcomp.eval() if hasattr(installer.par, 'Opcomp') else None
	if not op_comp:
		return None

	op_name = op_type.replace(installer.Properties.get('family_name', ''), '')
	for child in op_comp.findChildren(maxDepth=1):
		manifest = child.op('FamManifest')
		if manifest and manifest.op('OpInfo'):
			try:
				opinfo = json.loads(manifest.op('OpInfo').text)
				if opinfo.get('op_type', '') == op_name or child.name == op_name:
					return opinfo.get('doc_url')
			except:
				pass
	return None
