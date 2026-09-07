import unittest
from recognizer import build_averages, side_slots

class BuildTests(unittest.TestCase):
    def test_unknowns_excluded_and_manual_correction_recomputes(self):
        rows=[dict(player=0,accepted=True,winrate=.50),
              dict(player=0,accepted=False,winrate=.99),
              dict(player=0,accepted=True,winrate=.54),
              dict(player=1,accepted=False,winrate=.90),
              dict(accepted=True,winrate=1)]
        self.assertEqual(build_averages(rows),{0:(.52,2),1:(None,0)})
        rows[1].update(accepted=True,winrate=.46)
        self.assertAlmostEqual(build_averages(rows)[0][0],.5)
        self.assertEqual(build_averages(rows)[0][1],3)
    def test_ten_players_four_positions(self):
        rows=side_slots(2048,1018)
        self.assertEqual(len(rows),40)
        self.assertEqual([sum(r[3]==p for r in rows) for p in range(10)],[4]*10)
