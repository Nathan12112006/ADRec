"""Recommendation-only workload; selections and request outcomes remain durable."""

from adflow_workloads import AdFlowHttpUser
from locust import task


class RecommendationOnlyUser(AdFlowHttpUser):
    workload_name = "recommendation_only"

    @task
    def recommendation_only_opportunity(self) -> None:
        self.run_opportunity(lifecycle=False)
