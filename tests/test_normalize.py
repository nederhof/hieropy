import unittest
import csv

from hieropy import UniParser
from hieropy.uninormalize import UniNormalizer
from hieropy.uniconstants import num_to_rotate
from hieropy.uniprops import allowed_rotations, char_to_places
from hieropy.unistats import transforms_from, char_insertions_from

class TestNorm(unittest.TestCase):

	def setUp(self):
		self.parser = UniParser()

	def compare_pair(self, test_in, types, test_out):
		norm = UniNormalizer(types=types,excepts=['\U00013169'])
		parsed = self.parser.parse(test_in)
		normalized = str(norm.normalize(parsed))
		normalized_str = ' '.join(hex(ord(ch)) for ch in list(normalized))
		test_out_str = ' '.join(hex(ord(ch)) for ch in list(test_out))
		self.assertEqual(normalized_str, test_out_str)
		return norm.errors

	def test_nil(self):
		test_in = '\U00013000\U00013430\U00013001'
		test_out = '\U00013000\U00013430\U00013001'
		self.compare_pair(test_in, [], test_out)

	def test_rotated(self):
		test_in = '\U0001339C\ufe01'
		test_out = '\U0001309D\U00013436\U0001339B'
		errors = self.compare_pair(test_in, ['overlay'], test_out)
		self.assertEqual(len(errors), 1)

	def test_insertion(self):
		test_in = '\U00013172\U00013436\U00013000'
		test_out = '\ufffd'
		errors = self.compare_pair(test_in, ['insertion'], test_out)
		self.assertEqual(len(errors), 1)

	def test_tabular(self):
		test_in = '\U000131A5\U00013436\U00013000'
		test_out = '\ufffd'
		errors = self.compare_pair(test_in, ['tabular'], test_out)
		self.assertEqual(len(errors), 1)

	def test_unknown(self):
		test_in = '\U000131A5\U00013436\U00013000'
		test_out = '\U000131A5\U00013436\U00013000'
		errors = self.compare_pair(test_in, ['nonexistent'], test_out)
		self.assertEqual(len(errors), 1)

	def test_file(self):
		with open('tests/resources/normalization.csv', 'r') as f:
			reader = csv.reader(f)
			for fragment,types,alt in reader:
				errors = self.compare_pair(fragment, types.split('/'), alt)

	def get_transform_stats(self, test_in):
		parsed = self.parser.parse(test_in)
		return transforms_from(parsed)

	def test_transform_stats(self):
		stats = self.get_transform_stats('\U00013000\ufe00\U00013430\U00013000\U00013440')
		self.assertEqual(len(stats), 2)

	def test_rot(self):
		stats = self.get_transform_stats('\U00013000\ufe02\U000133BF\ufe02\U000133BF\ufe01')
		wrong_rots = []
		for ch, vs, _ in stats:
			rot = num_to_rotate(vs)
			if rot not in allowed_rotations(ch):
				wrong_rots.append((ch, rot))
		self.assertEqual(len(wrong_rots), 2)

	def get_insertion_stats(self, test_in):
		parsed = self.parser.parse(test_in)
		return char_insertions_from(parsed)

	def test_insertion(self):
		stats = self.get_insertion_stats('\U00013171\U00013433\U000133CF\U00013171\U00013439\U000133CF')
		wrong_inserts = []
		for ch, rotation, mirror, place in stats:
			allowed = char_to_places(ch, rotation, mirror)
			if place not in allowed:
				wrong_inserts.append((ch, place))
		self.assertEqual(len(wrong_inserts), 1)

	def test_rot_error(self):
		pass
