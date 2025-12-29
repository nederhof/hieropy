import unittest

from hieropy.unistructure import *
from hieropy.spatialparsing import *

class TestAux(unittest.TestCase):
	def test_split(self):
		t1 = GroupAndToken("A", 2, 6, 4, 2)
		t2 = GroupAndToken("B", 7, -5, 2, 11)
		t3 = GroupAndToken("C", 12, 9, 20, 5)
		tokens = [t1, t2, t3]
		top, bottom = split_from_top(tokens, ParseParams(slack=0, exhaustive=False))[0]
		self.assertEqual(len(top), 2)
		top, bottom = split_from_top(tokens, ParseParams(exhaustive=True))[0]
		self.assertEqual(len(top), 1)
		left, right = split_from_left(tokens, ParseParams(exhaustive=True))[0]
		self.assertEqual(len(left), 1)

	@unittest.skip("Temporarily skipping this test class")
	def test_cartouche(self):
		empty_cartouche = Enclosure('plain', [], None, 0, None, 0)
		a1 = Literal(chr(0x13000), 0, False, 0)
		a2 = Literal(chr(0x13001), 0, False, 0)
		cartouche = GroupAndToken(empty_cartouche, 2, 6, 5, 3)
		filled1 = GroupAndToken(a1, 3, 7, 0.9, 1)
		filled2 = GroupAndToken(a2, 4, 7, 0.9, 1)
		tokens = [cartouche, filled1, filled2]
		parse = best_top_group(tokens)
		self.assertEqual(str(parse), '𓐼𓀀𓐱𓀁𓐽')
	
