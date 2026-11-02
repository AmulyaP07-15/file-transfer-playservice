from locust import task, between
from locust.contrib.fasthttp import FastHttpUser

# Experiment 3, staged load against the AWS gateway.
# Every user just downloads the same small 10kb file over and over, so the only
# thing changing during the test is the load, not the file size or the loss.
# I use the 10kb file because on AWS it is reliable at a single request, while
# bigger files fail even at 0 loss, so load stays the real variable.
# The staged load shape lives in shapes.py and is what I actually run.

FILE_NAME = "10kb.bin"


class FileUser(FastHttpUser):
    # tiny wait so each user keeps downloading almost back to back
    wait_time = between(0.01, 0.05)

    @task
    def download(self):
        # name groups every download into one row in the Locust stats
        with self.client.get(f"/files?name={FILE_NAME}", name="/files",
                             catch_response=True) as resp:
            if resp.status_code == 200:
                resp.success()
            else:
                # 503 is the service shedding load, 504 is the backend not
                # answering, I count both as failures so they show on the chart
                resp.failure(f"status {resp.status_code}")
