#!/usr/bin/env python
# -*- coding: utf-8 -*-

__version__ = "0.6"

try:
    import nikola
except (ModuleNotFoundError, ImportError) as e:
    print("You have to install Nikola first.")
    raise

try:
    import gi

    gi.require_version('Gtk', '3.0')
    gi.require_version('Vte', '2.91')
    gi.require_version('WebKit2', '4.0')
    from gi.repository import Gtk, Vte, GObject, GLib, Gio, WebKit2
except (ModuleNotFoundError, ImportError) as e:
    print("Unable to load Python bindings for GObject Introspection.")
    raise

import datetime
import filecmp
import gettext
import importlib
import json
import locale
import logging
import logging.config
import markdown
import os
import setproctitle
import shutil
import subprocess
import sys
import time
import webbrowser
import yaml

_ = gettext.gettext


class Handler:
    """Signal assignment for Glade"""

    # ########## close/destroy  window ############

    def on_window_close(self, widget, *event):
        widget.hide_on_delete()
        return True

    # ########### toolbar ##########################

    def on_newpost_clicked(self, widget):
        app.obj("entry_message").set_text("")
        app.obj("newpost_entry").set_text("")
        app.obj("newpost_dialog").run()

    def on_preview_toggled(self, widget):
        if widget.get_active():
            app.messenger(_("Open preview in standard web browser"))
            self.serve = subprocess.Popen(["nikola", "serve", "-b"])
        else:
            # stop local server when untoggling button
            app.messenger(_("Stop preview"))
            self.serve.kill()

    def on_build_clicked(self, widget):
        app.run_nikola_build()

    def on_deploy_git_clicked(self, widget):
        app.run_nikola_github_deploy()

    def on_deploy_clicked(self, widget):
        app.run_nikola_deploy()

    def on_refresh_clicked(self, widget):
        app.update_sitedata(app.sitedata)
        app.get_window_content()

    def on_save_drafts(self, widget):
        # just to be sure, should already be on src
        app.exec_cmd("git checkout src")
        # git commit && git push origin src
        status = app.exec_cmd("git status")
        status = status.stdout.split("\n\n")
        if status[-1] == "nothing to commit, working tree clean\n":
            app.messenger(_("No changes, no upload."))
        elif status[-1] == "no changes added to commit (use \"git add\" \
and/or \"git commit -a\")\n" \
                or "Changes to be committed" in status[1]:
            app.obj("git_changed_files").set_label(status[-2])
            app.obj("git_push_changes_dialog").run()
        else:
            app.messenger(_("Unknown status: {}").format(status), "warning")

    def on_get_drafts(self, widget):
        # just to be sure, should already be on src
        app.exec_cmd("git checkout src")
        status = app.exec_cmd("git status")
        status = status.stdout.split("\n\n")
        if status[-1] == "nothing to commit, working tree clean\n":
            app.exec_cmd("git pull origin src")
            app.messenger(_("No local changes, pulled changes \
from origin/src."))
            self.on_refresh_clicked(None)
        elif status[-1] == "no changes added to commit (use \"git add\" \
and/or \"git commit -a\")\n":
            app.obj("git_unstashed_files").set_label(status[-2])
            app.obj("git_get_changes_dialog").run()
        else:
            app.messenger(_("Unknown status: {}").format(status), "warning")
        # git show --stat
        # git diff-tree --oneline --no-commit-id --name-only -r origin/src
        # git remote update
        # git diff src:posts/file.rst origin/src:posts/file.rst
        # src is the source branch, get name from conf.py
        # returns a list of filenames
        # show window with titles of changed files, cancel and proceed
        # buttons to handle

    # ########### vte terminal ########################

    def on_term_contents_changed(self, widget):
        last_line = widget.get_text()[0].rstrip().split("\n")[-1]
        if app.prompt == "":
            app.prompt = last_line
        if last_line == "INFO: github_deploy: Successful deployment":
            app.messenger(_("Deploying to GitHub/GitLab successful."))
        # gui_cmd is bool var for command being run via toolbar button
        # if command is invoked by button the app focus returns back to graphic
        # interface stack child 'gui'
        if app.gui_cmd is True and last_line == app.prompt:
            time.sleep(2)
            app.obj("stack").set_visible_child(app.obj("gui"))
            app.update_sitedata(app.sitedata)
            app.get_window_content()
            app.gui_cmd = False

    def on_term_child_exited(self, widget, *args):
        # on exit the console is restarted because it doesn't run in a separate
        # window anymore but as a (persistent) GTK stack child
        widget.reset(True, True)
        app.start_console(None)

    # ########## headerbar #########################

    def on_info_button_clicked(self, widget):
        app.messenger(_("Open About dialog"))
        app.obj("about_dialog").run()

    # ########## link menu #########################

    def on_ref_handbook_activate(self, widget):
        app.messenger(_("Open Nikola handbook in web browser"))
        webbrowser.open("https://getnikola.com/handbook.html")

    def on_ref_rest_markup_activate(self, widget):
        app.messenger(_("Open reST syntax reference in web browser"))
        webbrowser.open("http://docutils.sourceforge.net/docs/ref/rst/\
restructuredtext.html")

    def on_ref_rest_dir_activate(self, widget):
        app.messenger(_("Open reST directives in web browser"))
        webbrowser.open("http://docutils.sourceforge.net/docs/ref/rst/\
directives.html")

    def on_ref_md_activate(self, widget):
        app.messenger(_("Open Markdown syntax reference in web browser"))
        webbrowser.open("https://www.markdownguide.org/basic-syntax")

    # ########### menu #############################

    def on_open_conf_activate(self, widget):
        app.messenger(_("Open conf.py in external editor"))
        subprocess.run(['xdg-open', os.path.join(app.wdir, "conf.py")])

    def on_load_conf_activate(self, widget):
        app.messenger(_("Choose configuration file to read"))
        app.obj("choose_conf_file").run()

    def on_add_bookmark_activate(self, widget):
        # add title and location to bookmark dict
        bookmark = {app.siteconf.BLOG_TITLE: app.wdir}
        app.bookmarks.update(bookmark)
        app.messenger(_("New bookmark added for {}.").format(
            app.siteconf.BLOG_TITLE))
        app.check_nonconf()

    def on_gen_sum_activate(self, widget):
        app.messenger(_("Generate page for summary tab"))
        app.generate_summary()
        # change to tab when finished
        app.obj("notebook").set_current_page(-1)

    # ############## filechooser dialog ############

    def on_choose_conf_file_file_activated(self, widget):
        self.on_choose_conf_file_response(widget, -5)

    def on_choose_conf_file_response(self, widget, response):
        if response == -5:
            try:
                app.dump_sitedata_file()
                app.non_config["wdir"] = os.path.split(
                                                    widget.get_filename())[0]
                app.check_nonconf()
            except AttributeError:
                app.messenger(_("Working Nikola configuration required"),
                              "warning")
                app.obj("config_info").run()
        else:
            app.messenger(_("Working Nikola configuration required"),
                          "warning")
            app.obj("config_info").run()
        self.on_window_close(widget)

    # ############## new post dialog ############

    def on_newpost_dialog_response(self, widget, response):
        if response == -5:
            if app.obj("newpost_entry").get_text() == "":
                app.messenger(_("Create new post"))
                app.obj("entry_message").set_text(
                                                _("Title must not be empty."))
                app.obj("newpost_entry").grab_focus()
            else:
                self.on_window_close(widget)
                if app.obj("create_page").get_active():
                    new_site_obj = "new_page"
                else:
                    new_site_obj = "new_post"
                if app.obj("create_md").get_active():
                    format = "--format=markdown"
                else:
                    format = "--format=rest"

                # return string maybe of use later so I leave it that way
                status = app.exec_cmd("nikola {} --title={} {}".format(
                                        new_site_obj,
                                        app.obj("newpost_entry").get_text(),
                                        format,
                                       ))

                app.messenger(_("New post created: {}").format(
                                        app.obj("newpost_entry")).get_text())
                app.update_sitedata(app.sitedata)
                app.get_window_content()
        else:
            self.on_window_close(widget)

    def on_newpost_entry_activate(self, widget):
        self.on_newpost_dialog_response(app.obj("newpost_dialog"), 0)

    # ############## upload drafts to GitHub dialog ############

    def on_git_push_changes_dialog_response(self, widget, response):
        if response == -5:
            app.exec_cmd("git add .")
            app.exec_cmd("git commit -m \"NoN auto commit.\"")
            app.term_cmd("git push origin src")
            app.messenger(_("Pushed changes to origin/src"))
        else:
            app.messenger(_("Uploading drafts canceled."))
        self.on_window_close(widget)

    # ############## download drafts from GitHub dialog ############

    def on_git_get_changes_dialog_response(self, widget, response):
        if response == -3:
            app.exec_cmd("git stash")
            app.exec_cmd("git pull origin src")
            app.exec_cmd("git stash pop")
            app.messenger(_("Execute git stash & git pull origin src & git \
                            stash pop"))
        elif response == -2:
            self.on_window_close(widget)
            app.exec_cmd("git checkout -- .")
            app.exec_cmd("git pull origin src")
            # discard = app.exec_cmd("git checkout -- .")
            # pull_status = app.exec_cmd("git pull")
            # app.obj("git_conflict_message").set_text(pull_status.stdout)
            # app.obj("git_conflict_message_err").set_text(pull_status.stderr)
            # app.obj("git_conflict_dialog").run()
            app.messenger(_("Pulled files from origin/src."))
        else:
            self.on_window_close(widget)
            app.messenger(_("Downloading drafts canceled."))
        self.on_refresh_clicked(None)

    # ############### treeview rows activated ###############

    # open files on doubleclick

    def on_view_posts_row_activated(self, widget, *args):
        app.messenger(_("Open post file"))
        row, pos = app.obj("selection_post").get_selected()
        subprocess.run(['xdg-open',
                        os.path.join(app.wdir, row[pos][7], row[pos][2])]
                       )

    def on_view_pages_row_activated(self, widget, *args):
        app.messenger(_("Open page file"))
        row, pos = app.obj("selection_page").get_selected()
        subprocess.run(['xdg-open',
                        os.path.join(app.wdir, row[pos][7], row[pos][2])]
                       )

    def on_view_tags_row_activated(self, widget, pos, *args):
        if pos.get_depth() == 1:
            widget.expand_to_path(pos)
        else:
            row, pos = app.obj("selection_tags").get_selected()
            subprocess.run(['xdg-open',
                            os.path.join(app.wdir, row[pos][6], row[pos][5])]
                           )

    def on_view_cats_row_activated(self, widget, pos, *args):
        if pos.get_depth() == 1:
            widget.expand_to_path(pos)
        else:
            row, pos = app.obj("selection_cats").get_selected()
            subprocess.run(['xdg-open',
                            os.path.join(app.wdir, row[pos][6], row[pos][5])]
                           )

    def on_view_listings_row_activated(self, widget, *args):
        row, pos = app.obj("selection_listings").get_selected()
        subprocess.run(['xdg-open',
                        os.path.join(app.wdir, "listings", row[pos][0])]
                       )

    def on_view_images_row_activated(self, widget, *args):
        row, pos = app.obj("selection_images").get_selected()
        subprocess.run(['xdg-open',
                        os.path.join(app.wdir, "images", row[pos][0])]
                       )

    def on_view_files_row_activated(self, widget, *args):
        row, pos = app.obj("selection_files").get_selected()
        subprocess.run(['xdg-open',
                        os.path.join(app.wdir, "files", row[pos][0])]
                       )

    def on_view_translations_row_activated(self, widget, *args):
        app.messenger(_("Open file..."))
        row, pos = app.obj("selection_translations").get_selected()
        subprocess.run(['xdg-open',
                        os.path.join(app.wdir, row[pos][6], row[pos][2])]
                       )

    # open context menu for translation options

    def on_view_translations_button_release_event(self, widget, event):
        popup = Gtk.Menu()
        for l in app.translation_lang:
            item = Gtk.MenuItem.new_with_label(
                                    _("Create translation for {}".format(l)))
            # selected row already caught by on_treeview_selection_changed func
            item.connect("activate", self.on_create_translation, l)
            popup.append(item)
        popup.show_all()
        # only show on right click
        if event.button == 3:
            popup.popup(None, None, None, None, event.button, event.time)
            return True

    def on_create_translation(self, widget, lang):
        row, pos = app.obj("selection_translations").get_selected()
        subdir = row[pos][6]
        file = row[pos][2]
        file_base = file.split(".")[0]
        file_ext = file.split(".")[-1]
        trans_file = "{}.{}.{}".format(file_base, lang, file_ext)
        if os.path.isfile(os.path.join(subdir, trans_file)):
            app.messenger(_("Translation file already exists."), "warning")
        else:
            shutil.copy(
                os.path.join(subdir, file),
                os.path.join(subdir, trans_file))
            app.messenger(_("Create translation file for {}").format(
                                                                row[pos][0]))
            app.update_sitedata(app.sitedata)
            app.get_window_content()

    # open context menu on right click to open post/page in browser

    def on_view_posts_button_release_event(self, widget, event):
        self.on_pp_table_click(widget, event, "posts")

    def on_view_pages_button_release_event(self, widget, event):
        self.on_pp_table_click(widget, event, "pages")

    def on_pp_table_click(self, widget, event, sub):
        row, pos = app.obj("selection_post").get_selected()
        title = row[pos][0]
        slug = row[pos][1]
        filename = row[pos][2]
        meta = row[pos][10]
        # show info in statusbar on left click
        if event.button == 1:
            if meta is not "":
                has_meta = "yes"
            else:
                has_meta = "no"
            app.messenger(
                _("Input file format: {}. Separate metafile: {}.").format(
                                            filename.split("."))[1], has_meta)
        # only generate popup menu on right click
        elif event.button == 3:
            popup = Gtk.Menu()
            item = Gtk.MenuItem.new_with_label(_("Open in web browser"))
            # selected row already caught by on_treeview_selection_changed
            # function. I don't know what to do with this information but I'm
            # afraid to delete it
            item.connect("activate", self.on_open_pp_web, title, slug, sub)
            popup.append(item)
            if meta is not "":
                item = Gtk.MenuItem.new_with_label(_("Edit meta data file"))
                item.connect("activate", self.on_open_metafile, meta, sub)
                popup.append(item)
            popup.show_all()
            popup.popup(None, None, None, None, event.button, event.time)
            return True
        else:
            app.messenger(_("No function (button event: {})").format(
                                                        event.button), "debug")

    def on_open_pp_web(self, widget, title, slug, sub):
        app.messenger(_("Open '{}' in web browser").format(title))
        webbrowser.open("{}/{}/{}".format(app.siteconf.SITE_URL, sub, slug))

    def on_open_metafile(self, widget, meta, sub):
        app.messenger(_("Edit metafile: {}").format(meta))
        subprocess.run(['xdg-open',
                        os.path.join(app.wdir, sub, meta)]
                       )


class NiApp:

    def __init__(self):

        setproctitle.setproctitle("NoN")
        self.install_dir = os.getcwd()
        self.user_app_dir = os.path.join(os.path.expanduser("~"),
                                         ".non",
                                         )
        self.conf_file = os.path.join(self.user_app_dir, "config.yaml")

        # create hidden app folder in user's home directory if it does
        # not exist
        if not os.path.isdir(self.user_app_dir):
            os.makedirs(self.user_app_dir)

        # initiate GTK+ application
        GLib.set_prgname("Knights of Ni")

        # GSettings
        # self.app = Gtk.Application.new("app.knights-of-ni",

        self.app = Gtk.Application.new(None, Gio.ApplicationFlags(0))
        self.app.connect("startup", self.on_app_startup)
        self.app.connect("activate", self.on_app_activate)
        self.app.connect("shutdown", self.on_app_shutdown)

        # set environment to English to receive unlocalized return strings
        # from Git
        # https://stackoverflow.com/questions/51293480/
        # how-to-call-lc-all-c-sort-from-python-subprocess
        self.myenv = os.environ.copy()
        self.myenv["LC_ALL"] = "C"

    def on_app_shutdown(self, app):
        # write config to config.yaml in case of changes
        yaml.dump(self.non_config, open(self.conf_file, "w"),
                  default_flow_style=False)
        # write site data dict to json file
        self.dump_sitedata_file()
        self.app.quit()
        self.log.info(_("Application terminated on window close button. Bye."))

    def on_app_startup(self, app):
        os.chdir(self.user_app_dir)
        # setting up logging
        self.log = logging.getLogger("non")
        with open(os.path.join(self.install_dir, "logging.yaml")) as f:
            config = yaml.load(f)
            logging.config.dictConfig(config)

        # log version info for debugging
        self.log.debug("Application version: {}".format(__version__))
        self.log.debug("Application executed from {}".format(self.install_dir))
        self.log.debug("GTK+ version: {}.{}.{}".format(Gtk.get_major_version(),
                                                       Gtk.get_minor_version(),
                                                       Gtk.get_micro_version(),
                                                       ))
        self.loglevels = {"critical": 50,
                          "error": 40,
                          "warning": 30,
                          "info": 20,
                          "debug": 10,
                          }

    def on_app_activate(self, app):
        # setting up localization
        locales_dir = os.path.join(self.install_dir, "ui", "locale")
        appname = "NoN"
        locale.bindtextdomain(appname, locales_dir)
        locale.textdomain(locales_dir)
        gettext.bindtextdomain(appname, locales_dir)
        gettext.textdomain(appname)

        # Glade files/window configuration
        gladefile_list = ["non.glade"]

        # set up builder
        builder = Gtk.Builder()
        GObject.type_register(Vte.Terminal)

        builder.set_translation_domain(appname)
        [builder.add_from_file(os.path.join(self.install_dir,
                                            "ui",
                                            f)) for f in gladefile_list]
        builder.connect_signals(Handler())
        self.obj = builder.get_object

        # use WebKit for summary view
        self.webview = WebKit2.WebView()
        self.obj("html_view").add(self.webview)

        # set buttons inactive unless activated otherwise
        self.obj("build").set_sensitive(False)

        # error if created in Glade
        self.add_dialogbuttons(self.obj("choose_conf_file"))
        # self.add_dialogokbutton(self.obj("about_dialog"))

        # add image to menubutton (Glade bug)
        self.obj("ref_menu_button").add(self.obj("help_image"))

        # load config from config.yaml or start with new
        if not os.path.isfile(self.conf_file):
            self.messenger(_("No config available..."))
            self.non_config = {"wdir": None,
                               "bookmarks": dict(),
                               }
            self.messenger(_("Empty config created..."))
        else:
            self.non_config = yaml.load(open(self.conf_file))
            self.messenger(_("Found config to work with..."))

        # main window
        window = self.obj("non_window_stack")
        # application icon doesn't work under Wayland
        # window.set_icon_from_file(os.path.join(self.install_dir,
        #                                       "ui",
        #                                       "duckyou.svg"))
        window.set_application(app)
        window.show_all()

        self.check_nonconf()

    def start_console(self, wdir):
        # spawn_sync is deprecated and spawn_async doesn't exist anymore
        # and I don't understand how to use GLib.spawn_async so I leave
        # this here for now as long as this is only a warning and I
        # don't have a solution
        self.obj("term").spawn_sync(
            Vte.PtyFlags.DEFAULT,
            wdir,
            ["/bin/bash"],
            None,
            GLib.SpawnFlags.DEFAULT,
            None,
            None,
        )
        # prompt is detected on first emission of the 'contents changed' signal
        self.prompt = ""
        # bool variable to decide if focus should return from terminal stack
        # child, True when command is invoked by button, False if command is
        # typed directly in terminal
        self.gui_cmd = False

    def check_nonconf(self):
        self.wdir = self.non_config["wdir"]
        self.bookmarks = self.non_config["bookmarks"]
        # ##### setup bookmarks in menu ######
        # remove generated bookmark menu items, otherwise when
        # appending new bookmark all existing bookmarks are appended
        # repeatedly
        for i in self.obj("menu").get_children():
            # the separator item is stretched vertically when applying
            # get_label function (which does not return any value but
            # no error either) but I don't know how to do a GTK class
            # comparison to exclude the separator or include the
            # menuitems so this works fine
            if isinstance(i, type(self.obj("load_conf"))):
                if i.get_label().startswith(_("Bookmark: ")):
                    self.obj("menu").remove(i)
        # add menu items for bookmarks
        for b in self.bookmarks:
            if self.wdir == self.bookmarks[b]:
                item = Gtk.MenuItem.new_with_label(
                                        _("Bookmark: {} (active)").format(b))
                item.set_sensitive(False)
            else:
                item = Gtk.MenuItem.new_with_label(_("Bookmark: {}").format(b))
            item.connect("activate", self.select_bookmark, self.bookmarks[b])
            self.obj("menu").append(item)

        self.obj("menu").show_all()
        if len(self.bookmarks) > 0:
            self.messenger(_("Found {} bookmark(s)").format(
                len(self.bookmarks)))
        else:
            self.messenger(_("No bookmarks found."))
        # check if last wdir still exists
        try:
            os.chdir(self.wdir)
            self.messenger(_("Current Nikola folder: {}").format(self.wdir))
            # reload terminal with current wdir
            self.obj("term").reset(True, True)
            # by default set to false to prevent adding None entry
            self.obj("add_bookmark").set_sensitive(True)
            # refresh window
        except FileNotFoundError:
            self.messenger(_("The chosen Nikola instance isn't here \
anymore."), "warning")
            self.non_config["wdir"] = None
            self.obj("choose_conf_file").run()
        except TypeError as e:
            self.messenger(_("Path to working directory malformed or None."),
                           "warning")
            self.obj("choose_conf_file").run()
            self.wdir = os.path.expanduser("~")

        self.start_console(self.wdir)
        self.get_site_info()
        self.get_window_content()

    def add_dialogbuttons(self, dialog):
        # don't ask me why but add_action_widget doesn't work anymore
        # this is shorter anyway
        dialog.add_buttons(_("Cancel"), Gtk.ResponseType.CANCEL,
                           _("OK"), Gtk.ResponseType.OK)

    def add_dialogokbutton(self, dialog):
        # add ok button to about dialog to avoid Gtk warning
        button = Gtk.Button.new_with_label(_("OK"))
        dialog.add_action_widget(button, Gtk.ResponseType.OK)

    def select_bookmark(self, widget, path):
        self.dump_sitedata_file()
        self.non_config["wdir"] = path
        self.check_nonconf()

    def load_sitedata(self, f):
        with open(f) as data:
            try:
                sitedata = json.load(data)
            except json.decoder.JSONDecodeError:
                self.messenger(_("Could not read data file."), "error")
                sitedata = self.create_sitedata()
        self.messenger(_("Site data loaded from file."))
        sitedata = self.update_sitedata(sitedata)
        return sitedata

    def create_sitedata(self):
        # read all posts/pages and store in sitedata dict
        sitedata = dict()
        sitedata["posts"], \
            sitedata["post_tags"], \
            sitedata["post_cats"] = self.get_src_content("posts")
        sitedata["pages"], \
            sitedata["page_tags"], \
            sitedata["page_cats"] = self.get_src_content("pages")
        self.messenger(_("Collect data of Nikola site complete."))
        self.dump_sitedata_file()
        return sitedata

    def update_sitedata(self, sitedata):
        self.messenger(_("Update data file for: {}").format(
                                                    self.siteconf.BLOG_TITLE))
        filelist = dict()
        for sub in ["posts", "pages"]:
            filelist[sub] = []
            for f in [x for x in os.listdir(sub) if not (x.startswith(".") or
                                                         x.endswith(".meta"))]:
                if f in sitedata[sub].keys():
                    if not sitedata[sub][f]["last_modified"] == \
                                        os.path.getmtime(os.path.join(sub, f)):
                        filelist[sub].append(f)
                        self.messenger(
                                _("Update article data for: {}").format(f))
                else:
                    filelist[sub].append(f)
                    self.messenger(
                                _("Add new article data for: {}.").format(f))
            # delete dict items of removed source files
            for p in sitedata[sub].copy():
                if p not in os.listdir(sub):
                    self.messenger(_("Delete data for: {}.").format(p))
                    del sitedata[sub][p]

        sitedata["posts"], \
            sitedata["post_tags"], \
            sitedata["post_cats"] = self.get_src_content(
                                                    "posts",
                                                    d=sitedata["posts"],
                                                    update=filelist["posts"],
                                                    )
        sitedata["pages"], \
            sitedata["page_tags"], \
            sitedata["page_cats"] = self.get_src_content(
                                                    "pages",
                                                    sitedata["pages"],
                                                    update=filelist["pages"],
                                                    )
        return sitedata

    def dump_sitedata_file(self):
        try:
            with open(self.datafile, "w") as outfile:
                json.dump(self.sitedata, outfile, indent=4)
            self.messenger(_("Write site data to JSON file."))
        except AttributeError:
            self.messenger(_("Could not write site data to JSON file"), "warn")

    def get_site_info(self):
        # load nikola conf.py as module to gain simple access to variables
        try:
            spec = importlib.util.spec_from_file_location(
                "siteconf", os.path.join(self.wdir, "conf.py"))
            self.siteconf = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(self.siteconf)

            # labels
            self.obj("author").set_text(self.siteconf.BLOG_AUTHOR)
            self.obj("descr").set_text(self.siteconf.BLOG_DESCRIPTION)
            self.obj("title").set_text(self.siteconf.BLOG_TITLE)
            self.obj("pathlocal").set_uri("file://{}".format(self.wdir))
            self.obj("pathlocal").set_label("...{}".format(self.wdir[-25:]))
            self.obj("pathremote").set_uri(self.siteconf.SITE_URL)
            self.obj("pathremote").set_label(self.siteconf.SITE_URL)
            # detect multilingual sites
            self.default_lang = self.siteconf.DEFAULT_LANG
            self.translation_lang = set([key for key in
                                        self.siteconf.TRANSLATIONS
                                        if key != self.default_lang])
            self.obj("lang").set_text(self.default_lang)
            self.obj("trans_lang").set_text(", ".join(str(s) for s in
                                                      self.translation_lang
                                                      if s != self.default_lang
                                                      ))
            # activate toolbar item if deploy commands for default preset
            # exists
            try:
                self.deploy_cmd = self.siteconf.DEPLOY_COMMANDS["default"]
                self.obj("deploy").set_sensitive(True)
            except AttributeError:
                self.messenger(_("No deploy commands set, edit conf.py or use \
'github_deploy'"))
            # check for output folder, variable not set for GitHub deploy
            try:
                self.output_folder = self.siteconf.OUTPUT_FOLDER
                self.messenger(_("Output folder: '{}'").format(
                                                        self.output_folder))
            except AttributeError:
                self.output_folder = "output"
                self.messenger(_("Output folder is set to default 'output'"))
            # sync drafts with GitHub, activate only if setup in conf.py
            try:
                self.gh_src = self.siteconf.GITHUB_SOURCE_BRANCH
                self.gh_depl = self.siteconf.GITHUB_DEPLOY_BRANCH
                self.gh_rem = self.siteconf.GITHUB_REMOTE_NAME
                self.obj("get_drafts").set_sensitive(True)
                self.obj("save_drafts").set_sensitive(True)
                self.messenger(_("Up-/download drafts to/from GitHub is \
enabled."))
            except AttributeError:
                self.obj("save_drafts").set_sensitive(False)
                self.obj("get_drafts").set_sensitive(False)
                self.messenger(_("This site is not configured to use GitHub, \
up-/downloading drafts is deactivated."))

            # check if folder for files, listings and images exist to avoid
            # FileNotFoundError, this also has to be done only on startup
            for subdir in ["files", "listings", "images"]:
                if not os.path.isdir(os.path.join(self.wdir, subdir)):
                    self.messenger(_("{} doesn't exist...create...").format(
                                                                    subdir))
                    os.mkdir(os.path.join(self.wdir, subdir))

            # set 'add bookmark' menu item inactive if bookmark already
            # exists for wdir
            if self.siteconf.BLOG_TITLE in self.bookmarks:
                self.obj("add_bookmark").set_sensitive(False)

            # set checkbutton in new page dialog active
            if "markdown" in app.siteconf.COMPILERS:
                app.obj("create_md").set_sensitive(True)

            # don't show translation tab if site is not multilingual
            if self.translation_lang == set():
                self.obj("tab_transl").hide()
            else:
                self.obj("tab_transl").show()

            # look for JSON data file with sitedata
            # cut home dir in name and leading slash
            filename = self.wdir.split(os.path.expanduser("~"))[-1][1:]
            # replace slash by underscore
            filename = filename.replace("/", "_")

            # load or create json data for Nikola site
            self.datafile = os.path.join(self.user_app_dir, filename + ".json")
            if os.path.isfile(self.datafile):
                self.sitedata = self.load_sitedata(self.datafile)
            else:
                self.sitedata = self.create_sitedata()

            # load or create summary page for notebook tab
            self.summaryfile = os.path.join(self.user_app_dir,
                                            filename + ".html")
            if os.path.isfile(self.summaryfile):
                self.messenger(_("Found summary page."))
                self.webview.load_uri("file://" + self.summaryfile)
            else:
                self.messenger(_("No summary file to load, let's generate \
one!"))
                self.generate_summary()

        except FileNotFoundError:
            # if no conf.py is given on startup the working directory is set to
            # user's home and no conf.py will be found, if so ignore the error
            # and show an empty main application window instead of being caught
            # in a neverending loop of filechooser dialog
            # pass
            self.messenger(_("Going on without conf.py"), "error")

    def get_window_content(self):

        """Fill main window with content."""

        try:
            # posts/pages are dictionaries
            # tags/categories are sets to avoid duplicates but can only be
            # stored as list in JSON file
            self.posts = self.sitedata["posts"]
            post_tags = set(self.sitedata["post_tags"])
            post_cats = set(self.sitedata["post_cats"])
            self.pages = self.sitedata["pages"]
            page_tags = set(self.sitedata["page_tags"])
            page_cats = set(self.sitedata["page_cats"])

            self.messenger(_("Refresh window content"))
            [self.obj(store).clear() for store in ["store_posts",
                                                   "store_pages",
                                                   "store_tags",
                                                   "store_cats",
                                                   "store_listings",
                                                   "store_files",
                                                   "store_images",
                                                   "store_translation",
                                                   ]]

            # #### add information to notebook tab datastores #####
            # posts/pages tabs are based on liststores and created from dict
            # (see above)
            self.get_tree_data_src("store_posts", self.posts)
            self.get_tree_data_src("store_pages", self.pages)
            # files/listings/images are based on treestores, data rows are
            # appended without dict usage
            self.get_tree_data("store_listings", "listings",
                               self.output_folder)
            self.get_tree_data("store_files", "files", self.output_folder)
            self.get_tree_data("store_images", "images", self.output_folder)
            # tags/category tab
            self.get_tree_data_label(self.posts,
                                     self.pages,
                                     post_tags,
                                     page_tags,
                                     "store_tags",
                                     "tags",
                                     )
            self.get_tree_data_label(self.posts,
                                     self.pages,
                                     post_cats,
                                     page_cats,
                                     "store_cats",
                                     "category",
                                     )
            # translation tab
            self.get_tree_data_translations("store_translation", self.posts)
            self.get_tree_data_translations("store_translation", self.pages)

            # sort tags according to number of occurrences
            self.obj("store_tags").set_sort_column_id(4,
                                                      Gtk.SortType.DESCENDING)
            self.obj("store_cats").set_sort_column_id(4,
                                                      Gtk.SortType.DESCENDING)
            self.obj("store_translation").set_sort_column_id(
                3, Gtk.SortType.DESCENDING)

            # expands all rows in translation tab
            self.obj("view_translations").expand_all()
        except AttributeError:
            self.messenger(_("Failed to load data, choose another conf.py"),
                           "error")

    def get_src_content(self, subdir, d=dict(), t=set(), c=set(), update=None):
        if not update:
            files = [x for x in os.listdir(subdir) if not (x.startswith(".") or
                     x.endswith(".meta"))]
        else:
            files = update
        for f in files:
            title, slug, date, tagstr, tags, catstr, cats, metafile = \
                self.read_src_files(subdir, f)
            # detect language
            if len(self.translation_lang) > 0:
                if f.split(".")[1] == "rst" or f.split(".")[1] == "md":
                    # set empty string because var is used by os.path.join
                    # which throws NameError if var is None
                    lang = ""
                else:
                    lang = f.split(".")[1]
            else:
                lang = ""
            # check for equal file in output dir, mark bold (loaded by
            # treemodel) when False
            for od in {slug, f.split(".")[0]}:
                if self.compare_output_dir(od, subdir, f, f.split(".")[1],
                                           lang, self.output_folder):
                    fontstyle = "normal"
                    break
                else:
                    fontstyle = "bold"
                    self.obj("build").set_sensitive(True)
            # add new found tags/categories to set
            t.update(tags)
            c.update(cats)
            # mark title cell in italic font if title is missing (use slug or
            # filename instead)
            if title == "":
                if slug == "":
                    title = f
                else:
                    title = slug
                if fontstyle == "bold":
                    fontstyle = "bold italic"
                else:
                    fontstyle = "italic"
            # add dictionary entry for file
            # set filename as key for easy file comparison on datafile update
            d[f] = {"title": title,
                    "slug": slug,
                    "file": f,
                    "date": date,
                    "ger_date": datetime.datetime.strptime(
                        date, '%Y-%m-%d').strftime('%d.%m.%Y'),
                    "tags": tags,
                    "tagstr": tagstr,
                    "category": cats,
                    "catstr": catstr,
                    "fontstyle": fontstyle,
                    "sub": subdir,
                    "lang": lang,
                    "transl": [],
                    "last_modified": os.path.getmtime(os.path.join(subdir, f)),
                    "metafile": metafile,
                    }
        # add available translation to default file entry
        # ex: articlename.lang.rst > lang is added to transl entry of
        # articlename.rst
        for key in d:
            if d[key]["lang"] is not "":
                lang = d[key]["lang"]
                default_src = key.replace(".{}.".format(lang), ".")
                d[default_src]["transl"].append(lang)
        return d, list(t), list(c)

    def read_src_files(self, subdir, file):
        date = datetime.datetime.today().strftime("%Y-%m-%d")
        title, slug, tagstr, tags, catstr, cats = "", "", "", "", "", ""
        try:
            metafile = file.split(".")[0] + ".meta"
            with open(os.path.join(subdir, metafile)) as f:
                content = f.readlines()
        except FileNotFoundError:
            with open(os.path.join(subdir, file)) as f:
                content = f.readlines()
                metafile = ""

        for line in content:
            if line.startswith(".. title:"):
                title = line[9:].strip()
            elif line.startswith(".. slug:"):
                slug = line[8:].strip()
            elif line.startswith(".. date:"):
                date = line[8:20].strip()
            elif line.startswith(".. tags:"):
                tagstr = line[8:].strip()
                tags = [t.strip() for t in tagstr.split(",")]
            elif line.startswith(".. category:"):
                catstr = line[12:].strip()
                cats = [c.strip() for c in catstr.split(",")]
                break

        return title, slug, date, tagstr, tags, catstr, cats, metafile

    def compare_output_dir(self, od, subdir, filename, ext, lang, output):
        try:
            return filecmp.cmp(os.path.join(subdir, filename),
                               os.path.join(output,
                                            lang,
                                            subdir,
                                            od,
                                            "index.{}".format(ext),
                                            ))
        except FileNotFoundError:
            return False

    def get_tree_data_src(self, store, dict):
        # append only default language files to treestore
        [self.obj(store).append([dict[key]["title"],
                                 dict[key]["slug"],
                                 dict[key]["file"],
                                 dict[key]["date"],
                                 dict[key]["ger_date"],
                                 dict[key]["tagstr"],
                                 dict[key]["catstr"],
                                 dict[key]["sub"],
                                 # add available translations as comma
                                 # seperated string, stolen from
                                 # gist.github.com/23maverick23/6404685
                                 ",".join(str(s) for s in dict[key]["transl"]),
                                 dict[key]["fontstyle"],
                                 dict[key]["metafile"],
                                 ]) for key in dict if dict[key]["lang"] == ""]
        self.obj(store).set_sort_column_id(3, Gtk.SortType.DESCENDING)

    def get_tree_data(self, store, subdir, output, parent=None):
        for item in sorted(os.listdir(subdir)):
            if os.path.isfile(os.path.join(subdir, item)):
                # images are changed in size when deployed so check only for
                # filename
                if item.endswith(('.png', '.gif', '.jpeg', '.jpg')):
                    equ = os.path.isfile(os.path.join(output, subdir, item))
                # else compare if files are equal
                else:
                    try:
                        equ = filecmp.cmp(os.path.join(subdir, item),
                                          os.path.join(output, subdir, item))
                    except FileNotFoundError:
                        equ = False
                if not equ:
                    weight = 800
                    self.obj("build").set_sensitive(True)
                else:
                    weight = 400
                self.obj(store).append(parent,
                                       [item,
                                        os.path.getsize(os.path.join(
                                            subdir, item)),
                                        self.sizeof_fmt(os.path.getsize(
                                            os.path.join(subdir, item))),
                                        weight,
                                        ])
            elif os.path.isdir(os.path.join(subdir, item)):
                # TODO size of folder
                if os.path.isdir(os.path.join(output, subdir, item)):
                    weight = 400
                else:
                    weight = 800
                    self.obj("build").set_sensitive(True)
                row = self.obj(store).append(parent,
                                             [item, None, None, weight])
                subsubdir = os.path.join(subdir, item)
                # read subdirs as child rows
                self.get_tree_data(store, subsubdir, output, row)

    def get_tree_data_label(self, post_dict, page_dict,
                            post, page, store, label):
        # combine labels from posts and pages and remove empty strings
        post.update(page)
        post.discard("")
        for item in post:
            counter = 0
            # row = title,gerdate,date,weight,counter
            row = self.obj(store).append(
                None, [None, None, None, 800, None, None, None])
            for dict in (post_dict, page_dict):
                for key in dict:
                    if item in dict[key][label]:
                        self.obj(store).append(row,
                                               [dict[key]["title"],
                                                dict[key]["ger_date"],
                                                dict[key]["date"],
                                                400,
                                                None,
                                                dict[key]["file"],
                                                dict[key]["sub"],
                                                ])
                        counter += 1
            self.obj(store).set_value(row, 0, "{} ({})".format(item, counter))
            self.obj(store).set_value(row, 4, counter)

    def get_tree_data_translations(self, store, dict):
        for key in dict:
            # add parent row
            if dict[key]["lang"] == "":
                # row = title,slug,date,ger_date,lang,weight,sub
                row = self.obj(store).append(None,
                                             [dict[key]["title"],
                                              dict[key]["slug"],
                                              dict[key]["file"],
                                              dict[key]["date"],
                                              dict[key]["ger_date"],
                                              None,
                                              dict[key]["sub"],
                                              dict[key]["fontstyle"]])
                # search for translations and append as child row
                [self.obj(store).append(row,
                                        [dict[child]["title"],
                                         dict[child]["slug"],
                                         dict[child]["file"],
                                         dict[child]["date"],
                                         dict[child]["ger_date"],
                                         dict[child]["lang"],
                                         dict[child]["sub"],
                                         dict[key]["fontstyle"]])
                 for child in dict if
                 dict[child]["file"].split(".")[0] == dict[key]["file"].split(
                     ".")[0] and dict[child]["lang"] != ""]

    def get_filelist(self, subdir, output):
        d = {}
        for root, dirs, files in sorted(os.walk(subdir)):
            for f in files:
                # images are changed in size when deployed so check only for#
                # filename
                if subdir == "images":
                    equ = os.path.isfile(os.path.join(output, root, f))
                # else compare if files are identical
                else:
                    try:
                        equ = filecmp.cmp(os.path.join(root, f), os.path.join(
                            output, root, f))
                    except FileNotFoundError:
                        equ = False
                if equ is False:
                    weight = 800
                else:
                    weight = 400
                d[f] = {"size": os.path.getsize(os.path.join(root, f)),
                        "humansize": self.sizeof_fmt(os.path.getsize(
                            os.path.join(root, f))),
                        "weight": weight}
        return d

    def generate_summary(self):
        """Collect site data and generate HTML page which is displayed in the
           summary tab"""

        def get_dir_size(folder):
            total = 0
            counter = 0
            for path, dirs, files in os.walk(folder):
                counter += len([name for name in os.listdir(path) if
                                os.path.isfile(os.path.join(path, name))])
                for f in files:
                    fp = os.path.join(path, f)
                    total += os.path.getsize(fp)
            return self.sizeof_fmt(total), counter

        def get_diskusage_string(folders):
            string = "Name | Size | Files\n--- | --- | ---\n"
            for name, folder in folders:
                s, c = get_dir_size(os.path.join(self.wdir, folder))
                string += """{} | {} | {}\n""".format(name, s, c)
            return string

        def get_brokenlinks_string(output):
            string = ""
            for line in output.stderr.split("\n"):
                if "WARNING: check:" in line:
                    string += " * {}\n".format(
                                            line.split("WARNING: check: ")[1])
            if string == "":
                return "> (no broken links)"
            else:
                return string

        def get_themes_table(available, installed):
            # chop the output
            available = available.stdout.split("\n")[2:-1]
            installed = installed.stdout.split("\n")[2:-1]
            # generate a dict from a list with string value
            d = dict.fromkeys(available, "{} | | | x\n")

            for i in installed:
                name, path = i.split(" at ")
                if path.startswith("themes"):
                    d[name] = "{} | x | | \n"
                else:
                    d[name] = "{} | | x | \n"

            string = _("""available | local | systemwide | not installed
--- |:---:|:---:|:---:\n""")
            for line in d:
                string += d[line].format(line)

            return string

        # TODO: merge with nearly identical function obove
        def get_plugins_table(available, installed):
            # chop the output
            available = available.stdout.split("\n")[2:-1]
            installed = installed.stdout.split("\n")[2:-4]
            # generate a dict from a list with string value
            d = dict.fromkeys(available, "{} | | | x\n")

            for i in installed:
                name, path = i.split(" at ")
                if path.startswith("/home"):
                    d[name] = "{} | x | | \n"
                else:
                    d[name] = "{} | | x | \n"

            string = _("""available | local | systemwide | not installed
--- |:---:|:---:|:---:\n""")
            for line in d:
                string += d[line].format(line)

            return string

        def get_shortcodes(folder):
            try:
                sc = os.listdir(folder)
                string = ""
                for item in sc:
                    string += "* {}\n".format(item)
                return string
            except FileNotFoundError:
                return _("> (no custom shortcodes)")

        # load template
        with open(os.path.join(self.install_dir,
                               "templates",
                               "summary_css.md", )
                  ) as f:
            template = f.read()

        # collect data
        infodict = dict()

        # css version uses GitHub flavoured css from
        # https://github.com/sindresorhus/github-markdown-css
        infodict["css_file"] = os.path.join(self.install_dir,
                                            "templates",
                                            "github-markdown.css",
                                            )

        folders = [("Site", "output"),
                   ("Files", "files"),
                   ("Galleries", "galleries"),
                   ("Images", "images"),
                   ("Posts", "posts"),
                   ("Pages", "pages"),
                   ]

        infodict["disk_usage"] = get_diskusage_string(folders)
        infodict["status"] = self.exec_cmd("nikola status").stdout.split(
                                                                    "\n")[1]
        infodict["broken_links"] = get_brokenlinks_string(self.exec_cmd(
                                                            "nikola check -l"))
        infodict["current_theme"] = self.siteconf.THEME
        infodict["themes"] = get_themes_table(
                                self.exec_cmd("nikola theme -l"),
                                self.exec_cmd("nikola theme --list-installed")
                                )
        infodict["plugins"] = get_plugins_table(
                                self.exec_cmd("nikola plugin -l"),
                                self.exec_cmd("nikola plugin --list-installed")
                                )
        infodict["shortcodes"] = get_shortcodes("shortcodes")

        # template format data strings
        txt = template.format(**infodict)

        # convert markdown to html
        html = markdown.markdown(txt, extensions=["markdown.extensions.tables",
                                                  "markdown.extensions.toc",
                                                  ])
        # dump html to file
        with open(self.summaryfile, "w") as f:
            f.write(html)
        # load file into webview
        self.webview.load_uri("file://" + self.summaryfile)

    def run_nikola_build(self):
        # self.gui_cmd = True
        # self.obj("stack").set_visible_child(app.obj("term"))
        self.messenger(_("Execute Nikola: run build process"))
        self.term_cmd("nikola build")

    def run_nikola_github_deploy(self):
        self.run_nikola_build()
        # self.gui_cmd = True
        # self.obj("stack").set_visible_child(app.obj("term"))
        self.messenger(_("Execute Nikola: run deploy to GitHub command"))
        self.term_cmd("nikola github_deploy")

    def run_nikola_deploy(self):
        self.run_nikola_build()
        # self.gui_cmd = True
        self.messenger(
                    _("Execute Nikola: run deploy to default preset command"))
        self.term_cmd("nikola deploy")

    def exec_cmd(self, command):
        """Send command to subprocess
           Returns subprocess.CompletedProcess value"""
        command = command.split()
        output = subprocess.run(command,
                                stdout=subprocess.PIPE,
                                stderr=subprocess.PIPE,
                                encoding="utf-8",
                                env=self.myenv,
                                )
        return output

    def term_cmd(self, command):
        """Send command to integrated terminal"""
        self.gui_cmd = True
        self.obj("stack").set_visible_child(app.obj("term"))
        command += "\n"
        try:
            # Vte v2.91+
            self.obj("term").feed_child(command.encode())
        except TypeError:
            # Vte v2.90-
            self.obj("term").feed_child(command, len(command))

    def messenger(self, message, log="info"):
        """Show notifications in statusbar and log file/stream"""
        self.obj("statusbar").push(1, message)
        time.sleep(.1)
        while Gtk.events_pending():
            Gtk.main_iteration()
        if log in self.loglevels.keys():
            lvl = self.loglevels[log]
        else:
            lvl = 0
        self.log.log(lvl, message)

    def sizeof_fmt(self, num, suffix='B'):
        """File size shown in common units"""
        for unit in ['', 'K', 'M', 'G', 'T', 'P', 'E', 'Z']:
            if abs(num) < 1024.0:
                return "%3.1f %s%s" % (num, unit, suffix)
            num /= 1024.0
        return "%.1f %s%s" % (num, 'Y', suffix)

    def run(self, argv):
        self.app.run(argv)


app = NiApp()
app.run(sys.argv)
