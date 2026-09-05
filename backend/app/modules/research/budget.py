from dataclasses import dataclass


class ResearchBudgetExceeded(RuntimeError):
    pass


@dataclass(slots=True, frozen=True)
class ResearchBudget:
    max_provider_calls: int = 8
    max_selected_urls: int = 3
    max_pages_read: int = 3
    max_second_hop_candidates: int = 8
    max_raw_excerpt_chars: int = 8000


@dataclass(slots=True)
class BudgetLedger:
    budget: ResearchBudget
    provider_calls_used: int = 0
    pages_read: int = 0

    def consume_provider_calls(self, count: int, provider: str) -> None:
        if count < 0:
            raise ValueError("count_must_be_non_negative")
        if self.provider_calls_used + count > self.budget.max_provider_calls:
            raise ResearchBudgetExceeded(f"provider_budget_exhausted:{provider}")
        self.provider_calls_used += count

    def consume_page_read(self) -> None:
        if self.pages_read + 1 > self.budget.max_pages_read:
            raise ResearchBudgetExceeded("page_read_budget_exhausted")
        self.pages_read += 1
