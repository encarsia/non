#!/usr/bin/env python
# -*- coding: utf-8 -*-

# TODO setup: add appdata.xml and binary file

try:
    import nikola
except (ModuleNotFoundError, ImportError) as e:
    print("You have to install Nikola first.")
    raise

try:
    import gi
    gi.require_version("Gtk", "3.0")
    gi.require_version("Vte", "2.91")
    gi.require_version("WebKit2", "4.0")
    from gi.repository import Gtk, Vte, GObject, GLib, Gio, WebKit2, Gdk
except (ModuleNotFoundError, ImportError) as e:
    print("Unable to load Python bindings for GObject Introspection.")
    raise

import datetime
import filecmp
import gettext
import glob
import importlib
import json
import locale
import logging
import logging.config
import multiprocessing
import os
import shlex
import shutil
import subprocess
import sys
import time
import webbrowser

import yaml
import markdown
import setproctitle

try:
    import info
except ModuleNotFoundError:
    from non import info

_ = gettext.gettext


class Handler:
    """Signal assignment for Glade"""

    # ########## close/destroy  window ############

    def on_window_close(self, widget, *event):
        widget.hide_on_delete()
        return True

    # ########### toolbar ##########################

    def on_newpost_clicked(self, widget):
        self.stop_preview()
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
        self.stop_preview()
        app.run_nikola_build()

    def on_deploy_git_clicked(self, widget):
        self.stop_preview()
        app.run_nikola_github_deploy()

    def on_deploy_clicked(self, widget):
        self.stop_preview()
        app.run_nikola_deploy()

    def on_refresh_clicked(self, widget):
        try:
            app.update_sitedata(app.sitedata)
        except AttributeError:
            app.create_sitedata()
        app.get_window_content()

    # ########### vte terminal ########################

    def on_term_contents_changed(self, widget):
        # get_text returns a tuple of information including the complete
        # content of the console widget: rstrip cut empty lines, then cut the
        # rest in lines and use only the last
        last_line = widget.get_text()[0].rstrip().split("\n")[-1]
        try:
            if last_line.split("$")[1] == "":
                prompt_ready = True
            else:
                prompt_ready = False
        except IndexError:
            prompt_ready = False
        if last_line == "INFO: github_deploy: Successful deployment":
            app.messenger(_("Deploying to GitHub/GitLab successful."))
        # gui_cmd is bool var for command being run via toolbar button
        # if command is invoked by button the app focus returns back to graphic
        # interface stack child 'gui' if the command is finished
        if app.gui_cmd and prompt_ready:
            time.sleep(2)   # just wait a moment so the user can get output
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

    def on_search_button_toggled(self, widget):
        if widget.get_active():
            app.obj("gui").set_visible_child(app.obj("search"))
            app.obj("search_entry").grab_focus()
        else:
            app.obj("gui").set_visible_child(app.obj("main_gui"))

    # ########## searchbar #########################

    def on_search_entry_activate(self, widget):
        txt = app.obj("search_comboboxtext").get_active_text()
        if not txt == "":
            # stop search process if there is running any
            try:
                self.sp.terminate()
                time.sleep(.01)
                self.sp.close()
                app.messenger(_("Stop search process"), "debug")
            except AttributeError:
                app.messenger(_("No search process here to stop"), "debug")
            app.messenger(_("Search started: {}").format(txt))
            self.sp = app.process_search(txt)
            # wait until search is done before showing results
            while self.sp.is_alive():
                time.sleep(.1)

            # load results into TreeView
            store = app.obj("store_search")
            store.clear()

            for r in app.search_result:
                # row = title, file, weight, line (currently not used),
                # counter, preview
                row = store.append(None, [r[0], None, 800, None, r[1], ""])
                for f in r[2]:
                    store.append(row, [f[0], f[1], 400, None, f[2], f[3]])

            app.obj("view_search").expand_all()

    def on_search_entry_icon_press(self, widget, icon_pos, *args):
        if icon_pos == 1:
            widget.set_text("")
        else:
            self.on_search_entry_activate()

    def on_view_search_row_activated(self, widget, *args):
        app.messenger(_("Open file"))
        row, pos = app.obj("selection_search").get_selected()
        subprocess.run(['xdg-open',
                        os.path.join(app.wdir, row[pos][1])]
                       )

    # show search results in TextView
    def on_selection_search_changed(self, widget, *args):
        row, pos = app.obj("selection_search").get_selected()
        try:
            app.obj("search_result_textbuffer").set_text(row[pos][5],
                                                         len(row[pos][5]),
                                                         )
        except TypeError:
            # signal is triggered if widget outside the TreeView is activated
            # so we do not need any action here until
            # clicked on a search result again
            pass

    # ########## link menu #########################

    def on_ref_handbook_clicked(self, widget):
        app.messenger(_("Open Nikola handbook in web browser"))
        webbrowser.open("https://getnikola.com/handbook.html")

    def on_ref_rest_markup_clicked(self, widget):
        app.messenger(_("Open reST syntax reference in web browser"))
        webbrowser.open("http://docutils.sourceforge.net/docs/ref/rst/\
restructuredtext.html")

    def on_ref_rest_dir_clicked(self, widget):
        app.messenger(_("Open reST directives in web browser"))
        webbrowser.open("http://docutils.sourceforge.net/docs/ref/rst/\
directives.html")

    def on_ref_md_clicked(self, widget):
        app.messenger(_("Open Markdown syntax reference in web browser"))
        webbrowser.open("https://www.markdownguide.org/basic-syntax")

    # ########### menu #############################

    def on_open_conf_clicked(self, widget):
        app.messenger(_("Open conf.py in external editor"))
        subprocess.run(['xdg-open', os.path.join(app.wdir, "conf.py")])

    def on_load_conf_clicked(self, widget):
        app.messenger(_("Choose configuration file to read"))
        app.obj("choose_conf_file").run()

    def on_open_non_conf_clicked(self, widget):
        app.messenger(_("Open NoN config file in external editor"))
        subprocess.run(['xdg-open', app.conf_file])

    def on_open_non_log_clicked(self, widget):
        app.messenger(_("Open NoN log file in external editor"))
        subprocess.run(['xdg-open', app.log_file])

    def on_add_bookmark_clicked(self, widget):
        # add title and location to bookmark dict
        bookmark = {app.siteconf.BLOG_TITLE: app.wdir}
        app.bookmarks.update(bookmark)
        app.messenger(_("New bookmark added for {}.").format(
            app.siteconf.BLOG_TITLE))
        app.check_nonconf()

    def on_gen_sum_clicked(self, widget):
        app.messenger(_("Generate page for summary tab"))
        app.generate_summary()
        # change to tab when finished
        app.obj("notebook").set_current_page(-1)

    # ############## filechooser dialog ############

    def on_choose_conf_file_file_activated(self, widget):
        self.on_choose_conf_file_response(widget, -5)

    def on_choose_conf_file_response(self, widget, response):
        if response == -5:
            print(widget.get_filename())
            try:
                app.sitedata = dict()
                app.dump_sitedata_file(app.sitedata)
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
            self.on_window_close(widget)
            app.obj("config_info").run()
            raise
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
                if app.obj("create_page").get_active():
                    new_site_obj = "new_page"
                else:
                    new_site_obj = "new_post"
                if app.obj("create_md").get_active():
                    format = "--format=markdown"
                else:
                    format = "--format=rest"

                # return string maybe of use later so I leave it that way
                status = app.exec_cmd("nikola {} --title=\"{}\" {}".format(
                                        new_site_obj,
                                        app.obj("newpost_entry").get_text(),
                                        format,
                                        )
                                      )

                if "ERROR" in str(status.stderr):
                    app.messenger(_(f"Failed to create post. Message: "
                                    f"{status.stdout}"), "error")
                    # show Nikola error message
                    app.obj("entry_message").set_text(str(status.stderr).split(
                        "ERROR: ")[1].split("\n")[0])
                    app.obj("newpost_entry").grab_focus()
                elif status.returncode != 0:
                    app.messenger(_(f"Failed to create post. Message:"
                                    f" {status.stderr}"), "error")
                    app.obj("entry_message").set_text(f"Error while creating "
                                                      f"post. See logfile for "
                                                      f"details.")
                else:
                    self.on_window_close(widget)
                    app.messenger(_("New post created: {}").format(
                        app.obj("newpost_entry").get_text()))
                    app.update_sitedata(app.sitedata)
                    app.get_window_content()
        else:
            self.on_window_close(widget)

    def on_newpost_entry_activate(self, widget):
        self.on_newpost_dialog_response(app.obj("newpost_dialog"), -5)

    # ############## upload drafts to GitHub dialog ############

    def on_git_push_changes_dialog_response(self, widget, response):
        if response == -5:
            app.exec_cmd("git add .")
            app.exec_cmd("git commit -m \"NoN auto commit.\"")
            app.term_cmd("git push origin src")
            app.messenger(_("Pushed changes to origin/src."))
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
                        os.path.join(app.wdir, row[pos][2])]
                       )

    def on_view_pages_row_activated(self, widget, *args):
        app.messenger(_("Open page file"))
        row, pos = app.obj("selection_page").get_selected()
        subprocess.run(['xdg-open',
                        os.path.join(app.wdir, row[pos][2])]
                       )

    def on_view_tags_row_activated(self, widget, pos, *args):
        if pos.get_depth() == 1:
            widget.expand_to_path(pos)
        else:
            row, pos = app.obj("selection_tags").get_selected()
            subprocess.run(['xdg-open',
                            os.path.join(app.wdir, row[pos][5])]
                           )

    def on_view_cats_row_activated(self, widget, pos, *args):
        if pos.get_depth() == 1:
            widget.expand_to_path(pos)
        else:
            row, pos = app.obj("selection_cats").get_selected()
            subprocess.run(['xdg-open',
                            os.path.join(app.wdir, row[pos][5])]
                           )

    def on_view_listings_row_activated(self, widget, *args):
        row, pos = app.obj("selection_listings").get_selected()
        subprocess.run(['xdg-open',
                        os.path.join(app.wdir, row[pos][4])]
                       )

    def on_view_images_row_activated(self, widget, *args):
        row, pos = app.obj("selection_images").get_selected()
        subprocess.run(['xdg-open',
                        os.path.join(app.wdir, row[pos][4])]
                       )

    def on_view_files_row_activated(self, widget, *args):
        row, pos = app.obj("selection_files").get_selected()
        subprocess.run(['xdg-open',
                        os.path.join(app.wdir, row[pos][4])]
                       )

    def on_view_translations_row_activated(self, widget, *args):
        app.messenger(_("Open file..."))
        row, pos = app.obj("selection_translations").get_selected()
        subprocess.run(['xdg-open',
                        os.path.join(app.wdir, row[pos][2])]
                       )

    # open context menu for translation options

    def on_view_translations_button_release_event(self, widget, event):
        if event.button == 3:   # only show on right click
            popover = self.refresh_popover(widget, event)
            box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)
            popover.add(box)
            for l in app.translation_lang:
                item = Gtk.ModelButton()
                item.set_property("text",
                                  _("Create translation for {}".format(l)))
                box.add(item)
                item.connect("clicked", self.on_create_translation, l)
                popover.show_all()
                popover.popup()

    def on_create_translation(self, widget, lang):
        row, pos = app.obj("selection_translations").get_selected()
        file = row[pos][2]
        file_base = file.split(".")[0]
        file_ext = file.split(".")[-1]
        trans_file = "{}.{}.{}".format(file_base, lang, file_ext)
        if os.path.isfile(os.path.join(trans_file)):
            app.messenger(_("Translation file already exists."), "warning")
        else:
            shutil.copy(
                os.path.join(file),
                os.path.join(trans_file))
            app.messenger(_("Create translation file for {}").format(
                row[pos][0]))
            app.update_sitedata(app.sitedata)
            app.get_window_content()

    # open context menu on right click to open post/page in browser

    def on_view_posts_button_release_event(self, widget, event):
        row, pos = app.obj("selection_post").get_selected()
        # signal is emitted on clicking on the table header (sorting) so no
        # selection is possible
        if pos is not None:
            self.on_pp_table_click(event, row, pos, widget)

    def on_view_pages_button_release_event(self, widget, event):
        row, pos = app.obj("selection_page").get_selected()
        if pos is not None:
            self.on_pp_table_click(event, row, pos, widget)

    def on_pp_table_click(self, event, row, pos, widget):
        title = row[pos][0]
        slug = row[pos][1]
        filename = row[pos][2]
        # if slug is not set the output path is generated from the filename
        # without file extension
        if slug == "":
            slug = filename.split("/")[-1].split(".")[0]
        path = os.path.join(*filename.split("/")[:-1])
        meta = row[pos][10]
        # show info in statusbar on left click
        if event.button == 1:
            if meta != "":
                has_meta = _("yes")
            else:
                has_meta = _("no")
            app.messenger(
                _("Input file format: {}. Separate metafile: {}.").format(
                    filename.split(".")[1], has_meta))
        # only generate popup menu on right click
        elif event.button == 3:
            popover = self.refresh_popover(widget, event)
            box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)
            popover.add(box)
            item = Gtk.ModelButton()
            item.set_property("text", _("Open in web browser"))
            box.add(item)
            item.connect("clicked", self.on_open_pp_web, title, path, slug)
            if meta != "":  # create button if metafile exists
                item = Gtk.ModelButton()
                item.set_property("text", _("Edit meta data file"))
                item.connect("clicked", self.on_open_metafile, meta)
                box.add(item)
            popover.show_all()
            popover.popup()
        else:
            app.messenger(_("No function (button event: {})").format(
                event.button), "debug")

    def on_open_pp_web(self, widget, title, path, slug):
        app.messenger(_("Open '{}' in web browser").format(title))
        webbrowser.open("{}{}/{}".format(app.siteconf.SITE_URL, path, slug))

    def on_open_metafile(self, widget, meta):
        app.messenger(_("Edit metafile: {}").format(meta))
        subprocess.run(['xdg-open',
                        os.path.join(app.wdir, meta)]
                       )

    def on_status_reload_clicked(self, widget):
        for s in ("error", "warning", "info"):
            app.obj(f"textbuffer_{s}").set_text("")
        app.get_status()

    def refresh_popover(self, widget, event):
        popover = Gtk.Popover()
        # open popover at mouse position
        rect = Gdk.Rectangle()
        rect.x = event.x
        rect.y = event.y + 25
        # additional vertical space because popover is not positioned exactly
        rect.width = rect.height = 1
        popover.set_pointing_to(rect)
        popover.set_position(Gtk.PositionType.RIGHT)
        popover.set_relative_to(widget)
        return popover

    def stop_preview(self):
        if app.obj("preview").get_active():
            app.obj("preview").set_active(False)


class NiApp:

    def __init__(self):

        setproctitle.setproctitle("NoN")
        self.install_dir = os.getcwd()
        self.user_app_dir = os.path.join(os.path.expanduser("~"),
                                         ".non",
                                         )
        self.conf_file = os.path.join(self.user_app_dir, "config.yaml")
        self.log_file = os.path.join(self.user_app_dir, "non.log")

        # create hidden app folder in user's home directory if it does
        # not exist
        if not os.path.isdir(self.user_app_dir):
            os.makedirs(self.user_app_dir)

        # initiate GTK+ application
        GLib.set_prgname("Knights of Ni")

        # GSettings
        # self.app = Gtk.Application.new("app.knights-of-ni",

        self.app = Gtk.Application.new(None, Gio.ApplicationFlags(4))
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
        self.dump_sitedata_file(self.sitedata)
        self.app.quit()
        self.log.info(_("Application terminated on window close button. Bye."))

    def on_app_startup(self, app):
        os.chdir(self.user_app_dir)
        # setting up logging
        self.log = logging.getLogger("non")
        with open(os.path.join(self.install_dir, "logging.yaml")) as f:
            config = yaml.load(f, Loader=yaml.FullLoader)
            logging.config.dictConfig(config)

        self.loglevels = {"critical": 50,
                          "error": 40,
                          "warning": 30,
                          "info": 20,
                          "debug": 10,
                          }

        # log version info for debugging
        self.log.debug(f"Application version: {info.__version__}")
        self.log.debug(f"GTK+ version: {Gtk.get_major_version()}."
                       f"{Gtk.get_minor_version()}."
                       f"{Gtk.get_micro_version()}")
        self.log.debug(f"Python version: {sys.version_info.major}."
                       f"{sys.version_info.minor}."
                       f"{sys.version_info.micro}")
        self.log.debug(f"Nikola version: {nikola.__version__}")
        self.log.debug(f"Application executed from {self.install_dir}")

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

        # error if created in Glade
        self.add_dialogbuttons(self.obj("choose_conf_file"))
        # self.add_dialogokbutton(self.obj("about_dialog"))

        # load config from config.yaml or start with new
        if not os.path.isfile(self.conf_file):
            self.messenger(_("No config available..."))
            self.non_config = {"wdir": None,
                               "bookmarks": dict(),
                               }
            self.messenger(_("Empty config created..."))
        else:
            self.non_config = yaml.load(open(self.conf_file),
                                        Loader=yaml.FullLoader,
                                        )
            self.messenger(_("Found config to work with..."))

        # main window
        window = self.obj("non_window_stack")
        # application icon doesn't work under Wayland
        # window.set_icon_from_file(os.path.join(self.install_dir,
        #                                       "ui",
        #                                       "duckyou.svg"))
        window.set_application(app)
        self.check_nonconf()
        window.show_all()

    def start_console(self, wdir):

        # spawn_async throws a waning that the runtime check failed but at
        # least it's not deprecated
        self.obj("term").spawn_async(
            Vte.PtyFlags.DEFAULT,
            wdir,
            ["/bin/bash"],
            None,
            GLib.SpawnFlags.DO_NOT_REAP_CHILD,
            None,
            Gio.Cancellable,
            -1,
            None,
        )

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
        for i in self.obj("menu_box"):
            if isinstance(i, Gtk.ModelButton) and \
                    i.get_property("text").startswith(_("Bookmark: ")):
                self.obj("menu_box").remove(i)
        # add menu items for bookmarks
        if self.bookmarks:
            self.messenger(_("Found {} bookmark(s)").format(
                len(self.bookmarks)))
            for b in self.bookmarks:
                item = Gtk.ModelButton()
                item.set_property("text", _("Bookmark: {}").format(b))
                self.obj("menu_box").add(item)
                # mark current Nikola site and deactivate button
                if self.wdir == self.bookmarks[b]:
                    item.set_property("text",
                                      _("Bookmark: {} (active)").format(b),
                                      )
                    item.set_sensitive(False)
                item.connect("clicked",
                             self.select_bookmark,
                             self.bookmarks[b],
                             )
            self.obj("menu").show_all()
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
            print(e)
            self.messenger(_("Path to working directory malformed or None."),
                           "warning")
            self.obj("choose_conf_file").run()
            self.wdir = os.path.expanduser("~")

        self.get_status()
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
        Handler().stop_preview()
        try:
            self.dump_sitedata_file(self.sitedata)
        except AttributeError:
            pass
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
            sitedata["post_cats"] = self.get_src_content("posts",
                                                         d=dict(),
                                                         t=set(),
                                                         c=set(),
                                                         )
        sitedata["pages"], \
            sitedata["page_tags"], \
            sitedata["page_cats"] = self.get_src_content("pages",
                                                         d=dict(),
                                                         t=set(),
                                                         c=set(),
                                                         )
        self.messenger(_("Collect data of Nikola site complete."))
        self.dump_sitedata_file(sitedata)
        return sitedata

    def update_sitedata(self, sitedata):
        self.messenger(_("Update data file for: {}").format(
            self.siteconf.BLOG_TITLE))
        filelist = dict()
        new_files = dict()
        for sub in ["posts", "pages"]:
            filelist[sub] = self.get_src_filelist(sub)
            new_files[sub] = []
            for f in filelist[sub]:
                if f in sitedata[sub].keys():
                    if not sitedata[sub][f]["last_modified"] == \
                                                        os.path.getmtime(f):
                        new_files[sub].append(f)
                        self.messenger(_("Update article data for: {}").format(
                            sitedata[sub][f]["title"]))
                else:
                    new_files[sub].append(f)
                    self.messenger(
                        _("Add new article data for: {}.").format(f))
            # delete dict items of removed or renamed source files
            for p in sitedata[sub].copy():
                if p not in filelist[sub]:
                    self.messenger(_("Delete data for: {}.").format(p))
                    del sitedata[sub][p]

        sitedata["posts"], \
            sitedata["post_tags"], \
            sitedata["post_cats"] = self.get_src_content(
                "posts",
                d=sitedata["posts"],
                t=set(sitedata["post_tags"]),
                c=set(sitedata["post_cats"]),
                update=new_files["posts"],
                )
        sitedata["pages"], \
            sitedata["page_tags"], \
            sitedata["page_cats"] = self.get_src_content(
                "pages",
                sitedata["pages"],
                t=set(sitedata["page_tags"]),
                c=set(sitedata["page_cats"]),
                update=new_files["pages"],
                )
        sitedata["listings"] = glob.glob("listings/**/*.*", recursive=True)

        return sitedata

    def dump_sitedata_file(self, sitedata):
        try:
            with open(self.datafile, "w") as outfile:
                json.dump(sitedata, outfile, indent=4)
            self.messenger(_("Write site data to JSON file."))
        except AttributeError:
            self.messenger(_("Could not write site data to JSON file."),
                           "warn")

    def get_site_info(self):
        # load nikola conf.py as module to gain simple access to variables
        try:
            spec = importlib.util.spec_from_file_location(
                "siteconf", os.path.join(self.wdir, "conf.py"))
            self.siteconf = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(self.siteconf)

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

            # labels

            # author, description, title are translatable so either a string
            # or dict

            try:
                self.obj("author").set_text(self.siteconf.BLOG_AUTHOR)
            except TypeError:
                self.obj("author").set_text(self.siteconf.BLOG_AUTHOR[self.default_lang])
            try:
                self.obj("descr").set_text(self.siteconf.BLOG_DESCRIPTION)
            except TypeError:
                self.obj("descr").set_text(self.siteconf.BLOG_DESCRIPTION[self.default_lang])
            try:
                self.obj("title").set_text(self.siteconf.BLOG_TITLE)
            except TypeError:
                self.obj("title").set_text(self.siteconf.BLOG_TITLE[self.default_lang])

            self.obj("pathlocal").set_uri("file://{}".format(self.wdir))
            self.obj("pathlocal").set_label("...{}".format(self.wdir[-25:]))
            self.obj("pathremote").set_uri(self.siteconf.SITE_URL)
            self.obj("pathremote").set_label(self.siteconf.SITE_URL)

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

            # get paths and filetypes for posts/pages source files
            self.src_files_paths = {"pages": self.siteconf.PAGES,
                                    "posts": self.siteconf.POSTS,
                                    }
            self.src_files_ext = set()
            for key in self.src_files_paths:
                _paths = set()
                for val in self.src_files_paths[key]:
                    _paths.add(val[0].split("/*.")[0])
                    self.src_files_ext.add(val[0].split("/*.")[1])
                self.src_files_paths[key] = _paths

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
            self.get_tree_data("store_listings",
                               "listings",
                               self.output_folder,
                               )
            self.get_tree_data("store_files",
                               "files",
                               self.output_folder,
                               )
            self.get_tree_data("store_images",
                               "images",
                               self.output_folder,
                               )
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

            # sort tags/categories by number of occurrences and then by date
            self.obj("store_tags").set_sort_column_id(2,
                                                      Gtk.SortType.DESCENDING)
            self.obj("store_cats").set_sort_column_id(2,
                                                      Gtk.SortType.DESCENDING)
            self.obj("store_tags").set_sort_column_id(4,
                                                      Gtk.SortType.DESCENDING)
            self.obj("store_cats").set_sort_column_id(4,
                                                      Gtk.SortType.DESCENDING)
            self.obj("store_translation").set_sort_column_id(
                3, Gtk.SortType.DESCENDING)

            # expand rows in some tabs
            self.obj("view_translations").expand_all()
            self.obj("view_images").expand_all()
            self.obj("view_files").expand_all()

        except AttributeError:
            self.messenger(_("Failed to load data, choose another conf.py"),
                           "error")

    def get_src_filelist(self, sub):
        filelist = list()
        for path in self.src_files_paths[sub]:
            _allfiles = glob.glob(path + "/**/*.*", recursive=True)
            filelist += [x for x in _allfiles if not (x.endswith(".meta") or "/." in _allfiles)]
        return filelist

    def get_src_content(self, subdir, d, t, c, update=None):
        if not update:
            files = self.get_src_filelist(subdir)
        else:
            files = update

        for f in files:
            title, slug, date, tagstr, tags, catstr, cats, metafile = \
                self.read_src_files(f)
            # detect language
            if self.translation_lang:
                if f.split(".")[1] in self.src_files_ext:
                    # set empty string because var is used by os.path.join
                    # which throws NameError if var is None
                    lang = ""
                else:
                    lang = f.split(".")[1]
            else:
                lang = ""
            # check for equal file in output dir, mark bold (loaded by
            # treemodel) when False
            if self.compare_output_dir(slug, f, lang, self.output_folder):
                fontstyle = "normal"
            else:
                fontstyle = "bold"
            # add new found tags/categories to set
            t.update(tags)
            c.update(cats)
            # mark title cell in italic font if title is missing (use slug or
            # filename instead)
            if title == "":
                if slug == "":
                    title = f.split("/")[-1]
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
                    "last_modified": os.path.getmtime(f),
                    "metafile": metafile,
                    }
        # add available translation to default file entry
        # ex: articlename.lang.rst > lang is added to transl entry of
        # articlename.rst
        for key in d:
            if d[key]["lang"] != "":
                lang = d[key]["lang"]
                default_src = key.replace(".{}.".format(lang), ".")
                d[default_src]["transl"].append(lang)
        return d, list(t), list(c)

    def read_src_files(self, file):
        date = datetime.datetime.today().strftime("%Y-%m-%d")
        title, slug, tagstr, tags, catstr, cats = "", "", "", "", "", ""
        try:
            metafile = file.split(".")[0] + ".meta"
            with open(metafile, encoding="utf-8-sig") as f:
                content = f.readlines()
        except FileNotFoundError:
            with open(file, encoding="utf-8-sig") as f:
                content = f.readlines()
                metafile = ""
        for line in content:
            if line.startswith(".. title:"):
                title = line[9:].strip()
            elif line.startswith(".. slug:"):
                slug = line[8:].strip()
            elif line.startswith(".. date:"):
                date = line[8:20].strip()
                date = date.replace("/", "-")   # convert slash separated dates
            elif line.startswith(".. tags:"):
                tagstr = line[8:].strip()
                tags = [t.strip() for t in tagstr.split(",")]
            elif line.startswith(".. category:"):
                catstr = line[12:].strip()
                cats = [c.strip() for c in catstr.split(",")]
                break

        return title, slug, date, tagstr, tags, catstr, cats, metafile

    def compare_output_dir(self, slug, filename, lang, output):
        if slug == "":
            slug = filename.split("/")[-1].split(".")[0]
        try:
            return filecmp.cmp(os.path.join(filename),
                               os.path.join(
                                   output,
                                   lang,
                                   # path to file
                                   *filename.split("/")[:-1],
                                   slug,
                                   # file extension
                                   "index.{}".format(filename.split(".")[1]),
                                   ),
                               )
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
                else:
                    weight = 400
                self.obj(store).append(parent,
                                       [item,
                                        os.path.getsize(os.path.join(
                                            subdir, item)),
                                        self.sizeof_fmt(os.path.getsize(
                                            os.path.join(subdir, item))),
                                        weight,
                                        os.path.join(subdir, item),
                                        ])
            elif os.path.isdir(os.path.join(subdir, item)):
                # TODO size of folder
                if os.path.isdir(os.path.join(output, subdir, item)):
                    weight = 400
                else:
                    weight = 800
                row = self.obj(store).append(parent,
                                             [item,
                                              None,
                                              None,
                                              weight,
                                              os.path.join(subdir, item),
                                              ])
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
            # row = title, gerdate, date, weight, counter
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
            if counter > 0:
                self.obj(store).set_value(row, 0, "{} ({})".format(item,
                                                                   counter))
                self.obj(store).set_value(row, 4, counter)
            else:
                # do not append row if occurence is zero and delete from
                # sitedata dict
                self.obj(store).remove(row)
                for list in (self.sitedata["post_tags"],
                             self.sitedata["page_tags"],
                             self.sitedata["post_cats"],
                             self.sitedata["page_cats"]):
                    try:
                        list.remove(item)
                    except ValueError:
                        pass    # do nothing if item is not in list

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
                # images are changed in size when deployed so check only for
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

        # TODO merge with nearly identical function obove
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
        try:
            infodict["status"] = self.exec_cmd("nikola status").stdout.split("\n")[1]
        except IndexError:
            self.messenger(_("Could not fetch site status. See 'Status' \
messages and solve errors."), "error")
            return
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
        html_content = markdown.markdown(
            txt,
            extensions=["markdown.extensions.tables",
                        "markdown.extensions.toc",
                        ],
            )

        # wrap content in body
        html = """<!DOCTYPE html>
<html>
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <link rel="stylesheet" href="{}">
  <title>Summary</title>
</head>
<style>
    .markdown-body {{
        box-sizing: border-box;
        min-width: 200px;
        max-width: 700px;
        margin: 0 auto;
        padding: 20px;
    }}
</style>
<article class="markdown-body">
<body>
{}
</body>
</article>
</html>""".format(infodict["css_file"], html_content)

        # dump html to file
        with open(self.summaryfile, "w") as f:
            f.write(html)
        # load file into webview
        self.webview.load_uri("file://" + self.summaryfile)

    def process_search(self, pattern):
        # store search results as shared variable between mainloop and
        # multiprocessing thread
        self.search_result = multiprocessing.Manager().list()
        # start search as multiprocessing process/thread so it is interruptable
        # when the search pattern is changed
        p = multiprocessing.Process(target=self.search_files,
                                    args=(pattern, self.search_result))
        p.start()
        return p

    def search_files(self, pattern, result):
        # search results are stored as list and read when search is finished
        # the treeview then is updated by the mainloop because Gtk
        # variable structure:
        #       ("Posts", counter, [(file1, title1, counter, preview_string),
        #                           (file2, ...),
        #                          ]),
        #       ("Pages", ...),
        #       ("Listings", ...)
        subdirs = [("Posts", self.sitedata["posts"]),
                   ("Pages", self.sitedata["pages"]),
                   ("Listings", self.sitedata["listings"]),
                   ]

        for s in subdirs:

            match = []
            counter_sub = 0

            for f in s[1]:
                if s[0] == "Listings":
                    filename = f
                else:
                    filename = s[1][f]["file"]
                counter = 0
                preview = ""
                with open(filename) as txt:
                    try:
                        for no, line in enumerate(txt):
                            # do not search case-sensitive
                            if pattern.lower() in line.lower():
                                counter += 1
                                preview += "Line {}:\n\n{}\n----------- \
\n".format(no + 1, line)
                    except UnicodeDecodeError:
                        # ignore if line cannot be read
                        pass
                if counter > 0:
                    counter_sub += 1
                    if s[0] == "Listings":
                        match.append((filename, filename, counter, preview))
                    else:
                        match.append((s[1][f]["title"],
                                      s[1][f]["file"],
                                      counter,
                                      preview)
                                     )
            result.append((s[0], counter_sub, match))

    def get_status(self):
        output = self.exec_cmd("nikola status")
        output = output.stderr.split("\n")
        attention = False
        for s in ("error", "warning", "info"):
            textbuffer = self.obj(f"textbuffer_{s}")
            start_iter = textbuffer.get_start_iter()
            end_iter = textbuffer.get_end_iter()
            # error messages from executing commands are displayed in errors so
            # catch content instead of clearing the textbuffer
            txt = textbuffer.get_text(start_iter, end_iter, True)
            if txt != "":
                attention = True
            counter = 0
            for line in output:
                try:
                    message = line.split("{}: Nikola: ".format(s.upper()))[1]
                    counter += 1
                    txt += """    ({}) {}
                    
""".format(counter, message)
                    attention = True
                except IndexError:
                    pass
            textbuffer.set_text(txt)
        if attention:
            self.obj("status_button_label").set_text("Status (!)")
        else:
            self.obj("status_button_label").set_text("Status (ok)")
        self.messenger(_("Messages in 'Status' popover updated."))

    def run_nikola_build(self):
        self.messenger(_("Execute Nikola: run build process"))
        self.term_cmd("nikola build")

    def run_nikola_github_deploy(self):
        self.run_nikola_build()
        self.messenger(_("Execute Nikola: run deploy to GitHub command"))
        self.term_cmd("nikola github_deploy")

    def run_nikola_deploy(self):
        self.run_nikola_build()
        self.messenger(
            _("Execute Nikola: run deploy to default preset command"))
        self.term_cmd("nikola deploy")

    def exec_cmd(self, command):
        """Send command to subprocess
           Returns subprocess.CompletedProcess value"""
        command = shlex.split(command)
        output = subprocess.run(command,
                                stdout=subprocess.PIPE,
                                stderr=subprocess.PIPE,
                                encoding="utf-8",
                                env=self.myenv,
                                )
        if output.returncode != 0:
            self.messenger((f"Error while executing command: {output.stderr} "
                            f"(returncode: {output.returncode})"),
                           "error")
            self.obj("textbuffer_error").set_text(output.stderr)
            self.obj("status_button_label").set_text("Status (!)")

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
        """Show notifications in statusbar and log file/stream
           Default logging level is info."""
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


if __name__ == "__main__":
    app = NiApp()
    app.run(sys.argv)
else:
    # run application from Python console
    # from non import application
    os.chdir("non/")
    app = NiApp()
    app.run(None)
