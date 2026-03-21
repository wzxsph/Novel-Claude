class TextRedirector:
    def __init__(self, log_queue):
        self.log_queue = log_queue
    def write(self, text):
        if text:
            self.log_queue.put(text)
    def flush(self):
        pass
