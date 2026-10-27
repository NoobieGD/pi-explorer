import unittest,sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'research'))
import compact_engine as compact
import engine

class CompactResearchTests(unittest.TestCase):
    def test_cross_cancellation_preserves_both_rational_values(self):
        for begin,end in ((0,1),(0,64),(1,123),(75,400),(0,1000)):
            p,q,t=compact.split(begin,end,cancel=False)
            cp,cq,ct=compact.split(begin,end,cutoff=4)
            self.assertEqual(p*cq,cp*q);self.assertEqual(t*cq,ct*q)
            unused,nq,nt=compact.split(begin,end,cutoff=4,need_product=False)
            self.assertIsNone(unused);self.assertEqual(nt*q,t*nq)
    def test_digits_match_independent_mpfr(self):
        for count in (1,50,1000,10000,100000):
            digits,stats=compact.compute(count,cutoff=16)
            self.assertEqual(digits,engine.compute_pi(count,'mpfr'))
            if count>=1000:self.assertGreater(stats['cancelledBits'],0)
    def test_200b_plan_is_explicitly_unvalidated_and_not_launchable(self):
        plan=compact.plan(200_000_000_000)
        self.assertEqual(plan['budgetBytes'],210*1024**3)
        self.assertLess(plan['twoFullPrecisionValuesBytes'],plan['budgetBytes'])
        self.assertGreater(plan['threeFullPrecisionValuesBytes'],plan['budgetBytes'])
        self.assertFalse(plan['launchableAtRequestedScale'])

if __name__=='__main__':unittest.main()
