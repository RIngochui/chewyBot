from __future__ import annotations

import pytest

from utils.odds_math import (
    american_to_decimal,
    decimal_to_american,
    implied_probability,
    no_vig_probability,
)


class TestAmericanToDecimal:
    def test_positive_150(self):
        assert american_to_decimal(150) == 2.5

    def test_negative_110(self):
        assert american_to_decimal(-110) == pytest.approx(100 / 110 + 1, rel=1e-3)

    def test_positive_100(self):
        assert american_to_decimal(100) == 2.0

    def test_positive_200(self):
        assert american_to_decimal(200) == pytest.approx(3.0)

    def test_negative_200(self):
        assert american_to_decimal(-200) == pytest.approx(1.5)


class TestDecimalToAmerican:
    def test_2_5_returns_150(self):
        assert decimal_to_american(2.5) == 150

    def test_1_909_returns_minus_110(self):
        assert decimal_to_american(1.909) == -110

    def test_2_0_returns_100(self):
        assert decimal_to_american(2.0) == 100

    def test_3_0_returns_200(self):
        assert decimal_to_american(3.0) == 200

    def test_1_5_returns_minus_200(self):
        assert decimal_to_american(1.5) == -200


class TestImpliedProbability:
    def test_2_5_returns_0_4(self):
        assert implied_probability(2.5) == pytest.approx(0.4)

    def test_1_0_returns_1_0(self):
        # Edge case: evens in decimal is 1.0 (can't bet at these odds, but math works)
        assert implied_probability(1.0) == 1.0

    def test_2_0_returns_0_5(self):
        assert implied_probability(2.0) == pytest.approx(0.5)

    def test_1_5_returns_approx_0_667(self):
        assert implied_probability(1.5) == pytest.approx(1 / 1.5)


class TestNoVigProbability:
    def test_two_outcomes_sum_to_1(self):
        result = no_vig_probability([2.5, 1.75])
        assert len(result) == 2
        assert sum(result) == pytest.approx(1.0)

    def test_two_outcomes_different_odds_sum_to_1(self):
        result = no_vig_probability([2.2, 1.65])
        assert len(result) == 2
        assert sum(result) == pytest.approx(1.0)

    def test_three_equal_outcomes(self):
        result = no_vig_probability([3.0, 3.0, 3.0])
        assert len(result) == 3
        assert result[0] == pytest.approx(1 / 3)
        assert result[1] == pytest.approx(1 / 3)
        assert result[2] == pytest.approx(1 / 3)

    def test_values_are_probabilities(self):
        result = no_vig_probability([2.5, 1.75])
        for p in result:
            assert 0 < p < 1

    def test_output_length_matches_input(self):
        result = no_vig_probability([2.0, 2.0, 3.0, 4.0])
        assert len(result) == 4
        assert sum(result) == pytest.approx(1.0)
