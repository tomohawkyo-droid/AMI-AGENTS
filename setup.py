"""
Setup configuration for ami-agents package.

This package provides shared code quality configurations and tools
for use across AMI projects.
"""

from setuptools import find_packages, setup

# Read the contents of README.md for the long description
try:
    with open("README.md", encoding="utf-8") as fh:
        long_description = fh.read()
except FileNotFoundError:
    long_description = "AMI Agent Orchestration System"

setup(
    name="ami-agents",
    version="1.0.0",
    author="AMI Team",
    author_email="ami@example.com",
    description="AMI Agent Orchestration System with shared code quality infrastructure",
    long_description=long_description,
    long_description_content_type="text/markdown",
    url="https://github.com/ami/ami-agents",
    packages=find_packages(where="ami"),
    package_data={
        "ami": [
            "res/config/*.toml",
            "res/config/*.yaml",
            "res/config/vendor/*.toml",
            "res/config/vendor/*.txt",
        ]
    },
    include_package_data=True,
    classifiers=[
        "Development Status :: 3 - Alpha",
        "Intended Audience :: Developers",
        "License :: OSI Approved :: MIT License",
        "Programming Language :: Python :: 3",
        "Programming Language :: Python :: 3.11",
    ],
    python_requires="==3.11.*",
    install_requires=[
        "setuptools==80.9.0",
        "loguru==0.7.3",
        "pydantic==2.12.5",
        "matrix-nio==0.25.2",
        "python-dotenv==1.2.1",
        "prometheus-client==0.24.1",
        "psutil==7.2.1",
        "pyyaml==6.0.3",
    ],
    extras_require={
        "dev": [
            "pytest==9.0.2",
            "pytest-asyncio==1.3.0",
            "pre-commit==4.5.1",
            "black==25.12.0",
            "ruff==0.14.10",
            "mypy==1.19.1",
            "httpx==0.28.1",
            "types-requests==2.32.4.20250913",
            "types-setuptools==80.9.0.20251223",
            "types-PyYAML==6.0.12.20250915",
            "types-tqdm==4.67.0.20250809",
            "tomli==2.2.1",
            "tomli-w==1.1.0",
        ],
        "lint": [
            "ruff==0.14.10",
            "black==25.12.0",
        ],
        "type-check": [
            "mypy==1.19.1",
            "tomli==2.2.1",
            "tomli-w==1.1.0",
        ],
        "test": [
            "pytest==9.0.2",
            "pytest-asyncio==1.3.0",
            "pytest-cov>=7.0.0",
        ],
        "ci": [
            "pre-commit==4.5.1",
        ],
    },
    entry_points={
        "console_scripts": [
            "ami-generate-pyproject = scripts.generate_pyproject:main",
            "ami-inject-vendor-deps = scripts.inject_vendor_deps:main",
        ],
    },
)
