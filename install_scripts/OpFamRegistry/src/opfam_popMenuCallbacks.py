"""
OpFam Pop Menu Callbacks - deployed to /ui/dialogs/menu_op/nodetable/.
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
	current_family = op('/ui/dialogs/menu_op/current')[0, 0].val if op('/ui/dialogs/menu_op/current') else ''
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


def _registry_ext(ctx):
	registry = ctx.get('registry')
	if not registry or not hasattr(registry, 'ext'):
		return None
	return getattr(registry.ext, 'OpFamRegistryExt', None)


def _get_manifest_popmenu(installer, op_type):
	"""Get per-operator pop_menu items from embedded FamManifest/OpInfo."""
	if not installer:
		return []

	op_comp = installer.par.Opcomp.eval() if hasattr(installer.par, 'Opcomp') else None
	if not op_comp:
		return []

	op_name = op_type.replace(installer.Properties.get('family_name', ''), '')
	for child in op_comp.findChildren(maxDepth=1):
		manifest = child.op('FamManifest')
		if manifest and manifest.op('OpInfo'):
			try:
				opinfo = json.loads(manifest.op('OpInfo').text)
				if opinfo.get('op_type', '') == op_name or child.name == op_name:
					items = opinfo.get('pop_menu', [])
					return items if isinstance(items, list) else []
			except:
				pass
	return []


def _get_family_popmenu(ctx):
	"""Get family-level PopMenu items from family_info."""
	reg_ext = _registry_ext(ctx)
	if not reg_ext:
		return []
	items = reg_ext.getFamilyPopMenuItems(ctx.get('family', ''))
	return items if isinstance(items, list) else []


def _get_doc_url(ctx):
	"""Get operator doc_url, falling back to family_info doc_url."""
	reg_ext = _registry_ext(ctx)
	if not reg_ext:
		return None
	return reg_ext.getDocUrl(ctx.get('family', ''), ctx.get('op_type', ''))


def _get_support_url(ctx):
	"""Get support_url from family_info."""
	reg_ext = _registry_ext(ctx)
	if not reg_ext:
		return None
	return reg_ext.getSupportUrl(ctx.get('family', ''))


def _open_url(url):
	if not url:
		return
	if not url.startswith(('http://', 'https://')):
		url = 'https://' + url
	_close_opcreate()
	webbrowser.open(url)


def _append_entries(items, disabled, entries):
	"""Append menu entry labels and disabled flags."""
	for entry in entries:
		label = entry.get('label', '')
		if label:
			items.append(label)
			if entry.get('disabled', False):
				disabled.append(label)


def _dispatch_menu_callback(ctx, entry, item_label, info, scope):
	callback_name = entry.get('callback', '')
	registry = ctx.get('registry')
	family = ctx.get('family')
	if not callback_name or not registry or not family:
		return

	_close_opcreate()
	action_info = dict(info or {})
	action_info.update({
		'family': family,
		'opType': ctx.get('op_type', ''),
		'opLabel': ctx.get('op_label', ''),
		'item': item_label,
		'menuEntry': entry,
		'scope': scope,
	})
	registry.CallHook(family, '_PopMenuAction', callback_name, action_info)


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

	items = ['Documentation']
	disabled = []
	dividers = []

	if not _get_doc_url(ctx):
		disabled.append('Documentation')

	if _get_support_url(ctx):
		items.append('Support')

	family_items = _get_family_popmenu(ctx)
	if family_items:
		dividers.append(items[-1])
		_append_entries(items, disabled, family_items)

	manifest_items = _get_manifest_popmenu(ctx.get('installer'), ctx.get('op_type', ''))
	if manifest_items:
		dividers.append(items[-1])
		_append_entries(items, disabled, manifest_items)

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
		_open_url(_get_doc_url(ctx))
		return

	if item_label == 'Support':
		_open_url(_get_support_url(ctx))
		return

	for entry in _get_family_popmenu(ctx):
		if entry.get('label') == item_label:
			_dispatch_menu_callback(ctx, entry, item_label, info, 'family')
			return

	for entry in _get_manifest_popmenu(ctx.get('installer'), ctx.get('op_type', '')):
		if entry.get('label') == item_label:
			_dispatch_menu_callback(ctx, entry, item_label, info, 'operator')
			return


def onLostFocus(info):
	pass
