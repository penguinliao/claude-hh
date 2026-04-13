from setuptools import setup, find_packages

setup(
    name="harness",
    version="0.1.0",
    packages=find_packages(include=["harness*"]),
    install_requires=[
        "ruff",
        "bandit",
        "mypy",
    ],
    extras_require={
        "full": [
            "detect-secrets",
            "radon",
        ],
    },
    python_requires=">=3.9",
)
