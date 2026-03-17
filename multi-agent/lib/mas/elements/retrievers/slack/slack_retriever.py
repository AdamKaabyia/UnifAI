import requests
from typing import Any
from mas.elements.retrievers.common.base_retriever import BaseRetriever
from pydantic import HttpUrl
from mas.core.context import get_current_context


class SlackRetriever(BaseRetriever):
    """
    Calls an external Slack‐query API to fetch matching messages.
    """

    def __init__(self, api_url: HttpUrl,
                 top_k_results: int,
                 threshold: float):
        self.api_url = str(api_url)
        self.top_k = top_k_results
        self.threshold = threshold

    def retrieve(self, query: str) -> Any:
        params = {
            "query": query,
            "top_k_results": self.top_k,
            "scope": get_current_context().scope,
            "loggedInUser": get_current_context().logged_in_user
        }

        resp = requests.get(self.api_url, params=params)
        resp.raise_for_status()
        data = resp.json()
        if "search_results" in data:
            data = data["search_results"]
        if isinstance(data, list):
            return [item for item in data if item.get("score", 0.0) >= self.threshold]
        return data
