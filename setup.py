from setuptools import setup, find_packages

setup(
    name="voicemydocs",
    version="0.1.0",
    packages=find_packages(),
    install_requires=[
        "dash~=3.0",
        "dash-bootstrap-components",
        "pypdf2~=3.0.1",
        "python-dotenv",
        "openai>=1.0",  # tested with 1.74.0
    ],
    extras_require={
        "dev": [
            "pre-commit",
            "ruff~=0.6.9",
        ],
    },
    entry_points={
        "console_scripts": [
            "voicemydocs=voicemydocs.main:main",
        ],
    },
)
