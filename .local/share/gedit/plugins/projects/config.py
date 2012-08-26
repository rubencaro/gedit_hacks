# -*- coding: utf-8 -*-

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


import sys, os

from gi.repository import GLib
from gi.repository import GObject
from gi.repository import Gtk
from gi.repository import Gio

class GSettingsSchemaNotFound (Exception): pass


class ConfigHelper (GObject.GObject):
    __gsignals__ = {
        'find-projects':  (GObject.SignalFlags.RUN_FIRST, None, ()),
    }
    ui_file = os.path.join(os.path.dirname(__file__), 'config.ui')
    settings_schema = "org.gnome.gedit.plugins.projects"
    
    def __init__(self):
        GObject.GObject.__init__(self)
        schemas = Gio.Settings.list_schemas()
        if self.settings_schema not in schemas:
            raise GSettingsSchemaNotFound()
        self.settings = Gio.Settings.new(self.settings_schema)
        self._known_projects = None
        self.action_info = []
        self.loadsaver = ProjectsLoadSaver()
        # transition to the new file format and location once
        if not os.path.exists(self.loadsaver.data_file) and os.path.exists(ProjectsLoadSaver_pickle.cache_file):
            self._known_projects = ProjectsLoadSaver_pickle().load()
            self.loadsaver.save(self._known_projects)
            
    def deactivate(self):
        self.loadsaver.save(self._known_projects)
        self._known_projects = None
        self.settings = None
        
    def create_widget(self, window):
        builder = Gtk.Builder()
        builder.add_from_file(self.ui_file)
        builder.connect_signals(self)
        def bind(settings_key, object_name, attr):
            self.settings.bind(settings_key,
                               builder.get_object(object_name), attr,
                               Gio.SettingsBindFlags.DEFAULT)
        def bind_clear(settings_key, object_name):
            def on_button_clear(unused_button):
                self.settings.reset(settings_key)
            builder.get_object(object_name).connect('clicked', on_button_clear)
            
        bind('scan-location', 'entry_scandir', 'text')
        def on_button_scandir(unused_button):
            dialog = Gtk.FileChooserDialog("Select Folder",
                                          window,
                                          Gtk.FileChooserAction.SELECT_FOLDER,
                                          [Gtk.STOCK_CANCEL, Gtk.ResponseType.CANCEL,
                                          Gtk.STOCK_OPEN, Gtk.ResponseType.ACCEPT])
            dialog.set_current_folder(self.scan_location)
            if dialog.run() == Gtk.ResponseType.ACCEPT:
                self.scan_location = dialog.get_filename()
            dialog.destroy()
        builder.get_object('button_scandir').connect('clicked', on_button_scandir)
        
        bind('project-indications', 'entry_indications', 'text')
        bind_clear('project-indications', 'button_clear_indications')
        
        bind('project-indications-nosubprojects', 'entry_indications_ns', 'text')
        bind_clear('project-indications-nosubprojects', 'button_clear_indications_ns')
        
        bind('scan-on-start', 'checkbutton_scan_on_start', 'active')
        
        def on_button_find(unused_button):
            self.emit('find-projects')
        builder.get_object('button_find').connect('clicked', on_button_find)
        
        liststore_default_action = builder.get_object('liststore_default_action')
        for action_info in self.action_info:
            liststore_default_action.append(action_info)
        bind('default-project-action', 'combobox_default_action', 'active-id')
        bind_clear('default-project-action', 'button_clear_default_action')
        
        bind('filebrowser-set-root-on-project-open', 'checkbutton_filebrowser_set_root_on_project_open', 'active')
        bind_clear('filebrowser-set-root-on-project-open', 'button_clear_filebrowser_set_root_on_project_open')
        
        minr, maxr = self.max_recents_range
        adjustment = Gtk.Adjustment(minr, minr, maxr, 1, 10, 0)
        builder.get_object('spinbutton_max_recents').props.adjustment = adjustment
        bind('max-recents', 'spinbutton_max_recents', 'value')
        bind_clear('max-recents', 'button_clear_max_recents')
        
        return builder.get_object('widget_projects')
        
    scan_location = property(
        lambda self: self.settings.get_string("scan-location"),
        lambda self, value: self.settings.set_string("scan-location", value))
    project_indications = property(
        lambda self: self.settings.get_string("project-indications"),
        lambda self, value: self.settings.set_string("project-indications", value))
    project_indications_ns = property(
        lambda self: self.settings.get_string("project-indications-nosubprojects"),
        lambda self, value: self.settings.set_string("project-indications-nosubprojects", value))
    scan_on_start = property(
        lambda self: self.settings.get_boolean("scan-on-start"),
        lambda self, value: self.settings.set_boolean("scan-on-start", value))
    default_project_action = property(
        lambda self: self.settings.get_string("default-project-action"),
        lambda self, value: self.settings.set_string("default-project-action", value))
    filebrowser_set_root_on_project_open = property(
        lambda self: self.settings.get_boolean("filebrowser-set-root-on-project-open"),
        lambda self, value: self.settings.set_boolean("filebrowser-set-root-on-project-open", value))
    recent_projects = property(
        lambda self: self.settings['recent-projects'],
        lambda self, value: self.settings.set_strv('recent-projects', value))
    max_recents = property(
        lambda self: self.settings['max-recents'],
        lambda self, value: self.settings.set_uint('max-recents', value))
    @property
    def max_recents_range(self):
        range_tuple = self.settings.get_range('max-recents')
        assert range_tuple[0] == 'range'
        return range_tuple[1]
        
    def projects_modified(self):
        if self.loadsaver.modified:
            return
        self.loadsaver.modified = True
        GLib.timeout_add_seconds(20, self.loadsaver.save, self._known_projects)
    def get_projects(self):
        if self._known_projects is None:
            self._known_projects = self.loadsaver.load()
        return self._known_projects.keys()
    def get_project(self, path):
        if self._known_projects is None:
            self._known_projects = self.loadsaver.load()
        return self._known_projects[path]
    def new_project(self, path):
        project = Project(path)
        self._known_projects[path] = project
        self.projects_modified()
        return project
    def remove_project(self, path):
        del self._known_projects[path]
        self.projects_modified()
        
        
class ProjectsLoadSaver (object):
    '''Loads and saves Project data for gedit-projects 1.1'''
    
    file_version = 2
    file_signature = '### gedit-projects data file (version {}) ###'.format(file_version)
    data_dir = os.path.join(GLib.get_user_config_dir(), 'gedit-projects')
    data_file = os.path.join(data_dir, 'data.repr')
    
    def __init__(self):
        self.modified = False
        if not os.path.exists(self.data_dir):
            Gio.File.new_for_path(self.data_dir).make_directory_with_parents(None)
            
    def load(self):
        import ast
        known_projects = {}
        try:
            with open(self.data_file, 'rt') as data_file:
                file_signature = data_file.readline().strip()
                if file_signature != self.file_signature:
                    raise Exception('Unknown file signature: {}'.format(file_signature))
                known_projects = data_file.read()
            known_projects = ast.literal_eval(known_projects)
            def _convert(known_projects):
                for p_dict in known_projects:
                    p = Project(None)
                    p.__dict__.update(p_dict)
                    if p.path:
                        yield p
            known_projects = {p.path:p for p in _convert(known_projects)}
        except IOError as e:
            print e
        except Exception:
            sys.excepthook(*sys.exc_info())
        return known_projects
        
    def save(self, known_projects):
        if self.modified:
            self.modified = False
        else:
            return False
        known_projects = repr([p.__dict__ for p in known_projects.values()])
        try:
            with open(self.data_file, 'wt') as data_file:
                data_file.write(self.file_signature + '\n')
                data_file.write(known_projects)
                data_file.write('\n')
        except (OSError, IOError) as e:
            print e
        return False
        
        
class ProjectsLoadSaver_pickle (object):
    '''Loads Project data for gedit-projects 1.0
    The load function is used to transition
    to the new format and location in gedit-projects 1.1.
    '''
    file_version = 1
    cache_dir = os.path.join(GLib.get_user_cache_dir(), 'gedit', 'plugins')
    cache_file = os.path.join(cache_dir, 'projects')
    
    def __init__(self):
        self.modified = False
        if not os.path.exists(self.cache_dir):
            Gio.File.new_for_path(self.cache_dir).make_directory_with_parents(None)
            
    def load(self):
        import cPickle as pickle
        known_projects = []
        try:
            with open(self.cache_file, 'rb') as cache:
                p = pickle.Unpickler(cache)
                file_version = p.load()
                if file_version > self.file_version:
                    raise Exception('Unknown file version: %s' % file_version)
                known_projects = p.load()
        except IOError as e:
            print e
        except Exception:
            sys.excepthook(*sys.exc_info())
        return {p.path:p for p in known_projects}
        
        
class Project (object):
    def __init__(self, path):
        self.path = path
        self.files = []
        self.active_file = None
        
        
def main():
    dialog = Gtk.Dialog("Message",
                        None,
                        Gtk.DialogFlags.MODAL,
                        [Gtk.STOCK_CLOSE, Gtk.ResponseType.NONE])
    area = dialog.get_content_area()
    config = ConfigHelper()
    area.add(config.create_widget(dialog))
    dialog.run()
    dialog.destroy()
    
if __name__ == '__main__':
    main()
    
