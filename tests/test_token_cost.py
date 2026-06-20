from __future__ import annotations

import unittest

from app.services.token_cost import calculate_token_cost


class TokenCostTests(unittest.TestCase):
    def test_calculate_token_cost(self) -> None:
        self.assertEqual(
            calculate_token_cost(
                {"input_tokens": 1000, "output_tokens": 500},
                input_cost_per_1k=0.01,
                output_cost_per_1k=0.03,
            ),
            {
                "currency": "USD",
                "input_cost": 0.01,
                "output_cost": 0.015,
                "total_cost": 0.025,
                "input_cost_per_1k": 0.01,
                "output_cost_per_1k": 0.03,
            },
        )

    def test_calculate_token_cost_handles_missing_usage(self) -> None:
        self.assertEqual(calculate_token_cost(None)["total_cost"], 0.0)


if __name__ == "__main__":
    unittest.main()
