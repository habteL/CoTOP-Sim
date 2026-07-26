from setuptools import setup, find_packages

setup(
    name             = "cotopsim",
    version          = "0.1.0",
    author           = "Dr. Habte Lejebo",
    description      = "CoTOP: Mobility-Aware Collaborative Task Offloading Simulator",
    packages         = find_packages(where="src"),
    package_dir      = {"": "src"},
    python_requires  = ">=3.8",
    install_requires = [
        "torch>=2.0.0",
        "numpy>=1.21",
        "matplotlib>=3.4",
    ]
)