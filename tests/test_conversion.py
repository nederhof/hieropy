import unittest
import csv
import ast
import os

from hieropy import ResParser, ResUniConverter, MdcUniConverter
import hieropy.mdcstructure as mdc
import hieropy.unistructure as uni

class TestResConv(unittest.TestCase):

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
			for line_no, (res_str,gold_str) in enumerate(reader, start=1):
				res = self.parser.parse(res_str)
				mach = [(str(fragment), fragment.color) \
					for fragment in converter.convert_fragment_by_predominant_color(res)]
				gold = ast.literal_eval(gold_str)
				self.assertEqual(mach, gold, msg=f'Line {line_no}')

class TestMdcConv(unittest.TestCase):

	def convert_mdc_uni(self, mdc_str):
		converter = MdcUniConverter()
		uni_str = ''.join(map(str, converter.convert(mdc_str)))
		n_errors = len(converter.errors)
		return uni_str, n_errors

	def test_normal(self):
		with open('tests/resources/mdcuniconversion.csv', 'r') as f:
			reader = csv.reader(f, delimiter=' ')
			for line_no, (mdc_str,gold_str) in enumerate(reader, start=1):
				mach_str, n_error = self.convert_mdc_uni(mdc_str)
				mach = [hex(ord(x)) for x in mach_str]
				gold = [hex(ord(x)) for x in gold_str]
				self.assertEqual(mach_str, gold_str, msg=f'Line {line_no}\n{mach}\n{gold}')

	def test_errors(self):
		with open('tests/resources/mdcuniconversionerror.txt', 'r') as f:
			lines = f.readlines()
		for line_no, line in enumerate(lines, start=1):
			mdc_str = line.strip()
			mach_str, n_error = self.convert_mdc_uni(mdc_str)
			self.assertGreaterEqual(n_error, 1, msg=f'Line {line_no}')

	@unittest.skip("Skipping this test until real directory is added")
	def test_bulk(self):
		d = '/replace by directory of .hie or .gly files'
		for filename in os.listdir(d):
			if filename.endswith('.gly') or filename.endswith('.gly'):
				file_path = os.path.join(d, filename)
				with open(file_path, 'r', encoding='utf-8') as f:
					text = f.read()
					print(filename)
					converter = MdcUniConverter(text=True, numbers=True, colors=True)
					converted = converter.convert(text)
					for part in converted:
						match part:
							case mdc.LineNumber(): print(f'({part}): ')
							case mdc.Text(): print(f'"{part}"')
							case uni.Fragment(): print(f'[{part.color}] {part}')
					print(converter.errors)
