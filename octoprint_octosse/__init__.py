# coding=utf-8
from __future__ import absolute_import

import flask
import json
import logging
import octoprint.plugin
import octoprint.printer
import queue

class OctossePlugin(
    octoprint.plugin.SettingsPlugin,
    octoprint.plugin.AssetPlugin,
    octoprint.plugin.TemplatePlugin,
    octoprint.plugin.BlueprintPlugin,
):
    def __init__(self):
        from octoprint.logging.handlers import CleaningTimedRotatingFileHandler
        self._console_logger = logging.getLogger(
            "octoprint.plugins.octosse.console"
        )
        console_logging_handler = CleaningTimedRotatingFileHandler(
            self._settings.get_plugin_logfile_path(postfix="console"),
            when="D",
            backupCount=3,
        )
        console_logging_handler.setFormatter(logging.Formatter("%(asctime)s %(message)s"))
        self._console_logger.addHandler(console_logging_handler)
        console_logging_handler.setLevel(logging.DEBUG)
        self._console_logger.propagate = False
        self.queues = []

    def debug_log(self, msg, *args):
        self._console_logger.debug(msg, args)

    @octoprint.plugin.BlueprintPlugin.route("/subscribe", methods=["GET"])
    def subscribe(self):
        (connection_string, port, baudrate, printer_profile) = self._printer.get_current_connection()
        initial_data = self._printer.get_current_data()
        initial_data["connection"] = {
            "connection_state": connection_string,
            "port": port,
            "baudrate": baudrate,
            "profile": printer_profile,
        }
        messages = self.listen() 
        stream = SseStream(messages, self._console_logger)
        self._printer.register_callback(OctosseCallback(self._printer, stream, self._console_logger))
        stream.send_event(initial_data)
        res = flask.Response(stream.stream(), mimetype='text/event-stream')
        res.call_on_close(lambda: stream.done())
        return res

    def listen(self):
        q = queue.Queue(maxsize=1)
        return q

    def is_blueprint_csrf_protected(self):
        return True

    ##~~ SettingsPlugin mixin

    def get_settings_defaults(self):
        return {
            # put your plugin's default settings here
        }

    ##~~ AssetPlugin mixin

    def get_assets(self):
        # Define your plugin's asset files to automatically include in the
        # core UI here.
        return {
            "js": ["js/octosse.js"],
            "css": ["css/octosse.css"],
            "less": ["less/octosse.less"]
        }

    ##~~ Softwareupdate hook

    def get_update_information(self):
        # Define the configuration for your plugin to use with the Software Update
        # Plugin here. See https://docs.octoprint.org/en/master/bundledplugins/softwareupdate.html
        # for details.
        return {
            "octosse": {
                "displayName": "Octosse Plugin",
                "displayVersion": self._plugin_version,

                # version check: github repository
                "type": "github_release",
                "user": "FreeMasen",
                "repo": "OctoPrint-Octosse",
                "current": self._plugin_version,

                # update method: pip
                "pip": "https://github.com/FreeMasen/OctoPrint-Octosse/archive/{target_version}.zip",
            }
        }

class SseStream:
    def __init__(self, queue, logger):
        self.queue = queue
        self.not_done = True
        self._logger = logger

    def stream(self):
        while self.not_done:
            try:
                msg = self.queue.get()
                self._logger.debug(f"yielding message {msg}")
                yield msg
            except:
                return

    def done(self):
        self.not_done = False

    def send_event(self, event):
        if not self.not_done:
            return
        event_json = json.dumps(event)
        msg = f"data: {event_json}\n\n"
        self.queue.put_nowait(msg)

class OctosseCallback(octoprint.printer.PrinterCallback):
    def __init__(self, printer, sink, logger):
        self.printer = printer
        self.sink = sink
        self._logger = logger

    def on_printer_send_current_data(self, data):
        self._logger.debug(f"on_printer_send_current_data: {data}")
        try:
            self.sink.send_event(data)
        except:
            self.printer.unregister_callback(self)


# If you want your plugin to be registered within OctoPrint under a different name than what you defined in setup.py
# ("OctoPrint-PluginSkeleton"), you may define that here. Same goes for the other metadata derived from setup.py that
# can be overwritten via __plugin_xyz__ control properties. See the documentation for that.
__plugin_name__ = "Octosse Plugin"


# Set the Python version your plugin is compatible with below. Recommended is Python 3 only for all new plugins.
# OctoPrint 1.4.0 - 1.7.x run under both Python 3 and the end-of-life Python 2.
# OctoPrint 1.8.0 onwards only supports Python 3.
__plugin_pythoncompat__ = ">=3,<4"  # Only Python 3

def __plugin_load__():
    global __plugin_implementation__
    __plugin_implementation__ = OctossePlugin()

    global __plugin_hooks__
    __plugin_hooks__ = {
        "octoprint.plugin.softwareupdate.check_config": __plugin_implementation__.get_update_information
    }
