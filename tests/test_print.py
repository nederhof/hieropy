import unittest
import io
from PIL import Image

from reportlab.platypus import SimpleDocTemplate, Table, Paragraph, Image, Spacer
from reportlab.pdfgen import canvas
from reportlab.lib.pagesizes import A4

from hieropy import UniParser
from hieropy.options import Options

def make_image(img):
	img_buffer = io.BytesIO()
	img.save(img_buffer, format="PNG")
	img_buffer.seek(0)
	return Image(img_buffer)

class TestPrinting(unittest.TestCase):

	def test_print_all(self):
		myparser = UniParser()
		options_pdf_hlr = Options(imagetype='pdf', fontsize=30, direction='hlr')
		options_pdf_hrl = Options(imagetype='pdf', fontsize=30, direction='hrl')
		options_pil_vlr = Options(imagetype='pil', fontsize=30, direction='vlr')
		options_pil_vrl = Options(imagetype='pil', fontsize=30, direction='vrl')
		with open('tests/resources/unitestsuite.txt', 'r') as f:
			lines = f.readlines()
		rows = []
		for line in lines:
			line = line.strip()
			parsed = myparser.parse(line)
			pdf_hlr = parsed.print(options_pdf_hlr)                                                                 
			pdf_hrl = parsed.print(options_pdf_hrl)                                                                 
			pil_vlr = parsed.print(options_pil_vlr) 
			pil_vrl = parsed.print(options_pil_vrl) 
			im_pdf_hlr = make_image(pdf_hlr.get_pil())
			im_pdf_hrl = make_image(pdf_hrl.get_pil())
			im_pil_vlr = make_image(pil_vlr.get_pil())
			im_pil_vrl = make_image(pil_vrl.get_pil())
			rows.append([im_pdf_hlr, im_pdf_hrl, im_pil_vlr, im_pil_vrl])
		table = Table(rows)
		doc = SimpleDocTemplate("tests/tmp/testsuiteoutput.pdf", pagesize=A4)
		doc.build([table])

	def test_print(self):
		myparser = UniParser()
		options1 = Options(imagetype='pdf', fontsize=30, direction='hlr')
		options2 = Options(imagetype='pdf', fontsize=30, direction='hrl')
		line = '𓏶𓐲𓏏'
		parsed = myparser.parse(line)
		pdf1 = parsed.print(options1)
		pdf2 = parsed.print(options2)
		im1 = make_image(pdf1.get_pil())
		im2 = make_image(pdf2.get_pil())
		doc = SimpleDocTemplate("tests/tmp/pngindocument.pdf", pagesize=A4)
		doc.build([im1, im2])
