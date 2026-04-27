
from TDStoreTools import DependDict, DependSet
import json

class ShortcutManager:
	def __init__(self, ownerComp, registry):
		self.ownerComp = ownerComp
		self.registry = registry

		self.shortcutDict = DependDict()
		self.shortcutDat = self.ownerComp.op('keyboardin1')

	@property
	def currentOps(self):
		currPane = ui.panes.current
		if currPane.type == PaneType.NETWORKEDITOR:
			owner : baseCOMP = currPane.owner
			return owner.selectedChildren
		return []

	def enableShortcutDat(self):
		self.shortcutDat.par.active = 1

	def registerOpShortcut(self, _famName, _opType, _shortcut, _action):
		_currShortcutDict = self.shortcutDict.getRaw()
		if _shortcut not in _currShortcutDict:
			_currShortcutDict[_shortcut] = {}

		if (_famName, _opType) in _currShortcutDict[_shortcut]:
			return

		_currShortcutDict[_shortcut][(_famName, _opType)] = _action
		self.shortcutDict = DependDict(_currShortcutDict)
		self._persist()


	def unregisterOpShortcutsForFamily(self, _famName):
		# Cleanup shortcutDict
		_currShortcutDict = self.shortcutDict.getRaw()
		_shortcutsToDelete = []

		for _shortcut, _mappings in _currShortcutDict.items():
			# Find all (fam, type) keys that match the family name
			_keysToRemove = [k for k in _mappings.keys() if k[0] == _famName]
			
			for _key in _keysToRemove:
				del _mappings[_key]
			
			# If the shortcut mapping is now empty, mark the shortcut for deletion
			if not _mappings:
				_shortcutsToDelete.append(_shortcut)

		for _shortcut in _shortcutsToDelete:
			del _currShortcutDict[_shortcut]

		self.shortcutDict = DependDict(_currShortcutDict)
		self._persist()

	def _persist(self):
		"""Store shortcutDict on ownerComp for retention across updates."""
		self.ownerComp.store('ShortcutDict', self.shortcutDict.getRaw())

	def restore(self):
		"""Restore shortcutDict from ownerComp storage."""
		restored = self.ownerComp.fetch('ShortcutDict', None)
		if restored:
			self.shortcutDict = DependDict(restored)

	def onShortcut(self, shortcutName):
		if shortcutName not in self.shortcutDict:
			return
		for _op in self.currentOps:
			_famName, _opType = self._getFamOpType(_op)
			if _famName and _opType:
				_action = self.shortcutDict[shortcutName].get((_famName, _opType), None)
				if _action is None:
					continue
				if isinstance(_action, dict):
					self._execCallback(_op, _action, shortcutName, _famName, _opType)
				else:
					self._execParToggle(_op, _action)

	def _execParToggle(self, _op, _parName):
		if (_par := _op.par[_parName]) is not None:
			if _par.mode in [ParMode.CONSTANT, ParMode.BIND]:
				if _par.isPulse:
					_par.pulse()
				else:
					try:
						_par.val = not _par.eval()
					except:
						debug(f'Failed to toggle parameter {_parName} for operator {_op.name}')

	def _execCallback(self, _op, _action, shortcutName, _famName, _opType):
		_callbackName = _action.get('callback')
		if not _callbackName:
			return
		_info = {
			'shortcut': shortcutName, 'op': _op,
			'fam': _famName, 'opType': _opType,
			'about': 'Called when a shortcut with callback is triggered',
		}
		self.registry.CallHook(_famName, '_ShortcutAction', _callbackName, _info)

	def _getFamOpType(self, _op):
		# TODO this kind of a method should be in OpManager
		if manifest := _op.op('FamManifest'):
			if opInfo := manifest.op('OpInfo'):
				_opInfo = json.loads(opInfo.text)
				return (_opInfo.get('op_fam', None), _opInfo.get('op_type', None))
		return (None, None)