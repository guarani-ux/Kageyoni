import sys, pathlib, importlib.util
_root_subagent = pathlib.Path(__file__).resolve().parent.parent.parent / 'tools' / 'subagent.py'
spec = importlib.util.spec_from_file_location('_root_tools_subagent', _root_subagent)
mod = importlib.util.module_from_spec(spec)
spec.loader.exec_module(mod)
globals().update({k: v for k, v in mod.__dict__.items() if not k.startswith('__')})
if __name__ == '__main__':
    sys.exit(mod.main())
