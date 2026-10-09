"""Recommendation, impression and independently sampled click workload."""

from adflow_workloads import AdFlowHttpUser
from locust import task


class LifecycleUser(AdFlowHttpUser):
    workload_name = "lifecycle"

    @task
    def lifecycle_opportunity(self) -> None:
        self.run_opportunity(lifecycle=True)
