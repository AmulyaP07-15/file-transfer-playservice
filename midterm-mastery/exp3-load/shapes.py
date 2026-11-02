from locust import LoadTestShape

# reuse the same user from locustfile.py
from locustfile import FileUser  # noqa: F401

# Experiment 3 load shape, staged load that ramps the number of users up and
# then back down, all hands off so I am not clicking anything during the test.
# I run this file directly with Locust (shapes.py imports the user it needs).
#   locust -f shapes.py --host http://<ALB_DNS> --headless --csv locust_results --csv-full-history --html locust_report.html


class StagedLoad(LoadTestShape):
    # each row is (stage ends at this many seconds, target users, spawn rate)
    # 10 users, then 50, then 200, then back to 0, five minutes per stage
    stages = [
        (300, 10, 5),
        (600, 50, 10),
        (900, 200, 20),
        (1200, 0, 20),
    ]

    def tick(self):
        t = self.get_run_time()
        for ends_at, users, spawn_rate in self.stages:
            if t < ends_at:
                return (users, spawn_rate)
        # past the last stage, returning None tells Locust to stop the test
        return None
