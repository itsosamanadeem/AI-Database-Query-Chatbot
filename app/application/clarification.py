from __future__ import annotations

from dataclasses import dataclass
import re


@dataclass(frozen=True)
class ClarificationRequest:
    question: str


class ClarificationGuard:
    _RANKING_WORDS = {
        "top",
        "best",
        "highest",
        "largest",
        "lowest",
        "worst",
        "least",
        "bottom",
    }
    _BUSINESS_ENTITIES = {
        "customer",
        "customers",
        "client",
        "clients",
        "product",
        "products",
        "item",
        "items",
        "vendor",
        "vendors",
        "supplier",
        "suppliers",
        "account",
        "accounts",
        "gl",
        "ledger",
    }
    _RANKING_METRICS = {
        "sales",
        "sale",
        "amount",
        "revenue",
        "profit",
        "margin",
        "quantity",
        "qty",
        "balance",
        "outstanding",
        "receivable",
        "payable",
        "invoice",
        "invoices",
        "orders",
        "transactions",
    }
    _BREAKDOWN_WORDS = {
        "wise",
        "by",
        "against",
        "month",
        "monthly",
        "year",
        "yearly",
        "category",
        "region",
        "branch",
    }

    def check(self, question: str) -> ClarificationRequest | None:
        tokens = self._tokens(question)
        if self._is_ambiguous_ranking_request(tokens):
            return ClarificationRequest(
                question=(
                    "How should I calculate the top results? Please choose the basis "
                    "or breakdown, for example: sales amount, quantity, profit, "
                    "outstanding balance, GL-wise, product-wise, year-wise, or month-wise."
                )
            )

        if self._is_ambiguous_report_request(tokens):
            return ClarificationRequest(
                question=(
                    "What context should I use for this report? Please specify the "
                    "date range and whether you want it customer-wise, product-wise, "
                    "GL-wise, year-wise, or month-wise."
                )
            )

        return None

    def build_followup_prompt(
        self,
        original_question: str,
        clarification_question: str,
        clarification_answer: str,
    ) -> str:
        return f"""
The user previously asked:
{original_question}

The assistant asked this clarification:
{clarification_question}

The user clarified:
{clarification_answer}

Use the original question and the clarification together. Generate and run the
correct database query, then answer the user. Do not ask another clarification
unless an essential database detail is still missing.
""".strip()

    def _is_ambiguous_ranking_request(self, tokens: set[str]) -> bool:
        has_ranking = bool(tokens & self._RANKING_WORDS) or self._has_top_number(tokens)
        has_entity = bool(tokens & self._BUSINESS_ENTITIES)
        has_metric = bool(tokens & self._RANKING_METRICS)
        has_breakdown = bool(tokens & self._BREAKDOWN_WORDS)
        return has_ranking and has_entity and not (has_metric or has_breakdown)

    def _is_ambiguous_report_request(self, tokens: set[str]) -> bool:
        asks_report = bool(tokens & {"report", "summary", "analysis", "performance"})
        has_subject = bool(tokens & (self._BUSINESS_ENTITIES | self._RANKING_METRICS))
        has_context = bool(tokens & self._BREAKDOWN_WORDS)
        has_date_context = bool(tokens & {"today", "yesterday", "week", "month", "year"})
        return asks_report and has_subject and not (has_context or has_date_context)

    @staticmethod
    def _tokens(question: str) -> set[str]:
        return set(re.findall(r"[a-z0-9]+", question.lower()))

    @staticmethod
    def _has_top_number(tokens: set[str]) -> bool:
        return bool(tokens & {"10", "20", "50", "100"})
