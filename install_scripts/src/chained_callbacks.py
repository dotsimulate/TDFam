"""
ChainedCallbacksExt - Extends TDCallbacksExt to call BOTH assigned and DAT callbacks.
"""

CallbacksExt = op.TDModules.op('TDCallbacksExt').module.CallbacksExt


class ChainedCallbacksExt(CallbacksExt):
    """
    Extends CallbacksExt to call BOTH assigned callbacks and DAT callbacks.

    Standard CallbacksExt only calls one or the other.
    This version chains them: assigned runs first, DAT gets final say.
    """

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

        # 2. DAT callback (user layer) - also runs, gets final say
        dat = self.callbackDat
        if dat:
            try:
                datCallback = getattr(dat.module, callbackName, None)
                if datCallback:
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
