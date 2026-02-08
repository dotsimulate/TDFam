
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

	def registerOpShortcut(self, _famName, _opType, _shortcut, _parName):
		# Update shortcutDict
		_currShortcutDict = self.shortcutDict.getRaw()
		if _shortcut not in _currShortcutDict:
			_currShortcutDict[_shortcut] = {}
		
		# Check if the (fam, type) tuple already exists
		if (_famName, _opType) in _currShortcutDict[_shortcut]:
			return
			
		_currShortcutDict[_shortcut][(_famName, _opType)] = _parName
		self.shortcutDict = DependDict(_currShortcutDict)


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

	def onShortcut(self, shortcutName):
		if shortcutName not in self.shortcutDict:
			return
		for _op in self.currentOps:
			_famName, _opType = self._getFamOpType(_op)
			if _famName and _opType:
				if _parName := self.shortcutDict[shortcutName].get((_famName, _opType), None):
					if (_par := _op.par[_parName]) is not None:
						# toggle parameter if constant or bind
						if _par.mode in [ParMode.CONSTANT, ParMode.BIND]:
							if _par.isPulse:
								_par.pulse()
							else:
								try:
									_par.val = not _par.eval()
								except:
									debug(f'Failed to toggle parameter {_parName} for operator {_op.name}')
									pass

	def _getFamOpType(self, _op):
		# TODO this kind of a method should be in OpManager
		if manifest := _op.op('FamManifest'):
			if opInfo := manifest.op('OpInfo'):
				_opInfo = json.loads(opInfo.text)
				return (_opInfo.get('op_fam', None), _opInfo.get('op_type', None))
		return (None, None)