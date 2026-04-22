"""
ChainedCallbacksExt - Extends TDCallbacksExt to call BOTH assigned and DAT callbacks.

Uses lazy module loading: DAT changes only mark the cache dirty.
The module is only re-imported when a callback actually fires.
This prevents extension reinit cycles from getattr(dat.module, ...) on every DAT edit.
"""

CallbacksExt = op.TDModules.op('TDCallbacksExt').module.CallbacksExt


class ChainedCallbacksExt(CallbacksExt):
    """
    Extends CallbacksExt to call BOTH assigned callbacks and DAT callbacks.

    Standard CallbacksExt only calls one or the other.
    This version chains them: assigned runs first, DAT gets final say.

    DAT module access is cached and only refreshed when the DAT content changes,
    avoiding expensive getattr(dat.module, ...) calls that trigger TD recooks.
    """

    def __init__(self, ownerComp):
        # Bypass CallbacksExt.__init__ which accesses dat.module and creates
        # a cook dependency (DAT change -> reinit extension -> infinite loop).
        # We replicate the safe parts only.
        self.ownerComp = ownerComp
        self.AssignedCallbacks = {}
        self.PassTarget = None
        self._printCallbacks = False
        self.shortRepr = CallbacksExt.__init__.__globals__.get('shortRepr')
        if hasattr(ownerComp.par, 'Callbackdat'):
            self.callbackDat = ownerComp.par.Callbackdat.eval()
        else:
            self.callbackDat = None
        self._cbCache = {}
        self._cbCacheDatId = None
        self._cbCacheDatText = None

    def _refreshCallbackCache(self):
        """Reload the callback module cache if the DAT has changed."""
        dat = self.callbackDat
        if not dat:
            if self._cbCache:
                self._cbCache = {}
                self._cbCacheDatId = None
                self._cbCacheDatText = None
            return

        dat_id = dat.id
        dat_text = dat.text
        if dat_id == self._cbCacheDatId and dat_text == self._cbCacheDatText:
            return

        self._cbCacheDatId = dat_id
        self._cbCacheDatText = dat_text
        try:
            m = dat.module
            self._cbCache = {
                name: getattr(m, name)
                for name in dir(m)
                if callable(getattr(m, name, None)) and name.startswith('on')
            }
        except Exception as e:
            print(f"Error loading callback module from {dat}: {e}")
            self._cbCache = {}

    def InvalidateCallbackCache(self):
        """Force cache refresh on next DoCallback. Call from DAT change scripts if needed."""
        self._cbCacheDatText = None

    def CreateCallbackDat(self, owner, template):
        """
        Create a callbacks DAT from template if not already set.

        Args:
            owner: The component to dock the callbacks to
            template: The template DAT to copy

        Returns:
            The created callbacks DAT, or None if already exists
        """
        if not template:
            return None

        # Copy to sibling level
        parent_comp = owner.parent()
        callbacks_name = f'{owner.name}_callbacks'
        callbacks_dat = parent_comp.copy(template, name=callbacks_name)

        # Position underneath owner
        callbacks_dat.nodeX = owner.nodeX
        callbacks_dat.nodeY = owner.nodeY - 150

        # Dock to owner
        callbacks_dat.dock = owner

        self.InvalidateCallbackCache()
        return callbacks_dat

    def DoCallback(self, callbackName, callbackInfo=None):
        """
        Execute a chained callback - calls BOTH assigned callback and DAT callback.

        Args:
            callbackName: Name of the callback/hook
            callbackInfo: Dict with callback data

        Returns:
            callbackInfo dict with 'returnValue' key, or None if no callbacks found
        """
        if callbackInfo is None:
            callbackInfo = {}
        callbackInfo.setdefault('ownerComp', self.ownerComp)
        callbackInfo['callbackName'] = callbackName

        found_callback = False

        # 1. Assigned callback (extension's method) - runs first
        assigned = self.AssignedCallbacks.get(callbackName)
        if assigned:
            try:
                result = assigned(callbackInfo)
                callbackInfo['returnValue'] = result
                found_callback = True
            except Exception as e:
                print(f"Error in assigned callback {callbackName}: {e}")

        # 2. DAT callback (user layer) - lazy cached lookup
        self._refreshCallbackCache()
        datCallback = self._cbCache.get(callbackName)
        if datCallback:
            try:
                result = datCallback(callbackInfo)
                callbackInfo['returnValue'] = result
                found_callback = True
            except Exception as e:
                print(f"Error in DAT callback {callbackName}: {e}")

        # Print if enabled
        if self.PrintCallbacks:
            status = 'FOUND' if found_callback else 'NOT FOUND'
            debug(f"[{status}] {callbackName}:", callbackInfo)

        return callbackInfo if found_callback else None
