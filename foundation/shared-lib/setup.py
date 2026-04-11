from setuptools import setup, find_packages

setup(
    name="starpalace-shared",
    version="0.1.0",
    packages=find_packages(),
    python_requires=">=3.9",
    install_requires=[
        "PyJWT>=2.0",
        "pydantic>=2.0",
    ],
)
