#!/usr/bin/env python
# -*- coding: utf-8 -*-

import sys
import os
import shutil
import datetime
import time
import importlib
import filecmp
import subprocess
import locale
import gettext
import logging

_ = gettext.gettext

try:
    import gi
    gi.require_version('Gtk','3.0')
    gi.require_version('Vte', '2.91')
    from gi.repository import Gtk, Vte, GObject, GLib, Gio
except:
    print(_("Unable to load Python bindings for GObject Introspection."))
    raise

class Handler:
    """Signal assignment for Glade"""
    
    ############ close/destroy  window ############

    def on_window_close(self,widget,*event):
        widget.hide_on_delete()
        return True

    ############ toolbar ##########################
    
    def on_newpost_clicked(self,widget):
        app.obj("entry_message").set_text("")
        app.obj("newpost_entry").set_text("")
        app.obj("newpost_dialog").show_all()
    
    def on_preview_toggled(self,widget):
        if widget.get_active():
            app.messenger("Open preview in standard web browser")
            self.serve = subprocess.Popen(["nikola","serve","-b"])
        else:
            #stop local server when untoggling button
            app.messenger("Stop preview")
            self.serve.kill()

    def on_build_clicked(self,widget):
        app.run_nikola_build()
        
    def on_deploy_clicked(self,widget):
        app.run_nikola_github_deploy()

    def on_refresh_clicked(self,widget):
        app.get_window_content()

    ############ vte terminal ########################

    def on_term_contents_changed(self,widget):
        last_line = widget.get_text()[0].rstrip().split("\n")[-1]
        if app.prompt == "":
            app.prompt = last_line
        if last_line == "INFO: github_deploy: Successful deployment":
            app.messenger("Deploying to GitHub successful.")
        #gui_cmd is bool var for command being run via toolbar button
        #if command is invoked by button the app focus returns back to graphic interface stack child 'gui'
        if app.gui_cmd is True and last_line == app.prompt:
            time.sleep(2)
            app.obj("stack").set_visible_child(app.obj("gui"))
            app.get_window_content()
            app.gui_cmd = False

    def on_term_child_exited(self,widget,*args):
        #on exit the console is restarted because it does'n run in a separate window anymore but as a (persistent) GTK stack child 
        widget.reset(True, True)
        app.start_console(None)

    ########### headerbar #########################

    def on_info_button_clicked(self,widget):
        app.messenger("Open About dialog")
        app.obj("about_dialog").show_all()

    def on_manual_button_clicked(self, widget):
        app.messenger("Open Nikola handbook in web browser")
        subprocess.run(['xdg-open',"https://getnikola.com/handbook.html"])

    def on_open_conf_activate(self,widget):
        app.messenger("Open conf.py in external editor")
        subprocess.run(['xdg-open',os.path.join(app.wdir,"conf.py")])

    def on_load_conf_activate(self,widget):
        app.messenger("Choose configuration file to read")
        app.obj("choose_conf_file").show_all()
    
    def on_add_bookmark_activate(self,widget):
        bookmark = app.siteconf.BLOG_TITLE, app.wdir
        app.bookmarks.add(bookmark)
        with open(app.nonconfig_file) as f:
            content = f.readlines()
        for line in content:
            if line == ("\n"):
                content.remove(line)
            elif line.startswith("BOOKMARKS"):
                content[content.index(line)] = "BOOKMARKS = %s\n" % str(app.bookmarks)
        with open(app.nonconfig_file,"w") as f:
            for line in content:
                f.write(line)
        app.messenger("New bookmark for \'%s\' added." % app.siteconf.BLOG_TITLE)
        app.check_ninconf()

    ############### filechooser dialog ############

    def on_choose_conf_file_file_activated(self,widget):
        self.on_choose_conf_file_response(widget,-5)

    def on_choose_conf_file_response(self,widget,response):
        if response == -5:
            try:
                if os.path.split(widget.get_filename())[1] == "conf.py":
                    app.check_ninconf(os.path.split(widget.get_filename())[0])
                else:
                    app.messenger("Working Nikola configuration required","warning")
                    app.obj("config_info").show_all()
            except AttributeError:
                app.messenger("Working Nikola configuration required","warning")
                app.obj("config_info").show_all()
        else:
            app.messenger("Working Nikola configuration required","warning")
            app.obj("config_info").show_all()
        self.on_window_close(widget)

    ############### new post dialog ############

    def on_newpost_dialog_response(self,widget,response):
        if response == 0:
            if app.obj("newpost_entry").get_text() == "":
                app.messenger("Create new post")
                app.obj("entry_message").set_text("Title must not be empty.")
                app.obj("newpost_entry").grab_focus()
            else:
                self.on_window_close(widget)
                if app.obj("create_page").get_active():
                    new_site_obj = "new_page"
                else:
                    new_site_obj = "new_post"
                subprocess.run(["nikola",new_site_obj,"--title=%s" % app.obj("newpost_entry").get_text()])
                app.get_window_content()
        else:
            self.on_window_close(widget)

    def on_newpost_entry_activate(self,widget):
        self.on_newpost_dialog_response(app.obj("newpost_dialog"),0)

    ################ treeview rows activated ###############

    #open files on doubleclick

    def on_view_posts_row_activated(self,widget,*args):
        app.messenger("Open post file")
        row,pos = app.obj("selection_post").get_selected()
        subprocess.run(['xdg-open',os.path.join(app.wdir,row[pos][7],row[pos][2])])

    def on_view_pages_row_activated(self,widget,*args):
        app.messenger("Open page file")
        row,pos = app.obj("selection_page").get_selected()
        subprocess.run(['xdg-open',os.path.join(app.wdir,row[pos][7],row[pos][2])])
        
    def on_view_tags_row_activated(self,widget,pos,*args):
        if pos.get_depth() == 1:
            widget.expand_to_path(pos)
        else:
            row,pos = app.obj("selection_tags").get_selected()
            subprocess.run(['xdg-open',os.path.join(app.wdir,row[pos][6],row[pos][5])])

    def on_view_cats_row_activated(self,widget,pos,*args):
        if pos.get_depth() == 1:
            widget.expand_to_path(pos)
        else:
            row,pos = app.obj("selection_cats").get_selected()
            subprocess.run(['xdg-open',os.path.join(app.wdir,row[pos][6],row[pos][5])])
        
    def on_view_listings_row_activated(self,widget,*args):
        row,pos = app.obj("selection_listings").get_selected()
        subprocess.run(['xdg-open',os.path.join(app.wdir,"listings",row[pos][0])])
        
    def on_view_images_row_activated(self,widget,*args):
        row,pos = app.obj("selection_images").get_selected()
        subprocess.run(['xdg-open',os.path.join(app.wdir,"images",row[pos][0])])
        
    def on_view_files_row_activated(self,widget,*args):
        row,pos = app.obj("selection_files").get_selected()
        subprocess.run(['xdg-open',os.path.join(app.wdir,"files",row[pos][0])])

    def on_view_translations_row_activated(self,widget,*args):
        app.messenger("Open file...")
        row,pos = app.obj("selection_translations").get_selected()
        subprocess.run(['xdg-open',os.path.join(app.wdir,row[pos][6],row[pos][2])])

    def on_view_translations_button_release_event(self,widget,event):
        popup=Gtk.Menu()
        for l in app.translation_lang:
            item=Gtk.MenuItem(_("Create translation for %s" % l))
            #selected row is already caught by on_treeview_selection_changed function
            item.connect("activate",self.on_create_translation,l)
            popup.append(item)
        popup.show_all()
        #only show on right click
        if event.button == 3:
            popup.popup(None,None,None,None,event.button,event.time)
            return True

    def on_create_translation(self,widget,lang):
        row,pos = app.obj("selection_translations").get_selected()
        subdir = row[pos][6]
        file = row[pos][2]
        trans_file = "%s.%s.rst" % (file.split(".")[0], lang)
        if os.path.isfile(os.path.join(subdir,trans_file)):
            app.messenger("Translation file already exists.","warning")
        else:
            shutil.copy(os.path.join(subdir,file),os.path.join(subdir,trans_file))
            app.messenger("Create translation file for %s" % row[pos][0])
            app.get_window_content()
        
class NiApp:
    
    def __init__(self):
        self.app = Gtk.Application.new("app.knights-of-ni", Gio.ApplicationFlags(0))
        self.app.connect("startup", self.on_app_startup)
        self.app.connect("activate", self.on_app_activate)
        self.app.connect("shutdown", self.on_app_shutdown)

    def on_app_shutdown(self, app):
        self.app.quit()
        self.log.info("Application terminated on application window close button. Bye.")

    def on_app_startup(self,app):
        #get current directory
        self.install_dir = os.getcwd()
        #set up logging
        FORMAT = "%(asctime)s | %(levelname)-8s | %(message)s"
        logging.basicConfig(filename='non.log',level=logging.DEBUG,filemode='w',format=FORMAT,datefmt="%Y-%m-%d %H:%M:%S")
        self.log = logging.getLogger(__name__)

    def on_app_activate(self,app):
        #setting up localization
        locales_dir = os.path.join(self.install_dir,'locale')
        appname = 'NoN'
        locale.bindtextdomain(appname,locales_dir)
        locale.textdomain(locales_dir)      
        gettext.bindtextdomain(appname,locales_dir)
        gettext.textdomain(appname)

        #Glade files/window configuration
        gladefile_list = ["non.glade"]

        #set up builder
        builder = Gtk.Builder()
        GObject.type_register(Vte.Terminal)

        builder.set_translation_domain(appname)
        [builder.add_from_file(f) for f in gladefile_list]
        builder.connect_signals(Handler())
        self.obj = builder.get_object
        
        window = self.obj("non_window_stack")

        window.set_application(app)
        window.set_wmclass("Knights of Ni","Knights of Ni")
        window.show_all()
        #print(window.get_preferred_size())

        self.obj("open_conf").set_sensitive(False)
        self.obj("build").set_sensitive(False)

        self.check_ninconf()
        self.add_dialogbuttons(self.obj("choose_conf_file"))
        self.add_dialogokbutton(self.obj("about_dialog"))

    def start_console(self, wdir):
        self.obj("term").spawn_sync(
            Vte.PtyFlags.DEFAULT,
            wdir,
            ["/bin/bash"],
            None,
            GLib.SpawnFlags.DEFAULT,
            None,
            None,
            )
        #prompt is detected on first emission of the 'contents changed' signal
        self.prompt = ""
        #bool variable to decide if focus should return from terminal stack child
        #True when command is invoked by button, False if command is typed directly in terminal
        self.gui_cmd = False

    def check_ninconf(self,cfile=None):
        #cfile is None on app start
        if cfile == None:
            #check for config on app start or after changing conf.py
            if os.path.isfile(os.path.join(self.install_dir,"ninconf.py")):
                self.nonconfig_file = os.path.join(self.install_dir,"ninconf.py")
                self.messenger("Found conf.py to work with")
                import ninconf
                #reloading module is required when file is changed 
                ninconf = importlib.reload(ninconf)
                self.wdir = ninconf.CURRENT_DIR
                ###### setup bookmarks in menu ######
                self.bookmarks = ninconf.BOOKMARKS
                self.obj("open_conf").set_sensitive(True)
                #remove generated bookmark menu items, otherwise when appending new bookmark all existing bookmarks are appended repeatedly
                for i in self.obj("menu").get_children():
                    #the separator item is stretched vertically when applying get_label function (which does not return any value but no error either) but I don't know how to do a GTK class comparison to exclude the separator or include the menuitems so this works fine
                    if type(i) == type(self.obj("load_conf")):
                        if i.get_label().startswith("Bookmark: "):
                            self.obj("menu").remove(i)
                #add menu items for bookmarks
                for b in sorted(self.bookmarks):
                    item=Gtk.MenuItem(_("Bookmark: %s" % b[0]))
                    item.connect("activate",self.select_bookmark,b)
                    self.obj("menu").append(item)
                    #set 'add bookmark' menu item inactive if bookmark already exists
                    if b[1] == self.wdir:
                        self.obj("add_bookmark").set_sensitive(False)
                        img = Gtk.Image.new_from_stock(Gtk.STOCK_YES,1)
                self.obj("menu").show_all()
                if len(self.bookmarks) > 0:
                    self.messenger("Found %d bookmark(s)" % len(self.bookmarks))
                else:
                    self.messenger("No bookmarks")
                #check if last wdir still exists
                try:
                    os.chdir(self.wdir)
                    self.messenger("Current Nikola folder: %s" % self.wdir)
                    #reload terminal with current wdir
                    self.obj("term").reset(True, True)
                    self.start_console(self.wdir)
                    #refresh window
                    self.get_window_content()
                except FileNotFoundError:
                    self.messenger("Last working directory isn't here anymore.","warning")
                    self.obj("choose_conf_file").show_all()
            #show file chooser dialog when no config file exists
            else:
                self.obj("choose_conf_file").show_all()
        #cfile is not None when file chooser dialog from 'choose conf.py' menu item is executed
        else:
            #save new cfile in config
            if os.path.isfile(os.path.join(self.install_dir,"ninconf.py")):
                conf_file = os.path.join(self.install_dir,"ninconf.py")
                with open(conf_file) as f:
                    content = f.readlines()
                for line in content:
                    if line == ("\n"):
                        content.remove(line)
                    elif line.startswith("CURRENT_DIR"):
                        content[content.index(line)] = "CURRENT_DIR = \"%s\"\n" % cfile
                with open(conf_file,"w") as f:
                    for line in content:
                        f.write(line)
                self.messenger("New conf.py has been saved to nonconfig.")
            #or create config and use given cfile
            else:
                self.messenger("No NON config found.","warning")
                self.create_config(cfile)
            self.check_ninconf()
    
    def add_dialogbuttons(self,dialog):
        #add cancel/apply buttons to dialog to avoid Gtk warning
        button = Gtk.Button.new_from_stock(Gtk.STOCK_CANCEL)
        button.set_property("can-default",True)
        dialog.add_action_widget(button, Gtk.ResponseType.CANCEL)
        
        button = Gtk.Button.new_from_stock(Gtk.STOCK_APPLY)
        button.set_property("can-default",True)
        dialog.add_action_widget(button, Gtk.ResponseType.OK)

    def add_dialogokbutton(self,dialog):
        #add ok button to about dialog to avoid Gtk warning
        button = Gtk.Button.new_from_stock(Gtk.STOCK_OK)
        dialog.add_action_widget(button, Gtk.ResponseType.OK)

    def select_bookmark(self,widget,b):
        self.check_ninconf(b[1])
        self.messenger("Changed to %s" % b[1])

    def create_config(self,wdir):
        config = open(os.path.join(app.install_dir,"ninconf.py"),"w")
        config.write("##### non configuration #####\nCURRENT_DIR = \"%s\"\nBOOKMARKS = set()\n" % wdir)
        config.close()
        self.messenger("Configuration file for NON has been created.")

    def get_window_content(self):
        
        """Fill main window with content"""

        self.messenger("Refresh window content")

        [self.obj(store).clear() for store in ["store_posts","store_pages","store_tags","store_cats","store_listings","store_files","store_images","store_translation"]]

        os.chdir(self.wdir)

        #check if folder for files, listings and images exist to avoid FileNotFoundError
        for subdir in ["files", "listings", "images"]:
            if not os.path.isdir(os.path.join(self.wdir,subdir)):
                self.messenger("{} doesn't exist...create...".format(subdir))
                os.mkdir(os.path.join(self.wdir,subdir))

        #load nikola conf.py as module to gain simple access to variables
        spec = importlib.util.spec_from_file_location("siteconf", os.path.join(self.wdir,"conf.py"))
        self.siteconf = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(self.siteconf)

        #labels
        self.obj("author").set_text(self.siteconf.BLOG_AUTHOR)
        self.obj("descr").set_text(self.siteconf.BLOG_DESCRIPTION)
        self.obj("title").set_text(self.siteconf.BLOG_TITLE)
        self.obj("pathlocal").set_uri("file://%s" % self.wdir)
        self.obj("pathlocal").set_label("...%s" % self.wdir[-25:])
        self.obj("pathremote").set_uri(self.siteconf.SITE_URL)
        self.obj("pathremote").set_label(self.siteconf.SITE_URL)
        #set text aligned left, should work with glade but in reality it doesn't
        self.obj("author").set_alignment(xalign=0.0, yalign=0.5)
        self.obj("descr").set_alignment(xalign=0.0, yalign=0.5)
        self.obj("title").set_alignment(xalign=0.0, yalign=0.5)
        
        #detect multilingual sites
        self.default_lang = self.siteconf.DEFAULT_LANG
        self.translation_lang = set([key for key in self.siteconf.TRANSLATIONS if key != self.default_lang])

        self.obj("lang").set_text(self.default_lang)
        self.obj("trans_lang").set_text(", ".join(str(s) for s in self.translation_lang if s != self.default_lang))
       
        ##### these variables are dictionaries ##### 
        #posts/pages
        #get info: title, slug, date, tags, category, compare to index.rst in output 
        self.posts,post_tags,post_cats = self.get_rst_content("posts")
        self.pages,page_tags,page_cats = self.get_rst_content("pages")
        #listings/files/images (not needed because of treestores but I leave these here for possible later usage)
        listings = self.get_filelist("listings")
        files = self.get_filelist("files")
        images = self.get_filelist("images")
        
        ##### add information to notebook tab datastores #####
        # posts/pages tabs are based on liststores and created from dict (see above)
        self.get_tree_data_rst("store_posts",self.posts)
        self.get_tree_data_rst("store_pages",self.pages)
        # files/listings/images are based on treestores, data rows are appended without dict usage
        self.get_tree_data("store_listings","listings")
        self.get_tree_data("store_files","files")
        self.get_tree_data("store_images","images")
        # tags/category tab
        self.get_tree_data_label(self.posts,self.pages,post_tags,page_tags,"store_tags","tags")
        self.get_tree_data_label(self.posts,self.pages,post_cats,page_cats,"store_cats","category")
        # translation tab
        self.get_tree_data_translations("store_translation",self.posts)
        self.get_tree_data_translations("store_translation",self.pages)
        
        #sort tags according to number of occurrences
        self.obj("store_tags").set_sort_column_id(4, Gtk.SortType.DESCENDING)
        self.obj("store_cats").set_sort_column_id(4, Gtk.SortType.DESCENDING)
        self.obj("store_translation").set_sort_column_id(3, Gtk.SortType.DESCENDING)
        
        #expands all rows in translation tab
        self.obj("view_translations").expand_all()
        
        #set deploy button inactive if git status returns no change
        git_status = subprocess.Popen(["git","status","-s"],universal_newlines=True,stdout=subprocess.PIPE).communicate()
        if git_status[0] == "":
            self.obj("deploy").set_sensitive(False)
        else:
            self.obj("deploy").set_sensitive(True)

    def read_rst_files(self,subdir,file):
        title,slug,date,tagstr,tags,catstr,cats = "","",datetime.datetime.today().strftime("%Y-%m-%d"),"","","",""
        rst = open(os.path.join(subdir,file),"r")
        for line in rst:
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
        rst.close()
        return title, slug, date, tagstr, tags, catstr, cats

    def compare_output_dir(self,od,subdir,filename,slug,lang):
        try:
            return filecmp.cmp(os.path.join(subdir,filename),os.path.join("output",lang,subdir,od,"index.rst"))
        except FileNotFoundError:
            return False

    def get_rst_content(self,subdir):
        d = {}
        t = set()
        c = set()
        for f in os.listdir(subdir):
            title, slug, date, tagstr, tags, catstr, cats = self.read_rst_files(subdir,f)
            #detect language
            if len(self.translation_lang) > 0:
                if f.split(".")[1] == "rst":
                    #set empty string because var is used by os.path.join which throws NameError when var is None
                    lang = ""
                else:
                    lang = f.split(".")[1]
            else:
                lang = ""
            #check for equal file in output dir, mark bold (loaded by treemodel) when False
            for od in {slug,f[:-4]}:
                if self.compare_output_dir(od,subdir,f,slug,lang):
                    fontstyle = "normal"
                    break
                else:
                    fontstyle = "bold"
                    self.obj("build").set_sensitive(True)
            #add new found tags/categories to set
            t.update(tags)
            c.update(cats)
            #mark title cell in italic font if title is missing (use slug or filename instead)
            if title == "":
                if slug == "":
                    title = f
                else:
                    title = slug
                if fontstyle == "bold":
                    fontstyle = "bold italic"
                else:
                    fontstyle = "italic"
            #add dictionary entry for file
            d[f[:-4]] =    {"title":title,
                            "slug":slug,
                            "file":f,
                            "date":date,
                            "ger_date":datetime.datetime.strptime(date, '%Y-%m-%d').strftime('%d.%m.%Y'),
                            "tags":tags,
                            "tagstr":tagstr,
                            "category":cats,
                            "catstr":catstr,
                            "fontstyle":fontstyle,
                            "sub":subdir,
                            "lang":lang,
                            "transl":set()}
        #add available translation to default file entry
        #ex: articlename.lang > lang is added to transl entry of articlename
        [d[key.split(".")[0]]["transl"].add(d[key]["lang"]) for key in d if d[key]["lang"] != ""]
        return d,t,c

    def get_tree_data_rst(self,store,dict):
        #append only default language files to treestore
        [self.obj(store).append([dict[key]["title"],
                                dict[key]["slug"],
                                dict[key]["file"],
                                dict[key]["date"],
                                dict[key]["ger_date"],
                                dict[key]["tagstr"],
                                dict[key]["catstr"],
                                dict[key]["sub"],
                                #add available translations as comma seperated string
                                #stolen from gist.github.com/23maverick23/6404685
                                ",".join(str(s) for s in dict[key]["transl"]),
                                dict[key]["fontstyle"],
                                ]) for key in dict if dict[key]["lang"] == ""]
        self.obj(store).set_sort_column_id(3,Gtk.SortType.DESCENDING)

    def get_tree_data(self,store,subdir,parent=None):
        for item in sorted(os.listdir(subdir)):
            if os.path.isfile(os.path.join(subdir,item)):
                #images are changed in size when deployed so check only for filename
                if item.endswith(('.png', '.gif', '.jpeg', '.jpg')):
                    equ = os.path.isfile(os.path.join("output",subdir,item))
                #else compare if files are equal
                else:
                    try:
                        equ = filecmp.cmp(os.path.join(subdir,item),os.path.join("output",subdir,item))
                    except FileNotFoundError:
                        equ = False
                if not equ:
                    weight = 800
                    self.obj("build").set_sensitive(True)
                else:
                    weight = 400
                self.obj(store).append(parent,[item,os.path.getsize(os.path.join(subdir,item)),self.sizeof_fmt(os.path.getsize(os.path.join(subdir,item))),weight])
            elif os.path.isdir(os.path.join(subdir,item)):
                #TODO size of folder
                if os.path.isdir(os.path.join("output",subdir,item)):
                    weight = 400
                else:
                    weight = 800
                    self.obj("build").set_sensitive(True)
                row = self.obj(store).append(parent,[item,None,None,weight])
                subsubdir = os.path.join(subdir,item)
                #read subdirs as child rows
                self.get_tree_data(store,subsubdir,row)

    def get_tree_data_label(self,post_dict,page_dict,post,page,store,label):
        #combine labels from posts and pages and remove empty string
        post.update(page)
        post.discard("")
        for item in post:
            counter = 0
            # row = title,gerdate,date,weight,counter
            row = self.obj(store).append(None,[None,None,None,800,None,None,None])
            for dict in (post_dict,page_dict):
                for key in dict:
                    if item in dict[key][label]:
                        self.obj(store).append(row,[dict[key]["title"],dict[key]["ger_date"],dict[key]["date"],400,None,dict[key]["file"],dict[key]["sub"]])
                        counter += 1
            self.obj(store).set_value(row,0,"%s (%d)" % (item,counter))
            self.obj(store).set_value(row,4,counter)

    def get_tree_data_translations(self,store,dict):
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
                                    for child in dict if dict[child]["file"].split(".")[0] == dict[key]["file"].split(".")[0] and dict[child]["lang"] != ""]

    def get_filelist(self,subdir):
        d = {}
        for root,dirs,files in sorted(os.walk(subdir)):
            for f in files:
                #images are changed in size when deployed so check only for filename
                if subdir == "images":
                    equ = os.path.isfile(os.path.join("output",root,f))
                #else compare if files are identical
                else:
                    try:
                        equ = filecmp.cmp(os.path.join(root,f),os.path.join("output",root,f))
                    except FileNotFoundError:
                        equ = False
                if equ == False:
                    weight = 800
                else:
                    weight = 400
                d[f] = {"size":os.path.getsize(os.path.join(root,f)),
                        "humansize":self.sizeof_fmt(os.path.getsize(os.path.join(root,f))),
                        "weight":weight}
        return d

    def term_cmd(self,command):
        command += "\n" 
        self.obj("term").feed_child(command.encode())

    def run_nikola_build(self):
        self.gui_cmd = True
        self.obj("stack").set_visible_child(app.obj("term"))
        self.messenger("Execute Nikola: run build process")
        self.term_cmd("nikola build")

    def run_nikola_github_deploy(self):
        self.run_nikola_build()
        self.gui_cmd = True
        self.obj("stack").set_visible_child(app.obj("term"))
        self.messenger("Execute Nikola: run deploy to GitHub command ")
        self.term_cmd("nikola github_deploy")

    def messenger(self,message,log="info"):
        """Show notifications in statusbar and log file"""
        self.obj("statusbar").push(1,message)
        time.sleep(.1)
        while Gtk.events_pending(): Gtk.main_iteration()
        logcmd = "self.log.%s(\"%s\")" % (log,message)
        exec(logcmd)

    def sizeof_fmt(self,num, suffix='B'):
        """File size shown in common units"""
        for unit in ['','K','M','G','T','P','E','Z']:
            if abs(num) < 1024.0:
                return "%3.1f %s%s" % (num, unit, suffix)
            num /= 1024.0
        return "%.1f %s%s" % (num, 'Y', suffix)

    def run(self,argv):
        self.app.run(argv)

app = NiApp()
app.run(sys.argv)

#FIXME: glade file > window height/size (this is just a reminder for myself, ignore if you are not me)
