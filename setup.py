from setuptools import setup

setup(
        name = "robostat3-core",
        version = "0.1",
        packages = [
            "robostat",
        ],
        install_requires = [
            "sqlalchemy"
        ],
        extras_require = {
            "cli": ["click", "pttt"]
        },
        scripts = [
            "scripts/rsx"
        ]
)
