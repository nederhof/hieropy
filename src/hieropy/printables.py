import io
import math
import numpy as np
from collections import defaultdict
import svgwrite
import importlib.resources as resources
from PIL import Image, ImageFont, ImageDraw, ImageColor, ImageOps
from reportlab.pdfgen import canvas
from reportlab.pdfbase import pdfmetrics, pdfdoc
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.graphics.shapes import Drawing, Rect
from reportlab.graphics import renderPDF, renderPM
from reportlab.lib.colors import Color
from pypdfium2 import PdfDocument
from shapely.geometry import box, Polygon, MultiPolygon
from shapely.ops import unary_union

from .uniconstants import *

REFERENCE_GLYPH = '\U00013000'
MEASURE_SIZE = 150

_font_registered = False
_measurements_pdf = {}
_measurements_pil = {}
measure_font_pil = None

SHADE_DIST = 5

def register_pdf_font():
	global _font_registered
	if not _font_registered:
		with resources.as_file(resources.files('hieropy.resources').joinpath(HIERO_FONT_FILENAME)) as path:
			pdfmetrics.registerFont(TTFont(HIERO_FONT_NAME, path))
		_font_registered = True

def get_measure_font_pil():
	global measure_font_pil
	if not measure_font_pil:
		with resources.files('hieropy.resources').joinpath(HIERO_FONT_FILENAME).open('rb') as f:
			measure_font_pil = ImageFont.truetype(f, MEASURE_SIZE)
	return measure_font_pil

class MeasuredGlyph:
	def __init__(self, width, height, width_scaled, height_scaled, x, y, w, h):
		# width / height : size of rectangle to be reserved for printing
		self.width = width 
		self.height = height
		# width_scaled / height_scaled : as above, but taking into account x_scale / y_scale
		self.width_scaled = width_scaled
		self.height_scaled = height_scaled
		# x / y / w / h : bounding box
		self.x = x
		self.y = y
		self.w = w
		self.h = h

	def scaled(self, scale):
		return MeasuredGlyph(self.width * scale, self.height * scale, \
			self.width_scaled * scale, self.height_scaled * scale, \
			self.x * scale, self.y * scale, self.w * scale, self.h * scale)

	def __str__(self):
		return f'x={self.x} y={self.y} w={self.w} h={self.h}'

def measure_glyph_pdf(ch, fontsize, x_scale, y_scale, rotate, mirror):
	register_pdf_font()
	metric_width = pdfmetrics.stringWidth(ch, HIERO_FONT_NAME, fontsize)
	width = max(1, round(metric_width))
	height = max(1, round(fontsize))
	width_scaled = max(1, width, round(x_scale * metric_width))
	height_scaled = max(1, height, round(y_scale * fontsize))
	margin_hor = 3
	margin_ver = 3
	if rotate % 180:
		dim = max(width_scaled, height_scaled)
		if rotate % 90:
			dim *= math.sqrt(2)
		margin_hor += math.ceil((dim - width_scaled) / 2)
		margin_ver += math.ceil((dim - height_scaled) / 2)
	w_canvas = width_scaled + 2 * margin_hor
	h_canvas = height_scaled + 2 * margin_ver
	buffer = io.BytesIO()
	c = canvas.Canvas(buffer, pagesize=(w_canvas, h_canvas))
	c.setFont(HIERO_FONT_NAME, fontsize)
	c.translate(margin_hor + width_scaled/2, margin_ver + height_scaled/2)
	c.scale(-x_scale if mirror else x_scale, y_scale)
	c.rotate(-rotate)
	c.drawString(-width/2, -height/2, ch)
	c.save()
	im = PdfDocument(buffer).get_page(0).render().to_pil().convert('L')
	bw = im.point(lambda x: 0 if x == 255 else 255, '1')
	bbox = bw.getbbox()
	x = bbox[0] - margin_hor
	y = h_canvas - margin_ver - bbox[3]
	w = bbox[2] - bbox[0]
	h = bbox[3] - bbox[1]
	return MeasuredGlyph(width, height, width_scaled, height_scaled, x, y, w, h)

def measure_glyph_pil(ch, x_scale, y_scale, rotate, mirror):
	font = get_measure_font_pil()
	bbox = font.getbbox(ch)
	y = bbox[1]
	metric_width = bbox[2] - bbox[0]
	metric_height = MEASURE_SIZE - y 
	width = max(1, metric_width)
	height = max(1, MEASURE_SIZE)
	width_scaled = max(1, round(x_scale * metric_width))
	height_scaled = max(1, round(y_scale * MEASURE_SIZE))
	if x_scale == 1 and y_scale == 1 and rotate == 0:
		w = max(1, metric_width)
		h = max(1, metric_height)
		return MeasuredGlyph(width, height, width_scaled, height_scaled, 0, y, w, h)
	else:
		im = Image.new('L', (width, height), 'white')
		draw = ImageDraw.Draw(im)
		draw.text((0, 0), ch, fill='black', font=font)
		if x_scale != 1 or y_scale != 1:
			im = im.resize((width_scaled, height_scaled))
		if rotate:
			im = im.rotate(-rotate, expand=True, fillcolor='white')
		bw = im.point(lambda x: 0 if x == 255 else 255, '1')
		bbox = bw.getbbox()
		w = bbox[2] - bbox[0]
		h = bbox[3] - bbox[1]
		return MeasuredGlyph(width, height, width_scaled, height_scaled, 0, y, w, h)

def measurementKey(ch, fontsize, x_scale, y_scale, rotate, mirror):
	return (ch, round(fontsize, 2), round(x_scale, 2), round(y_scale, 2), rotate, mirror)

def measure_glyph_pdf_memo(ch, fontsize, x_scale, y_scale, rotate, mirror):
	key = measurementKey(ch, MEASURE_SIZE, x_scale, y_scale, rotate, mirror)
	if key in _measurements_pdf:
		meas = _measurements_pdf[key]
	else:
		meas = measure_glyph_pdf(ch, MEASURE_SIZE, x_scale, y_scale, rotate, mirror)
		_measurements_pdf[key] = meas
	scale = fontsize / MEASURE_SIZE
	return meas.scaled(scale)

def measure_glyph_pil_memo(ch, fontsize, x_scale, y_scale, rotate, mirror):
	key = measurementKey(ch, MEASURE_SIZE, x_scale, y_scale, rotate, mirror)
	if key in _measurements_pil:
		meas = _measurements_pil[key]
	else:
		meas = measure_glyph_pil(ch, x_scale, y_scale, rotate, mirror)
		_measurements_pil[key] = meas
	scale = fontsize / MEASURE_SIZE
	return meas.scaled(scale)

def corrected_measurement(ch, fontsize, x_scale, y_scale, rotate, mirror, x_as, y_as, measure_fun):
	meas = measure_fun(ch, fontsize, x_scale, y_scale, rotate, mirror)
	if x_as:
		meas_as = measure_fun(x_as, fontsize, 1, 1, rotate, mirror)
		meas.x = meas_as.x
		meas.width = meas_as.width
		meas.width_scaled = meas_as.width_scaled
	elif y_as:
		meas_as = measure_fun(y_as, fontsize, 1, 1, rotate, mirror)
		meas.y = meas_as.y
		meas.h = meas_as.h
		meas.height_scaled = meas_as.height_scaled
	elif x_scale != 1:
		meas_plain = measure_fun(ch, fontsize, 1, 1, rotate, mirror)
		meas.y = meas_plain.y
		meas.h = meas_plain.h
		meas.height_scaled = meas_plain.height_scaled
	elif y_scale != 1:
		meas_plain = measure_fun(ch, fontsize, 1, 1, rotate, mirror)
		meas.x = meas_plain.x
		meas.width = meas_plain.width
		meas.width_scaled = meas_plain.width_scaled
	return meas

def em_size_of(ch, options, x_scale, y_scale, rotate, mirror):
	fontsize = options.fontsize
	ref_height = measure_glyph_pil_memo(REFERENCE_GLYPH, fontsize, 1, 1, 0, False).h
	meas = measure_glyph_pil_memo(ch, fontsize, x_scale, y_scale, rotate, mirror)
	return meas.w / ref_height, meas.h / ref_height

class PlaneRestricted:
	def __init__(self, im):
		self.im = im.convert('L')

	def width(self):
		return self.im.size[0]

	def height(self):
		return self.im.size[1]

	def is_dark(self, x, y):
		return x < 0 or self.width() <= x or y < 0 or self.height() <= y or \
			self.im.getpixel((x, y)) < 128

	def topmost_dark(self, x, y_min, y_max):
		for y in range(y_min, y_max+1):
			if self.is_dark(x, y):
				return y
		return None

	def bottommost_dark(self, x, y_min, y_max):
		for y in range(y_max, y_min-1, -1):
			if self.is_dark(x, y):
				return y
		return None

	def leftmost_dark(self, x_min, x_max, y):
		for x in range(x_min, x_max+1):
			if self.is_dark(x, y):
				return x
		return None

	def rightmost_dark(self, x_min, x_max, y):
		for x in range(x_max, x_min-1, -1):
			if self.is_dark(x, y):
				return x
		return None

class PlaneExtended(PlaneRestricted):
	def __init__(self, im):
		super().__init__(im)

	def is_dark(self, x, y):
		return 0 <= x and x < self.width() and 0 <= y and y < self.height() and \
			self.im.getpixel((x, y)) == 0

class OrthogonalHull:
	def __init__(self, im, dist):
		self.im = ImageOps.invert(im.convert('1').convert('L'))
		self.dist = dist
		self.dist_slant = round(1 / math.sqrt(2))
		self.w, self.h = self.im.size
		bbox = self.im.getbbox()
		self.x_mins = {y: self.w-1 for y in range(-dist, self.h + dist)}
		self.x_maxs = {y: 0 for y in range(-dist, self.h + dist)}
		self.y_mins = {x: self.h-1 for x in range(-dist, self.w + dist)}
		self.y_maxs = {x: 0 for x in range(-dist, self.w + dist)}
		if bbox is None:
			self.add_ver(0, 0, self.h-1)
			self.add_ver(self.w-1, 0, self.h-1)
			self.add_hor(0, self.w-1, 0)
			self.add_hor(0, self.w-1, self.h-1)
			self.x_min = -dist
			self.x_max = self.w + dist -1
			self.y_min = -dist
			self.y_max = self.h + dist -1
			return
		x_min = bbox[0]
		x_max = bbox[2]-1
		y_min = bbox[1]
		y_max = bbox[3]-1
		x = x_min
		y = self.topmost_white(x, y_min, y_max)
		x_old = x
		while y > y_min:
			x += 1
			y_new = self.topmost_white(x, y_min, y-1)
			if y_new is not None:
				self.add_hor(x_old, x, y)
				self.add_ver(x, y_new, y)
				y = y_new
				x_old = x
		x = self.rightmost_white(x, x_max, y)
		self.add_hor(x_old, x, y)
		y_old = y
		while x < x_max:
			y += 1
			x_new = self.rightmost_white(x+1, x_max, y)
			if x_new is not None:
				self.add_ver(x, y_old, y)
				self.add_hor(x, x_new, y)
				x = x_new
				y_old = y
		y = self.bottommost_white(x, y, y_max)
		self.add_ver(x, y_old, y)
		x_old = x
		while y < y_max:
			x -= 1
			y_new = self.bottommost_white(x, y+1, y_max)
			if y_new is not None:
				self.add_hor(x, x_old, y)
				self.add_ver(x, y, y_new)
				y = y_new
				x_old = x
		x = self.leftmost_white(x_min, x, y)
		self.add_hor(x, x_old, y)
		y_old = y
		while x > x_min:
			y -= 1
			x_new = self.leftmost_white(x_min, x-1, y)
			if x_new is not None:
				self.add_ver(x, y, y_old)
				self.add_hor(x_new, x, y)
				x = x_new
				y_old = y
		y = self.topmost_white(x, y_min, y)
		self.add_ver(x, y, y_old)
		self.x_min = min(self.x_mins.values())
		self.x_max = max(self.x_maxs.values())
		self.y_min = min(self.y_mins.values())
		self.y_max = max(self.y_maxs.values())

	def add_ver(self, x, y_min, y_max):
		for y in range(y_min, y_max+1):
			self.x_mins[y] = min(self.x_mins[y], x - self.dist)
			self.x_mins[y - self.dist_slant] = min(self.x_mins[y - self.dist_slant], x - self.dist_slant)
			self.x_mins[y + self.dist_slant] = min(self.x_mins[y + self.dist_slant], x - self.dist_slant)
			self.x_maxs[y] = max(self.x_maxs[y], x + self.dist)
			self.x_maxs[y - self.dist_slant] = max(self.x_maxs[y - self.dist_slant], x + self.dist_slant)
			self.x_maxs[y + self.dist_slant] = max(self.x_maxs[y + self.dist_slant], x + self.dist_slant)

	def add_hor(self, x_min, x_max, y):
		for x in range(x_min, x_max+1):
			self.y_mins[x] = min(self.y_mins[x], y - self.dist)
			self.y_mins[x - self.dist_slant] = min(self.y_mins[x - self.dist_slant], y - self.dist_slant)
			self.y_mins[x + self.dist_slant] = min(self.y_mins[x + self.dist_slant], y - self.dist_slant)
			self.y_maxs[x] = max(self.y_maxs[x], y + self.dist)
			self.y_maxs[x - self.dist_slant] = max(self.y_maxs[x - self.dist_slant], y + self.dist_slant)
			self.y_maxs[x + self.dist_slant] = max(self.y_maxs[x + self.dist_slant], y + self.dist_slant)

	def topmost_white(self, x, y_min, y_max):
		for y in range(y_min, y_max+1):
			if self.im.getpixel((x, y)) == 255:
				return y
		return None

	def bottommost_white(self, x, y_min, y_max):
		for y in range(y_max, y_min-1, -1):
			if self.im.getpixel((x, y)) == 255:
				return y
		return None

	def leftmost_white(self, x_min, x_max, y):
		for x in range(x_min, x_max+1):
			if self.im.getpixel((x, y)) == 255:
				return x
		return None

	def rightmost_white(self, x_min, x_max, y):
		for x in range(x_max, x_min-1, -1):
			if self.im.getpixel((x, y)) == 255:
				return x
		return None

def open_rect(im, x, y):
	plane = PlaneExtended(im)
	w, h = im.size
	rect = Rectangle(x, y, 1, 1)
	extended = True
	while extended and rect.x < w and rect.y < h:
		extended = False
		if rect.x > 0 and plane.topmost_dark(rect.x-1, rect.y, rect.y+rect.h-1) is None:
			rect.x -= 1
			rect.w += 1
			extended = True
		if rect.x+rect.w < w and plane.topmost_dark(rect.x+rect.w, rect.y, rect.y+rect.h-1) is None:
			rect.w += 1
			extended = True
		if rect.y > 0 and plane.leftmost_dark(rect.x, rect.x+rect.w-1, rect.y-1) is None:
			rect.y -= 1
			rect.h += 1
			extended = True
		if rect.y+rect.h < h and plane.leftmost_dark(rect.x, rect.x+rect.w-1, rect.y+rect.h) is None:
			rect.h += 1
			extended = True
	return rect

class Shadings:
	def __init__(self, options, w_accum, h_accum):
		self.options = options
		self.w_accum = w_accum
		self.h_accum = h_accum
		self.rectangles = []
		self.intercept_to_lines = defaultdict(list)

	def add_diagonal(self, x_min, y_min, x_max):
		intercept_accum = y_min + self.h_accum - x_min - self.w_accum if self.options.imagetype == 'pdf' \
				else y_min + self.h_accum + x_min + self.w_accum
		if intercept_accum % self.options.shadedist:
			return
		intercept = y_min + - x_min if self.options.imagetype == 'pdf' \
				else y_min + x_min
		intervals = self.intercept_to_lines[intercept]
		intervals.append((x_min, x_max))
		intervals.sort(key=lambda pair: pair[0])
		merged = [intervals[0]]
		for cur in intervals[1:]:
			prev = merged[-1]
			if cur[0] <= prev[1]:
				merged[-1] = (merged[-1][0], max(prev[1], cur[1]))
			else:
				merged.append(cur)
		self.intercept_to_lines[intercept] = merged

	def add_rectangle(self, x_min, y_min, x_max, y_max):
		if self.options.shadepattern == 'uniform':
			self.rectangles.append((x_min, y_min, x_max, y_max))
		else:
			w = x_max - x_min
			h = y_max - y_min
			if self.options.imagetype == 'pdf':
				if w <= h:
					for y in range(w):
						self.add_diagonal(x_min, y_max - w + y, x_max - y)
					for y in range(h - w):
						self.add_diagonal(x_min, y_min + y, x_max)
					for x in range(w):
						self.add_diagonal(x_min + x, y_min, x_max)
				else:
					for y in range(h):
						self.add_diagonal(x_min, y_min + y, x_min + h - y)
					for x in range(w):
						self.add_diagonal(x_min + x, y_min, min(x_min + h + x, x_max))
			else:
				if w <= h:
					for x in range(w):
						self.add_diagonal(x_min + x, y_max, x_max)
					for y in range(h - w):
						self.add_diagonal(x_min, y_min + w + y, x_max)
					for y in range(w):
						self.add_diagonal(x_min, y_min + y, x_min + y)
				else:
					for y in range(h):
						self.add_diagonal(x_min, y_min + y, x_min + y)
					for x in range(w):
						self.add_diagonal(x_min + x, y_max, min(x_min + h + x, x_max))

	def segments(self):
		lines = []
		for y, xs in self.intercept_to_lines.items():
			for (x_min, x_max) in xs:
				y_min = y + x_min if self.options.imagetype == 'pdf' else y - x_min
				y_max = y + x_max if self.options.imagetype == 'pdf' else y - x_max
				lines.append((x_min, y_min, x_max, y_max))
		return lines

class PrintedAny:
	def __init__(self, w, h, w_accum, h_accum, mirrored, options):
		self.options = options
		self.w = w
		self.h = h
		self.w_px = self.em_to_px(w)
		self.h_px = self.em_to_px(h)
		self.shadings = Shadings(options, w_accum, h_accum)
		self.mirrored = mirrored
		self.is_complete = False

	def width(self):
		return math.ceil(self.w_px)

	def height(self):
		return math.ceil(self.h_px)

	def em_to_px(self, a):
		return self.options.fontsize * a

	def mirror(self, x, w):
		return self.w - (x+w) if self.mirrored else x

	def color(self, bracket):
		return self.options.bracketcolor if bracket else self.options.signcolor

	def add_text(self, text):
		pass

	def add_hidden(self, s):
		pass

class PrintedPdf(PrintedAny):
	def __init__(self, w, h, w_accum, h_accum, options):
		super().__init__(w, h, w_accum, h_accum, options.rl(), options)
		self.buffer = io.BytesIO()
		self.canvas = canvas.Canvas(self.buffer, pagesize=(self.width(), self.height()))
		if not options.transparent:
			self.canvas.setFillColor('white')
			self.canvas.rect(0, 0, self.width(), self.height(), fill=1, stroke=0)

	def complete(self):
		if self.is_complete:
			return
		self.canvas.setStrokeColor(self.options.shadecolor)
		self.canvas.setLineWidth(self.options.shadethickness)
		self.canvas.setFillColor(self.options.shadecolor)
		self.canvas.setFillAlpha(self.options.shadealpha / 255)
		self.canvas.setStrokeAlpha(self.options.shadealpha / 255)
		rectangles = self.shadings.rectangles
		if rectangles:
			boxes = [box(*rect) for rect in rectangles]
			merged = unary_union(boxes)
			minx = min(r[0] for r in rectangles)
			miny = min(r[1] for r in rectangles)
			maxx = max(r[2] for r in rectangles)
			maxy = max(r[3] for r in rectangles)
			if isinstance(merged, Polygon):
				geoms = [merged]
			elif isinstance(merged, MultiPolygon):
				geoms = merged.geoms
			else:
				geoms = []
			for geom in geoms:
				points = list(geom.exterior.coords)
				path = self.canvas.beginPath()
				path.moveTo(points[0][0], points[0][1])
				for x, y in points[1:]:
					path.lineTo(x, y)
				path.close()
				for hole in geom.interiors:
					hole_points = list(hole.coords)
					path.moveTo(hole_points[0][0], hole_points[0][1])
					for x, y in hole_points[1:]:
						path.lineTo(x, y)
					path.close()
				self.canvas.drawPath(path, fill=1, stroke=0)
		for x_min, y_min, x_max, y_max in self.shadings.segments():
			self.canvas.line(x_min, y_min, x_max, y_max)
		self.canvas.save()
		self.is_complete = True

	def get_pil(self):
		self.complete()
		page = PdfDocument(self.buffer).get_page(0)
		bitmap = page.render(fill_color=(255, 255, 255, 0)) if self.options.transparent else page.render()
		return bitmap.to_pil()

	def get_pdf(self):
		self.complete()
		return self.buffer.getvalue()

	def add_sign(self, ch, scale, x_scale, y_scale, rotate, mirror, rect, \
			extra=False, bracket=False, unselectable=False, x_as=None, y_as=None):
		x = self.mirror(rect.x, rect.w)
		mirror = self.mirrored ^ mirror
		x_px = self.em_to_px(x)
		y_px = self.em_to_px(rect.y + rect.h)
		fontsize = self.options.fontsize * scale
		fontcolor = self.color(bracket)
		meas = corrected_measurement(ch, fontsize, x_scale, y_scale, rotate, mirror, x_as, y_as, \
			measure_glyph_pdf_memo)
		self.canvas.saveState()
		self.canvas.setFont(HIERO_FONT_NAME, fontsize)
		self.canvas.setFillColor(fontcolor)
		y_diff = 0 if bracket else meas.y
		self.canvas.translate(x_px + meas.width_scaled/2 - meas.x, \
			(self.height() - y_px) + meas.height_scaled/2 - y_diff)
		self.canvas.scale(-x_scale if mirror else x_scale, y_scale)
		self.canvas.rotate(-rotate)
		self.canvas.drawString(-meas.width/2, -meas.height/2, ch)
		self.canvas.restoreState()
		
	def add_shading(self, rect):
		x = self.mirror(rect.x, rect.w)
		y = rect.y
		x_min = round(self.em_to_px(x))
		y_max = round(self.height() - self.em_to_px(y))
		x_max = round(self.em_to_px(x+rect.w))
		y_min = round(self.height() - self.em_to_px(y+rect.h))
		self.shadings.add_rectangle(x_min, y_min, x_max, y_max)

class PrintedSvg(PrintedAny):
	def __init__(self, w, h, w_accum, h_accum, options):
		super().__init__(w, h, w_accum, h_accum, options.rl(), options)
		self.draw = svgwrite.Drawing(size=(self.width(), self.height()))
		if not options.transparent:
			self.draw.add(self.draw.rect(insert=(0, 0), size=(self.width(), self.height()), fill='white'))

	def complete(self):
		if self.is_complete:
			return
		opacity = self.options.shadealpha / 255
		rectangles = self.shadings.rectangles
		if rectangles:
			boxes = [box(x_min, y_min, x_max, y_max) for x_min, y_min, x_max, y_max in rectangles]
			merged = unary_union(boxes)
			if isinstance(merged, Polygon):
				geoms = [merged]
			elif isinstance(merged, MultiPolygon):
				geoms = merged.geoms
			else:
				geoms = []
			for geom in geoms:
				points = list(geom.exterior.coords)
				self.draw.add(self.draw.polygon(points=points, fill=self.options.shadecolor, \
					fill_opacity=opacity, stroke_width=0))
		for x_min, y_min, x_max, y_max in self.shadings.segments():
			self.draw.add(self.draw.line(start=(x_min, y_min), end=(x_max, y_max),
				stroke=self.options.shadecolor, stroke_width=self.options.shadethickness, opacity=opacity))
		self.is_complete = True

	def get_svg(self):
		self.complete()
		return self.draw.tostring()

	def add_sign(self, ch, scale, x_scale, y_scale, rotate, mirror, rect, \
			extra=False, bracket=False, unselectable=False, x_as=None, y_as=None):
		x = self.mirror(rect.x, rect.w)
		mirror = self.mirrored ^ mirror
		x_px = round(self.em_to_px(x))
		y_px = round(self.em_to_px(rect.y + rect.h))
		fontsize = math.floor(self.options.fontsize * scale)
		fontcolor = self.color(bracket)
		meas = corrected_measurement(ch, fontsize, x_scale, y_scale, rotate, mirror, x_as, y_as, \
			measure_glyph_pdf_memo)
		x_trans = x_px + meas.width_scaled/2 - meas.x
		if bracket:
			y_trans = y_px - meas.height_scaled/2
		else:
			y_trans = y_px - meas.height_scaled/2 + meas.y
		rot = f'rotate({rotate})'
		t = f'translate({x_trans}, {y_trans}) '
		if mirror:
			trans=t + ' scale(-1,1) ' + rot
		else:
			trans=t + rot
		self.draw.add(self.draw.text(ch, \
			insert=(-meas.width/2, meas.height/2),
			transform=trans, fill=fontcolor, font_family=HIERO_FONT_NAME, font_size=fontsize))

	def add_shading(self, rect):
		x = self.mirror(rect.x, rect.w)
		y = rect.y
		x_min = round(self.em_to_px(x))
		y_min = round(self.em_to_px(y))
		x_max = round(self.em_to_px(x+rect.w))
		y_max = round(self.em_to_px(y+rect.h))
		self.shadings.add_rectangle(x_min, y_min, x_max, y_max)

class PrintedPil(PrintedAny):
	def __init__(self, w, h, w_accum, h_accum, options):
		super().__init__(w, h, w_accum, h_accum, options.rl(), options)
		dim = self.width(), self.height()
		if options.transparent:
			self.im = Image.new('RGBA', dim, (0, 0, 0, 0))
		else:
			self.im = Image.new('RGB', dim, 'white')
		self.draw = ImageDraw.Draw(self.im)

	def complete(self):
		if self.is_complete:
			return
		rectangles = self.shadings.rectangles
		lines = self.shadings.segments()
		if rectangles or lines:
			mask = Image.new('L', (self.width(), self.height()), 'black')
			mask_draw = ImageDraw.Draw(mask)
			for x_min, y_min, x_max, y_max in rectangles:
				mask_draw.rectangle([x_min, y_min, x_max, y_max], fill=self.options.shadealpha)
			for x_min, y_min, x_max, y_max in lines:
				mask_draw.line((x_min, y_min, x_max, y_max), fill=self.options.shadealpha, width=self.options.shadethickness)
			shade = Image.new('RGBA', (self.width(), self.height()), self.options.shadecolor)
			self.im.paste(shade, (0, 0), mask)
		self.is_complete = True

	def get_pil(self):
		self.complete()
		return self.im

	def add_sign(self, ch, scale, x_scale, y_scale, rotate, mirror, rect, \
			extra=False, bracket=False, unselectable=False, x_as=None, y_as=None):
		x = self.mirror(rect.x, rect.w)
		mirror = self.mirrored ^ mirror
		x_px = round(self.em_to_px(x))
		y_px = round(self.em_to_px(rect.y))
		w_px = max(1, round(self.em_to_px(rect.w)))
		h_px = max(1, round(self.em_to_px(rect.h)))
		fontsize = math.floor(self.options.fontsize * scale)
		fontcolor = self.color(bracket)
		font = get_measure_font_pil()
		bbox = font.getbbox(ch)
		metric_width = bbox[2] - bbox[0]
		width = max(1, metric_width)
		height = max(1, MEASURE_SIZE)
		width_scaled = max(1, round(x_scale * metric_width))
		height_scaled = max(1, round(y_scale * MEASURE_SIZE))
		im = Image.new('RGBA', (width, height), (255, 255, 255, 0))
		draw = ImageDraw.Draw(im)
		draw.text((0, 0), ch, fill=fontcolor, font=font)
		if x_scale != 1 or y_scale != 1:
			im = im.resize((width_scaled, height_scaled), resample=Image.LANCZOS)
		if rotate:
			im = im.rotate(-rotate, expand=True, resample=Image.BICUBIC, fillcolor=(0,0,0,0))
		if mirror:
			im = im.transpose(Image.FLIP_LEFT_RIGHT)
		if not bracket:
			copied = Image.new('RGBA', im.size, 'white')
			copied = Image.alpha_composite(copied, im)
			final_bbox = copied.convert('L').point(lambda x: 0 if x == 255 else 255, '1').getbbox()
			im = im.crop(final_bbox)
		im = im.resize((w_px, h_px), resample=Image.LANCZOS)
		self.im.paste(im, (x_px, y_px), im)

	def add_shading(self, rect):
		x = self.mirror(rect.x, rect.w)
		y = rect.y
		x_min = round(self.em_to_px(x))
		y_min = round(self.em_to_px(y))
		x_max = round(self.em_to_px(x+rect.w))
		y_max = round(self.em_to_px(y+rect.h))
		self.shadings.add_rectangle(x_min, y_min, x_max, y_max)

class PrintedPilWithoutExtras(PrintedPil):
	def __init__(self, options, w, h):
		super().__init__(w, h, 0, 0, options) 

	def add_sign(self, ch, scale, x_scale, y_scale, rotate, mirror, rect, \
			extra=False, bracket=False, unselectable=False, x_as=None, y_as=None):
		if not extra:
			super().add_sign(ch, scale, x_scale, y_scale, rotate, mirror, rect, \
				bracket=bracket, unselectable=unselectable, x_as=x_as, y_as=y_as)
	
	def add_shading(self, rect):
		pass

