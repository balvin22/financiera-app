# src/core/thread_utils.py
import threading

def run_async(target, on_done=None, on_error=None):
    def wrapper():
        try:
            result = target()
            if on_done:
                on_done(result)
        except Exception as e:
            import traceback
            traceback.print_exc()
            if on_error:
                on_error(e)
    threading.Thread(target=wrapper, daemon=True).start()
