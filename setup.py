"""Bundle public runtime assets without duplicating them in the source tree."""
from pathlib import Path
import shutil

from setuptools import setup
from setuptools.command.build_py import build_py
from wheel.bdist_wheel import bdist_wheel


ROOT = Path(__file__).resolve().parent
RESOURCE_DIRS = ("benchmarks", "configs", "schemas", "vendor", "licenses")
RESOURCE_FILES = ("benchmark_manifest.json", "THIRD_PARTY_NOTICES.md")


class BuildWithResources(build_py):
    def run(self):
        super().run()
        target = Path(self.build_lib) / "ahat_benchmark" / "resources"
        # This is generated build output; remove stale resources from old builds.
        if target.exists():
            shutil.rmtree(target)
        target.mkdir(parents=True)
        for name in RESOURCE_DIRS:
            shutil.copytree(ROOT / name, target / name)
        for name in RESOURCE_FILES:
            shutil.copy2(ROOT / name, target / name)


class LinuxValWheel(bdist_wheel):
    def finalize_options(self):
        super().finalize_options()
        self.root_is_pure = False

    def get_tag(self):
        # VAL is a bundled Linux x86-64 executable/shared library, not a Python
        # extension. Do not advertise a universal wheel or a manylinux ABI.
        return "py3", "none", "linux_x86_64"


setup(cmdclass={"build_py": BuildWithResources, "bdist_wheel": LinuxValWheel})
