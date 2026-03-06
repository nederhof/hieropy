import unittest
import difflib

from hieropy import UniParser, Options
from hieropy.uninames import all_chars
from hieropy.ocrdata import ocr_omit
from hieropy.ocr import *

pickle_filename = 'tests/tmp/testpickle.pkl'

resources_dir = 'tests/resources/'
tmp_ocr_dir = 'tests/tmp/'

@unittest.skip("Skipping tests that do file IO")
class TestOcr(unittest.TestCase):

	@unittest.skip("Skipping test that creates pickle file")
	def test_create_dump_load_font(self):
		converter = ImageUniConverter.from_font()
		converter.dump(pickle_filename)

	def make_ocr_testfile(self, encoding, filename, fontsize=40):
		parser = UniParser()
		fragment = parser.parse(encoding)
		options = Options(fontsize=fontsize)
		printed = fragment.print(options)
		printed.get_pil().save(tmp_ocr_dir + filename)

	def do_ocr_test(self, encoding_in, filename, \
				direction=None, shading=None, target=None, fontsize=40):
		self.make_ocr_testfile(encoding_in, filename, fontsize=fontsize)
		image = Image.open(tmp_ocr_dir + filename)
		converter = ImageUniConverter.load(pickle_filename)
		fragment = converter.convert_line(image, em=fontsize, direction=direction, shading=shading)
		encoding_out = str(fragment)
		if target is None:
			target = encoding_in
		self.assertEqual(encoding_out, target, msg=\
				str(encoding_in) + '\n' + \
				str([hex(ord(c)) for c in target]) + '\n' + \
				str([hex(ord(c)) for c in encoding_out]) + '\n' + \
				str(list(difflib.ndiff(target, encoding_out))))

	def test_simple_example(self):
		encoding = '𓆓𓐻𓂧𓏏𓐰𓈖𓈖𓐰𓐍𓐱𓏲𓏛𓀜𓅓𓅐𓐰𓏏𓐱𓏯𓀀𓐰𓈖𓇗𓂝𓐰𓏏𓐱𓏯𓁐𓐰𓈖𓇋𓏠𓐰𓈖𓅆𓏏𓏲𓁐'
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

	def test_dots1(self):
		encoding = '𔊢𔆖𔆗𔆝𓿱𓾨𓻸𓻻𓻼𓻽𓻾𓵴𓻿'
		filename = 'ocrtest4a.png'
		self.do_ocr_test(encoding, filename)

	@unittest.skip("Skipping test that are known to fail")
	def test_dots2(self):
		encoding = '𔊗𓀀𓻣𓀀𓵳'
		filename = 'ocrtest4b.png'
		self.do_ocr_test(encoding, filename)

	def test_sizes(self):
		encoding = '𓂂𓆇𓇳𓈒𓊗𓋰𓊌𓊪𓏑'
		filename = 'ocrtest5.png'
		self.do_ocr_test(encoding, filename)

	def test_included(self):
		encoding = '𓁷𓇳𓇵𓄤𓄔𓅓𓌲𓎼𓏞'
		filename = 'ocrtest6.png'
		self.do_ocr_test(encoding, filename)

	def test_multi_component1(self):
		encoding = '𓀀𓔧𓇾𓇠𓇢𓔜𔃇𓏭𓰃𓏭𓓅'
		filename = 'ocrtest7a.png'
		self.do_ocr_test(encoding, filename)

	@unittest.skip("Skipping test that are known to fail")
	def test_multi_component2(self):
		encoding = '𓌾𓀀𓔞'
		filename = 'ocrtest7b.png'
		self.do_ocr_test(encoding, filename)

	def test_cartouche1(self):
		encoding = '𓉘𓐼𓂝𓐽𓊂𓊆𓐾𔂤𓐱𓁐𓐿𓊇'
		filename = 'ocrtest8a.png'
		self.do_ocr_test(encoding, filename, fontsize=60)

	def test_cartouche2(self):
		encoding = '𓍹𓐼𓀀𓐱𓐍𓐽𓍺𓍹𓐼𓀿𓐱𓊧𓐽𓍺'
		filename = 'ocrtest8b.png'
		self.do_ocr_test(encoding, filename, fontsize=100)

	def test_compositional1(self):
		encoding = '𓏀𓅲𓂗'
		target = '𓎛𓐱𓎿𓐰𓊃𓅱𓐳𓏏𓂓𓐺𓍛'
		filename = 'ocrtest9a.png'
		self.do_ocr_test(encoding, filename, target=target)

	def test_compositional2(self):
		encoding = '𓆖'
		target = '𓆓𓐻𓐷𓏏𓐰𓇿𓐸'
		filename = 'ocrtest9b.png'
		self.do_ocr_test(encoding, filename, target=target)

	def test_mirror(self):
		encoding = '𓀀𓑀𓁐𓑀'
		target = '𓁐𓀀'
		filename = 'ocrtest10.png'
		self.do_ocr_test(encoding, filename, direction='hrl', target=target)

	def test_vrl(self):
		encoding = '𓀀𓑀𓐰𓁐𓑀'
		target = '𓀀𓁐'
		filename = 'ocrtest11.png'
		self.do_ocr_test(encoding, filename, direction='vrl', target=target)

	def test_shading(self):
		encoding = '𓀀𓀀𓀀'
		target = '𓀀𓑐𓀀𓑋𓀀𓑉'
		filename = 'ocrtest12.png'
		shading = [[(0,20),(30,20),(30,40),(0,40)], [(30,0),(75,0),(75,40),(60,40),(60,20),(30,20)]]
		self.do_ocr_test(encoding, filename, shading=shading, target=target)

	def test_shading_mirrored(self):
		encoding = '𓀀𓑀𓀀𓑀𓀀𓑀'
		target = '𓀀𓑒𓀀𓑋𓀀𓑐'
		filename = 'ocrtest13.png'
		shading = [[(0,20),(30,20),(30,40),(0,40)], [(30,0),(75,0),(75,40),(60,40),(60,20),(30,20)]]
		self.do_ocr_test(encoding, filename, shading=shading, direction='hrl', target=target)

@unittest.skip("Skipping tests that will take too long")
class TestExhaustive(unittest.TestCase):

	def make_image(self, parser, encoding, fontsize=40):
		fragment = parser.parse(encoding)
		options = Options(fontsize=fontsize)
		printed = fragment.print(options)
		return printed.get_pil()

	def no_test_all_horizontal(self):
		parser = UniParser()
		converter = ImageUniConverter.load(pickle_filename)
		for ch in all_chars():
			if ch not in ocr_omit():
				encoding_in = chr(0x13000) + ch + chr(0x13000)
				image = self.make_image(parser, encoding_in)
				encoding_out = str(converter.convert_line(image))
				if encoding_in != encoding_out:
					print("FAIL", hex(ord(ch)), ch, encoding_out[1:-1])
					print("IN", str([hex(ord(c)) for c in encoding_in[1:-1]]))
					print("OUT", str([hex(ord(c)) for c in encoding_out[1:-1]]))

	def test_all_vertical(self):
		parser = UniParser()
		converter = ImageUniConverter.load(pickle_filename)
		for ch in all_chars():
			if ch not in ocr_omit():
				encoding_in = chr(0x13000) + chr(0x1309E) + chr(0x13430) + ch + chr(0x13430) + chr(0x1309E) + chr(0x13000)
				image = self.make_image(parser, encoding_in)
				encoding_out = str(converter.convert_line(image))
				if encoding_in != encoding_out:
					print("FAIL", hex(ord(ch)), ch, encoding_out[3:-3])
					print("IN", str([hex(ord(c)) for c in encoding_in[3:-3]]))
					print("OUT", str([hex(ord(c)) for c in encoding_out[3:-3]]))

@unittest.skip("Skipping tests that rely on scanned images")
class TestScanned(unittest.TestCase):

	def test_scanned1(self):
		image = Image.open(tmp_ocr_dir + 'scanned1.png')
		converter = ImageUniConverter.load(pickle_filename)
		fragment = converter.convert_line(image)
		target = ''
		assertEqual(str(fragment), target)

@unittest.skip("Skipping tests for Sethe's handwriting")
class TestSethe(unittest.TestCase):
	def do_sethe_test(self, filename, encoding_in):
		converter = ImageUniConverter.from_exemplars('sethe')
		image = Image.open(resources_dir + filename)
		fragment = converter.convert_line(image)
		encoding_out = str(fragment)
		self.assertEqual(encoding_in, encoding_out)

	def test_sethe1(self):
		filename = 'sethe-A1.png'
		self.do_sethe_test(filename, '𓀀')

	def test_sethe2(self):
		filename = 'sethe-B1.png'
		self.do_sethe_test(filename, '𓁐')

	def test_sethe3(self):
		filename = 'sethe-I9.png'
		self.do_sethe_test(filename, '𓆑')
