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

import os, sys

from gi.repository import GLib
from gi.repository import GObject
from gi.repository import Gio
from gi.repository import Gdk
from gi.repository import Gtk

from projects.idle import IdleHelper

DATA_DIR = os.path.dirname(__file__)


class PanelHelper(GObject.GObject, IdleHelper):
    __gsignals__ = {
        'open-file': (GObject.SignalFlags.RUN_FIRST, None, (str,)),
        'add-directory': (GObject.SignalFlags.RUN_FIRST, None, (str,)),
        'open-project': (GObject.SignalFlags.RUN_FIRST, None, (str, bool)),
        'move-to-new-window': (GObject.SignalFlags.RUN_FIRST, None, (str,)),
    }
    
    def __init__ (self, app_data, uimanager):
        GObject.GObject.__init__ (self)
        IdleHelper.__init__(self)
        self.app_data = app_data
        
        builder = Gtk.Builder()
        builder.add_from_file(os.path.join(DATA_DIR, 'projects.ui'))
        builder.connect_signals(self)
        
        self.widget = builder.get_object('widget_projects')
        self.treeview_open = builder.get_object('treeview_open_projects')
        self.treeview_open.connect('button_press_event', self.on_treeview_projects_button_press_event)
        self.treeview_open.connect('row-activated', self.on_treeview_projects_row_activated)
        self.treeview = builder.get_object('treeview_projects')
        self.treeview.connect('button_press_event', self.on_treeview_projects_button_press_event)
        self.treeview.connect('row-activated', self.on_treeview_projects_row_activated)
        self.actiongroup_widget = builder.get_object('ProjectsPluginWidgetActions')
        self.actiongroup_active = builder.get_object('ProjectsPluginActiveActions')
        
        self.uimanager = uimanager
        self.uimanager.insert_action_group(self.actiongroup_widget, 0)
        self.uimanager.insert_action_group(self.actiongroup_active, 1)
        menu_file = os.path.join(DATA_DIR, 'menu.ui')
        self.merge_id = self.uimanager.add_ui_from_file(menu_file)
        self.menuitem_default_merge_id = self.uimanager.new_merge_id()
        self.menu_project = self.uimanager.get_widget('/projects_panel_popup')
        self.menu_project.attach_to_widget(self.treeview, None)
        
        self.treeview_open.set_model(self.app_data.sort_model_open)
        self.treeview.set_model(self.app_data.sort_model)
        
    def get_action_info(self):
        action_info = []
        for menuitem in self.menu_project.get_children():
            action = menuitem.get_related_action()
            if menuitem.get_name() != 'menuitem_default' and action is not None:
                action_info.append((action.props.name, action.props.stock_id, action.props.short_label))
        return action_info
        
    def set_default_menuitem(self):
        action_name = self.app_data.config.default_project_action
        default_action = self.actiongroup_widget.get_action(action_name)
        self.uimanager.remove_ui(self.menuitem_default_merge_id)
        if default_action is not None:
            self.uimanager.add_ui(self.menuitem_default_merge_id,
                                '/projects_panel_popup/placeholder_default',
                                'menuitem_default', action_name,
                                Gtk.UIManagerItemType.MENUITEM, True)
        for menuitem in self.menu_project.get_children():
            action = menuitem.get_related_action()
            if menuitem.get_name() != 'menuitem_default' and action is not None:
                menuitem.props.visible = action != default_action
                
    def deactivate(self):
        IdleHelper.deactivate(self)
        self.uimanager.remove_ui(self.menuitem_default_merge_id)
        self.uimanager.remove_ui(self.merge_id)
        self.uimanager.remove_action_group(self.actiongroup_widget)
        self.uimanager.remove_action_group(self.actiongroup_active)
        
        self.menu_project = None
        self.treeview_open = None
        self.treeview = None
        self.widget = None
        self.app_data = None
        
    def set_active_project(self, path):
        tpath = self.app_data.set_project_active(path)
        if tpath:
            tpath = self.app_data.sort_model.convert_child_path_to_path(tpath)
            self.treeview.expand_to_path(tpath)
        
    def on_treeview_projects_button_press_event(self, treeview, event):
        if event.button == 3 and event.type == Gdk.EventType.BUTTON_PRESS:
            def popup():
                self.set_default_menuitem()
                self.menu_project.detach()
                self.menu_project.attach_to_widget(treeview, None)
                self.menu_project.popup(None, None, None, None, event.button, event.time)
            # this prevents the warning: g_object_ref: assertion `G_IS_OBJECT (object)' failed
            self.idle_add(popup)
        return False
        
    def on_treeview_projects_popup_menu(self, treeview):
        #TODO: Open the popup at the position of the row
        #def menu_position_func(menu, unused_data):
        #    tpath, column = self.treeview.get_cursor()
        #    # How do i get the position at tpath?
        #    return x, y, True
        self.set_default_menuitem()
        self.menu_project.detach()
        self.menu_project.attach_to_widget(treeview, None)
        self.menu_project.popup(None, None, None, None, 0, Gtk.get_current_event_time())
        return True
        
    def on_treeview_projects_row_activated(self, treeview, treepath, unused_column):
        action_name = self.app_data.config.default_project_action
        func = self.action_func.get(action_name, None)
        projectpath = treepath and treeview.get_model()[treepath][1]
        if projectpath and func is not None:
            func(self, projectpath)
            
    def on_action(self, action):
        treeview = self.menu_project.get_attach_widget()
        tpath, unused_column = treeview.get_cursor()
        projectpath = tpath and treeview.get_model()[tpath][1]
        if projectpath:
            self.action_func[action.get_name()](self, projectpath)
            
    action_func = {
            'action_move_to_new_window': lambda self, projectpath:
                self.emit('move-to-new-window', projectpath),
            'action_open_directory_from_active': lambda self, projectpath:
                Gtk.show_uri(None, Gio.File.new_for_path(projectpath).get_uri(), Gdk.CURRENT_TIME),
            'action_close_active_project': lambda self, projectpath:
                self.app_data.emit('close-project', projectpath),
                
            'action_open_project': lambda self, projectpath:
                self.emit('open-project', projectpath, False),
            'action_open_project_newwindow': lambda self, projectpath:
                self.emit('open-project', projectpath, True),
            'action_close_project': lambda self, projectpath:
                self.app_data.emit('close-project', projectpath),
            'action_open_directory': lambda self, projectpath:
                Gtk.show_uri(None, Gio.File.new_for_path(projectpath).get_uri(), Gdk.CURRENT_TIME),
            'action_open_file': lambda self, projectpath:
                self.emit('open-file', projectpath),
            'action_add_parent': lambda self, projectpath:
                self.app_data.add_project(os.path.dirname(projectpath)),
            'action_add_directory': lambda self, projectpath:
                self.emit('add-directory', projectpath),
            'action_remove': lambda self, projectpath:
                self.app_data.remove_project(projectpath),
            'action_find': lambda self, projectpath:
                self.app_data.do_scan_projects(projectpath),
        }
        
def main(args):
    import appdata, config, idle
    filenames = args or [__file__]
    filenames = [os.path.abspath(f) for f in filenames]
    window = Gtk.Window()
    window.connect("destroy", Gtk.main_quit)
    window.set_title('Projects')
    window.resize(200, 400)
    config.ProjectsLoadSaver.data_file += '.test'
    app_data = appdata.ApplicationData()
    panel = PanelHelper(app_data)
    panel.connect('open-file', lambda panel, filename: sys.stdout.write(filename+'\n'))
    window.add(panel.widget)
    window.show_all()
    def add_filename(filename):
        app_data.add_filename(filename)
    for f in filenames:
        GLib.idle_add(add_filename, f, priority=idle.Priority.new_tab)
        GLib.idle_add(panel.set_active_project, f, priority=idle.Priority.active_tab)
    Gtk.main()
    app_data.config.deactivate()

if __name__ == '__main__':
    main(sys.argv[1:])
    
