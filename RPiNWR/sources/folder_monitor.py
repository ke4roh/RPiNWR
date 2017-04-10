from .alert_source import AlertSource, new_message
from ..messages import NWSText
from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler
from threading import Lock
from circuits import handler
import os
import time

class FolderMonitor(AlertSource):
    def __init__(self, location, monitor_path, quiescent_time=3):
        self.monitor_path = monitor_path
        self.observer = Observer()
        self.__listener = _FolderMonitorEventListener()
        self.observer.schedule(self.__listener, monitor_path, recursive=True)
        self.observer.start()
        self.quiescent_time = quiescent_time
        super().__init__(location)
        self.last_status_time = 0

    @handler("stopped")
    def stopped(self, manager):
        self.observer.stop()
        self.observer.join()

    @handler("generate_events")
    def generate_events(self, event):
        event.reduce_time_left(self.quiescent_time)
        with self.__listener.hot_items_lock:
            done = set(
                filter(lambda f: os.path.getmtime(f) < (time.time() - self.quiescent_time), self.__listener.hot_items))
            self.__listener.hot_items -= done
        for f in done:
            with open(f) as fh:
                msg = fh.read()
            tmsg = NWSText.factory(msg)
            if len(tmsg):
                for m in tmsg:
                    for v in m.vtec:
                        self.fireEvent(new_message(v))
                        # TODO os.remove(f) - except folders


class _FolderMonitorEventListener(FileSystemEventHandler):
    def __init__(self):
        self.hot_items = set()
        self.hot_items_lock = Lock()

    def on_created(self, event):
        self.on_modified(event)

    def on_modified(self, event):
        if not event.is_directory:
            with self.hot_items_lock:
                self.hot_items.add(event.src_path)


