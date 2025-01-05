import socket
import os
import threading
from multiprocessing import Process, Queue, Value
import logging
import time
from request_handler import RequestHandler

logging.basicConfig(
    filename='server.log',
    level=logging.INFO,
    format='%(asctime)s - %(message)s'
)


def worker_process(worker_id, request_queue, active_posts):
    """Worker process function"""
    print(f"Worker {worker_id} started")
    handler = RequestHandler(worker_id, active_posts)

    while True:
        try:
            # Get client socket from queue
            client_socket = request_queue.get()
            if client_socket == "STOP":
                break

            # Handle the request
            handler.handle_request(client_socket)

        except Exception as e:
            print(f"Worker {worker_id} error: {e}")


class HTTPServer:
    def __init__(self, host='localhost', port=8383, num_workers=4):
        self.host = host
        self.port = port
        self.num_workers = num_workers
        self.workers = []
        self.request_queue = Queue()
        self.active_posts = Value('i', 0)  # Shared counter for active POST requests

    def start(self):
        # Start worker processes
        for i in range(self.num_workers):
            worker = Process(target=worker_process, args=(i, self.request_queue, self.active_posts))
            worker.start()
            self.workers.append(worker)
            print(f"Created worker {i}")

        # Main server socket
        server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        server_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        server_socket.bind((self.host, self.port))
        server_socket.listen(5)
        print(f"Server listening on {self.host}:{self.port}")

        try:
            while True:
                client_socket, address = server_socket.accept()
                print(f"Accepted connection from {address}")
                self.request_queue.put(client_socket)

        except KeyboardInterrupt:
            print("\nShutting down server...")
            # Send stop signal to all workers
            for _ in range(self.num_workers):
                self.request_queue.put("STOP")
            # Wait for workers to finish
            for worker in self.workers:
                worker.join()
            server_socket.close()
            print("Server shutdown complete")


if __name__ == "__main__":
    if not os.path.exists("static"):
        os.makedirs("static")

    server = HTTPServer()
    server.start()
