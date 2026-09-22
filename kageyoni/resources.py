"""Locate the same canonical SQL scripts in a source tree or installed wheel."""
from pathlib import Path


def schema_path(name):
    if not isinstance(name, str) or Path(name).name != name or not name.endswith('.sql'):
        raise ValueError('SQL resource name required')
    package = Path(__file__).resolve().parent
    source = package.parent / name
    return source if source.is_file() else package / 'data' / name
