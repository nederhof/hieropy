import unittest
from hieropy import UniParser, UniFontBuilder, UniExtractor

# @unittest.skip("Skipping tests that do file IO")
class TestOpentype(unittest.TestCase):

	def test_extract(self):
		extractor = UniExtractor()
		encodings = extractor.extract('\U00013000plain\U00013001text\U00013050')
		self.assertEqual(len(encodings), 3)

	def test_extract_text(self):
		extractor = UniExtractor()
		encodings = extractor.extract_file('tests/resources/extract.txt')
		self.assertEqual(len(encodings), 3)

	def test_extract_xml(self):
		extractor = UniExtractor()
		encodings1 = extractor.extract_xml('tests/resources/extract.xml')
		encodings2 = extractor.extract_xml('tests/resources/extract.xml', attribute=('name','val'))
		self.assertEqual(len(encodings1), 2)
		self.assertEqual(len(encodings2), 1)

	def test_extract_odt(self):
		extractor = UniExtractor()
		encodings = extractor.extract_odt('tests/resources/extract.odt')
		self.assertEqual(len(encodings), 5)
		builder = UniFontBuilder(basename='TestodtHiero')
		parser = UniParser()
		for e in encodings:
			builder.add(parser.parse(e))
		builder.make_font('tests/tmp/odt.ttf') 

	def test_extract_docx(self):
		extractor = UniExtractor()
		encodings = extractor.extract_docx('tests/resources/extract.docx')
		self.assertEqual(len(encodings), 5)
		builder = UniFontBuilder(basename='TestdocxHiero')
		parser = UniParser()
		for e in encodings:
			builder.add(parser.parse(e))
		builder.make_font('tests/tmp/docx.ttf') 

	def test_webpage(self):
		parser = UniParser()
		builder_hlr = UniFontBuilder(linesize=1,descent=0.5, \
			sep=0.08, align='bottom', separated=True, signcolor='black',bracketcolor='black',shadepattern='uniform', \
			shadecolor='black',shadealpha=150)
		builder_hrl = UniFontBuilder(direction='hrl', linesize=1, \
			descent=0.1,signcolor='black',bracketcolor='red',shadepattern='diagonal', \
			shadecolor='black',shadealpha=150, gap=0.1)
		builder_vlr = UniFontBuilder(direction='vlr', linesize=1, separated=True, \
			descent=0,signcolor='blue',bracketcolor='red',shadepattern='diagonal', \
			shadecolor='black',shadealpha=150, gap=0.0)
		builder_vrl = UniFontBuilder(direction='vrl', linesize=1, \
			descent=0,signcolor='black',bracketcolor='red',shadepattern='diagonal', \
			shadecolor='black',shadealpha=250)
		extractor = UniExtractor()
		encodings_hlr = extractor.extract_html('tests/resources/opentype.html', classname='hlr')
		encodings_hrl = extractor.extract_html('tests/resources/opentype.html', classname='hrl')
		encodings_vlr = extractor.extract_html('tests/resources/opentype.html', classname='vlr')
		encodings_vrl = extractor.extract_html('tests/resources/opentype.html', classname='vrl')
		for e in encodings_hlr:
			builder_hlr.add(parser.parse(e))
		for e in encodings_hrl:
			builder_hrl.add(parser.parse(e))
		for e in encodings_vlr:
			builder_vlr.add(parser.parse(e))
		for e in encodings_vrl:
			builder_vrl.add(parser.parse(e))
		fragment = parser.parse('\U00013000\U00013455\U00013050')
		builder_hlr.add_mapping('x', fragment)
		builder_hlr.add_mapping('yyy', fragment)
		builder_hrl.add_mapping('abc', fragment)
		builder_vlr.add_mapping('abc', fragment)
		builder_vrl.add_mapping('abc', fragment)
		builder_hlr.make_font('tests/tmp/opentypehlr.ttf')
		builder_hrl.make_font('tests/tmp/opentypehrl.ttf')
		builder_vlr.make_font('tests/tmp/opentypevlr.ttf')
		builder_vrl.make_font('tests/tmp/opentypevrl.ttf')

	def test_bm(self):
		parser = UniParser()
		builder = UniFontBuilder(descent=0.3)
		encodings = UniExtractor().extract_html('tests/resources/BritishMuseumEA101.html', classname='hlr')
		for e in encodings:
			builder.add(parser.parse(e))
		builder.make_font('tests/tmp/bm.ttf')
