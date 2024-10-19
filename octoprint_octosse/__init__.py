# coding=utf-8
from __future__ import absolute_import

import flask
import json
import logging
import octoprint.plugin
import octoprint.printer
import queue

logger = logging.getLogger("octoprint.plugins.octosse")


class OctossePlugin(
    octoprint.plugin.SettingsPlugin,
    octoprint.plugin.AssetPlugin,
    octoprint.plugin.TemplatePlugin,
    octoprint.plugin.BlueprintPlugin,
    octoprint.plugin.EventHandlerPlugin,
):
    def __init__(self):
        self.queues = []

    def on_event(self, event, payload):
        logger.debug(f"event {payload}")
        for queue in self.queues:
            queue.send_event(
                {
                    "event": event,
                    "data": payload,
                }
            )

    @octoprint.plugin.BlueprintPlugin.route("/subscribe", methods=["GET"])
    def subscribe(self):
        logger.info("subscribing!")
        (connection_string, port, baudrate, printer_profile) = self._printer.get_current_connection()
        initial_data = self._printer.get_current_data()
        initial_data["connection"] = {
            "connection_state": connection_string,
            "port": port,
            "baudrate": baudrate,
            "profile": printer_profile,
        }
        messages = self.listen() 
        stream = SseStream(messages)
        stream.send_event(initial_data)
        self.queues.append(stream)
        res = flask.Response(stream.stream(), mimetype='text/event-stream')
        res.call_on_close(lambda: self.response_disconnected(stream))
        return res

    def response_disconnected(self, stream):
        stream.done()
        try:
            self.queues.remove(stream)
        except:
            pass

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
    def __init__(self, queue):
        self.queue = queue
        self.not_done = True

    def stream(self):
        while self.not_done:
            try:
                msg = self.queue.get()
                logger.debug(f"yielding message {msg}")
                yield msg
            except:
                return

    def done(self):
        self.not_done = False

    def send_event(self, event):
        logger.debug(f"send_event {event}")
        if not self.not_done:
            return
        event_json = json.dumps(event)
        msg = f"data: {event_json}\n\n"
        self.queue.put_nowait(msg)

class OctosseCallback(octoprint.printer.PrinterCallback):
    def __init__(self, printer, sink):
        self.printer = printer
        self.sink = sink

    def on_printer_add_log(self, data):
        logger.debug(f"on_printer_add_log: {data}")
        try:
            self.sink.send_event(data)
        except Exception as ex:
            logger.debug(f"error in on_printer_add_log, unregestering: {ex}")
            self.printer.unregister_callback(self)

    def on_printer_add_message(self, data):
        logger.debug(f"on_printer_add_message: {data}")
        try:
            self.sink.send_event(data)
        except Exception as ex:
            logger.debug(f"error in on_printer_add_message, unregestering: {ex}")
            self.printer.unregister_callback(self)

    def on_printer_received_registered_message(self, data):
        logger.debug(f"on_printer_received_registered_message: {data}")
        try:
            self.sink.send_event(data)
        except Exception as ex:
            logger.debug(
                f"error in on_printer_received_registered_message, unregestering: {ex}"
            )
            self.printer.unregister_callback(self)

    def on_printer_send_initial_data(self, data):
        logger.debug(f"on_printer_send_initial_data: {data}")
        try:
            self.sink.send_event(data)
        except Exception as ex:
            logger.debug(f"error in on_printer_send_initial_data, unregestering: {ex}")
            self.printer.unregister_callback(self)

    def on_printer_send_current_data(self, data):
        logger.debug(f"on_printer_send_current_data: {data}")
        try:
            self.sink.send_event(data)
        except Exception as ex:
            logger.debug(f"error in on_printer_send_current_data, unregestering: {ex}")
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
