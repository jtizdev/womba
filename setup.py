"""
Womba - AI-Powered Test Generation for Jira
"""

from setuptools import setup, find_packages
import os

# Read README for long description
readme_path = os.path.join(os.path.dirname(__file__), "README.md")
with open(readme_path, "r", encoding="utf-8") as fh:
    long_description = fh.read()

# Read requirements
requirements_path = os.path.join(os.path.dirname(__file__), "requirements-minimal.txt")
with open(requirements_path, "r", encoding="utf-8") as fh:
    requirements = [line.strip() for line in fh if line.strip() and not line.startswith("#")]

setup(
    name="womba",
    version="1.3.0",
    author="PlainID",
    author_email="support@plainid.com",
    description="AI-powered test generation from Jira stories to Zephyr Scale",
    long_description=long_description,
    long_description_content_type="text/markdown",
    url="https://github.com/jtizdev/womba",
    project_urls={
        "Bug Reports": "https://github.com/jtizdev/womba/issues",
        "Source": "https://github.com/jtizdev/womba",
        "Documentation": "https://github.com/jtizdev/womba#readme",
    },
    packages=find_packages(exclude=["tests*", "docs*", "examples*"]),
    classifiers=[
        "Development Status :: 4 - Beta",
        "Intended Audience :: Developers",
        "Topic :: Software Development :: Testing",
        "Topic :: Software Development :: Quality Assurance",
        "License :: OSI Approved :: MIT License",
        "Programming Language :: Python :: 3",
        "Programming Language :: Python :: 3.9",
        "Programming Language :: Python :: 3.10",
        "Programming Language :: Python :: 3.11",
        "Programming Language :: Python :: 3.12",
        "Programming Language :: Python :: 3.13",
        "Operating System :: OS Independent",
        "Environment :: Console",
        "Framework :: FastAPI",
    ],
    keywords="jira testing zephyr ai openai test-generation qa automation atlassian",
    python_requires=">=3.9",
    install_requires=requirements,
    extras_require={
        "dev": [
            "pytest>=8.0.0",
            "pytest-asyncio>=0.23.3",
            "pytest-cov>=4.1.0",
            "pytest-mock>=3.12.0",
            "black>=24.0.0",
            "flake8>=7.0.0",
            "mypy>=1.8.0",
        ],
        "api": [
            "fastapi>=0.115.0",
            "uvicorn[standard]>=0.32.0",
        ],
    },
    entry_points={
        "console_scripts": [
            "womba=womba_cli:main",
        ],
    },
    include_package_data=True,
    package_data={
        "src": ["*.txt", "*.md", "*.json"],
        "src.web": ["*.json", "*.html"],
    },
    zip_safe=False,
)

