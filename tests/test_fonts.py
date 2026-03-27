import unittest
from PIL import ImageFont

from hieropy.options import Options
from hieropy.uniconstants import Rectangle, HIERO_FONT_NAME
from hieropy.printables import register_pdf_font, measure_glyph_pdf, measure_glyph_pil, \
	measure_glyph_pdf_memo, em_size_of, PrintedPdf
from hieropy.hieroparsing import UniParser
from hieropy import CustomSignList

class TestFonts(unittest.TestCase):

	def measure_of(self, ch):
		fontsize = 40
		x_scale = 1
		y_scale = 1
		rotate = 180
		mirror = True
		meas = measure_glyph_pdf(ch, HIERO_FONT_NAME, fontsize, x_scale, y_scale, rotate, mirror)
		meas2 = measure_glyph_pdf_memo(ch, HIERO_FONT_NAME, fontsize, x_scale, y_scale, rotate, mirror)
		self.assertTrue(abs(meas.x - meas2.x) <= 3)
		self.assertTrue(abs(meas.y - meas2.y) <= 3)
		self.assertTrue(abs(meas.w - meas2.w) <= 3)
		self.assertTrue(abs(meas.h - meas2.h) <= 3)

	def test_measure(self):
		register_pdf_font()
		self.measure_of(chr(0x13000))
		self.measure_of(chr(0x130B7)) # flat
		self.measure_of(chr(0x130C0)) # tall

	def measure_pil_of(self, ch, y, w, h):
		fontsize = 40
		x_scale = 1.001
		y_scale = 1
		# rotate = 180
		rotate = 0
		mirror = False
		with open('src/hieropy/resources/NewGardiner.ttf', 'rb') as f:
			font = ImageFont.truetype(f, fontsize)
		meas = measure_glyph_pil(ch, font, x_scale, y_scale, rotate, mirror)
		self.assertTrue(abs(meas.y - y) <= 3)
		self.assertTrue(abs(meas.w - w) <= 3)
		self.assertTrue(abs(meas.h - h) <= 3)

	def test_measure_pil(self):
		self.measure_pil_of(chr(0x13000), 0, 28, 40)
		self.measure_pil_of(chr(0x130B7), 30, 40, 10) # flat
		self.measure_pil_of(chr(0x130C0), 0, 20, 40) # tall

	def em_size_of(self, ch, w_gold, h_gold):
		fontsize = 40
		x_scale = 1
		y_scale = 1
		rotate = 180
		mirror = True
		options = Options(fontsize=fontsize)
		w, h = em_size_of(ch, options, x_scale, y_scale, rotate, mirror)
		self.assertTrue(abs(w - w_gold) <= 0.2)
		self.assertTrue(abs(h - h_gold) <= 0.2)

	def test_em_size(self):
		self.em_size_of(chr(0x13000), 0.7, 1)
		self.em_size_of(chr(0x130B7), 1, 0.23)

	def printed_pdf_em(self, ch):
		scale = 1
		x_scale = 1
		y_scale = 1
		rotate = 0
		mirror = False
		printed = PrintedPdf(10, 10, 0, 0, Options())
		rect = Rectangle(3, 3, 5, 5)
		printed.add_sign(ch, scale, x_scale, y_scale, rotate, mirror, rect)
		im = printed.get_pil()
		im.save(f'tests/tmp/testprintedpdf{hex(ord(ch))}.png')
		with open(f'tests/tmp/testprintedpdf{hex(ord(ch))}.pdf', 'wb') as f:
			f.write(printed.get_pdf())
	
	def test_printed_pdf(self):
		self.printed_pdf_em(chr(0x13000))
		self.printed_pdf_em(chr(0x13005))

	def test_format(self):
		parser = UniParser()
		fragments = [\
			'𓃀𓐰𓈖𓈖𓐰𓆱𓐰𓐍𓐱𓏏𓀜𓏏𓏲𓆑𓀀𓅓𓋹𓍑𓋴𓅓𓎛𓎿𓋴𓀁𓇋𓏠𓐰𓈖𓅆',
			'𓈖𓐰𓄿𓇋𓇋𓏦𓐰𓎢𓂋𓐰𓍿𓀀𓐱𓁐𓐰𓏦𓏇𓇋𓐪𓂧𓐰𓏌𓏛𓐰𓏦𓐍𓐰𓂋𓊪𓏏𓐰𓂋',
			'𓇋𓆵𓁻𓆟𓂋𓐰𓈙𓏤𓆑𓐰𓄿𓀋𓂡𓅯𓄿𓇋𓇋𓋴𓏏',
			'𓊪𓏏𓐰𓂋𓇋𓆵𓁻𓂞𓏲𓈖𓐰𓎢𓈖𓐰𓄿𓃀𓂧𓐰𓏏𓐱𓏲']
		options = Options(fontsize=40, imagetype='pdf')
		for _ in range(50):
			for f in fragments:
				parsed = parser.parse(f)
				parsed.print(options).get_pil()

	def test_pdf_select(self):
		parser = UniParser()
		signs = [(chr(0x142AD), 'A1z', chr(0x13001))]
		custom = CustomSignList('CustomFont', 'tests/resources/Custom.ttf', signs)
		encodings = [\
			'𓀀',
			'𓆓𓐻𓐷𓈎𓐱𓏹𓐸',
			'𓀀𓀀𓀀︆',
			'𓀀[𓀀𓀀︆',
			'𓀀𓍹𓐼𓀀𓐽𓍺𓀀',
			'𓀀𓂝𓐶𓃀𓀀',
			'𓀀\U000142AD𓀀',
			'𓈖𓐰𓄿𓇋𓇋𓏦𓐰𓎢𓂋𓐰𓍿𓀀𓐱𓁐𓐰𓏦𓏇𓇋𓐪𓂧𓐰𓏌𓏛𓐰𓏦𓐍𓐰𓂋𓊪𓏏𓐰𓂋']
		options_pdf = Options(fontsize=40, imagetype='pdf', custom=custom)
		options_svg = Options(fontsize=40, imagetype='svg', custom=custom)
		for i, e in enumerate(encodings):
			save_path = f'tests/tmp/pdfselect{i}.pdf'
			fragment = parser.parse(e)
			printed_pdf = fragment.print(options_pdf).get_pdf()
			with open(save_path, 'wb') as f:
				f.write(printed_pdf)
			printed_svg = fragment.print(options_svg).get_svg()
			with open(f'tests/tmp/svgselect{i}.svg', 'w', encoding='utf-8') as f:
				f.write(printed_svg)
