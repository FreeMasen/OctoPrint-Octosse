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
    octoprint.plugin.StartupPlugin,
    octoprint.plugin.BlueprintPlugin,
    octoprint.plugin.EventHandlerPlugin,
):
    def __init__(self):
        self.queues = []

    def on_startup(self, host, port):
        logger.info(f"on_startup({host}, {port})")

    def on_after_startup(self):
        logger.info("on_after_startup")

    def on_event(self, event, payload):
        logger.info(f"event {payload}")
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
        initial_data = self.get_initial_info()
        messages = self.listen() 
        stream = SseStream(messages)
        stream.send_event(initial_data)
        self.queues.append(stream)
        res = flask.Response(stream.stream(), mimetype='text/event-stream')
        res.call_on_close(lambda: self.response_disconnected(stream))
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

    def listen(self):
        q = queue.Queue(maxsize=0)
        return q

    def is_blueprint_csrf_protected(self):
        return True


class SseStream:
    def __init__(self, queue):
        self.queue = queue
        self.not_done = True

    def stream(self):
        while self.not_done:
            try:
                msg = self.queue.get()
                logger.info(f"yielding message {msg}")
                yield msg
            except:
                return

    def done(self):
        self.not_done = False

    def send_event(self, event):
        logger.info(f"send_event {event}")
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
        logger.info(f"on_printer_add_log: {data}")
        try:
            self.sink.send_event(data)
        except Exception as ex:
            logger.info(f"error in on_printer_add_log, unregestering: {ex}")
            self.printer.unregister_callback(self)

    def on_printer_add_message(self, data):
        logger.info(f"on_printer_add_message: {data}")
        try:
            self.sink.send_event(data)
        except Exception as ex:
            logger.info(f"error in on_printer_add_message, unregestering: {ex}")
            self.printer.unregister_callback(self)

    def on_printer_received_registered_message(self, data):
        logger.info(f"on_printer_received_registered_message: {data}")
        try:
            self.sink.send_event(data)
        except Exception as ex:
            logger.info(
                f"error in on_printer_received_registered_message, unregestering: {ex}"
            )
            self.printer.unregister_callback(self)

    def on_printer_send_initial_data(self, data):
        logger.info(f"on_printer_send_initial_data: {data}")
        try:
            self.sink.send_event(data)
        except Exception as ex:
            logger.info(f"error in on_printer_send_initial_data, unregestering: {ex}")
            self.printer.unregister_callback(self)

    def on_printer_send_current_data(self, data):
        logger.info(f"on_printer_send_current_data: {data}")
        try:
            self.sink.send_event(data)
        except Exception as ex:
            logger.info(f"error in on_printer_send_current_data, unregestering: {ex}")
            self.printer.unregister_callback(self)

__plugin_name__ = "Octosse Plugin"
__plugin_pythoncompat__ = ">=3,<4"
__plugin_implementation__ = OctossePlugin()
