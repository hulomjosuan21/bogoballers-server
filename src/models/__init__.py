import pkgutil
import importlib
import pathlib

package_dir = pathlib.Path(__file__).resolve().parent
__all__ = []

for _, module_name, is_pkg in pkgutil.iter_modules([str(package_dir)]):
    if not is_pkg and module_name != "__init__":
        module = importlib.import_module(f"{__name__}.{module_name}")
        if hasattr(module, "__all__"):
            globals().update({name: getattr(module, name) for name in module.__all__})
            __all__.extend(module.__all__)
        else:
            public_names = [name for name in dir(module) if not name.startswith("_")]
            globals().update({name: getattr(module, name) for name in public_names})
            __all__.extend(public_names)
