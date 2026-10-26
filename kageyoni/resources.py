"""Locate the same canonical SQL scripts in a source tree or installed wheel."""
from pathlib import Path


def schema_path(name):
    if not isinstance(name, str) or Path(name).name != name or not name.endswith('.sql'):
        raise ValueError('SQL resource name required')
    package = Path(__file__).resolve().parent
    for candidate in (
        package / 'database' / 'migrations' / name,
        package / 'database' / name,
        package / 'data' / name,
        package.parent / name,
    ):
        if candidate.is_file():
            return candidate
    return package.parent / name


def fixture_path(name: str) -> Path:
    """Locate authentic historical test fixtures in fixtures/historical or fallback to build/."""
    package = Path(__file__).resolve().parent
    root = package.parent
    target = root / "fixtures" / "historical" / name
    if target.is_file():
        return target
    build_target = root / "build" / name
    if build_target.is_file():
        return build_target
    raise FileNotFoundError(f"Authentic historical fixture '{name}' not found in {target} or {build_target}")


def campaign_db_path() -> Path:
    """Locate or on-demand seed the canonical baseline campaign database."""
    package = Path(__file__).resolve().parent
    root = package.parent
    target = root / "build" / "kageyoni.sqlite"
    if target.is_file():
        return target
    target.parent.mkdir(parents=True, exist_ok=True)
    from .engine import Engine
    from .seed import _seed
    from .persistence.migrations import install_all
    e = Engine(target)
    _seed(e, root / "sources")
    install_all(e)
    e.close()
    return target

