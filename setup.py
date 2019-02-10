#!/usr/bin/env python
# -*- coding: utf-8 -*-

import glob
import os
import shutil
import site
import sys

from setuptools import setup, Command
from setuptools.command.install import install

# path related stuff
rel_app_path = "share/applications"
rel_icon_path = "share/icons/hicolor/scalable/apps"
here = os.path.abspath(os.path.dirname(__file__))

# package meta data
NAME = "non"
DESCRIPTION = "Knights Of Ni - a GTK+ manager for your Nikola powered website"
URL = "https://github.com/encarsia/non"
EMAIL = "An.Ke@bahnfreikartoffelbrei.de"
AUTHOR = "Anke K"
LICENSE = "MIT"
URL = "https://github.com/encarsia/non"
VERSION = "0.5"
REQUIRES_PYTHON = ">=3.2"
REQUIRED = [
            "Nikola",
            "PyGObject",
            "PyYAML",
            ]
# put desktop and app icon in the right place
DATAFILES = [
            (rel_app_path, ["data/non.desktop"]),
            (rel_icon_path, ["non/ui/duckyou.svg"]),
            ]
# add non-code ui (glade/icon) files
PACKAGES = ["non"]
PACKAGE_DIR = {"non": "non"}
PACKAGE_DATA = {"non": ["ui/*",
                        "logging.yaml",
                         ]
                }
    
with open(os.path.join(here, "README.md"), encoding="utf-8") as f:
    long_description = "\n" + f.read()

def _find_install_path():
    if "--user" in sys.argv:
        inst = site.getusersitepackages()
        prefix = site.getuserbase()
    else:
        inst = site.getsitepackages()[0]
        prefix = sys.prefix
    return inst, prefix


class CustomInstall(install):
    
    def run(self):      
        install_path, prefix = _find_install_path()
        self.update_desktop_file("data/KnightsOfNi.desktop",
                                 install_path,
                                 os.path.join(prefix, rel_icon_path))
        install.run(self)
        
    def update_desktop_file(self, filename, install_path, icon_path):
        """Set exec/icon path of install dir in .desktop file."""
        with open(filename) as f:
            content = f.readlines()
        content_new = ""
        for line in content:
            if line.startswith("Exec="):
                line = line.replace("/path/to/non", install_path)
            elif line.startswith("Icon="):
                line = line.replace("../non/ui/", "")
            content_new += line
        with open("data/non.desktop", "w") as f:
            f.writelines(content_new) 


class UnInstall(Command):
    """Custom command to remove all files from the install/build/sdist processes.
       This includes
            * files in the extracted repo folder
            * the Python module
            * .desktop files and the application icon
            
       Usage: 1) run 'python setup.py uninstall' without any options for
                    uninstalling system-wide, you may run this command
                    with superuser privilege
              2) run 'python setup.py uninstall --user' to undo
                    installation in local user directory.
    """
    
    description = "remove files from installation and build processes"
    user_options = [("user", "u", "delete local user installation")]

    def initialize_options(self):
        """Abstract method that is required to be overwritten.
           Define all available options here.
        """
        self.user = None

    def finalize_options(self):
        """Abstract method that is required to be overwritten."""

    def run(self):
        install_path, prefix = _find_install_path()
        
        print("Removing setuptools files...")
        dir_list = ["build",
                    "dist",
                    "non.egg-info",
                    ]
        for d in dir_list:
            try:
                shutil.rmtree(d)
                print("Removed '{}' folder...".format(d))
            except OSError as e:
                print(self._oserr_message(e, d))
        
        print("Removing Python package...") # and also the Egg dir
        for match in glob.glob(os.path.join(install_path, "non*")):
            try:
                shutil.rmtree(match)
            except OSError as e:
                print(self._oserr_message(e, match))

        print("Removing desktop files...")
        desktop_files = [(prefix, rel_app_path, "non.desktop"),
                         (prefix, rel_icon_path, "duckyou.svg"),
                         ("data", "non.desktop"),
                         ]
        for f in desktop_files:
            filepath = os.path.join(*f)
            try:
                os.remove(filepath)
                print("Removed '{}'...".format(filepath))
            except OSError as e:
                print(self._oserr_message(e, filepath))

    def _oserr_message(self, e, name):
        if e.errno == 2:
            return "Info: '{}' - {}.".format(name, e.strerror)
        else:
            return "Error: '{}' - {}.".format(name, e.strerror)

setup(
    name=NAME,
    version=VERSION,
    description=DESCRIPTION,
    long_description=long_description,
    long_description_content_type="text/markdown",
    author=AUTHOR,
    author_email=EMAIL,
    python_requires=REQUIRES_PYTHON,
    url=URL,
    license=LICENSE,
    packages=PACKAGES,
    package_dir=PACKAGE_DIR,
    package_data=PACKAGE_DATA,
    install_requires=REQUIRED,
    include_package_data=True,
    data_files=DATAFILES,
    cmdclass={"install": CustomInstall,
              "uninstall": UnInstall,
              }
    )

