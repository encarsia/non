#!/usr/bin/env python
# -*- coding: utf-8 -*-

import os
import datetime
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
    from gi.repository import Gtk,Vte,GObject,GLib
except:
    print(_("Unable to load Python bindings for GObject Introspection."))
    raise

class Handler:
    """Signal assignment for Glade"""
    
    ############ close/destroy  window ############
    
    def on_non_window_destroy(self,*args):
        Gtk.main_quit()

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
            self.serve = subprocess.Popen(["nikola","serve","-b"])
        else:
            #stop local server when untoggling button
            self.serve.kill()

    def on_build_clicked(self,widget):
        subprocess.run(["nikola","build"])
        app.get_window_content()

    def on_deploy_clicked(self,widget):
        subprocess.run(["nikola","build"])
        app.obj("term").spawn_sync(
            Vte.PtyFlags.DEFAULT,
            None,
            ["/bin/bash"],
            None,
            GLib.SpawnFlags.DEFAULT,
            None,
            None,
            )        
        app.obj("terminal_win").show_all()
        app.term_cmd("nikola github_deploy")
        app.get_wdir_info()

    def on_refresh_clicked(self,widget):
        app.get_window_content()

    ############ vte terminal ########################

    def on_term_contents_changed(self,widget):
        #close window if successfully deployed, otherwise window has to be exited manually
        if "INFO: github_deploy: Successful deployment" in widget.get_text()[0]:
            self.on_term_child_exited(app.obj("terminal_win"))

    def on_term_child_exited(self,widget,*args):
        app.obj("term").reset(True,True)
        self.on_window_close(app.obj("terminal_win"))

    ########### headerbar #########################

    def on_info_button_clicked(self,widget):
        app.obj("about_dialog").show_all()

    def on_open_conf_activate(self,widget):
        subprocess.run(['xdg-open',os.path.join(app.wdir,"conf.py")])

    def on_load_conf_activate(self,widget):
        app.obj("choose_conf_file").show_all()

    ############### filechooser dialog ############

    def on_choose_conf_file_file_activated(self,widget):
        self.on_choose_conf_file_response(widget,0)
        #app.create_config(os.path.split(widget.get_filename())[0])
        #self.on_window_close(widget)

    def on_choose_conf_file_response(self,widget,response):
        if response == 0:
            try:
                if os.path.split(widget.get_filename())[1] == "conf.py":
                    app.create_config(os.path.split(widget.get_filename())[0])
                    app.check_ninstance()
                else:
                    app.obj("config_info").show_all()
            except AttributeError:
                app.obj("config_info").show_all()
        else:
            app.obj("config_info").show_all()
        self.on_window_close(widget)

    ############### new post dialog ############

    def on_newpost_dialog_response(self,widget,response):
        if response == 0:
            if app.obj("newpost_entry").get_text() == "":
                app.obj("entry_message").set_text("Title must not be empty.")
                app.obj("newpost_entry").grab_focus()
            else:
                self.on_window_close(widget)
                subprocess.run(["nikola","new_post","--title=%s" % app.obj("newpost_entry").get_text()])
                app.get_window_content()
        else:
            self.on_window_close(widget)

    def on_newpost_entry_activate(self,widget):
        self.on_newpost_dialog_response(app.obj("newpost_dialog"),0)


    ################ treeview rows activated ###############

    #open files on doubleclick

    def on_view_posts_row_activated(self,widget,*args):
        row,pos = app.obj("selection_post").get_selected()
        print("row:",type(row))
        print("pos:",type(pos))
        subprocess.run(['xdg-open',os.path.join(app.wdir,row[pos][8],row[pos][2])])

    def on_view_pages_row_activated(self,widget,*args):
        row,pos = app.obj("selection_page").get_selected()
        subprocess.run(['xdg-open',os.path.join(app.wdir,row[pos][8],row[pos][2])])
        
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


class NiApp:
    
    def __init__(self):

        #get current directory
        self.install_dir = os.getcwd()

        #set up logging
        FORMAT = "%(asctime)s %(funcName)-14s %(lineno)d| %(levelname)-8s | %(message)s"
        logging.basicConfig(filename='non.log',level=logging.DEBUG,filemode='w',format=FORMAT,datefmt="%H:%M:%S")
        self.log = logging.getLogger(__name__)

        #Glade files/window configuration
        gladefile_list = ["non.glade"]

        #setting up localization
        locales_dir = os.path.join(self.install_dir,'locale')
        appname = 'NON'
        locale.bindtextdomain(appname,locales_dir)
        locale.textdomain(locales_dir)      
        gettext.bindtextdomain(appname,locales_dir)
        gettext.textdomain(appname)

        #set up builder
        builder = Gtk.Builder()
        GObject.type_register(Vte.Terminal)

        builder.set_translation_domain(appname)
        [builder.add_from_file(f) for f in gladefile_list]
        builder.connect_signals(Handler())
        self.obj = builder.get_object
        self.obj("non_window").show_all()
        self.obj("open_conf").set_sensitive(False)
        self.obj("build").set_sensitive(False)

    def get_window_content(self):
        
        """Fill main window with content"""
        [self.obj(store).clear() for store in ["store_posts","store_pages","store_tags","store_cats","store_listings","store_files","store_images"]]
        self.get_wdir_info()

    def check_ninstance(self):
        if os.path.isfile(os.path.join(self.install_dir,"ninstance.py")):
            import ninstance
            self.wdir = ninstance.CURRENT_DIR
            self.obj("open_conf").set_sensitive(True)
            self.get_window_content()
        else:
            self.obj("choose_conf_file").show_all()

    def create_config(self,wdir):
        config = open(os.path.join(app.install_dir,"ninstance.py"),"w")
        config.write("##### working directory #####\nCURRENT_DIR = \"%s\"\n" % wdir)
        config.close()

    def get_wdir_info(self):
        os.chdir(self.wdir)
        #load nikola conf.py as module to gain simple access to variables
        spec = importlib.util.spec_from_file_location("siteconf", os.path.join(self.wdir,"conf.py"))
        siteconf = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(siteconf)
        #labels
        self.obj("author").set_text(siteconf.BLOG_AUTHOR)
        self.obj("descr").set_text(siteconf.BLOG_DESCRIPTION)
        self.obj("title").set_text(siteconf.BLOG_TITLE)
        self.obj("pathlocal").set_uri("file://%s" % self.wdir)
        self.obj("pathlocal").set_label("...%s" % self.wdir[-25:])
        self.obj("pathremote").set_uri(siteconf.SITE_URL)
        self.obj("pathremote").set_label(siteconf.SITE_URL)
        
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
        # tags/category tabs
        self.get_tree_data_label(self.posts,self.pages,post_tags,page_tags,"store_tags","tags")
        self.get_tree_data_label(self.posts,self.pages,post_cats,page_cats,"store_cats","category")
        
        #sort tags according to number of occurrences
        self.obj("sort_tags").set_sort_column_id(4, Gtk.SortType.DESCENDING)
        self.obj("sort_cats").set_sort_column_id(4, Gtk.SortType.DESCENDING)
        
        #set deploy button inactive if git status returns no change
        git_status = subprocess.Popen(["git","status","-s"],universal_newlines=True,stdout=subprocess.PIPE).communicate()
        if git_status[0] == "":
            self.obj("deploy").set_sensitive(False)
    
    def get_rst_content(self,subdir):
        d = {}
        t = set()
        c = set()
        for f in os.listdir(subdir):
            rst = open(os.path.join(subdir,f),"r")
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
            #check output subdir whether files are equal
            try:
                equ = filecmp.cmp(os.path.join(subdir,f),os.path.join("output",subdir,slug,"index.rst"))
            except FileNotFoundError:
                try:
                    equ = filecmp.cmp(os.path.join(subdir,f),os.path.join("output",subdir,f[:-4],"index.rst"))
                except FileNotFoundError:
                    equ = False
            if equ == False:
                weight = 800
                self.obj("build").set_sensitive(True)
            else:
                weight = 400
            #add new found tags/categories to set
            t.update(tags)
            c.update(cats)
            d[f[:-4]] =    {"title":title,
                            "slug":slug,
                            "file":f,
                            "date":date,
                            "ger_date":datetime.datetime.strptime(date, '%Y-%m-%d').strftime('%d.%m.%Y'),
                            "tags":tags,
                            "tagstr":tagstr,
                            "category":cats,
                            "catstr":catstr,
                            "status":equ,
                            "weight":weight,
                            "sub":subdir}
        return d,t,c

    def get_tree_data_rst(self,store,dict):
        #append(["title","slug","file","date","ger_date",
        #       "tags","category","weight","sub"])
        for key in dict:
            self.obj(store).append([dict[key]["title"],
                                    dict[key]["slug"],
                                    dict[key]["file"],
                                    dict[key]["date"],
                                    dict[key]["ger_date"],
                                    dict[key]["tagstr"],
                                    dict[key]["catstr"],
                                    dict[key]["weight"],
                                    dict[key]["sub"]])
        self.obj(store).set_sort_column_id(3,Gtk.SortType.DESCENDING)

    def get_tree_data(self,store,subdir,parent=None):
        for item in sorted(os.listdir(subdir)):
            if os.path.isfile(os.path.join(subdir,item)):
                #images are changed in size when deployed so check only for filename
                if item.endswith(".png"):
                    equ = os.path.isfile(os.path.join("output",subdir,item))
                #else compare if files are equal
                else:
                    try:
                        equ = filecmp.cmp(os.path.join(subdir,item),os.path.join("output",subdir,item))
                    except FileNotFoundError:
                        equ = False
                if equ == False:
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
        app.obj("term").feed_child(command,len(command))
    
    def sizeof_fmt(self,num, suffix='B'):
        """File size shown in common units"""
        for unit in ['','K','M','G','T','P','E','Z']:
            if abs(num) < 1024.0:
                return "%3.1f %s%s" % (num, unit, suffix)
            num /= 1024.0
        return "%.1f %s%s" % (num, 'Y', suffix)
    
    def main(self):
        Gtk.main()

app = NiApp()
app.check_ninstance()
#app.get_window_content()
app.main()

