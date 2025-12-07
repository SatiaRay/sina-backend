import sys, os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../src')))

from main import app, guard_middleware

def force_patch_guard_auth(new_func):
    # Patch closure cell if present (for direct closure reference)
    closure_cells = guard_middleware.__closure__
    freevars = guard_middleware.__code__.co_freevars
    for i, name in enumerate(freevars):
        if name == 'auth_validate':
            try:
                closure_cells[i].cell_contents = new_func
            except Exception:
                pass
            break
    # Patch main.auth_validate global (for global lookup in the module)
    import main
    main.auth_validate = new_func