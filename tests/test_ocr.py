import unittest
import difflib

from hieropy import UniParser, Options
from hieropy.ocr import *

unittest.TestLoader.sortTestMethodsUsing = None

pickle_filename = 'tests/tmp/testpickle.pkl'
tmp_ocr_dir = 'tests/tmp/'

@unittest.skip("Skipping tests that do file IO")
class TestOcr(unittest.TestCase):

	@unittest.skip("Skipping test that does file IO")
	def test_create_dump_load_font(self):
		converter = ImageUniConverter.from_font()
		converter.dump(pickle_filename)
		converter = ImageUniConverter.load(pickle_filename)

	def make_ocr_testfile(self, encoding, filename):
		parser = UniParser()
		fragment = parser.parse(encoding)
		options = Options(fontsize=40)
		printed = fragment.print(options)
		printed.get_pil().save(tmp_ocr_dir + filename)

	def do_ocr_test(self, encoding_in, filename):
		self.make_ocr_testfile(encoding_in, filename)
		image = Image.open(tmp_ocr_dir + filename)
		converter = ImageUniConverter.load(pickle_filename)
		fragment = converter.convert_line(image, em=40)
		encoding_out = str(fragment)
		print(encoding_in, encoding_out)
		print(encoding_in == encoding_out)
		print(list(difflib.ndiff(encoding_in, encoding_out)))

	def test_simple_example(self):
		encoding = '𓆓𓐳𓂧𓏏𓐰𓈖𓈖𓐰𓐍𓐱𓏲𓏛𓀜𓅓𓅐𓐰𓏏𓐱𓏯𓀀𓐰𓈖𓇗𓂝𓐰𓏏𓐱𓏯𓁐𓐰𓈖𓇋𓏠𓐰𓈖𓅆𓏏𓏲𓁐'
		filename = 'ocrtest1.png'
		self.do_ocr_test(encoding, filename)

	@unittest.skip("Skipping test that will fail (characters are excluded)")
	def test_strokes(self):
		encoding = '𓏥𓏦𓏨𓏩'
		filename = 'ocrtest2.png'
		self.do_ocr_test(encoding, filename)

	def test_eyes(self):
		encoding = '𓁶𓁷𓂉𓂊𓆲𓄀𓤰𓤯𓦑𓭜𓿬'
		filename = 'ocrtest3.png'
		self.do_ocr_test(encoding, filename)

	def test_dots(self):
		encoding = '𔊢𔊗𔆖𔆗𔆝𓿱𓾨𓻣𓻸𓻻𓻼𓻽𓻾𓻿𓵳𓵴'
		# encoding = '𓵴'
		filename = 'ocrtest4.png'
		self.do_ocr_test(encoding, filename)

	def test_sizes(self):
		encoding = '𓂂𓆇𓇳𓈒𓊗𓋰𓊌𓊪𓏑'
		filename = 'ocrtest5.png'
		self.do_ocr_test(encoding, filename)

	def test_included(self):
		encoding = '𓁷𓇳𓇵𓄤𓄔𓅓𓌲𓎼𓏞'
		filename = 'ocrtest6.png'
		self.do_ocr_test(encoding, filename)

	def test_multi_component(self):
		encoding = '𓔧𓇾𓇠𓇢𓔜𓔞𓓅𔃇𓏭𓰃𓏭𓀀𓌾'
		encoding = '𓌾'
		filename = 'ocrtest7.png'
		self.do_ocr_test(encoding, filename)

	@unittest.skip("Skipping test that will fail (characters are excluded)")
	def test_compositional(self):
		encoding = '𓏀𓆖𓅲𓂗'
		filename = 'ocrtest8.png'
		self.do_ocr_test(encoding, filename)

	def test_external(self):
		image = Image.open(tmp_ocr_dir + 'test9.png')
		converter = ImageUniConverter.load(pickle_filename)
		fragment = converter.convert_line(image)
		encoding_out = str(fragment)
		print(encoding_out)

	def do_sethe_test(self, filename, encoding_in):
		converter = ImageUniConverter.from_exemplars('sethe')
		# converter.dump(pickle_filename)
		# converter = ImageUniConverter.load(pickle_filename)
		image = Image.open(tmp_ocr_dir + filename)
		fragment = converter.convert_line(image)
		encoding_out = str(fragment)
		print(encoding_out)

	def test_sethe1(self):
		filename = 'B1-2.png'
		self.do_sethe_test(filename, '')

	def test_sethe2(self):
		filename = 'A1-6.png'
		self.do_sethe_test(filename, '')

	def test_sethe3(self):
		filename = 'I9-3.png'
		self.do_sethe_test(filename, '')
