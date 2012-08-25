# -*- coding: utf8 -*-
#  Click Config  plugin for gedit
#
#  Copyright (C) 2010-2012 Derek Veit
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

"""
This module provides the plugin object that gedit interacts with.

Classes:
ClickConfigPlugin       -- one instance is created by the first
                           ClickConfigWindowHelper
ClickConfigWindowHelper -- object is created for each gedit window

Each time the same gedit instance makes a new window, gedit creates a
ClickConfigWindowHelper.  The first ClickConfigWindowHelper creates a
ClickConfigPlugin object to handle the the shared configuration.

Settings common to all gedit windows are attributes of ClickConfigPlugin.
Settings specific to one window are attributes of ClickConfigWindowHelper.

"""

import itertools
import os
import re
import sys
import time

from gi.repository import Gdk
from gi.repository import Gedit
from gi.repository import GObject
from gi.repository import Gtk
from gi.repository import GtkSource
from gi.repository import PeasGtk

from .data import SelectionOp, ConfigSet, Config
from .ui import ConfigUI
from .logger import Logger
LOGGER = Logger(level=('DEBUG', 'INFO', 'WARNING', 'ERROR', 'CRITICAL')[2])

class ClickConfigPlugin(object):
    
    """
    An object of this class is loaded once by a gedit instance.
    
    It establishes and maintains the configuration data.
    
    Public methods:
    activate                -- gedit calls this to start the plugin.
    deactivate              -- gedit calls this to stop the plugin.
    create_configure_dialog -- gedit calls this when "Configure" is
                               selected in the Preferences Plugins tab.
                               Also, ClickConfigWindowHelper calls this
                               when Edit > Click Config > Configure is
                               selected.
    update_configuration    -- The ConfigUI object calls this when Apply
                               or OK is clicked on the configuration
                               window.
    open_config_dir         -- Opens a Nautilus window of the
                               configuration file's directory.  This is
                               called by the ConfigUI object when the
                               Browse button is clicked.
    get_gedit_window        -- Returns the current gedit window.
    
    """
    
    def __init__(self):
        """Initialize plugin attributes."""
        LOGGER.log()
        
        self._instances = {}
        """Each gedit window will get a ClickConfigWindowHelper instance."""
        
        self.plugin_path = None
        """The directory path of this file and the configuration file."""
        
        self.config_ui = None
        """This will identify the (singular) ConfigUI object."""
        
        self.conf = None
        """This object contains all the settings."""
    
    def activate(self, window, window_helper):
        """Establish the configuration."""
        LOGGER.log()
        if not self._instances:
            LOGGER.log('Click Config activating.')
            self.conf = Config(self)
            self.set_conf_defaults()
            self.plugin_path = os.path.dirname(os.path.realpath(__file__))
            
            common_config_dir = os.path.expanduser('~/.config')
            if not os.path.exists(common_config_dir):
                os.mkdir(common_config_dir)
            config_dir = os.path.join(common_config_dir, 'clickconfig')
            if not os.path.exists(config_dir):
                os.mkdir(config_dir)
            self.conf.filename = os.path.join(config_dir,
                                              'click_config_configs')
            if os.path.exists(self.conf.filename):
                self.conf.load()
            
            self.conf.check_language_configsets()
        self._instances[window] = window_helper
    
    def deactivate(self, window):
        """Remove the configuration."""
        LOGGER.log()
        self._instances.pop(window)
        if not self._instances:
            self.conf = None
            self.config_ui = None
            self.plugin_path = None
            LOGGER.log('Click Config deactivated.')
            return True
        return False
    
    def create_configure_dialog(self):
        """Produce the configuration window and provide it to gedit."""
        LOGGER.log()
        if self.config_ui:
            self.config_ui.window.present()
        else:
            self.config_ui = ConfigUI(self)
        return self.config_ui.window
    
    def set_conf_defaults(self):
        """
        Set the configuration to initial default values.
        These values get replaced if there is a configuration file.
        """
        LOGGER.log()
        self.conf.ops = [
            SelectionOp('None',
                preserved=True),
            SelectionOp('gedit word',
                pattern='[a-zA-Z]+|[0-9]+|[^a-zA-Z0-9]+',
                preserved=True),
            SelectionOp('GNOME Terminal default',
                pattern='[-A-Za-z0-9,./?%&#:_]+'),
            SelectionOp('Line',
                pattern='.*',
                preserved=True),
            SelectionOp('Line+',
                pattern='^.*\\n',
                flags=re.M,
                preserved=True),
            SelectionOp('Python name',
                pattern='[_a-zA-Z][_a-zA-Z0-9]*',
                preserved=True),
            SelectionOp('Paragraph',
                pattern=('(?: ^ (?:  [ \\t]*  \\S+  [ \\t]*  )  +  \\n  )+'
                 '  # \xe2\x9c\x94X allows comment'),
                flags=(re.M + re.X)),
            SelectionOp('Paragraph+',
                pattern='(?:^(?:[ \\t]*\\S+[ \\t]*)+\\n)+(?:[ \\t]*\\n)?',
                flags=re.M,
                preserved=True),
            SelectionOp('Python name 2',
                pattern='[_a-z][_.a-z0-9]*',
                flags=re.I),
            ]
        self.conf.configsets = [
            ConfigSet('gedit built-in',
                op_names=[
                    'None',
                    'gedit word',
                    'Line',
                    'None',
                    'None',
                    ],
                preserved=True),
            ConfigSet('Click Config default',
                op_names=[
                    'None',
                    'gedit word',
                    'Python name',
                    'Line+',
                    'Paragraph+',
                    ],
                preserved=True),
            ConfigSet('Custom',
                op_names=[
                    'None',
                    'gedit word',
                    'Python name',
                    'Line+',
                    'Paragraph+',
                    ]),
            ]
        self.conf.current_configset_name = 'Custom'
        self.conf.current_op_name = 'None'
        self.conf.languages = {
            '-None-': 'Click Config default',
            'Python': 'Custom',
            }
        self.conf.is_set_by_language = False
    
    def update_configuration(self, conf):
        """Adopt the provided configuration and save it."""
        LOGGER.log()
        self.conf = conf
        self.conf.save()
        for window in self._instances:
            self._instances[window].update_menu()
        LOGGER.log('Configuration updated.')
    
    def open_config_dir(self):
        """Open a Nautilus window of the configuration file's directory."""
        LOGGER.log()
        import subprocess
        directory = os.path.dirname(self.conf.filename)
        args = ['nautilus', directory]
        subprocess.Popen(args, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    
    def get_gedit_window(self):
        """
        Return the current gedit window.
        ConfigUI uses this to identify its parent window.
        """
        LOGGER.log()
        return Gedit.App.get_default().get_active_window()
    
    def _get_languages(self):
        """Return a list of the languages known to gedit."""
        LOGGER.log()
        gtk_lang_mgr = GtkSource.LanguageManager.get_default()
        language_ids = gtk_lang_mgr.get_language_ids()
        language_names = []
        for language_id in language_ids:
            language = gtk_lang_mgr.get_language(language_id)
            language_names.append(language.get_name())
        language_names.sort(lambda a, b:
                                cmp(a.lower(), b.lower()))
        return language_names
    
    def _get_languages_by_section(self):
        """Return a dictionary of the languages known to gedit, grouped."""
        LOGGER.log()
        gtk_lang_mgr = GtkSource.LanguageManager.get_default()
        language_ids = gtk_lang_mgr.get_language_ids()
        languages_by_section = {}
        for language_id in language_ids:
            language = gtk_lang_mgr.get_language(language_id)
            section = language.get_section()
            name = language.get_name()
            if section in languages_by_section:
                languages_by_section[section].append(name)
            else:
                languages_by_section[section] = [name]
        for section in languages_by_section:
            languages_by_section[section].sort(lambda a, b:
                                                cmp(a.lower(), b.lower()))
        return languages_by_section

class ClickConfigWindowHelper(GObject.Object,
                              Gedit.WindowActivatable,
                              PeasGtk.Configurable):
    
    """
    gedit creates a ClickConfigWindowHelper object for each
    gedit window.  This object receives mouse and menu inputs from the
    gedit window and responds by selecting text, or if the menu item is
    for Configuration, it calls the plugin's method to open the
    configuration window.
    
    Public methods:
    do_activate        -- gedit calls this to activate for this window.
    do_deactivate      -- gedit calls this to deactivate for this window.
    do_update_state    -- gedit calls this at certain times when the ui
                          changes.  It activates the menu for the gedit window
                          and connects the mouse event handler to the current
                          View.  Also, ClickConfigWindowHelper.__init_ calls
                          this.
    on_scrollwin_add   -- do_update_state connects this to the 'add' event of
                          a new ScrolledWindow it finds in order to find
                          out about a new Viewport created by the Split
                          View plugin.
    on_viewport_add    -- on_scrollwin_add connects this to the 'add'
                          event of a new Viewport it finds in order to
                          find out about new views created by the Split
                          View plugin.  When called, it calls do_update_state
                          to connect the mouse event handler to both
                          views.
    
    """
    
    _plugin = None
    
    window = GObject.property(type=Gedit.Window)
    
    def __init__(self):
        """Initialize values of this Click Config instance."""
        LOGGER.log()
        
        GObject.Object.__init__(self)
        
        LOGGER.log('Started for %s' % self.window)
        
        self._ui_id = None
        """The menu's UI identity, saved for removal."""
        self._action_group = None
        """The menu's action group, saved for removal."""
        
        self._last_click = [None, 0, 0, 0, 0, 0]
        """
        The Gtk.TextIter of the most recent click and the times of the most
        recent click for each of the five click types.
        """
        
        gtk_settings = Gtk.Settings.get_default()
        gtk_doubleclick_ms = gtk_settings.get_property('gtk-double-click-time')
        self._double_click_time = float(gtk_doubleclick_ms)/1000
        """Maximum time between consecutive clicks in a multiple click."""
        
        self._mouse_handler_ids_per_view = {}
        """The mouse handler id for each of the window's views."""
        
        self._key_handler_ids_per_view = {}
        """The key_press handler id for each of the window's views."""
        
        self._handlers_per_scrollwin = {}
        """A special 'add' signal handler for each ScrolledWindow found."""
        self._handlers_per_viewport = {}
        """A special 'add' signal handler for each Viewport found."""
        
        self._drag_handler_ids_per_view = {}
        """Motion and button-release handlers for drag selecting."""
        
        self.tab_removed_handler = None
        """Signal handler for a tab being removed from the window."""
        
        # These attributes are used for extending the selection for click-drag.
        self._word_re = None
        """The compiled regular expression object of the current click."""
        self._boundaries = None
        """All start and end positions of matches of the current click."""
        self._click_start_iter = None
        """Start iter of the clicked selection."""
        self._click_end_iter = None
        """End iter of the clicked selection."""
    
    def _insert_menu(self):
        """Create the Click Config submenu under the Edit menu."""
        LOGGER.log()
        
        actions = []
        
        name = 'ClickConfig'
        stock_id = None
        label = 'Click Config'
        actions.append((name, stock_id, label))
        
        name = 'Configure'
        stock_id = None
        label = 'Configure'
        accelerator = '<Control>b'
        tooltip = 'Configure Click Config'
        callback = lambda action: self.open_config_window()
        actions.append((name, stock_id, label, accelerator, tooltip, callback))
        
        op_menuitems = ''
        for op_name in self._plugin.conf.get_op_names()[1:]:
            # Iterating get_op_names ensures that the names are sorted.
            op = self._plugin.conf.get_op(op_name=op_name)
            name = op.name
            stock_id = None
            label = op.name
            accelerator = ''
            flag_text =  ' I' * bool(op.flags & re.I)
            flag_text += ' M' * bool(op.flags & re.M)
            flag_text += ' S' * bool(op.flags & re.S)
            flag_text += ' X' * bool(op.flags & re.X)
            flag_text = flag_text or '(None)'
            tooltip = ('Select text at the cursor location: '
                    'pattern = %s, flags = %s' % (repr(op.pattern), flag_text))
            callback = lambda action: self._select_op(
                        self._plugin.conf.get_op(op_name=action.get_name()))
            action = (name, stock_id, label, accelerator, tooltip, callback)
            actions.append(action)
            op_menuitems += '\n' + ' ' * 22 + '<menuitem action="%s"/>' % name
        
        self._action_group = Gtk.ActionGroup("ClickConfigPluginActions")
        self._action_group.add_actions(actions)
        manager = self.window.get_ui_manager()
        manager.insert_action_group(self._action_group, -1)
        
        ui_str = """
            <ui>
              <menubar name="MenuBar">
                <menu name="EditMenu" action="Edit">
                  <placeholder name="EditOps_6">
                    <menu action="ClickConfig">
                      <menuitem action="Configure"/>
                      <separator/>%s
                    </menu>
                  </placeholder>
                </menu>
              </menubar>
            </ui>
            """ % op_menuitems
        self._ui_id = manager.add_ui_from_string(ui_str)
    
        LOGGER.log('Menu added for %s' % self.window)
    
    def _remove_menu(self):
        """Remove the Click Config submenu."""
        LOGGER.log()
        manager = self.window.get_ui_manager()
        manager.remove_ui(self._ui_id)
        manager.remove_action_group(self._action_group)
        self._action_group = None
        manager.ensure_update()
        LOGGER.log('Menu removed for %s' % self.window)
    
    def update_menu(self):
        """Update the menu (in case the SelectionOp list has changed)."""
        LOGGER.log()
        self._remove_menu()
        self._insert_menu()
    
    def do_activate(self):
        """Start this instance of the plugin"""
        LOGGER.log()
        if self._plugin is None:
            self.__class__._plugin = ClickConfigPlugin()
        self._plugin.activate(self.window, self)
        LOGGER.log('Click Config activating for %s' % self.window)
        self._insert_menu()
        self._connect_window()
        self.do_update_state()
    
    def do_deactivate(self):
        """End this instance of the plugin"""
        LOGGER.log()
        self._disconnect_mouse_handlers()
        self._disconnect_scrollwin_handlers()
        self._disconnect_viewport_handlers()
        self._disconnect_window()
        self._remove_menu()
        self._last_click = None
        self._double_click_time = None
        LOGGER.log('Click Config do_deactivated for %s' % self.window)
        if self._plugin.deactivate(self.window):
            self.__class__._plugin = None
    
    def open_config_window(self):
        """Open the Click Config plugin configuration window."""
        LOGGER.log()
        self._plugin.create_configure_dialog()
        self._plugin.config_ui.window.show()
    
    def get_doc_language(self):
        """Return the programming language of the current document."""
        LOGGER.log()
        doc = self.window.get_active_document()
        doc_language = doc.get_language()
        if doc_language:
            doc_language_name = doc_language.get_name()
        else:
            doc_language_name = '-None-'
        return doc_language_name
    
    def do_update_state(self):
        """
        Identify the document and connect the menu and mouse handling.
        
        A mouse handler connection must be made for each view.
        
        The Split View 2 plugin creates two views in each tab, and
        GeditWindow.get_active_view() only gets the first one.  So it's
        necessary to get the active tab and then drill down to get its
        view(s), so that a mouse handler can be attached to each.
        """
        LOGGER.log()
        doc = self.window.get_active_document()
        view = self.window.get_active_view()
        tab = self.window.get_active_tab()
        if doc and view and view.get_editable():
            if self._plugin.conf.is_set_by_language:
                language = self.get_doc_language()
                LOGGER.log('Language detected: %s' % language)
                if language in self._plugin.conf.languages:
                    configset_name = self._plugin.conf.languages[language]
                    self._plugin.conf.current_configset_name = configset_name
                    LOGGER.log('ConfigSet selected: %s' %
                                             configset_name)
            self._action_group.set_sensitive(True)
            self._connect_tab(tab)
    
    def _connect_window(self):
        """Connect handler for tab removal."""
        LOGGER.log()
        self.tab_removed_handler = self.window.connect('tab-removed',
            self.on_tab_removed)
        
    def _disconnect_window(self):
        """Disconnect handler for tab removal."""
        LOGGER.log()
        if self.window.handler_is_connected(self.tab_removed_handler):
            self.window.disconnect(self.tab_removed_handler)
    
    def on_tab_removed(self, window, tab):
        LOGGER.log()
        LOGGER.log(var='window')
        LOGGER.log(var='tab')
        self._disconnect_tab(tab)
        return False
    
    def _connect_tab(self, tab):
        """Connect signal handlers to the View(s) in the tab."""
        LOGGER.log()
        scrollwin = self._get_tab_scrollwin(tab)
        if scrollwin not in self._handlers_per_scrollwin:
            # Prepare to catch any new Split View views.
            self._handlers_per_scrollwin[scrollwin] = \
                scrollwin.connect('add',
                                  self.on_scrollwin_add, self.window)
        for view in self._get_scrollwin_views(scrollwin):
            self._connect_view(view)
    
    def _disconnect_tab(self, tab):
        """Disconnect signal handlers from the View(s) in the tab."""
        LOGGER.log()
        scrollwin = self._get_tab_scrollwin(tab)
        if scrollwin in self._handlers_per_scrollwin:
            # Stop catching any new Split View views.
            handler_id = self._handlers_per_scrollwin.pop(scrollwin)
            if scrollwin.handler_is_connected(handler_id):
                scrollwin.disconnect(handler_id)
        for view in self._get_scrollwin_views(scrollwin):
            self._disconnect_view(view)
    
    def _get_tab_scrollwin(self, tab):
        """Return the ScrolledWindow of the tab."""
        LOGGER.log()
        view_frame = tab.get_children()[0]
        animated_overlay = view_frame.get_children()[0]
        scrollwin = animated_overlay.get_children()[0]
        return scrollwin
    
    def _get_scrollwin_views(self, scrollwin):
        """Return the View(s) in the ScrolledWindow."""
        child = scrollwin.get_child()
        if type(child).__name__ == 'View':
            # the view within the normal GUI structure.
            view = child
            return [view]
        elif type(child).__name__ == 'Viewport':
            # views within Split View's GUI structure.
            viewport = child
            vbox = viewport.get_child()
            if vbox:
                vpaned = vbox.get_children()[1]
                scrolled_window_1 = vpaned.get_child1()
                scrolled_window_2 = vpaned.get_child2()
                view_1 = scrolled_window_1.get_child()
                view_2 = scrolled_window_2.get_child()
                LOGGER.log('Split View 1: %s' % repr(view_1))
                LOGGER.log('Split View 2: %s' % repr(view_2))
                return [view_1, view_2]
    
    def on_scrollwin_add(self, scrollwin, widget, window):
        """Call do_update_state to add any new view added by Split View"""
        LOGGER.log()
        if type(widget).__name__ == 'Viewport':
            viewport = widget
            vbox = viewport.get_child()
            if vbox:
                # Have do_update_state hook up the views in the Vbox.
                self.do_update_state()
            else:
                # Tell on_viewport_add when the Vbox has been added.
                self._handlers_per_viewport[viewport] = \
                    viewport.connect('add', self.on_viewport_add, window)
        # If it's not a Viewport, then it's probably just the normal View.
        return False
    
    def on_viewport_add(self, viewport, widget, window):
        """Call do_update_state to add any new view added by Split View"""
        LOGGER.log()
        viewport.disconnect(self._handlers_per_viewport.pop(viewport))
        # The Vbox is there, so have do_update_state hook up the views in it.
        # (This is presuming the Hpaned or Vpaned and Views within it
        # are reliably already in the Vbox.  Otherwise, another event
        # handler step or two might be needed.  But, so far, they seem
        # to always be ready.)
        self.do_update_state()
        return False
    
    def _connect_view(self, view):
        """Connect the mouse handler to the view."""
        LOGGER.log()
        LOGGER.log(var='view')
        if view not in self._mouse_handler_ids_per_view:
            self._connect_mouse_handler(view)
            LOGGER.log('Connected to: %s' % repr(view))
    
    def _disconnect_view(self, view):
        """Disconnect the mouse handler from the view."""
        LOGGER.log()
        LOGGER.log(var='view')
        if view in self._mouse_handler_ids_per_view:
            self._disconnect_mouse_handler(view)
            LOGGER.log('Disconnected from: %s' % repr(view))
    
    def _connect_mouse_handler(self, view):
        """Connect the handler for the view's button_press_event."""
        LOGGER.log()
        self._mouse_handler_ids_per_view[view] = \
            view.connect("button_press_event", self._handle_button_press)
    
    def _disconnect_mouse_handler(self, view):
        """Disconnect the handler for the view's button_press_event."""
        LOGGER.log()
        handler_id = self._mouse_handler_ids_per_view.pop(view)
        if view.handler_is_connected(handler_id):
            view.disconnect(handler_id)
    
    def _connect_drag_handler(self, view):
        """
        Connect handlers for the view's motion_notify_event
                                    and button_release_event.
        The motion events will be used to trigger multiple-click
        drag-selecting and the release event will be used to end it.
        """
        LOGGER.log()
        self._drag_handler_ids_per_view[view] = [
            view.connect("motion_notify_event", self._drag_select),
            view.connect("button_release_event",
                         self._handle_button_release)
            ]
        LOGGER.log('Connected drag handlers %r: ' %
                   self._drag_handler_ids_per_view[view], level='debug')
    
    def _drag_select(self, widget, event):
        """
        Extend the text selection to include a selection at the current pointer
        position.
        """
        LOGGER.log()
        view = widget
        
        # Scroll if dragging beyond top or bottom of the view.
        rect = view.get_visible_rect()
        visible_top_y = rect.y
        view_height = rect.height
        visible_bottom_y = visible_top_y + view_height
        if event.y < 0:
            top_line_iter, top_line_y = \
                view.get_line_at_y(visible_top_y)
            if (view.backward_display_line(top_line_iter) or
                    top_line_y < visible_top_y):
                view.scroll_to_iter(top_line_iter,
                                    within_margin=0.0,
                                    use_align=False,
                                    xalign=0.5,
                                    yalign=0.5)
        if event.y > view_height:
            bottom_line_iter, bottom_line_y = \
                view.get_line_at_y(visible_bottom_y)
            bottom_line_height = view.get_line_yrange(bottom_line_iter)[1]
            if (view.forward_display_line(bottom_line_iter) or
                    bottom_line_y > visible_bottom_y - bottom_line_height):
                view.scroll_to_iter(bottom_line_iter,
                                    within_margin=0.0,
                                    use_align=False,
                                    xalign=0.5,
                                    yalign=0.5)
        
        drag_iter = self._get_click_iter(view, event)
        
        self._select_regex(drag_iter, word_re=self._word_re, extend=True)
    
    def _disconnect_drag_handler(self, view):
        """Disconnect the event handlers for drag selecting."""
        LOGGER.log()
        handler_ids = self._drag_handler_ids_per_view.pop(view)
        for handler_id in handler_ids:
            if view.handler_is_connected(handler_id):
                LOGGER.log('Disconnecting drag handler %r' % handler_id,
                           level='debug')
                view.disconnect(handler_id)
            else:
                LOGGER.log('handler %r is not connected' % handler_id)
        # Clear the match data of the click.
        self._word_re = None
        self._boundaries = None
        self._click_start_iter = None
        self._click_end_iter = None
    
    def _disconnect_scrollwin_handlers(self):
        """Disconnect any remaining ScrolledWindow event handlers."""
        LOGGER.log()
        for scrollwin in self._handlers_per_scrollwin.keys():
            handler_id = self._handlers_per_scrollwin.pop(scrollwin)
            if scrollwin.handler_is_connected(handler_id):
                scrollwin.disconnect(handler_id)
    
    def _disconnect_viewport_handlers(self):
        """Disconnect any remaining Viewport event handlers."""
        LOGGER.log()
        for viewport in self._handlers_per_viewport.keys():
            handler_id = self._handlers_per_viewport.pop(viewport)
            if viewport.handler_is_connected(handler_id):
                viewport.disconnect(handler_id)
    
    def _disconnect_mouse_handlers(self):
        """Disconnect from mouse signals from all views in the window."""
        LOGGER.log()
        for view in self._mouse_handler_ids_per_view.keys():
            handler_id = self._mouse_handler_ids_per_view.pop(view)
            if view.handler_is_connected(handler_id):
                view.disconnect(handler_id)
    
    def _handle_button_press(self, view, event):
        """
        Evaluate mouse click and call for text selection as appropriate.
        Return False if the click should still be handled afterwards.
        """
        LOGGER.log()
        handled = False
        if event.button == 1:
            click_iter = self._get_click_iter(view, event)
            now = time.time()
            handlers_by_type = {
                Gdk.EventType.BUTTON_PRESS: self._handle_1button_press,
                Gdk.EventType._2BUTTON_PRESS: self._handle_2button_press,
                Gdk.EventType._3BUTTON_PRESS: self._handle_3button_press,
                }
            handled, click = handlers_by_type[event.type](click_iter, now)
            if click:
                handled = self._make_assigned_selection(click, click_iter)
                if handled:
                    self._connect_drag_handler(view)
        return handled
    
    def _handle_button_release(self, widget, event):
        """Handle left mouse button being released."""
        LOGGER.log()
        if event.button == 1:
            self._disconnect_drag_handler(widget)
        return False
    
    def _handle_1button_press(self, click_iter, now):
        """Detect 5-click, 4-click, or 1-click. Otherwise eat the signal."""
        LOGGER.log()
        handled = False
        click = None
        if self._last_click[0] and click_iter.equal(self._last_click[0]):
            # The pointer must remain in the same position as the first click,
            # for it to be considered a successive click of a multiple click.
            if now - self._last_click[4] < self._double_click_time:
                LOGGER.log('Quintuple-click.')
                # QUINTUPLE-CLICKS are handled here.
                self._last_click[5] = now
                click = 5
            elif now - self._last_click[3] < self._double_click_time:
                LOGGER.log('Quadruple-click.')
                # QUADRUPLE-CLICKS are handled here.
                self._last_click[4] = now
                click = 4
            elif now - self._last_click[2] < self._double_click_time:
                LOGGER.log('(3rd click of a triple-click.)', level='debug')
                # Ignore and consume it.  Triple-clicks are not handled here.
                handled = True
            elif now - self._last_click[1] < self._double_click_time:
                LOGGER.log('(2nd click of a double-click.)', level='debug')
                # Ignore and consume it.  Double-clicks are not handled here.
                handled = True
        if not handled and not click:
            LOGGER.log('Single-click.')
            # SINGLE-CLICKS are handled here.
            # Record this as the original click.
            self._last_click = [click_iter, now, 0, 0, 0, 0]
            click = 1
        return handled, click
    
    def _handle_2button_press(self, click_iter, now):
        """Detect 2-click. Otherwise eat the signal."""
        LOGGER.log()
        handled = False
        click = None
        if self._last_click[0] and click_iter.equal(self._last_click[0]):
            if (now - self._last_click[4]) < self._double_click_time:
                LOGGER.log('(4th & 5th of a quintuple-click.)', level='debug')
                # Ignore and consume it.  Quintuple-clicks are not handled here.
                handled = True
            else:
                LOGGER.log('Double-click.')
                # DOUBLE-CLICKS are handled here.
                self._last_click[2] = now
                click = 2
        return handled, click
    
    def _handle_3button_press(self, click_iter, now):
        """Detect 3-click. Otherwise eat the signal."""
        LOGGER.log()
        handled = False
        click = None
        if self._last_click[0] and click_iter.equal(self._last_click[0]):
            if (now - self._last_click[5]) < self._double_click_time:
                LOGGER.log('(4th-6th of a sextuple-click.)', level='debug')
                # Ignore and consume it.  Sextuple-clicks are not handled here.
                handled = True
            else:
                LOGGER.log('Triple-click.')
                # TRIPLE-CLICKS are handled here.
                self._last_click[3] = now
                click = 3
        return handled, click
    
    def _get_click_iter(self, view, event):
        """Return the current cursor location based on the click location."""
        LOGGER.log()
        buffer_x, buffer_y = view.window_to_buffer_coords(
                        view.get_window_type(event.window),
                        int(event.x),
                        int(event.y))
        event_iter = view.get_iter_at_location(buffer_x, buffer_y)
        return event_iter
    
    def _get_insert_iter(self):
        """Return the current cursor location based on the insert mark."""
        LOGGER.log()
        doc = self.window.get_active_document()
        insert_mark = doc.get_insert()
        insert_iter = doc.get_iter_at_mark(insert_mark)
        return insert_iter
    
    def _make_assigned_selection(self, click, click_iter):
        """Select text based on the click type and location."""
        LOGGER.log()
        acted = False
        op = self._plugin.conf.get_op(click=click)
        if op.name != 'None':
            acted = self._select_op(op, click_iter=click_iter)
        return acted
    
    # Text selection functions:
    
    def _select_op(self, op, click_iter=None):
        """Finds first regex match that includes the click position."""
        LOGGER.log()
        
        char_spec = op.pattern
        flags = op.flags
        
        LOGGER.log('Selection name: %s' % op.name)
        
        if not click_iter:
            click_iter = self._get_insert_iter()
        
        word_re = re.compile(char_spec, flags)
        
        did_select = self._select_regex(click_iter, word_re)
        return did_select
    
    def _select_regex(self, click_iter, word_re, extend=False):
        """
        Select text in the document matching word_re and containing click_iter.
        """
        LOGGER.log()
        
        if not extend:
            self._word_re = word_re
        
        doc = self.window.get_active_document()
        
        multiline = bool(word_re.flags & re.M)
        if multiline:
            if not extend:
                source_start_iter, source_end_iter = doc.get_bounds()
            pick_pos = click_iter.get_offset()
        else:
            source_start_iter, source_end_iter = \
                self._get_line_iter_pair(click_iter)
            pick_pos = click_iter.get_line_offset()
        
        if extend and multiline:
            source_text = None
        else:
            source_text = source_start_iter.get_slice(source_end_iter)
            #FIXME: Update the whole plugin properly for Unicode.
            encoding = doc.get_encoding().get_charset()
            source_text = unicode(source_text, encoding)
            if source_text == '':
                return False
        
        match_start, match_end = self._find_text(source_text, pick_pos, word_re)
        target_start_iter = click_iter.copy()
        target_end_iter = click_iter.copy()
        if multiline:
            target_start_iter.set_offset(match_start)
            target_end_iter.set_offset(match_end)
        else:
            target_start_iter.set_line_offset(match_start)
            target_end_iter.set_line_offset(match_end)
        
        if extend:
            target_start_iter = min((self._click_start_iter,
                                    target_start_iter),
                                    key=lambda i: i.get_offset())
            #extended_back = target_start_iter != self._click_start_iter
            target_end_iter = max((self._click_end_iter,
                                  target_end_iter),
                                  key=lambda i: i.get_offset())
            #extended_forward = target_end_iter != self._click_end_iter
        else:
            self._click_start_iter = target_start_iter
            self._click_end_iter = target_end_iter
        
        current_selection_bounds = doc.get_selection_bounds()
        if current_selection_bounds:
            current_start_iter, current_end_iter = current_selection_bounds
            if (current_start_iter.equal(target_start_iter) and
                    current_end_iter.equal(target_end_iter)):
                # The text is already selected; there's no need to re-select it.
                return True
        doc.select_range(target_start_iter, target_end_iter)
        selected_text = doc.get_text(target_start_iter, target_end_iter, False)
        LOGGER.log('Selected text:\n%s' % selected_text)
        # These two lines will activate search highlighting on the text:
#        found_text = doc.get_text(target_start_iter, target_end_iter)
#        doc.set_search_text(found_text, 1)
        return True
    
    def _find_text(self, source_text, pick_pos, word_re):
        """
        Finds the range of the match, or the range between matches, for regex
        word_re within source_text that includes the position pick_pos.
        If there is no match, then the whole document is selected as being
        between matches.
        """
        LOGGER.log()
        
        # self._boundaries is set by a multiline click selection,
        # remains available for a multiline click-drag selection,
        # and then is set to None by self._disconnect_drag_handler().
        boundaries = self._boundaries
        if not boundaries:
            boundaries = self._find_boundaries(source_text, word_re)
        
        after = next((p for p in boundaries if p > pick_pos), boundaries[-1])
        after_index = boundaries.index(after)
        before = boundaries[after_index - 1]
        
        # For single-line regexes, the boundaries
        # need to be determined each time.
        if word_re.flags & re.M:
            self._boundaries = boundaries
        
        return before, after
    
    def _find_boundaries(self, source_text, word_re):
        """Find the offsets of all match starting and ending positions."""
        LOGGER.log()
        
        spans = ((m.start(), m.end()) for m in word_re.finditer(source_text))
        boundaries = list(itertools.chain.from_iterable(spans))
        
        source_start = 0
        source_end = len(source_text)
        
        if boundaries:
            if boundaries[0] != source_start:
                boundaries.insert(0, source_start)
            if boundaries[-1] != source_end:
                boundaries.append(source_end)
        else:
            boundaries = [source_start, source_end]
        
        return boundaries
    
    def _get_line_iter_pair(self, a_text_iter):
        """Return iters for the start and end of this iter's line."""
        LOGGER.log()
        left_iter = a_text_iter.copy()
        right_iter = a_text_iter.copy()
        left_iter.set_line_offset(0)
        if not right_iter.ends_line():
            right_iter.forward_to_line_end()
        return left_iter, right_iter

