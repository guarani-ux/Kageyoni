"""Package canonical root SQL scripts without maintaining duplicate sources."""
from pathlib import Path
from setuptools import setup
from setuptools.command.build_py import build_py


class BuildWithSQL(build_py):
    def run(self):
        super().run()
        target = Path(self.build_lib) / 'kageyoni' / 'data'
        target.mkdir(parents=True, exist_ok=True)
        for source in Path(__file__).resolve().parent.glob('*.sql'):
            self.copy_file(str(source), str(target / source.name))


setup(cmdclass={'build_py': BuildWithSQL})
