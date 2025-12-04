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

    def CreateCallbackDat(self, owner, template):
        """
        Create a callbacks DAT from template if not already set.

        Args:
            owner: The component to dock the callbacks to
            template: The template DAT to copy

        Returns:
            The created callbacks DAT, or None if already exists
        """
        if self.callbackDat:
            return None

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
