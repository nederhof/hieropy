import unittest
import csv
import ast

from hieropy import ResParser, ResUniConverter

class TestConv(unittest.TestCase):

	def setUp(self):
		self.parser = ResParser()

	def convert_res_uni(self, res_str):
		converter = ResUniConverter()
		res = self.parser.parse(res_str)
		mach_str = str(converter.convert_fragment(res))
		return mach_str, len(converter.errors)

	def test_normal(self):
		with open('tests/resources/resuniconversion.csv', 'r') as f:
			reader = csv.reader(f, delimiter=' ')
			for res_str,gold_str in reader:
				mach_str, n_error = self.convert_res_uni(res_str)
				res = self.parser.parse(res_str)
				self.assertEqual(mach_str, gold_str)
				self.assertEqual(n_error, 0)

	def test_errors(self):
		with open('tests/resources/resuniconversionerror.txt', 'r') as f:
			lines = f.readlines()
		for line in lines:
			res_str = line.strip()
			_, n_error = self.convert_res_uni(res_str)
			self.assertGreaterEqual(n_error, 1)

	def test_testsuites(self):
		with open('tests/resources/restestsuitenormalized.txt', 'r') as f:
			lines = f.readlines()
		for line in lines:
			self.convert_res_uni(line.strip())
		with open('tests/resources/restestsuitespecial.txt', 'r') as f:
			lines = f.readlines()
		for line in lines:
			self.convert_res_uni(line.strip())

	def test_colored(self):
		with open('tests/resources/resuniconversioncolored.csv', 'r') as f:
			converter = ResUniConverter()
			reader = csv.reader(f, delimiter=' ')
			for res_str,gold_str in reader:
				res = self.parser.parse(res_str)
				mach = [(str(group), color) for group,color in converter.convert_fragment_by_predominant_color(res)]
				gold = ast.literal_eval(gold_str)
				self.assertEqual(mach, gold)
