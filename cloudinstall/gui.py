#
# gui.py - Cloud install gui components
#
# Copyright 2014 Canonical, Ltd.
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU Affero General Public License as
# published by the Free Software Foundation, either version 3 of the
# License, or (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU Affero General Public License for more details.
#
# You should have received a copy of the GNU Affero General Public License
# along with this program.  If not, see <http://www.gnu.org/licenses/>.

""" Pegasus - gui interface to  Installer """

from __future__ import unicode_literals
import re
import sys
import logging
import functools
from operator import attrgetter
import random

import urwid
from urwid import (AttrWrap, Text, Columns, Overlay, LineBox,
                   ListBox, Filler, BoxAdapter, Frame, WidgetWrap,
                   RadioButton, IntEdit, Padding, Pile,
                   SimpleListWalker, Divider, Button,

                   signals, emit_signal, connect_signal)
from cloudinstall import utils
from cloudinstall.status import get_sync_status
from cloudinstall.ui import (ScrollableWidgetWrap,
                             ScrollableListBox)
from cloudinstall.ui.helpscreen import HelpScreen

log = logging.getLogger('cloudinstall.gui')
sys.excepthook = utils.global_exchandler

TITLE_TEXT = "Ubuntu Openstack Installer - Dashboard"

# - Properties ----------------------------------------------------------------
IS_TTY = re.match('/dev/tty[0-9]', utils.get_command_output('tty')['stdout'])

# Time to lock in seconds
LOCK_TIME = 120

padding = functools.partial(Padding, left=2, right=2)


class AddCharmDialog(WidgetWrap):
    """ Adding charm dialog

    :param list charms: list of charms that can be added
    :param cb: callback routine to process submit/cancel actions
    :returns: input from dialog
    """

    __metaclass__ = signals.MetaSignals
    signals = ['done']

    def __init__(self, charm_classes, cb, **kwargs):
        self.charms = charm_classes
        self.cb = cb
        self.count_editor = None
        self.boxes = []

        w = self._build_widget()
        w = AttrWrap(w, "dialog")

        # Handle signals from add charm
        connect_signal(self, 'done', cb)
        super().__init__(w)

    def submit(self):
        """ Handle OK submit """
        selected = [r for r in self.boxes if
                    r is not self.count_editor
                    and r.get_state()][0]
        _charm_to_deploy = selected.label
        n = self.count_editor.value()
        self.emit_done_signal(n, _charm_to_deploy)

    def cancel(self):
        """ Handle cancel action """
        self.emit_done_signal()

    def emit_done_signal(self, *args):
        emit_signal(self, 'done', *args)

    def _build_widget(self, **kwargs):
        # Charm selections
        num_of_items, charm_sel = self._insert_charm_selections()

        # Control buttons
        buttons = self._insert_buttons()

        return LineBox(
            BoxAdapter(
                ListBox([charm_sel, Divider(), buttons]),
                height=num_of_items+2),
            title="Add unit")

    def _insert_charm_selections(self):
        first_index = 0
        bgroup = []
        for i, charm_class in enumerate(self.charms):
            charm = charm_class
            if charm.name() and not first_index:
                first_index = i
            r = RadioButton(bgroup, charm.name())
            r.text_label = charm.name()
            self.boxes.append(r)

        # Add input widget for specifying NumUnits
        self.count_editor = IntEdit("Number of units to add: ", 1)
        self.boxes.append(self.count_editor)
        wrapped_boxes = self._wrap_focus(self.boxes)
        items = ListBox(SimpleListWalker(wrapped_boxes))
        items.set_focus(first_index)
        return (len(self.boxes), BoxAdapter(items, len(self.boxes)))

    def _insert_buttons(self):
        bs = [Button("Ok", self.yes), Button("Cancel", self.no)]
        wrapped_buttons = self._wrap_focus(bs)
        return Columns(wrapped_buttons)

    def yes(self, button):
        self.submit()

    def no(self, button):
        self.cancel()

    def _wrap_focus(self, widgets, unfocused=None):
        try:
            return [AttrWrap(w, "focus") for w in widgets]
        except TypeError:
            return AttrWrap(widgets, "focus")


class Banner(ScrollableWidgetWrap):
    def __init__(self):
        self.text = []

        self.BANNER = [
            "",
            "",
            "Ubuntu Openstack Installer",
            "",
            "By Canonical, Ltd.",
            "",

        ]
        super().__init__(self._create_text())

    def _create_text(self):
        self.text = []
        for line in self.BANNER:
            self._insert_line(line)

        return ScrollableListBox(self.text)

    def _insert_line(self, line):
        text = Text(line, align='center')
        self.text.append(text)


class NodeInstallWaitMode(ScrollableWidgetWrap):
    def __init__(self):
        super().__init__(self._build_node_waiting())

    def _build_node_waiting(self):
        """ creates a loading screen if nodes do not exist yet """
        text = Text("\n\n\nInstaller is initializing nodes. "
                    "Please wait.\n\n\n",
                    align="center")
        load_box = [AttrWrap(Text("\u2582",
                                  align="center"), "pending_icon_on"),
                    AttrWrap(Text("\u2581",
                                  align="center"),
                             "pending_icon_on"),
                    AttrWrap(Text("\u2583",
                                  align="center"), "pending_icon_on"),
                    AttrWrap(Text("\u2584",
                                  align="center"),
                             "pending_icon_on"),
                    AttrWrap(Text("\u2585",
                                  align="center"),
                             "pending_icon_on"),
                    AttrWrap(Text("\u2586",
                                  align="center"),
                             "pending_icon_on"),
                    AttrWrap(Text("\u2587",
                                  align="center"),
                             "pending_icon_on"),
                    AttrWrap(Text("\u2588",
                                  align="center"),
                             "pending_icon_on")]

        # Add loading boxes
        random.shuffle(load_box)
        loading_boxes = []
        loading_boxes.append(('weight', 1, Text('')))
        for i in load_box:
            loading_boxes.append(('pack',
                                 load_box[random.randrange(len(load_box))]))
        loading_boxes.append(('weight', 1, Text('')))
        loading_boxes = Columns(loading_boxes)

        return ScrollableListBox([text, loading_boxes])


class NodeViewMode(ScrollableWidgetWrap):
    def __init__(self, nodes, juju_state, maas_state, **kwargs):
        nodes = [] if nodes is None else nodes
        self.juju_state = juju_state
        self.maas_state = maas_state
        widget = self._build_widget(nodes, **kwargs)
        super().__init__(widget)

    def _build_widget(self, nodes, **kwargs):
        unit_info = []
        for node in nodes:
            node_pile = []
            node_cols = []
            charm_class, service = node
            if charm_class.menuable and len(service.units) > 0:
                for u in sorted(service.units, key=attrgetter('unit_name')):
                    node_cols = self._build_node_columns(u, charm_class)
                    node_pile.append(node_cols)

                unit_info.append(padding(LineBox(
                    Pile(node_pile),
                    title=charm_class.display_name,
                    lline=' ',
                    blcorner=' ',
                    rline=' ',
                    bline=' ',
                    brcorner=' ')))

        return ScrollableListBox(unit_info)

    def _build_node_columns(self, unit, charm_class):
        """ builds columns of node status """
        node_cols = []

        status_txt = "[{}] ".format(unit.agent_state)

        # unit.agent_state may be "pending" despite errors elsewhere,
        # so we check for error_info first.
        # if the agent_state is "error", _detect_errors returns that.
        error_info = self._detect_errors(unit, charm_class)

        if error_info:
            status = ("error_icon", "\N{TETRAGRAM FOR FAILURE} ")
            if unit.agent_state != "error":
                status_txt = "[{} (error)] ".format(unit.agent_state)
        elif unit.agent_state == "pending":
            pending_status = [("pending_icon", "\N{CIRCLED BULLET} "),
                              ("pending_icon", "\N{CIRCLED WHITE BULLET} "),
                              ("pending_icon_on", "\N{FISHEYE} ")]
            status = random.choice(pending_status)
        elif unit.agent_state == "installed":
            status = ("pending_icon", "\N{HOURGLASS} ")
        elif unit.agent_state == "started":
            status = ("success_icon", "\u2713 ")
        elif unit.agent_state == "stopped":
            status = ("error_icon", "\N{BLACK FLAG} ")
        elif unit.agent_state == "down":
            status = ("error_icon", "\N{DOWNWARDS BLACK ARROW} ")
        else:
            # shouldn't get here
            status = "? "

        node_cols.append(('pack', Text([status, status_txt])))
        if unit.public_address:
            node_cols.append(
                ('pack',
                 Text("{0:<12}".format(unit.public_address))))
        elif error_info:
            node_cols.append(('pack', Text("{:<12}".format("Error"))))
        else:
            node_cols.append(
                ('pack',
                 Text("{:<12}".format("IP Pending"))))

        if error_info:
            node_cols.append(('pack', Text(" | {}".format(error_info))))
        else:
            hw_text = Text([" | "] + self._get_hardware_info(unit))

            if 'glance-simplestreams-sync' in unit.unit_name:
                status_oneline = get_sync_status().replace("\n", " - ")
                sync_text = Text('   ' + status_oneline)
                node_cols.append(Pile([hw_text, sync_text]))
            else:
                node_cols.append(hw_text)

        return Columns(node_cols)

    def _get_hardware_info(self, unit):
        """Get hardware info from juju or maas

        Returns list of text and formatting tuples
        """
        juju_machine = self.juju_state.machine(unit.machine_id)
        maas_machine = None
        if self.maas_state:
            maas_machine = self.maas_state.machine(juju_machine.instance_id)

        m = juju_machine
        if juju_machine.arch == "N/A":
            if maas_machine:
                m = maas_machine
            else:
                return self._get_container_info(unit)

        return ["Machine {}: ".format(juju_machine.machine_id)] \
            + self._hardware_info_for_machine(m)

    def _get_container_info(self, unit):
        """Attempt to get hardware info of host machine for a unit that looks
        like a container.

        """
        base_machine = self.juju_state.base_machine(unit.machine_id)

        if base_machine.arch == "N/A" and self.maas_state is not None:
            m = self.maas_state.machine(base_machine.instance_id)
        else:
            m = base_machine

        container_id = unit.machine_id.split('/')[-1]
        base_id = base_machine.machine_id

        rl = ["Container {} (Machine {}".format(container_id,
                                                base_id)]
        if m:
            rl += [":  "] + self._hardware_info_for_machine(m) + [")"]
        else:
            rl += [")"]
        return rl

    def _hardware_info_for_machine(self, m):
        return [('label', 'arch'), ' {}  '.format(m.arch),
                ('label', 'cores'), ' {}  '.format(m.cpu_cores),
                ('label', 'mem'), ' {}  '.format(m.mem),
                ('label', 'storage'), ' {}'.format(m.storage)]

    def _detect_errors(self, unit, charm_class):
        """Look in multiple places for an error.

        Return error info string if present,
        or None if no error is found
        """
        unit_machine = self.juju_state.machine(unit.machine_id)

        if unit.agent_state == "error":
            return unit.agent_state_info.lstrip()

        err_info = ""

        if unit.agent_state == 'pending' and \
           unit_machine.agent_state is '' and \
           unit_machine.agent_state_info is not None:

            # detect MAAS API errors, returned as 409 conflict:
            if "409" in unit_machine.agent_state_info:
                if charm_class.constraints is not None:
                    err_info = "Found no machines meeting constraints: "
                    err_info += ', '.join(["{}='{}'".format(k, v) for k, v
                                           in charm_class.constraints.items()])
                else:
                    err_info += "No machines available for unit."
            else:
                err_info += unit_machine.agent_state_info
            return err_info
        return None


class Header(WidgetWrap):
    def __init__(self):
        w = []
        w.append(AttrWrap(padding(Text(TITLE_TEXT)), "header_title"))
        w.append(AttrWrap(Text(
            '(A)dd units \N{BULLET} (H)elp \N{BULLET} '
            '(R)efresh \N{BULLET} (Q)uit', align='center'), "header_menu"))
        w = Pile(w)
        super().__init__(w)


class StatusBar(WidgetWrap):
    """Displays text."""

    INFO = "[INFO]"
    ERROR = "[ERROR]"
    ARROW = " \u21e8 "

    def __init__(self, text=''):
        self._pending_deploys = Text('')
        self._status_line = Text(text)
        self._horizon_url = Text('')
        self._jujugui_url = Text('')
        self._openstack_rel = Text('Icehouse (2014.1.1)')
        self._status_extra = self._build_status_extra()
        status = Pile([self._pending_deploys,
                       self._status_line, self._status_extra])
        super().__init__(status)

    def _build_status_extra(self):
        status = []
        status.append(Pile([self._horizon_url, self._jujugui_url]))
        status.append(('pack', self._openstack_rel))
        return AttrWrap(Columns(status), 'status_extra')

    def set_dashboard_url(self, ip=None):
        """ sets horizon dashboard url """
        text = "Openstack Dashboard: "
        if not ip:
            text += "(pending)"
        else:
            text += "http://{}/horizon".format(ip)
        return self._horizon_url.set_text(text)

    def set_jujugui_url(self, ip=None):
        """ sets juju gui url """
        text = "{0:<21}".format("JujuGUI:")
        if not ip:
            text += "(pending)"
        else:
            text += "http://{}/".format(ip)
        return self._jujugui_url.set_text(text)

    def message(self, text):
        """Write `text` on the footer."""
        self._status_line.set_text(text)

    def error_message(self, text):
        self.message([('error', self.ERROR),
                      ('default', self.ARROW + text)])

    def info_message(self, text):
        self.message([('info', self.INFO),
                      ('default', self.ARROW + text)])

    def set_pending_deploys(self, pending_deploys):
        if len(pending_deploys) > 0:
            msg = "Pending deploys: " + ", ".join(pending_deploys)
            self._pending_deploys.set_text(msg)
        else:
            self._pending_deploys.set_text('')

    def clear(self):
        """Clear the text."""
        self._w.set_text('')


class StepInfo(WidgetWrap):
    def __init__(self, msg=None):
        if not msg:
            msg = "Processing."
        super().__init__(AttrWrap(LineBox(Text(msg)), 'dialog'))


def _check_encoding():
    """Set the Urwid global byte encoding to utf-8.

    Exit the application if, for some reasons, the change does not have effect.
    """
    urwid.set_encoding('utf-8')
    if not urwid.supports_unicode():
        # Note: the following message must only include ASCII characters.
        msg = (
            'Error: your terminal does not seem to support UTF-8 encoding.\n'
            'Please check your locale settings.\n'
            'On Ubuntu, running the following might fix the problem:\n'
            '  sudo locale-gen en_US.UTF-8\n'
            '  sudo dpkg-reconfigure locales'
        )
        sys.exit(msg.encode('ascii'))


class PegasusGUI(WidgetWrap):
    def __init__(self):
        _check_encoding()  # Make sure terminal supports utf8
        header = Header()
        body = Banner()
        footer = StatusBar('')

        self.frame = Frame(body,
                           header=header,
                           footer=footer)

        super().__init__(self.frame)

    def _build_overlay_widget(self,
                              top_w,
                              align,
                              width,
                              valign,
                              height,
                              min_width,
                              min_height):
        return Overlay(top_w=Filler(top_w),
                       bottom_w=self.frame,
                       align=align,
                       width=width,
                       valign=valign,
                       height=height,
                       min_width=width,
                       min_height=height)

    def show_widget_on_top(self,
                           widget,
                           width,
                           height,
                           align='center',
                           valign='middle',
                           min_height=0,
                           min_width=0):
        """Show `widget` on top of :attr:`frame`."""
        self._w = self._build_overlay_widget(top_w=widget,
                                             align=align,
                                             width=width,
                                             valign=valign,
                                             height=height,
                                             min_width=min_width,
                                             min_height=min_height)

    def focus_next(self):
        self.frame.body.scroll_down()

    def focus_previous(self):
        self.frame.body.scroll_up()

    def focus_first(self):
        self.frame.body.scroll_top()

    def focus_last(self):
        self.frame.body.scroll_bottom()

    def hide_widget_on_top(self):
        """Hide the topmost widget (if any)."""
        self._w = self.frame

    def show_help_info(self):
        widget = HelpScreen()
        self.show_widget_on_top(widget, width=80, height=22,
                                align="center", valign="middle",
                                min_height=10)

    def hide_help_info(self):
        self.hide_widget_on_top()

    def show_step_info(self, msg=None):
        self.hide_step_info()
        widget = StepInfo(msg)
        self.show_widget_on_top(widget, width=50, height=3, align="center",
                                valign="middle", min_height=10)

    def hide_step_info(self):
        self.hide_widget_on_top()

    def show_add_charm_info(self, charms, cb):
        widget = AddCharmDialog(charms, cb)
        self.show_widget_on_top(widget, width=50, height=10)

    def hide_add_charm_info(self):
        self.hide_widget_on_top()

    def set_pending_deploys(self, pending_charms):
        self.frame.footer.set_pending_deploys(pending_charms)

    def status_message(self, text):
        self.frame.footer.message(text)
        self.frame.set_footer(self.frame.footer)

    def status_error_message(self, message):
        self.frame.footer.error_message(message)

    def status_info_message(self, message):
        self.frame.footer.info_message(message)

    def status_dashboard_url(self, ip):
        self.frame.footer.set_dashboard_url(ip)

    def status_jujugui_url(self, ip):
        self.frame.footer.set_jujugui_url(ip)

    def clear_status(self):
        self.frame.footer = None
        self.frame.set_footer(self.frame.footer)

    def render_nodes(self, nodes, juju_state, maas_state, **kwargs):
        self.frame.body = NodeViewMode(nodes, juju_state, maas_state)
        self.frame.set_body(self.frame.body)

    def render_node_install_wait(self, **kwargs):
        self.frame.body = NodeInstallWaitMode()
        self.frame.set_body(self.frame.body)
