import socket
import os
from datetime import datetime
import time
import uuid
from multiprocessing import Pipe, Process, Lock, Value
import threading
from concurrent.futures import ThreadPoolExecutor
import msvcrt


class FileLocker:
    def __init__(self, file_obj):
        self.file_obj = file_obj

    def __enter__(self):
        msvcrt.locking(self.file_obj.fileno(), msvcrt.LK_NBLCK, 1)
        return self.file_obj

    def __exit__(self, exc_type, exc_val, exc_tb):
        try:
            self.file_obj.seek(0)
            msvcrt.locking(self.file_obj.fileno(), msvcrt.LK_UNLCK, 1)
        except:
            pass


class Worker(Process):
    def __init__(self, worker_id, pipe, log_lock):
        super().__init__()
        self.worker_id = worker_id
        self.pipe = pipe
        self.log_lock = log_lock
        self.static_dir = "static"

        if not os.path.exists(self.static_dir):
            os.makedirs(self.static_dir)

    def handle_get_request(self, request_data):
        try:
            path = request_data['path']
            file_path = os.path.join(self.static_dir, path.lstrip('/'))
            if not os.path.normpath(file_path).startswith(os.path.normpath(self.static_dir)):
                return {
                    'status': 403,
                    'content': b'Access forbidden'
                }

            if os.path.exists(file_path) and os.path.isfile(file_path):
                with open(file_path, 'rb') as f:
                    with FileLocker(f):
                        content = f.read()

                response = {
                    'status': 200,
                    'headers': {
                        'Content-Type': 'text/plain',
                        'Content-Length': len(content)
                    },
                    'content': content
                }
            else:
                response = {
                    'status': 404,
                    'content': b'File not found'
                }
            return response
        except Exception as e:
            return {
                'status': 500,
                'content': f'Internal server error: {str(e)}'.encode()
            }

    def handle_post_request(self, request_data):
        try:
            content = request_data.get('content', '').strip()
            if not content:
                return {
                    'status': 400,
                    'content': b'Empty content is not allowed'
                }

            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            request_id = str(uuid.uuid4())[:8]
            filename = f"{timestamp}_{request_id}.txt"
            file_path = os.path.join(self.static_dir, filename)

            time.sleep(2)

            try:
                with open(file_path, 'w') as f:
                    with FileLocker(f):
                        f.write(content)
                        f.flush()
                        os.fsync(f.fileno())
            except Exception as file_error:
                print(f"[Worker {self.worker_id}] ❌ Error writing file: {file_error}")
                if os.path.exists(file_path):
                    os.remove(file_path)
                raise

            if os.path.getsize(file_path) == 0:
                os.remove(file_path)
                raise Exception("File was created but is empty")

            print(f"[Worker {self.worker_id}] ✅ Created file: {filename}")
            return {
                'status': 201,
                'content': b'File created successfully'
            }
        except Exception as e:
            print(f"[Worker {self.worker_id}] ❌ Error in POST request: {e}")
            return {
                'status': 500,
                'content': f'Error processing request: {str(e)}'.encode()
            }

    def log_request(self, method, path, status_code):
        with self.log_lock:
            with open('server.log', 'a') as f:
                with FileLocker(f):
                    timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
                    log_entry = f"[{timestamp}] Worker {self.worker_id} - {method} {path} - Status: {status_code}\n"
                    f.write(log_entry)

    def run(self):
        print(f"[Worker {self.worker_id}] 🚀 Started")
        while True:
            try:
                if not self.pipe.poll(1):
                    continue

                request = self.pipe.recv()
                if request == "shutdown":
                    break

                print(f"[Worker {self.worker_id}] 📝 Processing {request['method']} request for {request['path']}")

                if request['method'] == "GET":
                    response = self.handle_get_request(request)
                    self.log_request("GET", request['path'], response['status'])
                elif request['method'] == "POST":
                    response = self.handle_post_request(request)
                    self.log_request("POST", request['path'], response['status'])
                else:
                    response = {
                        'status': 405,
                        'content': b'Method not allowed'
                    }
                    self.log_request(request['method'], request['path'], 405)

                self.pipe.send(response)
                print(f"[Worker {self.worker_id}] ✅ Request completed")

            except EOFError:
                break
            except Exception as e:
                print(f"[Worker {self.worker_id}] ❌ Error: {e}")
                try:
                    self.pipe.send({
                        'status': 500,
                        'content': b'Internal server error'
                    })
                except:
                    pass

        print(f"[Worker {self.worker_id}] 🔒 Shutting down")


class HTTPServer:
    def __init__(self, host='localhost', port=8080, num_workers=5):
        self.host = host
        self.port = port
        self.num_workers = num_workers
        self.thread_pool = ThreadPoolExecutor(max_workers=20)

        self.log_lock = Lock()
        self.active_posts = Value('i', 0)
        self.posts_lock = Lock()

        self.workers = []
        self.pipes = []
        self.current_worker = 0

        print("\n=== HTTP Server Starting ===")
        print(f"📡 Server listening on {host}:{port}")
        print(f"👥 Number of worker processes: {num_workers}")
        print(f"📊 Maximum concurrent POST requests: 5")
        print("===========================\n")

        # Initialize workers
        for i in range(self.num_workers):
            parent_conn, child_conn = Pipe()
            worker = Worker(i, child_conn, self.log_lock)
            worker.start()
            self.workers.append(worker)
            self.pipes.append(parent_conn)

    def get_next_worker(self):
        with threading.Lock():
            worker_index = self.current_worker
            self.current_worker = (self.current_worker + 1) % self.num_workers
            return worker_index

    def handle_request(self, client_socket, addr):
        self.thread_pool.submit(self._process_request_wrapper, client_socket, addr)

    def _process_request_wrapper(self, client_socket, addr):
        try:
            request_data = b''
            while True:
                chunk = client_socket.recv(4096)
                if not chunk:
                    break
                request_data += chunk
                if b'\r\n\r\n' in request_data:
                    headers, body = request_data.split(b'\r\n\r\n', 1)
                    content_length = None
                    for line in headers.split(b'\r\n'):
                        if line.lower().startswith(b'content-length:'):
                            content_length = int(line.split(b':', 1)[1].strip())
                            break
                    if content_length is None or len(body) >= content_length:
                        break

            if not request_data:
                return

            try:
                headers = request_data.split(b'\r\n\r\n', 1)[0].decode()
                first_line = headers.split('\n')[0].strip()
                method, path, _ = first_line.split()
            except Exception:
                response = b"HTTP/1.0 400 Bad Request\r\n\r\nInvalid request format"
                client_socket.send(response)
                return

            body = ""
            if method == "POST":
                try:
                    body = request_data.split(b'\r\n\r\n', 1)[1].decode()
                except Exception:
                    response = b"HTTP/1.0 400 Bad Request\r\n\r\nMissing or invalid request body"
                    client_socket.send(response)
                    return

                if not body.strip():
                    response = b"HTTP/1.0 400 Bad Request\r\n\r\nEmpty request body"
                    client_socket.send(response)
                    return

            post_request = False
            if method == "POST":
                with self.posts_lock:
                    if self.active_posts.value >= 5:
                        print(
                            f"[Server] ⛔ Rejecting POST request - Maximum concurrent POSTs reached ({self.active_posts.value}/5)")
                        response = (b"HTTP/1.0 503 Service Unavailable\r\nContent-Type: text/plain\r\n\r\nServer is "
                                    b"handling maximum number of concurrent POST requests")
                        client_socket.send(response)
                        return

                    self.active_posts.value += 1
                    post_request = True
                    print(f"[Server] ✅ Accepted POST request ({self.active_posts.value}/5)")

            try:
                self._process_request(method, path, body, addr, client_socket, post_request)
            finally:
                if post_request:
                    with self.posts_lock:
                        self.active_posts.value -= 1
                        print(f"[Server] 📊 Active POST requests: {self.active_posts.value}/5")

        except Exception as e:
            print(f"[Server] ❌ Error handling request: {e}")
            try:
                client_socket.send(b"HTTP/1.0 500 Internal Server Error\r\n\r\n")
            except:
                pass
        finally:
            client_socket.close()

    def _process_request(self, method, path, body, addr, client_socket, post_request):
        try:
            worker_index = self.get_next_worker()
            print(f"[Server] ➡️ Routing request to Worker {worker_index}")

            request = {
                'method': method,
                'path': path,
                'content': body,
                'addr': addr
            }
            self.pipes[worker_index].send(request)

            response = self.pipes[worker_index].recv()

            status_messages = {
                200: 'OK',
                201: 'Created',
                400: 'Bad Request',
                403: 'Forbidden',
                404: 'Not Found',
                405: 'Method Not Allowed',
                500: 'Internal Server Error',
                503: 'Service Unavailable'
            }
            status_text = status_messages.get(response['status'], 'Unknown')
            http_response = f"HTTP/1.0 {response['status']} {status_text}\r\n"

            if 'headers' in response:
                for key, value in response['headers'].items():
                    http_response += f"{key}: {value}\r\n"
            http_response += "\r\n"
            http_response = http_response.encode()
            http_response += response['content']

            client_socket.send(http_response)

        except Exception as e:
            print(f"[Server] ❌ Error processing request: {e}")
            try:
                client_socket.send(b"HTTP/1.0 500 Internal Server Error\r\n\r\n")
            except:
                pass

    def start(self):
        server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        server_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        server_socket.bind((self.host, self.port))
        server_socket.listen(5)

        try:
            while True:
                try:
                    client_socket, addr = server_socket.accept()
                    print(f"\n[Server] 🔔 New connection from {addr}")
                    self.handle_request(client_socket, addr)
                except KeyboardInterrupt:
                    print("\n\n=== Shutting down server... ===")
                    break
                except Exception as e:
                    print(f"[Server] ❌ Error accepting connection: {e}")

        finally:
            self.thread_pool.shutdown(wait=True)

            for pipe in self.pipes:
                pipe.send("shutdown")

            for worker in self.workers:
                worker.join()

            server_socket.close()
            print("=== Server shutdown complete ===\n")

    def log_request(self, method, path, status_code, worker_id="Server"):
        with self.log_lock:
            with open('server.log', 'a') as f:
                with FileLocker(f):
                    timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
                    log_entry = f"[{timestamp}] {worker_id} - {method} {path} - Status: {status_code}\n"
                    f.write(log_entry)


if __name__ == "__main__":
    server = HTTPServer(num_workers=5)
    server.start()
