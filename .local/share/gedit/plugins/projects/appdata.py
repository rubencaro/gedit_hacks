#!/usr/bin/python
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

import os

from gi.repository import GObject
from gi.repository import Gtk
from gi.repository import Pango
from gi.repository import Gedit

from projects.idle import IdleHelper, Priority
from projects.config import ConfigHelper

class NotReady (Exception): pass


def compare_relative(p, q):
    '''
    >>> compare_relative('/x/y','/x/yz')
    >>> compare_relative('/x/yz','/x/y')
    >>> compare_relative('/x/y/a','/x/yz/a')
    >>> compare_relative('/x/yz/a','/x/y/a')
    >>> compare_relative('/x/y/z','/x/y')
    1
    >>> compare_relative('/x/y','/x/y/z')
    -1
    >>> compare_relative('/x/y','/x/y')
    -1
    >>> compare_relative('/x/y','/x/z')
    '''
    _p = p.split(os.path.sep)
    _q = q.split(os.path.sep)
    for i, c in enumerate(_p):
        try:
            if c == _q[i]:
                continue
        except IndexError:
            return 1 # q is prefix of p
        return None # not related
    return -1 # p is prefix of q or equal

class ApplicationData(GObject.GObject, IdleHelper):
    __gsignals__ = {
        'close-project': (GObject.SignalFlags.RUN_FIRST, None, (str,)),
        'reassign-project': (GObject.SignalFlags.RUN_FIRST, None, (str,)),
    }
    
    def __init__(self):
        GObject.GObject.__init__ (self)
        IdleHelper.__init__(self)
        
        self.config = ConfigHelper()
        #   projectname, projectpath, pangoweight, sort-path, projectpath
        self.model_open = Gtk.ListStore(str, str, int, str, str)
        self.sort_model_open = self.model_open.sort_new_with_model()
        self.sort_model_open.set_sort_column_id(3, Gtk.SortType.ASCENDING)
        self.model = Gtk.TreeStore(str, str, int, str, str)
        self.sort_model = self.model.sort_new_with_model()
        self.sort_model.set_sort_column_id(3, Gtk.SortType.ASCENDING)
        self.known_projects = {} # key: project path, value: inserted (bool)
        self.active_project = None # filename
        self.scan_queue = None # if not None scan for projects is in progress
        self.insert_queue = None # if not None insert projects to model is in progress
        
        self.config.connect('find-projects', lambda unused: self.do_scan_projects())
        
        self._project_ind = self.config.project_indications.split()
        self._project_ind_ns = self.config.project_indications_ns.split()
        if self.config.scan_on_start:
            self.do_scan_projects()
        else:
            self.known_projects = {p: False for p in self.config.get_projects()}
            self.do_insert_known_projects()
            
    def deactivate(self):
        IdleHelper.deactivate(self)
        self._project_ind_ns = []
        self._project_ind = []
        self.scan_queue = None
        self.insert_queue = None
        self.active_project = None
        self.known_projects.clear()
        self.config.deactivate()
        self.config = None
        
    def do_scan_projects(self, path=None):
        if self.config is None:
            return
        if self.scan_queue is not None:
            # wait until the previous idle removed
            self.scan_queue = []
            self.idle_add(self.do_scan_projects, path, priority=Priority.scan_projects2)
            return
        self._project_ind = self.config.project_indications.split()
        self._project_ind_ns = self.config.project_indications_ns.split()
        if path is None:
            self.known_projects = {p: False for p in self.config.get_projects()}
            self.model.clear()
            self.scan_queue = [(None, self.config.scan_location)]
        else:
            titer = self._lookup(path, None)
            parent_titer = self.model.iter_parent(titer)
            self._remove_subprojects(titer)
            self.scan_queue = [(parent_titer, path)]
        self.idle_add(self._idle_scan_projects, priority=Priority.scan_projects)
        self.idle_add(self.do_insert_known_projects, priority=Priority.insert_known_projects2)
        
    def _append_path(self, titer, path):
        titer = self.model.append(titer,
                        [os.path.basename(path), path, Pango.Weight.NORMAL,
                        path.lower(), Gedit.utils_replace_home_dir_with_tilde(path)])
        return titer
        
    def _idle_scan_projects(self):
        if not self.scan_queue:
            self.scan_queue = None
            return False
        titer, path = self.scan_queue.pop(0)
        assert path
        try:
            filenames = sorted(os.listdir(path), key=str.lower)
        except OSError:
            filenames = []
        
        # check if project and add it
        name = os.path.basename(path)
        if not name:
            pass
        elif path in self.known_projects.keys():
            self.known_projects[path] = False
            for filename in self._project_ind_ns:
                if filename in filenames:
                    filenames = []
                    break
        else:
            for filename in self._project_ind + self._project_ind_ns:
                if filename in filenames:
                    self.known_projects[path] = False
                    self.config.new_project(path)
                    if filename in self._project_ind_ns:
                        filenames = []
                        break
                    for filename in self._project_ind_ns:
                        if filename in filenames:
                            filenames = []
                            break
                    break
                    
        for filename in filenames:
            if filename in self._project_ind + self._project_ind_ns:
                continue
            subpath = os.path.join(path, filename)
            if os.path.islink(subpath):
                continue
            if os.path.isdir(subpath):
                self.scan_queue.append((titer, subpath))
                
        if self.scan_queue:
            return True # continue
        else:
            self.scan_queue = None
            return False
        
    def do_insert_known_projects(self):
        if self.config is None:
            return
        if self.insert_queue is not None:
            # wait until the previous idle removed
            self.insert_queue = []
            self.idle_add(self.do_insert_known_projects, priority=Priority.insert_known_projects2)
            return
        self.insert_queue = [path for path, inserted in self.known_projects.items() if not inserted]
        if self.insert_queue:
            self.insert_queue.sort()
            self.idle_add(self._idle_insert_known_projects, priority=Priority.insert_known_projects)
        else:
            self.insert_queue = None
        self.idle_add(self._idle_style_projects, priority=Priority.style_projects)
        
    def _idle_insert_known_projects(self):
        if not self.insert_queue:
            self.insert_queue = None
            return False
        path = self.insert_queue.pop(0)
        titer = self._lookup(path, self.model.remove)
        # check if project and add it
        self._append_path(titer, path)
        self.known_projects[path] = True
        
        if self.insert_queue:
            return True # continue
        else:
            self.insert_queue = None
            return False
            
    def _idle_style_projects(self):
        if self.active_project:
            active_titer = self._lookup(self.active_project, None)
            if active_titer:
                self.model.set_value(active_titer, 2, Pango.Weight.BOLD)
        return False
        
    def _lookup(self, lookup_path, subproject_cb):
        titer = self.model.iter_children(None)
        parent_titer = None
        while titer:
            path = self.model[titer][1]
            rel = compare_relative(path, lookup_path)
            if rel == 1:
                # path is a subproject of lookup_path
                sub_titer = titer
                titer = self.model.iter_next(titer)
                if subproject_cb:
                    subproject_cb(sub_titer)
            elif rel == -1:
                # lookup_path is a subproject of path
                parent_titer = titer
                titer = self.model.iter_children(titer)
            else:
                titer = self.model.iter_next(titer)
        return parent_titer
        
    def _remove_subprojects(self, titer):
        while True:
            child_titer = self.model.iter_children(titer)
            if child_titer is None:
                break
            self._remove_subprojects(child_titer)
        path = self.model[titer][1]
        self.model.remove(titer)
        self.known_projects[path] = False
        
    def add_project(self, path):
        if self.scan_queue is not None:
            return
        if path in self.known_projects.keys():
            return
        self.known_projects[path] = False
        self.config.new_project(path)
        titer = self._lookup(path, self._remove_subprojects)
        self.do_insert_known_projects()
        if titer:
            parent_projectpath = self.model[titer][1]
            self.idle_add(self._reassign_files, parent_projectpath, priority=Priority.reassign_files)
            self.idle_add(self.emit, 'reassign-project', parent_projectpath, priority=Priority.new_tab)
        
    def _reassign_files(self, projectpath):
        project = self.config.get_project(projectpath)
        filenames = project.files[:]
        del project.files[:]
        self.config.projects_modified()
        for filename in filenames:
            self.add_filename(filename)
            
    def remove_project(self, path):
        if self.scan_queue is not None:
            return
        if path not in self.known_projects.keys():
            return
        titer = self._lookup(path, None)
        if titer is None:
            return
        self._remove_subprojects(titer)
        self.remove_from_open_projects(path)
        del self.known_projects[path]
        self.config.remove_project(path)
        self.do_insert_known_projects()
        self.emit('reassign-project', path)
        
    def set_project_active(self, projectpath):
        if self.active_project:
            active_titer = self._lookup(self.active_project, None)
            if active_titer:
                self.model.set_value(active_titer, 2, Pango.Weight.NORMAL)
        self.active_project = projectpath
        if projectpath:
            active_titer = self._lookup(projectpath, None)
            if active_titer:
                self.model.set_value(active_titer, 2, Pango.Weight.BOLD)
                projectpath = self.model[active_titer][1]
        else:
            active_titer = None
        for row in self.model_open:
            row[2] = Pango.Weight.BOLD if projectpath == row[1] else Pango.Weight.NORMAL
        return active_titer and self.model.get_path(active_titer)
        
    def add_open_project(self, titer, projectpath):
        open_project_name = []
        while titer:
            open_project_name.insert(0, self.model[titer][0])
            titer = self.model.iter_parent(titer)
        open_project_name = '/'.join(open_project_name)
        for row in self.model_open:
            if projectpath == row[1]:
                break
        else:
            self.model_open.append(
                        [open_project_name, projectpath, Pango.Weight.NORMAL,
                        projectpath.lower(), Gedit.utils_replace_home_dir_with_tilde(projectpath)])
        
    def add_filename(self, filepath):
        if self.scan_queue is not None or self.insert_queue is not None:
            raise NotReady()
        titer = self._lookup(filepath, None)
        if titer is None:
            return None
        projectpath = self.model[titer][1]
        project = self.config.get_project(projectpath)
        while filepath in project.files:
            project.files.remove(filepath)
        project.files.append(filepath)
        self.config.projects_modified()
        self.add_open_project(titer, projectpath)
        return projectpath
        
    def remove_filename(self, projectpath, filepath):
        project = self.config.get_project(projectpath)
        project.files.remove(filepath)
        self.config.projects_modified()
        
    def remove_from_open_projects(self, projectpath):
        titer = self.model_open.get_iter_first()
        while titer:
            prev_titer = titer
            titer = self.model_open.iter_next(titer)
            if self.model_open[prev_titer][1] == projectpath:
                self.model_open.remove(prev_titer)
        titer = self._lookup(projectpath, None)
        if titer:
            self.model.set_value(titer, 2, Pango.Weight.NORMAL)
        
        

