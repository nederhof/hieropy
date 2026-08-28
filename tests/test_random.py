import unittest

from hieropy import UniParser
from hieropy.unirandom import UniGenerator

class TestGenerator(unittest.TestCase):

	def test_generation(self):
		generator = UniGenerator(depth_limit=10)
		parser = UniParser()
		for i in range(10000):
			frag = generator.generate_fragment()
			fragment = parser.parse(str(frag))
			if parser.last_error:
				print(str(frag))
				print(parser.last_error)
			
