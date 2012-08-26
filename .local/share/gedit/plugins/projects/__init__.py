# -*- coding:utf-8 -*-

#  Copyright © 2012  B. Clausius <barcc@gmx.de>
#
#  This program is free software: you can redistribute it and/or modify
#  it under the terms of the GNU General Public License as published by
#  the Free Software Foundation, either version 3 of the License, or
#  (at your option) any later version.
#
#  This program is distributed in the hope that it will be useful,
#  but WITHOUT ANY WARRANTY; without even the implied warranty of
#  MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
#  GNU General Public License for more details.
#
#  You should have received a copy of the GNU General Public License
#  along with this program.  If not, see <http://www.gnu.org/licenses/>.


import os

from gi.repository import Gedit
from gi.repository import GObject
from gi.repository import GLib
from gi.repository import Gio
from gi.repository import Gtk
from gi.repository import PeasGtk

from projects.panel import PanelHelper
from projects import config
from projects import appdata
from projects.idle import IdleHelper, Priority


if hasattr(Gedit.MessageBus, 'send'):
    def send_message(window, object_path, method, **kwargs):
        return window.get_message_bus().send(object_path, method, **kwargs)
else:
    # For installations that do not have the Gedit.py override file
    def send_message(window, object_path, method, **kwargs):
        bus = window.get_message_bus()
        tp = bus.lookup(object_path, method)
        if not tp.is_a(Gedit.Message.__gtype__):
            return None
        kwargs['object-path'] = object_path
        kwargs['method'] = method
        msg = GObject.new(tp, **kwargs)
        bus.send_message(msg)
        return msg
        

class ProjectsWindow(GObject.Object, Gedit.WindowActivatable, PeasGtk.Configurable, IdleHelper):
    __gtype_name__ = "ProjectsWindow"
    window = GObject.property(type=Gedit.Window)
    app_data = None
    
    def __init__(self):
        GObject.Object.__init__(self)
        IdleHelper.__init__(self)
        self.panel_helper = None
        self.handlers = []
        self.uimanager = None
        self.recent_merge_id = None
        self.actiongroup_recent = None
        
    def do_activate(self):
        if self.app_data is None:
            try:
                self.__class__.app_data = appdata.ApplicationData()
            except config.GSettingsSchemaNotFound:
                dialog = Gtk.MessageDialog(self.window,
                                     Gtk.DialogFlags.DESTROY_WITH_PARENT,
                                     Gtk.MessageType.ERROR,
                                     Gtk.ButtonsType.CLOSE)
                dialog.props.text = 'GSettings schema for the Projects Plugin is not installed.'
                dialog.props.secondary_text = (
                        "If you've installed the plugin manually (and this is most likely"
                        " the case if you see this message), you should read the file"
                        " README.install file included with this plugin on how to install"
                        " the schema. After that you have to restart gedit.")
                dialog.run()
                dialog.destroy()
                return
        
        self.uimanager = self.window.get_ui_manager()
        self.panel_helper = PanelHelper(self.app_data, self.uimanager)
        self.app_data.config.action_info = self.panel_helper.get_action_info()
        
        icon = Gtk.Image.new_from_icon_name('applications-development', Gtk.IconSize.MENU)
        panel = self.window.get_side_panel()
        panel.add_item(self.panel_helper.widget, "ProjectsSidePanel", "Projects", icon)
        
        self._connect('tab-added', self.on_window_tab_added)
        self._connect('active-tab-changed', self.on_window_tab_changed)
        self._connect('tab-removed', self.on_window_tab_removed)
        self._connect("delete-event", self.on_window_delete_event)
        # or focus-in-event?
        self._connect("notify::is-active", self.on_window_notify_is_active)
        self.app_data.config.settings.connect('changed::max-recents', self.on_settings_changed_max_recents)
        
        menu = self.uimanager.get_widget('/MenuBar/ExtraMenu_1/ProjectsPluginMenu')
        for menuitem in menu.get_submenu().get_children():
            action = menuitem.get_related_action()
            if action is not None:
                action.connect('activate', self.on_menu_action)
        self.recent_merge_id = self.uimanager.new_merge_id()
        self.actiongroup_recent = Gtk.ActionGroup('actiongroup_recent_projects')
        self.uimanager.insert_action_group(self.actiongroup_recent)
        for i in range(self.app_data.config.max_recents_range[1]):
            action_name = 'action_recent_%d' % i
            action = Gtk.Action(action_name, None, None, None)
            action.connect('activate', self.on_action_recent_project)
            self.actiongroup_recent.add_action(action)
            self.uimanager.add_ui(self.recent_merge_id,
                                '/MenuBar/ExtraMenu_1/ProjectsPluginMenu/project_recent',
                                'project_recent_%d' % i,
                                action_name,
                                Gtk.UIManagerItemType.AUTO, False)
        self.app_data.connect('close-project', self.on_app_data_close_project)
        self.panel_helper.connect('open-file', self.on_panel_open_file)
        self.panel_helper.connect('open-project', self.on_panel_open_project)
        self.panel_helper.connect('add-directory', self.on_panel_add_directory)
        self.panel_helper.connect('move-to-new-window', self.on_panel_move_to_new_window)
        self.app_data.connect('reassign-project', self.on_app_data_reassign_project)
        
        self._update_recent_menu()
        
        # this is necessary if activated via plugin manager
        for doc in self.window.get_documents():
            tab = Gedit.Tab.get_from_document(doc)
            doc.connect('notify::location', self.on_document_notify_location)
            self._init_new_tab(tab, doc)
        tab = self.window.get_active_tab()
        if tab:
            self._init_active_tab(tab)
        
    def do_deactivate(self):
        IdleHelper.deactivate(self)
        self._disconnect_all()
        if self.app_data is None:
            return
        
        self.uimanager.remove_ui(self.recent_merge_id)
        self.uimanager.remove_action_group(self.actiongroup_recent)
        self.actiongroup_recent = None
        panel = self.window.get_side_panel()
        panel.remove_item(self.panel_helper.widget)
        self.panel_helper.deactivate()
        self.panel_helper = None
        
        if len(Gedit.App.get_default().get_windows()) <= 1:
            self.app_data.deactivate()
            self.__class__.app_data = None
        
    #def do_update_state(self):
    #    pass
        
    def do_create_configure_widget(self):
        return self.app_data.config.create_widget(self.window)
        
    def _connect(self, signal, func):
        self.handlers.append(self.window.connect(signal, func))
    def _disconnect_all(self):
        for handler in self.handlers:
            self.window.disconnect(handler)
        self.handlers = []
        
    def _update_recent_menu(self):
        max_recents = self.app_data.config.max_recents
        for action in self.actiongroup_recent.list_actions():
            i = int(action.props.name.rsplit('_', 1)[1])
            if i >= max_recents:
                action.props.visible = False
                continue
            try:
                projectpath = self.app_data.config.recent_projects[i]
            except IndexError:
                projectpath = None
            if projectpath:
                action.props.label = Gedit.utils_replace_home_dir_with_tilde(projectpath)
            action.props.visible = bool(projectpath)
            
    def _init_new_tab(self, tab, doc):
        location = doc and doc.get_location()
        filepath = location and location.get_path()
        if filepath is not None:
            try:
                projectpath = self.app_data.add_filename(filepath)
            except appdata.NotReady:
                tab.set_data('projectpath', False)
                self.idle_add(self._init_new_tab, tab, doc, priority=Priority.new_tab)
            else:
                tab.set_data('projectpath', projectpath)
                tab.set_data('filepath', filepath)
                recent_projects = self.app_data.config.recent_projects
                if projectpath:
                    if projectpath in recent_projects:
                        recent_projects.remove(projectpath)
                    recent_projects.insert(0, projectpath)
                    max_recents_max = self.app_data.config.max_recents_range[1]
                    del recent_projects[max_recents_max:]
                    if recent_projects != self.app_data.config.recent_projects:
                        self.app_data.config.recent_projects = recent_projects
                self._update_recent_menu()
                
    def on_window_tab_added(self, unused_window, tab):
        doc = tab.get_document()
        doc.connect('notify::location', self.on_document_notify_location)
        self._init_new_tab(tab, doc)
        
    def _init_active_tab(self, tab):
        projectpath = tab.get_data('projectpath')
        if projectpath is None:
            # file not part of a project
            self.panel_helper.set_active_project(None)
        elif not projectpath:
            # not ready
            self.idle_add(self._init_active_tab, tab, priority=Priority.active_tab)
        else:
            doc = tab.get_document()
            location = doc and doc.get_location()
            filename = location and location.get_path()
            self.app_data.config.get_project(projectpath).active_file = filename
            self.app_data.config.projects_modified()
            self.panel_helper.set_active_project(projectpath)
            
    def on_window_tab_changed(self, unused_window, tab):
        self._init_active_tab(tab)
        
    def _remove_if_unused(self, projectpath, filepath=None):
        app = Gedit.App.get_default()
        cnt_files = 0
        cnt_projects = 0
        for doc in app.get_documents():
            loc = doc.get_location()
            if loc and loc.get_path() == filepath:
                cnt_files += 1
            tab = Gedit.Tab.get_from_document(doc)
            if tab.get_data('projectpath') == projectpath:
                cnt_projects += 1
        if filepath is not None and not cnt_files:
            self.app_data.remove_filename(projectpath, filepath)
        if not cnt_projects:
            self.app_data.remove_from_open_projects(projectpath)
        
    def on_window_tab_removed(self, unused_window, tab):
        projectpath = tab.get_data('projectpath')
        if not projectpath:
            return
        doc = tab.get_document()
        location = doc and doc.get_location()
        filepath = location and location.get_path()
        if filepath is None:
            return
        self._remove_if_unused(projectpath, filepath)
        
    def on_window_delete_event(self, unused_window, unused_event):
        self._disconnect_all()
        app = Gedit.App.get_default()
        if len(app.get_windows()) <= 1:
            return
        for wdoc in self.window.get_documents():
            projectpath = Gedit.Tab.get_from_document(wdoc).get_data('projectpath')
            if not projectpath:
                continue
            for window in app.get_windows():
                if window == self.window:
                    continue
                for doc in window.get_documents():
                    if Gedit.Tab.get_from_document(doc).get_data('projectpath') == projectpath:
                        break
                else:
                    continue
                break
            else:
                self.app_data.remove_from_open_projects(projectpath)
                
    def on_window_notify_is_active(self, window, unused_paramspec):
        if window.props.is_active:
            tab = window.get_active_tab()
            if tab:
                self._init_active_tab(tab)
            
    def on_document_notify_location(self, doc, param):
        tab = Gedit.Tab.get_from_document(doc)
        #TODO: is the filepath thing really needed?
        filepath = tab.get_data('filepath')
        location = doc.get_location()
        filepath_new = location and location.get_path()
        if filepath != filepath_new:
            projectpath = tab.get_data('projectpath')
            try:
                projectpath_new = self.app_data.add_filename(filepath_new)
            except appdata.NotReady:
                tab.set_data('projectpath', False)
                self.idle_add(self.on_document_notify_location, doc, param, priority=Priority.new_tab)
            else:
                tab.set_data('projectpath', projectpath_new)
                tab.set_data('filepath', filepath_new)
                if projectpath:
                    self._remove_if_unused(projectpath, filepath)
                if not projectpath_new:
                    pass
                elif self.window.get_active_tab() == tab:
                    self.app_data.config.get_project(projectpath_new).active_file = filepath_new
                    self.app_data.config.projects_modified()
                    self.panel_helper.set_active_project(projectpath_new)
                elif projectpath_new == projectpath:
                    project = self.app_data.config.get_project(projectpath_new)
                    if project.active_file == filepath:
                        project.active_file = filepath_new
                        self.app_data.config.projects_modified()
                        
    def _open_file(self, window, filename, jump_to):
        location = Gio.File.new_for_path(filename)
        tab = window.get_tab_from_location(location)
        if tab is None:
            tab = window.create_tab_from_location(location, None, 0, 0, False, jump_to)
        elif jump_to:
            window.set_active_tab(tab)
        if jump_to:
            self.idle_add(tab.get_view().grab_focus)
        
    def on_menu_action(self, action):
        tab = self.window.get_active_tab()
        projectpath = tab and tab.get_data('projectpath')
        if projectpath:
            self.panel_helper.action_func[action.get_name()](self.panel_helper, projectpath)
            
    def on_action_recent_project(self, action):
        i = int(action.props.name.rsplit('_', 1)[1])
        projectpath = self.app_data.config.recent_projects[i]
        if projectpath:
            self.panel_helper.action_func['action_open_project'](self.panel_helper, projectpath)
            
    def on_panel_open_file(self, unused_panel, dirname):
        dialog = Gtk.FileChooserDialog("Open File",
                                      self.window,
                                      Gtk.FileChooserAction.OPEN,
                                      [Gtk.STOCK_CANCEL, Gtk.ResponseType.CANCEL,
                                      Gtk.STOCK_OPEN, Gtk.ResponseType.ACCEPT])
        dialog.set_current_folder(dirname)
        if dialog.run() == Gtk.ResponseType.ACCEPT:
            filename = dialog.get_filename()
            self._open_file(self.window, filename, jump_to=True)
        dialog.destroy()
        
    def on_panel_add_directory(self, unused_panel, dirname):
        dialog = Gtk.FileChooserDialog("Add Folder",
                                      self.window,
                                      Gtk.FileChooserAction.SELECT_FOLDER,
                                      [Gtk.STOCK_CANCEL, Gtk.ResponseType.CANCEL,
                                      Gtk.STOCK_OPEN, Gtk.ResponseType.ACCEPT])
        dialog.set_current_folder(dirname)
        if dialog.run() == Gtk.ResponseType.ACCEPT:
            filename = dialog.get_filename()
            if filename and os.path.isdir(filename):
                self.app_data.add_project(filename)
        dialog.destroy()
        
    def on_panel_open_project(self, unused_panel, projectpath, newwindow):
        try:
            project = self.app_data.config.get_project(projectpath)
        except KeyError:
            #TODO: Remove the item that caused the exception
            # Happens if Projects-menuitem activated (GSettings) that is not
            # a known project (stored in file).
            # * config file was removed or replace with an older version
            # * Project was removed from side pane
            return
        self.app_data.config.projects_modified()
        if newwindow:
            window = Gedit.App.get_default().create_window(None)
            window.show()
        else:
            window = self.window
        # project.files may be modified in on_window_tab_added inside the loop, so use a copy
        for filename in project.files[:]:
            if not os.path.exists(filename):
                project.files.remove(filename)
        if project.active_file and not os.path.exists(project.active_file):
            project.active_file = None
        if project.files:
            if project.active_file not in project.files:
                project.active_file = project.files and project.files[-1]
        elif project.active_file:
            project.files.append(project.active_file)
        for filename in project.files[:]:
            if os.path.exists(filename):
                self._open_file(window, filename, jump_to=(filename == project.active_file))
        if self.app_data.config.filebrowser_set_root_on_project_open:
            location = Gio.File.new_for_path(projectpath)
            send_message(window, '/plugins/filebrowser', 'set_root', location=location)
            
    def on_app_data_close_project(self, unused_app_data, projectpath):
        tabs = []
        for doc in self.window.get_documents():
            tab = Gedit.Tab.get_from_document(doc)
            if tab.get_data('projectpath') == projectpath:
                tab.set_data('projectpath', None)
                tabs.append(tab)
        # Now that projectpath is removed from the tabs, the handlers
        # on_window_tab_removed and on_window_tab_changed will not modify
        # project metadata.
        self.app_data.remove_from_open_projects(projectpath)
        for tab in tabs:
            self.window.close_tab(tab)
            
    def on_panel_move_to_new_window(self, panel, projectpath):
        self.app_data.emit('close-project', projectpath)
        self.on_panel_open_project(panel, projectpath, True)
        
    def on_app_data_reassign_project(self, unused_app_data, old_projectpath):
        for doc in self.window.get_documents():
            tab = Gedit.Tab.get_from_document(doc)
            if tab.get_data('projectpath') == old_projectpath:
                tab.set_data('projectpath', None)
                self._remove_if_unused(old_projectpath)
                self._init_new_tab(tab, doc)
                
    def on_settings_changed_max_recents(self, unused_settings, unused_key):
        self._update_recent_menu()
        
