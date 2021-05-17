#!/usr/bin/env python
# -*- coding: utf-8 -*-

# path related stuff
rel_app_path = "share/applications"
rel_icon_path = "share/icons/hicolor/scalable/apps"

# package meta data
__version__ = "0.8"
__license__ = "MIT"

NAME = "non"
DESCRIPTION = "Knights Of Ni - a GTK+ manager for your Nikola powered website"
URL = "https://github.com/encarsia/non"
EMAIL = "An.Ke@bahnfreikartoffelbrei.de"
AUTHOR = "Anke K"
LICENSE = "MIT"
VERSION = "0.8"
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
