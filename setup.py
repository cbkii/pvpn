# setup.py

from setuptools import setup, find_packages

setup(
    name="pvpn",
    version="0.1.0",
    description="Headless ProtonVPN WireGuard CLI with qBittorrent-nox integration",
    author="Your Name",
    author_email="you@example.com",
    packages=find_packages(),
    install_requires=[
        "requests>=2.28,<3.0"
    ],
    entry_points={
        "console_scripts": [
            "pvpn = pvpn.cli:main",
        ],
    },
    include_package_data=True,
    classifiers=[
        "Programming Language :: Python :: 3",
        "Operating System :: POSIX :: Linux"
    ],
)
