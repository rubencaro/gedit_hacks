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

from gi.repository import GLib


class Priority:
    default = GLib.PRIORITY_DEFAULT_IDLE
    scan_projects = default + 1
    scan_projects2 = default + 2
    insert_known_projects = default + 3
    insert_known_projects2 = default + 4
    style_projects = default + 5
    reassign_files = default + 6
    new_tab = default + 7
    active_tab = default + 8
    
    
class IdleHelper (object):
    def __init__(self):
        self.ids = []
        
    def idle_add(self, func, *args, **kwargs):
        def call(func, *args):
            try:
                res = func(*args)
            except:
                self.ids.remove(id_)
                raise
            if not res:
                self.ids.remove(id_)
            return res
        id_ = GLib.idle_add(call, func, *args, **kwargs)
        self.ids.append(id_)
        
    def deactivate(self):
        for id_ in self.ids:
            GLib.source_remove(id_)
        del self.ids[:]
        


