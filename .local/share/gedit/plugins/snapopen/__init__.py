from gi.repository import GObject, Gedit, Gtk, Gio, Gdk
import os, os.path
from urllib.request import pathname2url
import tempfile

max_result = 50
app_string = "Snap open"

def send_message(window, object_path, method, **kwargs):
    return window.get_message_bus().send_sync(object_path, method, **kwargs)

ui_str="""<ui>
<menubar name="MenuBar">
    <menu name="FileMenu" action="File">
        <placeholder name="FileOps_2">
            <menuitem name="SnapOpen" action="SnapOpenAction"/>
        </placeholder>
    </menu>
</menubar>
</ui>
"""

# essential interface
class SnapOpenPluginInstance:
    def __init__( self, plugin, window ):
        self._window = window
        self._plugin = plugin
        self._dirs = [] # to be filled
        self._tmpfile = os.path.join(tempfile.gettempdir(), 'snapopen.%s.%s' % (os.getuid(),os.getpid()))
        self._show_hidden = False
        self._liststore = None;
        self._init_ui()
        self._insert_menu()

    def deactivate( self ):
        self._remove_menu()
        self._action_group = None
        self._window = None
        self._plugin = None
        self._liststore = None;
        os.popen('rm %s &> /dev/null' % (self._tmpfile))

    def update_ui( self ):
        return

    # MENU STUFF
    def _insert_menu( self ):
        manager = self._window.get_ui_manager()
        self._action_group = Gtk.ActionGroup( "SnapOpenPluginActions" )
        self._action_group.add_actions([
            ("SnapOpenAction", Gtk.STOCK_OPEN, "Snap open...",
             '<Ctrl><Alt>O', "Open file by autocomplete",
             lambda a: self.on_snapopen_action())
        ])

        manager.insert_action_group(self._action_group)
        self._ui_id = manager.add_ui_from_string(ui_str)

    def _remove_menu( self ):
        manager = self._window.get_ui_manager()
        manager.remove_ui( self._ui_id )
        manager.remove_action_group( self._action_group )
        manager.ensure_update()

    # UI DIALOGUES
    def _init_ui( self ):
        filename = os.path.dirname( __file__ ) + "/snapopen.ui"
        self._builder = Gtk.Builder()
        self._builder.add_from_file(filename)

        #setup window
        self._snapopen_window = self._builder.get_object('SnapOpenWindow')
        self._snapopen_window.connect("key-release-event", self.on_window_key)
        self._snapopen_window.set_transient_for(self._window)

        #setup buttons
        self._builder.get_object( "ok_button" ).connect( "clicked", self.open_selected_item )
        self._builder.get_object( "cancel_button" ).connect( "clicked", lambda a: self._snapopen_window.hide())

        #setup entry field
        self._glade_entry_name = self._builder.get_object( "entry_name" )
        self._glade_entry_name.connect("key-release-event", self.on_pattern_entry)

        #setup list field
        self._hit_list = self._builder.get_object( "hit_list" )
        self._hit_list.connect("select-cursor-row", self.on_select_from_list)
        self._hit_list.connect("button_press_event", self.on_list_mouse)
        self._liststore = Gtk.ListStore(str, str)
        self._liststore.set_sort_column_id(0, Gtk.SortType.ASCENDING)

        self._hit_list.set_model(self._liststore)
        column = Gtk.TreeViewColumn("Name" , Gtk.CellRendererText(), text=0)
        column.set_sizing(Gtk.TreeViewColumnSizing.AUTOSIZE)
        column2 = Gtk.TreeViewColumn("File", Gtk.CellRendererText(), text=1)
        column2.set_sizing(Gtk.TreeViewColumnSizing.AUTOSIZE)
        self._hit_list.append_column(column)
        self._hit_list.append_column(column2)
        self._hit_list.get_selection().set_mode(Gtk.SelectionMode.MULTIPLE)

    #mouse event on list
    def on_list_mouse( self, widget, event ):
        if event.type == Gdk.EventType._2BUTTON_PRESS:
            self.open_selected_item( event )

    #key selects from list (passthrough 3 args)
    def on_select_from_list(self, widget, event):
        self.open_selected_item(event)

    #keyboard event on entry field
    def on_pattern_entry( self, widget, event ):
        oldtitle = self._snapopen_window.get_title().replace(" * too many hits", "")

        if event.keyval == Gdk.KEY_Return:
            self.open_selected_item( event )
            return
        pattern = self._glade_entry_name.get_text()
        pattern = pattern.replace(" ",".*")
        cmd = ""
        if self._show_hidden:
            filefilter = ""
        if len(pattern) > 0:
            # To search by name
            cmd = "grep -i -m %d -e '%s' %s 2> /dev/null" % (max_result, pattern, self._tmpfile)
            self._snapopen_window.set_title("Searching ... ")
        else:
            self._snapopen_window.set_title("Enter pattern ... ")
        #print cmd

        self._liststore.clear()
        maxcount = 0
        print(cmd)
        hits = os.popen(cmd).readlines()
        for file in hits:
            file = file.rstrip().replace("./", "") #remove cwd prefix
            name = os.path.basename(file)
            self._liststore.append([name, file])
            if maxcount > max_result:
                break
            maxcount = maxcount + 1
        if maxcount > max_result:
            oldtitle = oldtitle + " * too many hits"
        self._snapopen_window.set_title(oldtitle)

        selected = []
        self._hit_list.get_selection().selected_foreach(self.foreach, selected)

        if len(selected) == 0:
            iter = self._liststore.get_iter_first()
            if iter != None:
                self._hit_list.get_selection().select_iter(iter)

    def get_git_base_dir( self, path ):
        """ Get git base dir if given path is inside a git repo. None otherwise. """
        try:
            cmd = "cd '%s' 2> /dev/null; git rev-parse --show-toplevel 2> /dev/null" % path
            print(cmd)
            gitdir = os.popen(cmd).readlines()
        except:
            gitdir = ''
        if len(gitdir) > 0:
            return gitdir[0].replace("\n","")
        return None

    def map_to_git_base_dirs( self ):
        """ Replace paths with respective git repo base dirs if it exists """
        # use git repo base dir is more suitable if we are inside a git repo, for any dir we have guessed before
        dirs = []
        for d in self._dirs:
            gitdir = self.get_git_base_dir(d)
            if gitdir is None:
                dirs.append(d)
            else:
                dirs.append(gitdir)
        self._dirs = dirs
        # we could have introduced duplicates here
        self.ensure_unique_entries()

    def ensure_unique_entries( self ):
        """ Remove duplicates from dirs list """
        # this also looks for paths already included in other paths
        unique = []
        for d in self._dirs:
            d = d.replace("file://","").replace("//","/")
            should_append = True
            for i,u in enumerate(unique): # replace everyone with its wider parent
                if u in d: # already this one, or a parent
                    should_append = False
                elif d in u: # replace with the parent
                    unique[i] = d
                    should_append = False

            if should_append:
                unique.append(d)

        self._dirs = set(unique)

    def get_dirs_string( self ):
        """ Gets the quoted string built with dir list, ready to be passed on to 'find' """
        string = ''
        for d in self._dirs:
            string += "'%s' " % d
        return string

    #on menuitem activation (incl. shortcut)
    def on_snapopen_action( self ):
        self._init_ui()

        # build paths list
        self._dirs = []

        # append current local open files dirs
        for doc in self._window.get_documents():
            location = doc.get_location()
            if location and doc.is_local():
                self._dirs.append( location.get_parent().get_uri() )

        # append filebrowser root if available
        fbroot = self.get_filebrowser_root()
        if fbroot != "" and fbroot is not None:
            self._dirs.append(fbroot)

        # ensure_unique_entries is executed after mapping to git base dir
        # but it's cheaper, then do it before too, avoiding extra work
        self.ensure_unique_entries()

        # replace each path with its git base dir if exists
        self.map_to_git_base_dirs()

        # append gedit dir (usually too wide for a quick search) if we have nothing so far
        if len(self._dirs) == 0:
            self._dirs = [ os.getcwd() ]

        # build filters list
        #modify lines below as needed, these defaults work pretty well
        filters = " ! -iname '*.jpg' ! -iname '*.jpeg' ! -iname '*.gif' ! -iname '*.png' ! -iname '*.psd' ! -iname '*.tif' "
        filters += " ! -path '*.svn*' ! -path '*.git*' "
        filters += " ! -iname '*.o' ! -iname '*.so' ! -iname '*.lo' ! -iname '*.Plo' ! -iname '*.a' ! -iname '*.pyc' "
        filters += " ! -iname '*~' ! -iname '*.swp' "

        # cache the file list in the background
        cmd = "find %s -type f %s > %s 2> /dev/null &" % (self.get_dirs_string(), filters, self._tmpfile)
        print(cmd)
        os.popen(cmd)

        self._snapopen_window.show()
        self._glade_entry_name.select_region(0,-1)
        self._glade_entry_name.grab_focus()

    #on any keyboard event in main window
    def on_window_key( self, widget, event ):
        if event.keyval == Gdk.KEY_Escape:
            self._snapopen_window.hide()

    def foreach(self, model, path, iter, selected):
        selected.append(model.get_value(iter, 1))

    #open file in selection and hide window
    def open_selected_item( self, event ):
        selected = []
        self._hit_list.get_selection().selected_foreach(self.foreach, selected)
        for selected_file in    selected:
            self._open_file ( selected_file )
        self._snapopen_window.hide()

    #gedit < 2.16 version (get_tab_from_uri)
    def old_get_tab_from_uri(self, window, uri):
        docs = window.get_documents()
        for doc in docs:
            if doc.get_uri() == uri:
                return gedit.tab_get_from_document(doc)
        return None

    #opens (or switches to) the given file
    def _open_file( self, filename ):
        #uri      = self._rootdir + "/" + pathname2url(filename)
        uri      = "file:///" + pathname2url(filename)
        gio_file = Gio.file_new_for_uri(uri)
        tab = self._window.get_tab_from_location(gio_file)
        if tab == None:
            tab = self._window.create_tab_from_location( gio_file, None, 0, 0, False, False )
        self._window.set_active_tab( tab )

    # filebrowser integration
    def get_filebrowser_root(self):
        res = send_message(self._window, '/plugins/filebrowser', 'get_root')
        if res.location is not None:
            return res.location.get_path()

# STANDARD PLUMMING
class SnapOpenPlugin(GObject.Object, Gedit.WindowActivatable):
    __gtype_name__ = "SnapOpenPlugin"
    DATA_TAG = "SnapOpenPluginInstance"

    window = GObject.property(type=Gedit.Window)

    def __init__(self):
        GObject.Object.__init__(self)

    def _get_instance( self ):
        return self.window.DATA_TAG

    def _set_instance( self, instance ):
        self.window.DATA_TAG = instance

    def do_activate( self ):
        self._set_instance( SnapOpenPluginInstance( self, self.window ) )

    def do_deactivate( self ):
        if self._get_instance():
            self._get_instance().deactivate()
        self._set_instance( None )

    def do_update_ui( self ):
        self._get_instance().update_ui()
