#!/usr/bin/env python
# -*- coding: utf-8 -*-

import glob
import os
import shutil
import site
import sys

from setuptools import setup, Command
from setuptools.command.install import install

from non import info

here = os.path.abspath(os.path.dirname(__file__))
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


def _oserr_message(e, name):
    if e.errno == 2:
        return "Info: '{}' - {}.".format(name, e.strerror)
    else:
        return "Error: '{}' - {}.".format(name, e.strerror)


class CustomInstall(install):
    
    def run(self):      
        install_path, prefix = _find_install_path()
        self.update_desktop_file("data/KnightsOfNi.desktop",
                                 install_path,
                                 )
        install.run(self)

    def update_desktop_file(self, filename, install_path):
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
    """Custom command to remove all files from the install/build/sdist
       processes. This includes
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
                print(_oserr_message(e, d))

        print("Removing Python package...")  # and also the Egg dir
        for match in glob.glob(os.path.join(install_path, "non*")):
            try:
                shutil.rmtree(match)
            except OSError as e:
                print(_oserr_message(e, match))

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
                print(_oserr_message(e, filepath))


class CustomClean(Command):
    """Custom command to remove all files from the build/sdist processes.
       The regular 'clean' does not do the job adequately, see
       https://github.com/pypa/setuptools/issues/1347

       Usage: run 'python setup.py clean' without any options
    """

    description = "remove files from the build processes"
    user_options = []

    def initialize_options(self):
        """Abstract method that is required to be overwritten.
           Define all available options here.
        """

    def finalize_options(self):
        """Abstract method that is required to be overwritten."""

    def run(self):
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
                print(_oserr_message(e, d))


setup(
    name=info.NAME,
    version=info.__version__,
    description=info.DESCRIPTION,
    long_description=long_description,
    long_description_content_type="text/markdown",
    author=info.AUTHOR,
    author_email=info.EMAIL,
    python_requires=info.REQUIRES_PYTHON,
    url=info.URL,
    license=info.__license__,
    packages=info.PACKAGES,
    package_dir=info.PACKAGE_DIR,
    package_data=info.PACKAGE_DATA,
    install_requires=info.REQUIRED,
    include_package_data=True,
    data_files=info.DATAFILES,
    cmdclass={"install": CustomInstall,
              "uninstall": UnInstall,
              "clean": CustomClean,
              }
    )
