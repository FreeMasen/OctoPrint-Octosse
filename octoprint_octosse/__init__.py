# coding=utf-8
from __future__ import absolute_import

import flask
import json
import logging
import octoprint.plugin
import octoprint.printer
import queue
from typing import Generator, Optional
from threading import Thread

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
            queue.put_nowait(
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
        q = queue.Queue()
        self.queues.append(q)
        res = flask.Response(
            flask.stream_with_context(create_generator(q)),
            mimetype="text/event-stream",
            headers={
                "Cache-Control": "no-cache",
            },
        )
        res.automatically_set_content_length = False
        q.put_nowait(initial_data)

        # res.call_on_close(lambda: self.response_disconnected(q))
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

def format_sse_message(obj: Optional[dict]) -> str:
    if obj is None:
        return ":comment\n\n"
    s = json.dumps(obj)
    return f"data: {s}"


def create_generator(queue) -> Generator[str, None, None]:
    try:
        yield format_sse_message(queue.get(False, 60))
    except queue.Empty:
        logger.info("queue was empty, sending comment")
        yield format_sse_message()
    except queue.Shutdown:
        logger.info("queue has been shutdown")
        return

__plugin_name__ = "Octosse Plugin"
__plugin_pythoncompat__ = ">=3,<4"
__plugin_implementation__ = OctossePlugin()
