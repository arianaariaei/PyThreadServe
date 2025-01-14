import unittest
import requests
import threading
import time
import os
import shutil
from concurrent.futures import ThreadPoolExecutor, as_completed
from server import HTTPServer


class TestHTTPServer(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.server = HTTPServer(host='localhost', port=8080, num_workers=5)
        cls.server_thread = threading.Thread(target=cls.server.start)
        cls.server_thread.daemon = True
        cls.server_thread.start()
        time.sleep(2)

        if not os.path.exists('static'):
            os.makedirs('static')
        with open('static/test.txt', 'w') as f:
            f.write('Test content')

    @classmethod
    def tearDownClass(cls):
        """Clean up after all tests"""
        if os.path.exists('static'):
            shutil.rmtree('static')
        os.makedirs('static')

    def setUp(self):
        """Set up before each test"""
        self.base_url = 'http://localhost:8080'
        open('server.log', 'w').close()

    def test_01_basic_get_request(self):
        """Test basic GET request for existing file"""
        print("\n=== Testing Basic GET Request ===")
        response = requests.get(f"{self.base_url}/test.txt")
        print(f"Status Code: {response.status_code}")
        print(f"Response Content: {response.text}")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.text, 'Test content')

    def test_02_get_nonexistent_file(self):
        """Test GET request for non-existent file"""
        print("\n=== Testing GET Request for Non-existent File ===")
        response = requests.get(f"{self.base_url}/nonexistent.txt")
        print(f"Status Code: {response.status_code}")
        self.assertEqual(response.status_code, 404)

    def test_03_basic_post_request(self):
        """Test basic POST request"""
        print("\n=== Testing Basic POST Request ===")
        content = "Test POST content"
        response = requests.post(f"{self.base_url}/upload", data=content)
        print(f"Status Code: {response.status_code}")
        print(f"Response Content: {response.text}")
        self.assertEqual(response.status_code, 201)

    def test_04_empty_post_request(self):
        """Test POST request with empty content"""
        print("\n=== Testing Empty POST Request ===")
        response = requests.post(f"{self.base_url}/upload", data="")
        print(f"Status Code: {response.status_code}")
        self.assertEqual(response.status_code, 400)

    def test_05_concurrent_post_requests(self):
        """Test concurrent POST requests (should handle max 5)"""
        print("\n=== Testing Concurrent POST Requests ===")

        def make_post_request(i):
            response = requests.post(f"{self.base_url}/upload", data=f"Content {i}")
            return response.status_code

        with ThreadPoolExecutor(max_workers=8) as executor:
            futures = [executor.submit(make_post_request, i) for i in range(8)]
            results = [future.result() for future in as_completed(futures)]

        print(f"Response Status Codes: {results}")
        self.assertEqual(results.count(201), 5)
        self.assertEqual(results.count(503), 3)

    def test_06_directory_traversal(self):
        """Test protection against directory traversal"""
        print("\n=== Testing Directory Traversal Protection ===")
        response = requests.get(f"{self.base_url}/../server.log")
        print(f"Status Code: {response.status_code}")
        self.assertEqual(response.status_code, 404)

    def test_07_invalid_method(self):
        """Test invalid HTTP method"""
        print("\n=== Testing Invalid HTTP Method ===")
        response = requests.put(f"{self.base_url}/test.txt")
        print(f"Status Code: {response.status_code}")
        self.assertEqual(response.status_code, 405)

    def test_08_large_post_request(self):
        """Test large POST request"""
        print("\n=== Testing Large POST Request ===")
        large_content = "A" * 1024 * 1024  # 1MB of data
        response = requests.post(f"{self.base_url}/upload", data=large_content)
        print(f"Status Code: {response.status_code}")
        self.assertEqual(response.status_code, 201)

    def test_09_rapid_requests(self):
        """Test rapid sequence of requests"""
        print("\n=== Testing Rapid Requests ===")
        results = []
        for _ in range(20):
            response = requests.get(f"{self.base_url}/test.txt")
            results.append(response.status_code)
        print(f"Response Status Codes: {results}")
        self.assertTrue(all(status == 200 for status in results))

    def test_10_check_logging(self):
        """Test if requests are properly logged"""
        print("\n=== Testing Server Logging ===")
        requests.get(f"{self.base_url}/test.txt")
        requests.post(f"{self.base_url}/upload", data="Test content")

        time.sleep(1)

        with open('server.log', 'r') as f:
            log_content = f.read()
            print("Log file content:")
            print(log_content)
            self.assertTrue('GET /test.txt' in log_content)
            self.assertTrue('POST /upload' in log_content)


def run_tests():
    loader = unittest.TestLoader()
    loader.sortTestMethodsUsing = None
    suite = loader.loadTestsFromTestCase(TestHTTPServer)

    runner = unittest.TextTestRunner(verbosity=2)
    runner.run(suite)


if __name__ == '__main__':
    run_tests()
