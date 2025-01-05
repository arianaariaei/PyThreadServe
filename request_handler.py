import threading
import urllib.parse
from pathlib import Path
import time


class RequestHandler:
    def __init__(self, worker_id, active_posts):
        self.worker_id = worker_id
        self.static_dir = Path("static")
        self.log_lock = threading.Lock()
        self.active_posts = active_posts
        self.posts_lock = threading.Lock()

    def handle_post_request(self, request_info):
        """Handle POST request with true concurrency"""
        # Check if we're at limit BEFORE adding a new request
        with self.posts_lock:
            with self.active_posts.get_lock():
                if self.active_posts.value >= 5:
                    print(f"Worker {self.worker_id}: Rejecting POST - over limit")
                    return "HTTP/1.0 429 Too Many Requests\r\n\r\nToo many concurrent requests", 429
                self.active_posts.value += 1
                print(f"Worker {self.worker_id}: Accepted POST ({self.active_posts.value}/5)")

        try:
            print(f"Worker {self.worker_id}: Processing POST request")
            path = request_info['path'].lstrip('/')
            if not path:
                path = f"uploaded_file_{int(time.time())}"

            file_path = self.static_dir / path

            # Security check
            if not str(file_path.resolve()).startswith(str(self.static_dir.resolve())):
                return "HTTP/1.0 403 Forbidden\r\n\r\nAccess Denied", 403

            # Save file
            with open(file_path, 'wb') as f:
                f.write(request_info['body'].encode())

            time.sleep(2)  # Simulate work

            print(f"Worker {self.worker_id}: Successfully saved {path}")
            return f"HTTP/1.0 200 OK\r\n\r\nFile saved successfully: {path}", 200

        except Exception as e:
            print(f"Worker {self.worker_id}: Error in POST request: {e}")
            return "HTTP/1.0 500 Internal Server Error\r\n\r\nServer Error", 500
        finally:
            with self.active_posts.get_lock():
                self.active_posts.value -= 1
                print(f"Worker {self.worker_id}: Released POST ({self.active_posts.value}/5)")

    def handle_get_request(self, path):
        """Handle GET request"""
        try:
            decoded_path = urllib.parse.unquote(path.lstrip('/'))
            file_path = self.static_dir / decoded_path

            if not str(file_path.resolve()).startswith(str(self.static_dir.resolve())):
                return "HTTP/1.0 403 Forbidden\r\n\r\nAccess Denied", 403

            if not file_path.exists():
                return "HTTP/1.0 404 Not Found\r\n\r\nFile not found", 404

            with open(file_path, 'rb') as f:
                content = f.read()

            content_type = 'text/plain'
            if file_path.suffix == '.html':
                content_type = 'text/html'
            elif file_path.suffix in ['.jpg', '.jpeg']:
                content_type = 'image/jpeg'
            elif file_path.suffix == '.png':
                content_type = 'image/png'

            response = f"HTTP/1.0 200 OK\r\nContent-Type: {content_type}\r\nContent-Length: {len(content)}\r\n\r\n".encode()
            response += content
            return response, 200

        except Exception as e:
            print(f"Worker {self.worker_id}: Error in GET request: {e}")
            return "HTTP/1.0 500 Internal Server Error\r\n\r\nServer Error", 500

    def handle_request(self, client_socket):
        """Main request handling method"""
        try:
            print(f"Worker {self.worker_id}: Starting to handle request")
            request_data = client_socket.recv(1024)
            if not request_data:
                print(f"Worker {self.worker_id}: Empty request received")
                return

            request = self.parse_http_request(request_data)
            if not request:
                print(f"Worker {self.worker_id}: Failed to parse request")
                return

            print(f"Worker {self.worker_id}: Handling {request['method']} request to {request['path']}")

            if request['method'] == 'GET':
                response, status = self.handle_get_request(request['path'])
            elif request['method'] == 'POST':
                response, status = self.handle_post_request(request)
            else:
                response = "HTTP/1.0 405 Method Not Allowed\r\n\r\nMethod not allowed"
                status = 405

            if isinstance(response, str):
                response = response.encode()

            print(f"Worker {self.worker_id}: Sending response, status {status}")
            client_socket.send(response)

        except Exception as e:
            print(f"Worker {self.worker_id}: Error handling request: {e}")
        finally:
            try:
                client_socket.close()
                print(f"Worker {self.worker_id}: Closed client socket")
            except:
                pass

    def parse_http_request(self, request_data):
        """Parse HTTP request"""
        try:
            request_text = request_data.decode('utf-8')
            headers_raw, body = request_text.split('\r\n\r\n', 1) if '\r\n\r\n' in request_text else (request_text, '')

            headers_lines = headers_raw.split('\r\n')
            method, path, _ = headers_lines[0].split(' ')

            headers = {}
            for line in headers_lines[1:]:
                if ': ' in line:
                    key, value = line.split(': ', 1)
                    headers[key.lower()] = value

            return {
                'method': method,
                'path': path,
                'headers': headers,
                'body': body
            }
        except Exception as e:
            print(f"Error parsing request: {e}")
            return None
