# coding=utf-8
from __future__ import absolute_import

import flask
import json
import logging
import octoprint.plugin
import octoprint.printer
import queue
from typing import Generator

logger = logging.getLogger("octoprint.plugins.octosse")

IGNORED_EVENTS = set(
    [
        "ClientOpened",
        "UserLoggedIn",
        "ClientAuthed",
        "ConnectionsAutorefreshed",
        "Startup",
        "plugin_firmware_check_warning",
        "plugin_pi_support_throttle_state",
    ]
)

class OctossePlugin(
    octoprint.plugin.SimpleApiPlugin,
    octoprint.plugin.EventHandlerPlugin,
):
    def __init__(self):
        self.queues = []

    def on_event(self, event, payload):
        if event in IGNORED_EVENTS:
            logger.info("unhandled event {}:\n{}".format(event, json.dumps(payload)))
            return
        for queue in self.queues:
            queue.send_event(
                {
                    "event": event,
                    "data": payload,
                }
            )
    def get_api_commands(self):
        return dict()

    def on_api_command(self, command, data):
        logger.info(f"api command: {command} {data}")

    def on_api_get(self, request):
        logger.info("subscribing!")
        initial_data = self.get_initial_info()
        stream = SseStream()
        self.queues.append(stream)
        res = flask.Response(
            stream.stream(initial_data),
            mimetype="text/event-stream",
            headers={
                "Content-Type": "text/event-stream",
                "Cache-Control": "no-cache",
            }
        )
        # res.call_on_close(lambda: self.response_disconnected(stream))
        return res

    def get_initial_info(self):
        (connection_string, port, baudrate, printer_profile) = (
            self._printer.get_current_connection()
        )
        initial_data = self._printer.get_current_data()
        initial_data["connection"] = {
            "connection_state": connection_string,
            "port": port,
            "baudrate": baudrate,
            "profile": printer_profile,
        }
        return initial_data

    def response_disconnected(self, stream):
        logger.info("response_disconnected")
        stream.done()
        try:
            self.queues.remove(stream)
        except:
            pass

    def is_blueprint_csrf_protected(self):
        return True


class SseStream:
    def __init__(self):
        self.queue = queue.Queue(maxsize=0)
        self.not_done = True

    def stream(self, initial_data) -> Generator[str, None, None]:
        if self.initial_data is not None:
            yield self.format_event(initial_data)
        while self.not_done:
            try:
                msg = self.queue.get()
                logger.info("yielding {msg}")
                yield msg
            except:
                return

    def done(self):
        self.not_done = False

    def send_event(self, event):
        if not self.not_done:
            return
        logger.info("queueing {}".format(event.get("event", "unknown-event")))
        self.queue.put_nowait(self.format_event(event))

    def format_event(self, event):
        event_json = json.dumps(event)
        return f"data: {event_json}\n\n"

__plugin_name__ = "Octosse Plugin"
__plugin_pythoncompat__ = ">=3,<4"
__plugin_implementation__ = OctossePlugin()
