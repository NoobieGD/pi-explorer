import sys, unittest, random
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import engine

PI100='1415926535897932384626433832795028841971693993751058209749445923078164062862089986280348253421170679'

class PrecisionTests(unittest.TestCase):
    def test_known_digits_and_exact_length(self):
        for n in (1,9,50,99,100):
            self.assertEqual(engine.compute_pi(n),PI100[:n])
    def test_independent_mpfr_agreement(self):
        self.assertEqual(engine.compute_pi(10000),engine.compute_pi(10000,'mpfr'))
    def test_reject_invalid_precision(self):
        for n in (0,-1,1.5,True,'1e12'):
            with self.assertRaises(ValueError):engine.compute_pi(n)
    def test_video_text_mapping(self):
        self.assertEqual(engine.letters(b'0001252699'),b'ABZA V'.replace(b' ',b''))
        self.assertEqual(engine.letters(b'01022600','a1z26'),b'ABZ.')
        self.assertEqual(engine.letters(b'072101108108111','ascii'),b'Hello')
    def test_video_discoveries(self):
        pi=engine.compute_pi(200000).encode()
        text=engine.letters(pi)
        self.assertEqual(text.find(b'CAT')+1,22731)
        self.assertEqual(text.find(b'DOG')+1,44145)
        self.assertEqual(text.find(b'MATH')+1,91682)
        self.assertEqual(pi.find(b'12345')+1,49702)
        self.assertEqual(pi.find(b'999999')+1,762)
    def test_binary_maps(self):
        self.assertEqual(engine.binary(b'0123456789'),b'0000011111')
        self.assertEqual(engine.binary(b'0123456789','parity'),b'0101010101')
    def test_overlapping_search(self):
        self.assertEqual(engine.find_matches(b'1111',b'11'),([0,1,2],False))
        self.assertEqual(engine.find_matches(b'1111',b'11',2),([0,1],True))

class ShapeTests(unittest.TestCase):
    def test_bitset_matches_bruteforce(self):
        rng=random.Random(14159)
        for _ in range(30):
            bits=bytes(rng.choice(b'01') for i in range(320))
            rows=[''.join(rng.choice('01?') for x in range(3)) for y in range(3)]
            expected=[]
            for stride in (5,8,13):
                for p in range(len(bits)-2*stride-3+1):
                    if p%stride+3>stride:continue
                    if all(ch=='?' or bits[p+y*stride+x]==ord(ch) for y,row in enumerate(rows) for x,ch in enumerate(row)):
                        expected.append((p,stride))
            got,capped=engine.find_shapes(bits,rows,[5,8,13],10000)
            self.assertFalse(capped)
            self.assertEqual(sorted((m['index'],m['width']) for m in got),sorted(expected))
    def test_no_wrap_or_tail(self):
        result,_=engine.find_shapes(b'00011000',['11'],[4])
        self.assertEqual(result,[])
        result,_=engine.find_shapes(b'111111',['11','11'],[4])
        self.assertEqual([r['index'] for r in result],[0])
    def test_cancel(self):
        with self.assertRaises(InterruptedError):engine.find_shapes(b'010101'*100,['01','10'],[10],cancelled=lambda:True)
    def test_stats(self):
        result=engine.statistics(b'0123456789'*10)
        self.assertEqual(result['counts'],[10]*10)
        self.assertAlmostEqual(result['entropy'],3.321928094887)
        self.assertEqual(result['chiSquare'],0)

if __name__=='__main__':unittest.main()
