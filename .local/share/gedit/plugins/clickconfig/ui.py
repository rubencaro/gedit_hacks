# -*- coding: utf8 -*-
#  Click_Config plugin for Gedit
#
#  Copyright (C) 2010 Derek Veit
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
This module provides a GUI window for configuring the Click_Config plugin for
Gedit.

The ConfigUI object is constructed with a reference to the ClickConfigPlugin
object through which it accesses the plugin's configuration.

Classes:
ConfigUI -- The Click_Config plugin creates one object of this class when the
            configuration window is opened.  The object removes its own
            reference from the plugin when the configuration window is closed.

In addition to the imported modules, this module requires:
Click_Config.xml -- configuration GUI layout converted from Click_Config.glade

2010-05-26  for Click Config version 1.1.2
    Fixed Issue #4 in ConfigUI._update_config_display.

"""


import os
import re
import sys

from gi.repository import Gdk
from gi.repository import Gtk

from .logger import Logger
LOGGER = Logger(level=('DEBUG', 'INFO', 'WARNING', 'ERROR', 'CRITICAL')[2])
import dialogs

class ConfigUI(object):
    
    """
    The configuration window for Click_Config.
    
    Usage:
    config_ui = ConfigUI()
    config_ui.window.show()
    
    See:
    click_config.py ClickConfigPlugin.create_configure_dialog()
    
    """
    
    def __init__(self, plugin):
        """
        1. Create the window.
        2. Make a temporary copy of the configuration.
        3. Update the window's widgets to reflect the configuration.
        4. Connect the event handlers.
        """
        self._plugin = plugin
        LOGGER.log()
        
        # 1. Create the window.
        glade_file = os.path.join(self._plugin.plugin_path, 'Click_Config.ui')
        self.builder = Gtk.Builder()
        self.builder.add_from_file(glade_file)
        self.window = self.builder.get_object("config_window")
        gedit_window = self._plugin.get_gedit_window()
        self.window.set_transient_for(gedit_window)
        self.window.set_destroy_with_parent(True)
        self.window.set_position(Gtk.WindowPosition.CENTER_ON_PARENT)
        self.language_dialog = None
        
        # 2. Make a temporary copy of the configuration.
        self._mod_conf = self._plugin.conf.copy()
        self.preserved_sets = [item.name for item in
            self._mod_conf.configsets if item.preserved]
        self.preserved_ops = [item.name for item in
            self._mod_conf.ops if item.preserved]
        
        # 3. Update the window's widgets to reflect the configuration.
        width = self._mod_conf.window_width
        if width:
            self.window.set_default_size(width, -1)
        self._update_config_combobox()
        self._update_config_display()
        self._update_define_combobox()
        self._update_define_display()
        self._update_apply_button()
    
        # 4. Connect the event handlers.
        signals_to_actions = {
            'on_config_window_destroy':
                self.on_config_window_destroy,
            'on_config_combobox_changed':
                self.on_config_combobox_changed,
            'on_comboboxentryentry1_key_press_event':
                self.on_comboboxentryentry1_key_press_event,
            'on_config_add_button_clicked':
                self.on_config_add_button_clicked,
            'on_config_remove_button_clicked':
                self.on_config_remove_button_clicked,
            'on_languages_button_clicked':
                self.on_languages_button_clicked,
            'on_combobox_changed':
                self.on_combobox_changed,
            'on_edit_clicked':
                self.on_edit_clicked,
            'on_define_combobox_changed':
                self.on_define_combobox_changed,
            'on_define_name_entry_key_press_event':
                self.on_define_entry_key_press_event,
            'on_define_regex_entry_changed':
                self.on_define_changed,
            'on_define_regex_entry_key_press_event':
                self.on_define_entry_key_press_event,
            'on_define_i_checkbutton_toggled':
                self.on_define_changed,
            'on_define_m_checkbutton_toggled':
                self.on_define_changed,
            'on_define_s_checkbutton_toggled':
                self.on_define_changed,
            'on_define_x_checkbutton_toggled':
                self.on_define_changed,
            'on_define_add_button_clicked':
                self.on_define_add_button_clicked,
            'on_define_remove_button_clicked':
                self.on_define_remove_button_clicked,
            'on_define_save_button_clicked':
                self.on_define_save_button_clicked,
            'on_OK_button_clicked':
                self.on_OK_button_clicked,
            'on_Apply_button_clicked':
                self.on_Apply_button_clicked,
            'on_Cancel_button_clicked':
                self.on_Cancel_button_clicked,
            'on_Browse_button_clicked':
                self.on_Browse_button_clicked,
            'on_Import_button_clicked':
                self.on_Import_button_clicked,
            }
        self.builder.connect_signals(signals_to_actions)
        
        LOGGER.log('Configuration window opened.')
        
        
    ### 1 - General configure window
    
    # 1.1 - Event handlers
    
    def on_config_window_destroy(self, event):
        """Let the ClickConfigPlugin know that the ConfigUI is gone."""
        LOGGER.log()
        LOGGER.log('Configuration window closed.')
        self._plugin.config_ui = None
        return False
    
    def on_OK_button_clicked(self, button):
        """
        Give the ClickConfigPlugin the modified configuration, then close.
        """
        LOGGER.log()
        width, height = self.window.get_size()
        self._mod_conf.window_width = width
        self._plugin.update_configuration(self._mod_conf.copy())
        self.window.destroy()
        self._plugin.config_ui = None
    
    def on_Apply_button_clicked(self, button):
        """Give the ClickConfigPlugin the modified configuration."""
        LOGGER.log()
        self._plugin.update_configuration(self._mod_conf.copy())
        self._update_apply_button()
    
    def on_Cancel_button_clicked(self, button):
        """Close without giving ClickConfigPlugin the modified configuration."""
        LOGGER.log()
        self.window.destroy()
    
    def on_Browse_button_clicked(self, button):
        """Browse to the configuration file."""
        LOGGER.log()
        self._plugin.open_config_dir()
    
    def on_Import_button_clicked(self, button):
        """Import ConfigSets and SelectionOps from another configuration file."""
        LOGGER.log()
        filename = self._filechooser_dialog(
            title='Import from a Click_Config configuration file')
        if filename:
            self._mod_conf.import_file(filename)
        self._update_config_combobox()
        self._update_config_display()
        self._update_define_combobox()
        self._update_define_display()
        self._update_apply_button()
    
    # 1.2 - Support functions
    
    def _update_apply_button(self):
        """Correct the Apply button's sensitivity."""
        LOGGER.log()
        apply_button = self.builder.get_object('Apply_button')
        has_changes = self._mod_conf != self._plugin.conf
        LOGGER.log(var='has_changes')
        apply_button.set_sensitive(has_changes)
    
    def _filechooser_dialog(self, title='Open'):
        """
        Provide file selection dialog to user and return the selected filename.
        """
        LOGGER.log()
        dialog = Gtk.FileChooserDialog(
            title=title,
            parent=self.window,
            action=Gtk.FileChooserAction.OPEN,
            buttons=(Gtk.STOCK_CANCEL, Gtk.ResponseType.CANCEL,
                Gtk.STOCK_OPEN, Gtk.ResponseType.OK))
        dialog.set_default_response(Gtk.ResponseType.OK)
        file_filter = Gtk.FileFilter()
        file_filter.set_name('All files')
        file_filter.add_pattern('*')
        dialog.add_filter(file_filter)
        text_file_filter = Gtk.FileFilter()
        text_file_filter.set_name('Text files')
        text_file_filter.add_mime_type('text/plain')
        dialog.add_filter(text_file_filter)
        dialog.set_filter(text_file_filter)
        dialog.set_current_folder(self._plugin.plugin_path)
        response = dialog.run()
        if response == Gtk.ResponseType.OK:
            filename = dialog.get_filename()
        else:
            filename = ''
        dialog.destroy()
        return filename
    
    ### 2 - ConfigSet name section
    
    # 2.1 - Event handlers
    
    def on_config_combobox_changed(self, combobox):
        """Update the configuration and interface based on the selection."""
        LOGGER.log()
        # Get objects
        config_combobox = combobox
        config_remove_button = self.builder.get_object('config_remove_button')
        # Get circumstance
        config_name = config_combobox.get_active_id()
        is_removable = self._is_config_name_removable(config_name)
        # Update configuration
        self._mod_conf.current_configset_name = config_name
        # Update interface
        self._update_config_display()
        config_remove_button.set_sensitive(is_removable)
    
    def on_comboboxentryentry1_key_press_event(self, widget, event):
        """React to the Enter key here the same as for the Add button."""
        LOGGER.log()
        keyval = event.keyval
        keyval_name = Gdk.keyval_name(keyval)
        if keyval_name in ('Return', 'KP_Enter'):
            self._add_config()
    
    def on_config_add_button_clicked(self, button):
        """Call function to add the configuration."""
        LOGGER.log()
        self._add_config()

    def on_config_remove_button_clicked(self, button):
        """Call function to remove the configuration."""
        LOGGER.log()
        self._remove_config()
    
    def on_languages_button_clicked(self, button):
        """Call function for the languages configuration dialog."""
        LOGGER.log()
        language_window = self._create_languages_dialog()
        language_window.show()
    
    def _create_languages_dialog(self):
        """Display the languages configuration dialog."""
        LOGGER.log()
        if self.language_dialog:
            self.language_dialog.window.present()
        else:
            self.language_dialog = dialogs.LanguageDialog(self._plugin)
        return self.language_dialog.window
    
    # 2.2 - Support functions
    
    def _update_config_combobox(self):
        """Reflect the ConfigSets and current ConfigSet in the interface."""
        LOGGER.log()
        configset_names = self._mod_conf.get_configset_names()
        combobox_list = configset_names[0:2] + [' - '] + configset_names[2:]
        config_combobox = \
            self.builder.get_object('config_combobox')
        config_combobox.set_row_separator_func(self._row_separator_func, None)
        self._fill_combobox(config_combobox, combobox_list)
        config_combobox.set_id_column(0)
        config_combobox.set_active_id(self._mod_conf.current_configset_name)
    
    def _row_separator_func(self, model, iter_, data=None):
        """Identify what item represents a separator."""
        LOGGER.log()
        row_is_a_separator = model.get_value(iter_, 0) == ' - '
        return row_is_a_separator

    def _get_configset_names(self):
        """Return a list of the ConfigSet names."""
        LOGGER.log()
        configset_names = [item.name for item in self._mod_conf.configsets]
        configset_names = configset_names[0:2] + sorted(configset_names[2:])
        return configset_names
    
    def _add_config(self):
        """Add the configuration."""
        LOGGER.log()
        # Get objects
        combobox = self.builder.get_object('config_combobox')
        # Get the new name
        configset_name = combobox.get_active_id()
        configset_names = self._mod_conf.get_configset_names()
        configset_name = self._get_new_name(configset_name,
                                            configset_names,
                                            'configuration')
        if not configset_name:
            return
        # Update configuration
        new_configset = self._mod_conf.get_configset().copy_as(configset_name)
        LOGGER.log(var='new_configset')
        self._mod_conf.add_configset(new_configset)
        self._mod_conf.current_configset_name = configset_name
        # Update interface
        self._update_config_combobox()
        self._update_config_display()
        LOGGER.log('ConfigSet added: %s.' % configset_name)
    
    def _get_new_name(self, name='', existing_names=(), desc=''):
        """Ask the user for a new name, and ensure it is new."""
        while 1:
            name = dialogs.ask_for_text(parent=self.window,
                                        title='Add %s' % desc,
                                        prompt='Enter a new name:',
                                        default=name)
            if name:
                name = name.strip()
            if name not in existing_names:
                break
            dialogs.show_message(title='Error adding %s name' % desc,
                                 message='"%s" already exists.' % name,
                                 type_=Gtk.MessageType.ERROR,
                                 parent=self.window)
        return name
    
    def _remove_config(self):
        """Remove the configuration."""
        LOGGER.log()
        # Get objects
        config_combobox = self.builder.get_object('config_combobox')
        # Get circumstance
        config_name = config_combobox.get_active_id()
        config_names = self._mod_conf.get_configset_names()
        is_removable = self._is_config_name_removable(config_name)
        # Update configuration
        if is_removable:
            # Switch to preceding config set
            config_name_index = config_names.index(config_name)
            preceding_config_name = config_names[config_name_index - 1]
            self._mod_conf.current_configset_name = preceding_config_name
            # Remove the config set
            old_configset = self._mod_conf.get_configset(config_name)
            self._mod_conf.remove_configset(old_configset)
            self._mod_conf.check_language_configsets()
        # Update interface
            self._update_config_combobox()
            self._update_config_display()
            LOGGER.log('ConfigSet removed: %s.' % config_name)
    
    def _is_config_name_removable(self, config_name):
        """Check if ConfigSet of this name can be removed."""
        LOGGER.log()
        return (config_name in self._mod_conf.get_configset_names() and
                     config_name not in self.preserved_sets)
    
    ### 3 - ConfigSet settings section
    
    # 3.1 - Event handlers
    
    def on_combobox_changed(self, combobox):
        """
        Update the configuration and interface to reflect the SelectionOp name.
        """
        LOGGER.log()
        # Get objects
        config_combobox = \
            self.builder.get_object('config_combobox')
        # Get circumstance
        op_name = combobox.get_active_id()
        click_number = combobox.get_name()[8:]
        click = int(click_number)
        entry_config_name = config_combobox.get_active_id().strip()
        # Update configuration
        self._mod_conf.set_op(op_name=op_name, click=click)
        # Update interface
        self._set_combobox_op(combobox, op_name)
        self._update_apply_button()
        # Make sure a typed-but-not-added config name isn't showing
        if entry_config_name != self._mod_conf.current_configset_name:
            self._update_config_combobox()
    
    def on_edit_clicked(self, button):
        """Set the selection for this n-click as the current selection."""
        LOGGER.log()
        # Get circumstance
        click_number = button.get_name()[4:]
        click = int(click_number)
        op_name = self._mod_conf.get_op(click=click).name
        # Update configuration
        self._mod_conf.current_op_name = op_name
        # Update interface
        self._update_apply_button()
        self._update_define_combobox()
        self._update_define_display()
    
    # 3.2 - Support functions
    
    def _fill_combobox(self, combobox, items):
        """Put a list of the SelectionOp names in the combobox."""
        LOGGER.log()
        combobox_liststore = Gtk.ListStore(str)
        for item in items:
            combobox_liststore.append([item])
        combobox.set_model(combobox_liststore)
    
    def _update_config_display(self):
        """
        Reflect the five SelectionOps of the current ConfigSet in the widgets.
        """
        LOGGER.log()
        op_names = self._mod_conf.get_op_names()
        for click in range(1, 6):
            combobox = self.builder.get_object('combobox%d' % click)
            edit_button = self.builder.get_object('edit%d' % click)
            # As of GTK+ 2.20, the widget name does not automatically equal the
            # widget id, so I have to set it here to let it work as before.
            combobox.set_name('combobox%d' % click)
            edit_button.set_name('edit%d' % click)
            self._fill_combobox(combobox, op_names)
            combobox.set_id_column(0)
            op_name = self._mod_conf.get_op(click=click).name
            self._set_combobox_op(combobox, op_name)
        self._update_apply_button()

    def _set_combobox_op(self, combobox, op_name):
        """Reflect the SelectionOp in the widgets for the click."""
        LOGGER.log()
        # Get objects
        objects = {}
        objects['combobox'] = combobox
        combobox_name = objects['combobox'].get_name()
        click_number = combobox_name[8:]
        entry_name = "entry" + click_number
        objects['entry'] = self.builder.get_object(entry_name)
        objects['i'] = self.builder.get_object('i_checkbutton' + click_number)
        objects['m'] = self.builder.get_object('m_checkbutton' + click_number)
        objects['s'] = self.builder.get_object('s_checkbutton' + click_number)
        objects['x'] = self.builder.get_object('x_checkbutton' + click_number)
        # Get circumstance
        is_editable = not self._mod_conf.get_configset().preserved
        op = self._mod_conf.get_op(op_name=op_name)
        pattern = op.pattern
        flags = op.flags
        # Update interface
        objects['combobox'].set_active_id(op_name)
        objects['combobox'].set_sensitive(is_editable)
        objects['entry'].set_text(pattern)
        objects['entry'].set_sensitive(False)
        objects['i'].set_active(flags & re.I)
        objects['m'].set_active(flags & re.M)
        objects['s'].set_active(flags & re.S)
        objects['x'].set_active(flags & re.X)
        objects['i'].set_sensitive(False)
        objects['m'].set_sensitive(False)
        objects['s'].set_sensitive(False)
        objects['x'].set_sensitive(False)
        
    ### 4 - Define section
    
    # 4.1 - Event handlers
    
    def on_define_combobox_changed(self, combobox):
        """Update the configuration and interface for the SelectionOp name."""
        LOGGER.log()
        op_name = combobox.get_active_id()
        op_names = self._mod_conf.get_op_names()
        if op_name in op_names:
            self._mod_conf.current_op_name = op_name
            self._update_apply_button()
        self._update_define_display()
    
    def on_define_changed(self, editable):
        """Call function to update the Add button."""
        LOGGER.log()
        self._update_define_save_button()
    
    def on_define_entry_key_press_event(self, widget, event):
        """React to the Enter key here the same as for the Add button."""
        LOGGER.log()
        keyval = event.keyval
        keyval_name = Gdk.keyval_name(keyval)
        if keyval_name in ('Return', 'KP_Enter'):
            self._add_define()
    
    def on_define_add_button_clicked(self, button):
        """Call function to add a new SelectionOp with the current pattern."""
        LOGGER.log()
        self._add_define()
    
    def on_define_remove_button_clicked(self, button):
        """Call function to remove the current SelectionOp."""
        LOGGER.log()
        self._remove_define()
    
    def on_define_save_button_clicked(self, button):
        """Call function to update the SelectionOp for the changed pattern."""
        LOGGER.log()
        self._save_define()
    
    # 4.2 - Support functions
    
    def _update_define_combobox(self):
        """Reflect the SelectionOps and current SelectionOp in the combobox."""
        LOGGER.log()
        combobox = self.builder.get_object('define_combobox')
        op_names = self._mod_conf.get_op_names()
        self._fill_combobox(combobox, op_names)
        combobox.set_id_column(0)
        op_name = self._mod_conf.current_op_name
        combobox.set_active_id(op_name)
    
    def _update_define_display(self):
        """Reflect the current SelectionOp in the interface."""
        LOGGER.log()
        # Get objects
        combobox = self.builder.get_object('define_combobox')
        save_button = self.builder.get_object('define_save_button')
        remove_button = self.builder.get_object('define_remove_button')
        # Get circumstance
        op_name = combobox.get_active_id()
        is_editable = op_name not in self.preserved_ops
        # Update interface
        op = self._mod_conf.get_op(op_name=op_name)
        self._set_define_in_ui(op.pattern, op.flags, is_editable)
        save_button.set_sensitive(False)
        remove_button.set_sensitive(is_editable)
    
    def _get_definition_objects(self):
        """Get a dictionary of the widgets that describe the selection."""
        LOGGER.log()
        names = [
            ('combobox', 'define_combobox'),
            ('pattern', 'define_regex_entry'),
            ('i', 'define_i_checkbutton'),
            ('m', 'define_m_checkbutton'),
            ('s', 'define_s_checkbutton'),
            ('x', 'define_x_checkbutton'),
        ]
        objects = dict((k, self.builder.get_object(n)) for k, n in names)
        return objects
    
    def _get_define_in_ui(self):
        """Get the pattern, and flags from the define objects."""
        LOGGER.log()
        # Get objects
        objects = self._get_definition_objects()
        # Get circumstance
        pattern = objects['pattern'].get_text()
        flags = (objects['i'].get_active() * re.I +
                 objects['m'].get_active() * re.M +
                 objects['s'].get_active() * re.S +
                 objects['x'].get_active() * re.X)
        return pattern, flags
    
    def _set_define_in_ui(self, pattern, flags, is_editable=True):
        """Set the pattern, and flags of the define objects."""
        LOGGER.log()
        # Get objects
        objects = self._get_definition_objects()
        # Update interface
        objects['pattern'].set_text(pattern)
        objects['i'].set_active(flags & re.I)
        objects['m'].set_active(flags & re.M)
        objects['s'].set_active(flags & re.S)
        objects['x'].set_active(flags & re.X)
        objects['pattern'].set_sensitive(is_editable)
        objects['i'].set_sensitive(is_editable)
        objects['m'].set_sensitive(is_editable)
        objects['s'].set_sensitive(is_editable)
        objects['x'].set_sensitive(is_editable)
    
    def _update_define_save_button(self):
        """Correct the Save button's sensitivity for the pattern and flags."""
        LOGGER.log()
        # Get objects
        combobox = self.builder.get_object('define_combobox')
        save_button = self.builder.get_object('define_save_button')
        # Get circumstance
        op_name = combobox.get_active_id()
        pattern, flags = self._get_define_in_ui()
        current_op = self._mod_conf.get_op()
        has_new_pattern = pattern != current_op.pattern
        has_new_flags = flags != current_op.flags
        has_changes = has_new_pattern or has_new_flags
        is_preserved_op = op_name in self.preserved_ops
        # Update interface
        save_button.set_sensitive(has_changes and not is_preserved_op)
    
    def _add_define(self):
        """Add a new SelectionOp."""
        LOGGER.log()
        # Get the definition and check it before asking for a name
        pattern, flags = self._get_define_in_ui()
        if not self._is_valid_re(pattern, flags):
            return False
        # Get objects
        combobox = self.builder.get_object('define_combobox')
        # Get the new name
        op_name = combobox.get_active_id()
        op_names = self._mod_conf.get_op_names()
        op_name = self._get_new_name(op_name, op_names, 'selection')
        if not op_name:
            return
        # Record new definition
        saved = self._save_op(op_name, pattern, flags)
        if not saved:
            return
        self._mod_conf.current_op_name = op_name
        # Update interface
        self._update_config_display()
        self._update_define_combobox()
        LOGGER.log('SelectionOp added: %s.' % op_name)
    
    def _save_define(self):
        """Update the current SelectionOp."""
        LOGGER.log()
        # Get objects
        combobox = self.builder.get_object('define_combobox')
        # Get circumstance
        op_name = combobox.get_active_id()
        pattern, flags = self._get_define_in_ui()
        # Update the definition
        saved = self._save_op(op_name, pattern, flags)
        if not saved:
            return
        # Update interface
        self._update_config_display()
        self._update_define_save_button()
        LOGGER.log('SelectionOp saved: %s.' % op_name)
    
    def _save_op(self, op_name, pattern, flags):
        """Add or update a SelectionOp."""
        LOGGER.log()
        if op_name in self.preserved_ops:
            return False
        if not self._is_valid_re(pattern, flags):
            return False
        new_op = self._mod_conf.get_op().copy_as(op_name)
        new_op.pattern = pattern
        new_op.flags = flags
        self._mod_conf.add_op(new_op)
        return True
    
    def _is_valid_re(self, pattern, flags):
        """
        Check the validity of the regular expression and
        inform the user if it fails.
        """
        LOGGER.log()
        try:
            is_valid = bool(re.compile(pattern, flags))
        except re.error, re_error:
            is_valid = False
            title = 'Click Config: error in input'
            flag_text =  '\n    I (IGNORECASE)' * bool(flags & re.I)
            flag_text += '\n    M (MULTILINE)'  * bool(flags & re.M)
            flag_text += '\n    S (DOTALL)'     * bool(flags & re.S)
            flag_text += '\n    X (VERBOSE)'    * bool(flags & re.X)
            flag_text = flag_text or '\n    (None)'
            message = ('Invalid regular expression pattern.'
                       '\n\nError:\n    %s'
                       '\n\nPattern:\n    %s'
                       '\n\nFlags:%s'
                       % (re_error.message, pattern, flag_text))
            dialogs.show_message(title,
                                 message,
                                 Gtk.MessageType.ERROR,
                                 self.window)
        return is_valid
    
    def _remove_define(self):
        """Select the preceding SelectionOp and remove the current one."""
        LOGGER.log()
        # Get objects
        combobox = self.builder.get_object('define_combobox')
        # Get circumstance
        op_name = combobox.get_active_id()
        is_preserved_op = op_name in self.preserved_ops
        op_names = self._mod_conf.get_op_names()
        op_index = op_names.index(op_name)
        preceding_op_name = op_names[op_index - 1]
        none_op_name = op_names[0]
        # Remove definition
        if is_preserved_op:
            return
        # Remove the select operation from configurations
        for configset in self._mod_conf.configsets:
            for i in range(5):
                if configset.op_names[i] == op_name:
                    configset.op_names[i] = none_op_name
        # Remove it from select operations set
        self._mod_conf.remove_op(op_name)
        self._mod_conf.current_op_name = preceding_op_name
        # Update interface
        self._update_config_display()
        self._update_define_combobox()
        LOGGER.log('SelectionOp removed: %s.' % op_name)
    

