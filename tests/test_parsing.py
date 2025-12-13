import unittest

from hieropy import UniParser, ResParser
from hieropy.unistats import chars_from
from hieropy.options import Options

@unittest.skip('Skipping tests to save time')
class TestUniParsing(unittest.TestCase):
	def test_one(self):
		myparser = UniParser()
		parsed = myparser.parse('\U00013000\U00013430\U00013001')
		parsed_str = str(parsed)
		parsed_list = list(parsed_str)
		self.assertEqual(parsed_list, [chr(0x13000), chr(0x13430), chr(0x13001)])
		parsed_repr = repr(parsed)
		self.assertEqual(parsed_repr, 'A1:A2')

	def test_unchanging_testsuite(self):
		myparser = UniParser()
		with open('tests/resources/unitestsuite.txt', 'r') as f:
			lines = f.readlines()
		for line in lines:
			line = line.strip()
			parsed = myparser.parse(line)
			line_parsed = str(parsed)
			self.assertEqual(line, line_parsed)

	def test_unchanging_testsuite_with_copy(self):
		myparser = UniParser()
		with open('tests/resources/unitestsuite.txt', 'r') as f:
			lines = f.readlines()
		for line in lines:
			line = line.strip()
			parsed = myparser.parse(line)
			chars = chars_from(parsed)
			copy = parsed.copy()
			line_parsed = str(parsed)
			self.assertEqual(line, line_parsed)

	@unittest.skip('Skipping test to save time')
	def test_testsuite_formatting(self):
		myparser = UniParser()
		options_pdf = Options(imagetype='pdf')
		options_svg = Options(imagetype='svg')
		options_pil = Options(imagetype='pdf')
		with open('tests/resources/unitestsuite.txt', 'r') as f:
			lines = f.readlines()
		for line in lines:
			line = line.strip()
			parsed = myparser.parse(line)
			parsed.print(options_pdf)
			parsed.print(options_svg)
			parsed.print(options_pil)

	def test_bracket(self):
		myparser = UniParser()
		parsed = myparser.parse('\U00013258')
		parsed_repr = repr(parsed)
		self.assertEqual(parsed_repr, 'O6a')

	def test_parse_error1(self):
		myparser = UniParser()
		parsed = myparser.parse('\U00013000\U00013430')
		self.assertEqual(myparser.last_error, 'Unexpected end of input')

	def test_parse_error2(self):
		myparser = UniParser()
		parsed = myparser.parse('\U00013430\U00013000\U00013430')
		self.assertEqual(myparser.last_error, 'Syntax error at position 0')

@unittest.skip('Skipping tests to save time')
class TestResParsing(unittest.TestCase):
	def test_one(self):
		myparser = ResParser()
		line = 'oval[blue](A1)'
		parsed = myparser.parse(line)
		copy = str(parsed)
		self.assertEqual(line, copy)

	def test_normalized_equal(self):
		myparser = ResParser()
		with open('tests/resources/restestsuitenormalized.txt', 'r') as f:
			lines = f.readlines()
		for line in lines:
			line = line.strip()
			parsed = myparser.parse(line)
			copy = str(parsed)
			self.assertEqual(line, copy)

	@unittest.skip('Skipping (verbose) test')
	def test_normalization(self):
		myparser = ResParser()
		with open('tests/resources/restestsuitespecial.txt', 'r') as f:
			lines = f.readlines()
		for line in lines:
			line = line.strip()
			parsed = myparser.parse(line)
			copy = str(parsed)
			if copy != line:
				print('normalization changed\n', line, '\ninto\n', copy)

if __name__ == '__main__':
	unittest.main()
