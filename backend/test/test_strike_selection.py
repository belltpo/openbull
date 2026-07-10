import unittest

from backend.futures_risk.strike_selection import (
    MoneynessSelection,
    StrikeSelectionMethod,
    normalize_method,
    resolve_strike,
)


STRIKES = [100.0, 110.0, 120.0, 130.0, 140.0, 150.0, 160.0, 170.0, 180.0, 190.0, 200.0]


class StrikeSelectionTests(unittest.TestCase):
    def test_itm_otm_mapping_is_directional_for_ce_and_pe(self):
        self.assertEqual(resolve_strike(
        method=StrikeSelectionMethod.ITM_OTM,
        option_type="CE",
        strikes=STRIKES,
        atm=150,
        moneyness=MoneynessSelection.ITM2,
        ), 130)
        self.assertEqual(resolve_strike(
        method=StrikeSelectionMethod.ITM_OTM,
        option_type="PE",
        strikes=STRIKES,
        atm=150,
        moneyness=MoneynessSelection.ITM2,
        ), 170)

    def test_atm_and_offset_resolve_without_changing_existing_offset_value(self):
        self.assertEqual(resolve_strike(
        method=StrikeSelectionMethod.ATM,
        option_type="CE",
        strikes=STRIKES,
        atm=150,
        ), 150)
        self.assertEqual(resolve_strike(
        method=StrikeSelectionMethod.OFFSET,
        option_type="PE",
        strikes=STRIKES,
        atm=150,
        offset_strike=170,
        ), 170)

    def test_manual_strike_requires_positive_value_and_available_strike(self):
        self.assertEqual(resolve_strike(
        method=StrikeSelectionMethod.MANUAL,
        option_type="CE",
        strikes=STRIKES,
        atm=150,
        manual_strike=140,
        ), 140)
        with self.assertRaisesRegex(ValueError, "not available"):
            resolve_strike(
            method=StrikeSelectionMethod.MANUAL,
            option_type="CE",
            strikes=STRIKES,
            atm=150,
            manual_strike=145,
            )

    def test_invalid_selector_falls_back_to_atm_method_and_moneyness(self):
        self.assertIs(normalize_method("unknown"), StrikeSelectionMethod.ATM)
        self.assertIs(normalize_method("ITM / OTM"), StrikeSelectionMethod.ITM_OTM)


if __name__ == "__main__":
    unittest.main()
