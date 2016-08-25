#!/usr/bin/python3

import signal
import os
import time

import gi
gi.require_version('Gtk', '3.0')
gi.require_version('Notify', '0.7')

from gi.repository import Gtk, GLib
from gi.repository import Notify


APPID = 'Pomodoro'
CURRDIR = os.path.dirname(os.path.abspath(__file__))
ICON = os.path.join(CURRDIR, 'icon.png')


class TrayIcon:
    def __init__(self, appid, icon, menu):
        self.menu = menu
        self.ind = Gtk.StatusIcon()
        self.ind.set_from_file(icon)
        self.ind.connect('popup-menu', self.on_popup_menu)
        self.ind.set_tooltip_text('Pomodoro')

    def on_popup_menu(self, icon, button, time):
        self.menu.popup(None, None, Gtk.StatusIcon.position_menu,
                        icon, button, time)


class Timer(object):
    """
    Pomodoro timer. Substracts 1 second on tick() call,
    reinits self value when current time is over.
    """

    def __init__(self, work, short_break, long_break, num_of_intervals):
        self.work = {'min': int(work), 'sec': 0}
        self.short_break = {'min': int(short_break), 'sec': 0}
        self.long_break = {'min': int(long_break), 'sec': 0}
        self.num_of_intervals = int(num_of_intervals)

        # TODO: Remove after testing.
        # self.work = {'min': 0, 'sec': 2}
        # self.short_break = {'min': 0, 'sec': 1}
        # self.long_break = {'min': 0, 'sec': 1}
        # self.num_of_intervals = 5

        self.value = self.work.copy()
        self.round = 1
        self.is_work = True


    def get_time(self):
        return '%02d:%02d' % (self.value['min'], self.value['sec'])


    def tick(self):
        """Substruct 1 sec and return timer's value"""

        self.value['sec'] -= 1
        if self.value['sec'] == -1:
            self.value['sec'] = 59
            self.value['min'] -= 1
        if self.value['min'] == -1:
            self.next_round()

        return self.get_time()


    def next_round(self):
        """Update timer value when current time is over"""

        self.is_work = not self.is_work

        # Go to next round of work
        if self.is_work:
            self.value = self.work.copy()
            self.round += 1

            # Reset round counter
            if self.round > self.num_of_intervals:
                self.round = 1
        # Go to rest
        else:
            if self.round < self.num_of_intervals:
                self.value = self.short_break.copy()
            else:
                self.value = self.long_break.copy()


class Handler(object):
    def __init__(self, builder, tray_icon):
        self.builder = builder
        self.tray_icon = tray_icon

        # Main window
        self.window = self.builder.get_object('main_window')
        self.window.connect('notify::is-active', self.is_active_changed)

        # Inputs
        self.input_work = self.builder.get_object('input_work')
        self.input_short_break = self.builder.get_object('input_short_break')
        self.input_long_break = self.builder.get_object('input_long_break')
        self.input_num_of_intervals = self.builder.get_object('input_intervals_number')

        # Timer
        self.label_timer = self.builder.get_object('label_timer')
        self.timer = None
        self.in_progress = False
        self.is_paused = False

        # Buttons
        self.btn_start = self.builder.get_object('btn_start')
        self.btn_pause = self.builder.get_object('btn_pause')
        self.btn_stop = self.builder.get_object('btn_stop')

        # Dialogs
        self.about = self.builder.get_object('dialog_about')


    def is_active_changed(self, window, param):
        """Remove urgency hint. Otherwise it won't work."""
        if window.props.is_active:
            self.window.set_urgency_hint(False)


    def on_start(self, button):
        """Start/resume timer"""

        work_time = self.input_work.get_text()

        # Just resume if paused
        if self.is_paused:
            self.is_paused = False
        # Init new timer
        else:
            self.timer = Timer(
                work_time,
                self.input_short_break.get_text(),
                self.input_long_break.get_text(),
                self.input_num_of_intervals.get_text()
            )
            self.tray_icon.set_tooltip_text(
                'Work: ' + work_time + ':00'
            )

        self.in_progress = True
        self.label_timer.set_text(work_time+':00')

        # Repeat every second while timer_tick() returns True
        GLib.timeout_add_seconds(1, self.timer_tick)


    def on_pause(self, button):
        """Pause timer"""
        if self.in_progress:
            self.is_paused = True


    def on_stop(self, button):
        """Stop (reset) timer"""
        self.label_timer.set_text('00:00')
        self.tray_icon.set_tooltip_text('Pomodoro')
        self.in_progress = False
        self.is_paused = False


    def on_about_open(self, menu_item):
        self.about.run()
        self.about.hide()


    def on_about_close(self, menu_item):
        x = self.about.hide()


    def timer_tick(self):
        """Substract 1 second from timer"""

        if not self.in_progress or self.is_paused:
            return False  # stop Glib timeout

        # Update timer
        time_string = self.timer.tick()

        # Notify if interval ended
        if time_string == '00:00':
            if self.timer.is_work:
                msg = 'Time to relax'
            else:
                msg = 'Get back to work'

            # Highlight window in panel
            self.window.set_urgency_hint(True)

            Notify.Notification.new('Pomodoro', msg, ICON).show()

        # Update tray icon tooltip
        tray_text = 'Work: ' if self.timer.is_work else 'Break: '
        self.tray_icon.set_tooltip_text(tray_text+time_string)

        self.label_timer.set_text(time_string)
        return True  # continue Glib timeout


    def on_quit(self, *args):
        Notify.uninit()
        Gtk.main_quit()


class App(object):
    def __init__(self):
        # Handle pressing Ctr+C properly, ignored by default
        signal.signal(signal.SIGINT, signal.SIG_DFL)

        builder = Gtk.Builder()
        ui_file = os.path.join(CURRDIR, 'ui.glade')
        builder.add_from_file(ui_file)

        menu = builder.get_object('menu_file')
        tray_icon = TrayIcon(APPID, ICON, menu)

        builder.connect_signals(Handler(builder, tray_icon.ind))

        Notify.init(APPID)

        window = builder.get_object('main_window')
        window.show_all()


if __name__ == '__main__':
    app = App()
    Gtk.main()
