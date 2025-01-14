# PyThreadServe

A lightweight, multi-process HTTP/1.0 server implementation with worker processes and thread pooling. This server handles GET and POST requests with built-in concurrency management and file locking mechanisms.

## Features

- **HTTP/1.0 Implementation**: Supports basic GET and POST methods
- **Multi-Process Architecture**: 
  - Main process for request acceptance
  - Worker processes for request handling
  - Round-Robin load balancing between workers
- **Concurrency Management**:
  - Thread pooling for connection handling
  - Maximum 5 concurrent POST requests
  - File locking mechanism for thread-safe operations
- **Request Handling**:
  - GET: Serves files from static directory
  - POST: Creates new files with unique timestamps
  - Protection against directory traversal attacks
- **Logging**: Thread-safe logging of all requests with timestamps and status codes

## Requirements

- Python 3.x
- Windows OS (due to msvcrt file locking)
- Required Python packages:
  ```
  requests (for testing only)
  ```

## Project Structure

```
PyThreadServe/
├── server.py       # Main server implementation
├── test.py        # Test suite
├── static/        # Directory for serving static files
└── server.log     # Request log file
```

## Installation

1. Clone the repository
2. Install required packages:
   ```bash
   pip install requests
   ```

## Usage

### Starting the Server

```python
from server import HTTPServer

server = HTTPServer(host='localhost', port=8080, num_workers=5)
server.start()
```

### Making Requests

#### GET Request
```bash
curl http://localhost:8080/filename.txt
```

#### POST Request
```bash
curl -X POST -d "Your content here" http://localhost:8080/upload
```

## Testing

The project includes a comprehensive test suite that covers:
- Basic GET and POST functionality
- Error handling
- Concurrent request handling
- Security features
- Logging functionality

To run tests:
```bash
python test.py
```

## Technical Details

### Worker Process Management
- Main process distributes requests using Round-Robin scheduling
- Inter-Process Communication (IPC) via pipes
- Worker processes handle file operations and request processing

### Concurrency Controls
- Thread pool for handling multiple connections
- Semaphore-like control for POST requests (max 5)
- File locking for thread-safe file operations

### Security Features
- Directory traversal protection
- Request validation
- Error handling for malformed requests

### Logging System
- Thread-safe logging mechanism
- Detailed request information including:
  - Timestamp
  - Worker ID
  - Request method
  - Path
  - Status code

## Limitations

1. HTTP/1.0 only (no persistent connections)
2. Windows-specific file locking
3. Maximum 5 concurrent POST requests
4. No support for:
   - HTTP/1.1 features
   - HTTPS
   - Custom headers
   - Content-type handling

## Performance Considerations

- Thread pool size: 20 threads
- Worker processes: 5 by default
- POST request limit: 5 concurrent requests
- File operations are synchronized using locks

## Error Handling

The server handles various error cases:
- 400 Bad Request
- 404 Not Found
- 405 Method Not Allowed
- 503 Service Unavailable (POST limit reached)
- 500 Internal Server Error

## License

This project is open source and available under the MIT License.