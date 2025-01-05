import requests
import threading
import time
from datetime import datetime


def send_post(file_num):
    """Send a POST request"""
    url = f'http://localhost:8383/file{file_num}.txt'
    data = f'This is test file {file_num}'

    try:
        start_time = datetime.now()
        response = requests.post(url, data=data)
        end_time = datetime.now()

        duration = (end_time - start_time).total_seconds()
        print(f'File {file_num}: Status {response.status_code} - Duration: {duration:.2f}s - {response.text}')
    except Exception as e:
        print(f'File {file_num}: Error - {str(e)}')


# Create threads for concurrent requests
threads = []
for i in range(8):  # Try 8 requests to clearly see the limit
    thread = threading.Thread(target=send_post, args=(i + 1,))
    threads.append(thread)

print("Starting concurrent POST requests...")
# Start all threads at nearly the same time
for thread in threads:
    thread.start()
    time.sleep(0.1)  # Small delay to make output more readable

# Wait for all threads to complete
for thread in threads:
    thread.join()

print("All requests completed!")