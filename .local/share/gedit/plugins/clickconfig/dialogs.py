#!/usr/bin/env python
# -*- coding: utf8 -*-
#  Click_Config plugin for Gedit
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
This module provides supplementary dialogs for the configuration dialog of the
Click Config plugin for gedit.

Classes:
LanguageDialog -- The ConfigUI object creates one object of this class when the
                  Assign languages button is opened.  The object removes its
                  own reference from the ConfigUI object when it is closed.

Functions:
ask_for_text -- Present a simple text entry dialog and return the result.
show_message -- Present a text message with an OK button.

In addition to the imported modules, this module requires:
languages.ui -- a Glade file describing the widget layout

2012-07-03  for Click Config version 1.4.0

"""


import os

from gi.repository import Gtk

try:
    from .logger import Logger
except ValueError:
    class Logger(object):
        def __init__(self, level=None):
            pass
        def log(self, message='', var=None):
            print(message)
LOGGER = Logger(level=('DEBUG', 'INFO', 'WARNING', 'ERROR', 'CRITICAL')[2])


class LanguageDialog(object):
    """Dialog for language-to-configset assignment."""
    
    def __init__(self, plugin):
        LOGGER.log()
        self._plugin = plugin
        self.builder = Gtk.Builder()
        self.window = self._make_window()
        self._fill_window()
        self._show_languages_mode()
        self._connect_handlers()
    
    def _make_window(self):
        LOGGER.log()
        glade_file = os.path.join(self._plugin.plugin_path, 'languages.ui')
        self.builder.add_from_file(glade_file)
        window = self.builder.get_object("languages_window")
        window.set_transient_for(self._plugin.config_ui.window)
        window.set_destroy_with_parent(True)
        window.set_position(Gtk.WindowPosition.CENTER_ON_PARENT)
        return window
    
    def _fill_window(self):
        LOGGER.log()
        # Get data
        languages = self._plugin._get_languages()
        configsets_by_language = self._plugin.conf.languages
        
        # Get objects
        liststore_configsets = self.builder.get_object("liststore_configsets")
        liststore_language_mapping = self.builder.get_object(
                "liststore_language_mapping")
        #treeview = self.builder.get_object("treeview1")
        
        # Add languages and their assigned configsets to the listing.
        for language in languages:
            configset_name = configsets_by_language[language]
            liststore_language_mapping.append([language, configset_name])
        
        # Add configset list to combobox.
        configset_names = self._plugin.config_ui._mod_conf.get_configset_names()
        #combobox_list = configset_names[0:2] + [' - '] + configset_names[2:]
        for configset_name in configset_names:
            liststore_configsets.append([configset_name])
        
        #config_combobox = self.builder.get_object('cellrenderercombo_config')
        #row_separator_func = self._plugin.config_ui._row_separator_func
        #config_combobox.set_row_separator_func(row_separator_func, None)
    
    def _connect_handlers(self):
        LOGGER.log()
        signals_to_actions = {
            'on_languages_window_destroy':
                self.on_languages_window_destroy,
            'on_close_button_clicked':
                self.on_close_button_clicked,
            'on_cellrenderercombo_config_changed':
                self.on_cellrenderercombo_config_changed,
            'on_lang_checkbutton_toggled':
                self.on_lang_checkbutton_toggled,
            }
        self.builder.connect_signals(signals_to_actions)
    
    def on_languages_window_destroy(self, widget):
        """Close the language window and remove its object."""
        LOGGER.log()
        LOGGER.log(locals(), level='debug')
        try:
            self._plugin.config_ui.language_dialog = None
        except AttributeError as e:
            # If this window is being destroyed because the main configuration
            # window was closed, then the config_ui attribute may already be
            # set to None.  But we don't want to silence any other condition.
            if 'NoneType' not in e.message:
                raise e
        self.builder = None
        self._plugin = None
    
    def on_close_button_clicked(self, button):
        """Close the language window and remove its object."""
        LOGGER.log()
        LOGGER.log(locals(), level='debug')
        self.window.destroy()
    
    def on_cellrenderercombo_config_changed(self,
                                            combo,
                                            path_string,
                                            new_iter,
                                            user_data=None):
        """Update the configuration and the ListStore."""
        LOGGER.log()
        LOGGER.log(locals(), level='debug')
        # Get objects
        liststore_language_mapping = self.builder.get_object(
            "liststore_language_mapping")
        liststore_configsets = self.builder.get_object('liststore_configsets')
        # Get circumstance
        language, old_configset_name = liststore_language_mapping[path_string]
        configset_name = liststore_configsets[new_iter][0]
        # Update configuration
        self._plugin.config_ui._mod_conf.languages[language] = configset_name
        # Update interface
        liststore_language_mapping[path_string] = [language, configset_name]
        self._plugin.config_ui._update_apply_button()
    
    def on_lang_checkbutton_toggled(self, togglebutton):
        """Update the configuration and the interface sensitivity."""
        LOGGER.log()
        LOGGER.log(locals(), level='debug')
        # Get objects
        lang_checkbutton = togglebutton
        # Get circumstance
        is_checked = lang_checkbutton.get_active()
        # Update configuration
        self._plugin.config_ui._mod_conf.is_set_by_language = is_checked
        # Update interface
        self._show_languages_mode()
    
    def _show_languages_mode(self):
        """Update the language checkbox and language list sensitivity."""
        LOGGER.log()
        # Get objects
        lang_checkbutton = self.builder.get_object('lang_checkbutton')
        scrolledwindow = self.builder.get_object('scrolledwindow1')
        # Get circumstance
        is_checked = self._plugin.config_ui._mod_conf.is_set_by_language
        # Update interface
        lang_checkbutton.set_active(is_checked)
        scrolledwindow.set_sensitive(is_checked)

def ask_for_text(prompt='', title='', default='', parent=None):
    """Display a dialog to get text from the user."""
    LOGGER.log()
    flags = Gtk.DialogFlags.MODAL | Gtk.DialogFlags.DESTROY_WITH_PARENT
    message_type = Gtk.MessageType.OTHER
    buttons = Gtk.ButtonsType.OK_CANCEL
    dialog = Gtk.MessageDialog(parent, flags, message_type, buttons, prompt)
    dialog.set_title(title)
    
    content_area = dialog.get_content_area()
    entry = Gtk.Entry()
    entry.set_text(default)
    entry.show()
    content_area.pack_start(entry, expand=True, fill=True, padding=0)
    entry.connect('activate', lambda _: dialog.response(Gtk.ResponseType.OK))
    dialog.set_default_response(Gtk.ResponseType.OK)
    
    response = dialog.run()
    LOGGER.log(var='response')
    text = entry.get_text().decode('utf8')
    dialog.destroy()
    if response == Gtk.ResponseType.OK:
        return text
    else:
        return None

def show_message(title='', message='', type_=None, parent=None):
    """Display a simple dialog box with a message and an OK button."""
    LOGGER.log()
    if type_ is None:
        type_ = Gtk.MessageType.OTHER
    dialog = Gtk.MessageDialog(None,
                               Gtk.DialogFlags.MODAL,
                               type_,
                               Gtk.ButtonsType.OK,
                               message)
    dialog.set_title(title)
    if parent is not None:
        dialog.set_transient_for(parent)
        dialog.set_destroy_with_parent(True)
        dialog.set_position(Gtk.WindowPosition.CENTER_ON_PARENT)
    dialog.run()
    dialog.destroy()


if __name__ == '__main__':
    text = ask_for_text('a prompt', 'a title', 'a default', None)
    print('text: %s ' % text)
    text = ask_for_text()
    print('text: %s ' % text)

