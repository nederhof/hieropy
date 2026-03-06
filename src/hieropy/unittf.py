import math
import webcolors
import importlib.resources as resources
from fontTools.ttLib import TTFont
from fontTools.fontBuilder import FontBuilder
from fontTools.colorLib.builder import buildCOLR, buildCPAL
from fontTools.pens.ttGlyphPen import TTGlyphPen
from fontTools.pens.transformPen import TransformPen
from fontTools.pens.reverseContourPen import ReverseContourPen
from fontTools.feaLib import ast
from fontTools.feaLib.builder import addOpenTypeFeaturesFromString
from fontTools.misc.timeTools import timestampNow
from fontTools.misc.transform import Transform

from .options import Options
from .uniconstants import HIERO_FONT_NAME, HIERO_FONT_FILENAME

PUA = 0xF0000

def rotate_affine(angle_deg):
	rad = math.radians(angle_deg)
	return math.cos(rad), math.sin(rad), -math.sin(rad), math.cos(rad), 0, 0

def scale_affine(sx, sy):
	return sx, 0, 0, sy, 0, 0

def mirror_affine():
	return -1, 0, 0, 1, 0, 0

def translate_affine(dx, dy):
	return 1, 0, 0, 1, dx, dy

def id_affine():
	return translate_affine(0, 0)

def multiply_affines(aff1, aff2):
	xx1, xy1, yx1, yy1, dx1, dy1 = aff1
	xx2, xy2, yx2, yy2, dx2, dy2 = aff2
	return xx1*xx2 + xy1*yx2, xx1*xy2 + xy1*yy2, yx1*xx2 + yy1*yx2, yx1*xy2 + yy1*yy2, \
			dx1*xx2 + dy1*yx2 + dx2, dx1*xy2 + dy1*yy2 + dy2

def chain_affines(*affs):
	aff_out = id_affine()
	for aff in affs:
		aff_out = multiply_affines(aff, aff_out)
	return aff_out
	
def rectangular_glyph(upm, margin, thickness):
	x0 = margin
	y0 = margin
	x1 = upm-margin
	y1 = upm-margin
	pen = TTGlyphPen(None)
	pen.moveTo((x0, y0))
	pen.lineTo((x1, y0))
	pen.lineTo((x1, y1))
	pen.lineTo((x0, y1))
	pen.closePath()
	pen.moveTo((x0+thickness, y0+thickness))
	pen.lineTo((x0+thickness, y1-thickness))
	pen.lineTo((x1-thickness, y1-thickness))
	pen.lineTo((x1-thickness, y0+thickness))
	pen.closePath()
	return pen.glyph()

def make_substitution(syms0, syms1):
	str0 = ' '.join(syms0)
	str1 = ' '.join(syms1)
	return f'sub {str0} by {str1};\n'

def make_substitutions(subs):
	return ''.join(make_substitution(syms0, syms1) for syms0, syms1 in subs)

def color_name_to_palette(name, alpha):
	rgb = webcolors.name_to_rgb(name)
	return (rgb.red / 255.0, rgb.green / 255.0, rgb.blue / 255.0, alpha / 255.0)

def fresh_point(pua):
	point = PUA + pua['size']
	name = f'c{point:X}'
	pua['size'] += 1
	return point, name

def is_modifier(c):
	n = ord(c)
	return n == 0x13440 or 0x13447 <= n and n <= 0x13455 or 0xFE00 <= n and n <= 0xFE0F

def clustered_reorder(s, direction):
	if direction == 'hrl':
		clusters = []
		for c in s:
			if is_modifier(c) and len(clusters) > 0:
				clusters[-1].append(c)
			else:
				clusters.append([c])
		return [c for cluster in reversed(clusters) for c in cluster]
	else:
		return s

class UniFontBuilder:
	def __init__(self, direction='hlr', linesize=1.0, sep=0.08, 
				signcolor='black', bracketcolor='black', shadecolor='black', shadealpha=255,
				shadepattern='diagonal', shadedist=100, shadethickness=16,
				align='middle', separated=True, basename=HIERO_FONT_NAME, descent=0.0, gap=0.1):
		self.read_src_font()
		self.options = Options(direction=direction, linesize=linesize, fontsize=self.upm, \
				sep=sep, hmargin=0.0, vmargin=0.0, imagetype='ttf', transparent=True, \
				signcolor=signcolor, bracketcolor=bracketcolor, shadecolor=shadecolor, shadealpha=shadealpha, \
				shadepattern=shadepattern, shadedist=shadedist, shadethickness=shadethickness, \
				align=align, separated=separated)
		self.mapping_options = Options(direction=direction, linesize=linesize, fontsize=self.upm, \
				sep=sep, hmargin=0.0, vmargin=0.0, imagetype='ttf', transparent=True, \
				signcolor=signcolor, bracketcolor=bracketcolor, shadecolor=shadecolor, shadealpha=shadealpha, \
				shadepattern=shadepattern, shadedist=shadedist, shadethickness=shadethickness, \
				align=align, separated=False)
		self.basename = basename
		self.descent = int(round(descent * self.upm))
		self.ascent = int(round(self.upm * (linesize + sep - descent)))
		self.total_height = self.descent + self.ascent
		self.gap = int(round(gap * self.upm))
		self.str_to_formatting = {}

	def read_src_font(self):
		with resources.files('hieropy.resources').joinpath(HIERO_FONT_FILENAME).open('rb') as f:
			self.src_font = TTFont(f)
			self.src_cmap = self.src_font.getBestCmap()
			self.src_glyf = self.src_font['glyf']
			self.src_hmtx = self.src_font['hmtx']
			self.src_version = round(self.src_font['head'].fontRevision, 2)
			self.upm = self.src_font['head'].unitsPerEm

	def add(self, fragment):
		if not fragment:
			return
		printed = fragment.print(self.options)
		if self.options.separated:
			for p in printed:
				self.str_to_formatting[p.chars] = p
		else:
			self.str_to_formatting[printed.chars] = printed

	def add_mapping(self, chars, fragment):
		self.str_to_formatting[chars] = fragment.print(self.mapping_options)

	def make_font(self, path):
		notdef_margin = 50
		notdef_thickness = 50
		notdef_glyph = rectangular_glyph(self.upm, notdef_margin, notdef_thickness)

		glyph_order = ['.notdef']
		cmap = {}
		glyf = {'.notdef': notdef_glyph}
		hmtx = {'.notdef': (self.upm, notdef_margin)}
		vmtx = {'.notdef': (self.upm, notdef_margin)}

		pua = {'size': 0}
			
		strings = sorted(self.str_to_formatting.keys(), key=len, reverse=True)
		code_chars = set()
		glyph_chars = set()
		reverse_chars = set()
		for s in strings:
			for ch in s:
				code_chars.add(ch)
			formatting = self.str_to_formatting[s]
			glyphs = formatting.glyphs
			for ch, color, aff, _, _, mirror in glyphs:
				if mirror:
					reverse_chars.add(ch)
				else:
					glyph_chars.add(ch)

		code_to_name = self.make_code_chars(glyph_order, cmap, glyf, hmtx, vmtx, code_chars)
		glyph_to_name = self.make_glyph_chars(glyph_order, cmap, glyf, hmtx, vmtx, pua, glyph_chars)
		reverse_to_name = self.make_glyph_chars(glyph_order, cmap, glyf, hmtx, vmtx, pua, reverse_chars,reverse=True)
		ch_names = set(glyph_to_name.values()) | set(reverse_to_name.values())
		substitutions, string_to_name, string_to_shade, string_to_bracket = \
			self.make_composite_chars(glyph_order, cmap, glyf, hmtx, vmtx, pua, \
			code_to_name, glyph_to_name, reverse_to_name, ch_names, strings)

		fb = self.make_font_init(glyph_order, cmap, glyf, hmtx, vmtx)

		self.make_font_properties(fb)
		self.make_font_colors(fb, string_to_name, string_to_shade, string_to_bracket)

		tt = self.make_font_features(fb, substitutions)
		tt.save(path)

	def make_code_chars(self, glyph_order, cmap, glyf, hmtx, vmtx, code_chars):
		code_to_name = {}
		for ch in sorted(code_chars):
			point = ord(ch)
			name = self.src_cmap.get(point) or f'u{point:05X}'
			code_to_name[ch] = name
			glyph_order.append(name)
			cmap[point] = name
			glyf[name] = TTGlyphPen(None).glyph()
			hmtx[name] = (0,0)
			vmtx[name] = (0,0)
		return code_to_name

	def make_glyph_chars(self, glyph_order, cmap, glyf, hmtx, vmtx, pua, glyph_chars, reverse=False):
		glyph_to_name = {}
		for ch in sorted(glyph_chars):
			point, name = fresh_point(pua)
			glyph_to_name[ch] = name
			glyph_order.append(name)
			cmap[point] = name
			if reverse:
				glyf[name] = reverse_winding_direction(self.src_glyf[self.src_cmap.get(ord(ch))], self.src_glyf)
			else:
				glyf[name] = self.src_glyf[self.src_cmap.get(ord(ch))]
			glyf[name].recalcBounds(glyf)
			hmtx[name] = self.src_hmtx[self.src_cmap.get(ord(ch))]
			vmtx[name] = (self.upm, 0)
		return glyph_to_name

	def make_composite_chars(self, glyph_order, cmap, glyf, hmtx, vmtx, pua, \
			code_to_name, glyph_to_name, reverse_to_name, ch_names, strings):
		substitutions = []
		string_to_name = {}
		string_to_shade = {}
		string_to_bracket = {}
		for s in strings:
			formatting = self.str_to_formatting[s]
			w = formatting.w
			h = formatting.h
			glyphs = formatting.glyphs
			segments = formatting.shadings.segments()
			polygons = formatting.shadings.polygons()
			point, name = fresh_point(pua)
			string_to_name[s] = name
			glyph_order.append(name)
			cmap[point] = name
			descent_affine = translate_affine(0, -self.descent)
			pen = TTGlyphPen(ch_names)
			normal_glyphs = [(ch, aff, x, y, m) for ch, color, aff, x, y, m in glyphs if color == self.options.signcolor]
			bracket_glyphs = [(ch, aff, x, y, m) for ch, color, aff, x, y, m in glyphs if color != self.options.signcolor]
			width = int(round(w * self.upm))
			height = int(round(h * self.upm))
			lsb, tsb = width, height
			for ch, aff, x, y, mirror in normal_glyphs:
				transform = multiply_affines(aff, descent_affine)
				if mirror:
					pen.addComponent(reverse_to_name[ch], transform)
				else:
					pen.addComponent(glyph_to_name[ch], transform)
			if len(segments) > 0:
				shading_name, _, shading_tsb = self.make_diagonal_char(glyph_order, cmap, glyf, hmtx, vmtx, pua, \
						ch_names, width, height, segments)
				if self.options.shadecolor == self.options.signcolor and self.options.shadealpha == 255:
					pen.addComponent(shading_name, Transform())
				else:
					string_to_shade[s] = shading_name
				tsb = min(tsb, shading_tsb)
			if len(polygons) > 0:
				shading_name, _, shading_tsb = self.make_polygon_char(glyph_order, cmap, glyf, hmtx, vmtx, pua, \
						ch_names, width, height, polygons)
				if self.options.shadecolor == self.options.signcolor and self.options.shadealpha == 255:
					pen.addComponent(shading_name, Transform())
				else:
					string_to_shade[s] = shading_name
				tsb = min(tsb, shading_tsb)
			if len(bracket_glyphs) > 0:
				bracket_name, _, bracket_tsb = self.make_bracket_char(glyph_order, cmap, glyf, hmtx, vmtx, pua, \
						ch_names, glyph_to_name, reverse_to_name, width, height, bracket_glyphs)
				if self.options.bracketcolor == self.options.signcolor:
					pen.addComponent(bracket_name, Transform())
				else:
					string_to_bracket[s] = bracket_name
				tsb = min(tsb, bracket_tsb)
			glyf[name] = pen.glyph()
			glyf[name].recalcBounds(glyf)
			if glyf[name].isComposite():
				lsb = glyf[name].xMin
				tsb = min(tsb, height - glyf[name].yMax)
			hmtx[name] = (width, lsb)
			vmtx[name] = (height, tsb)
			s_ordered = clustered_reorder(s, self.options.direction)
			names = [code_to_name[ch] for ch in s_ordered]
			substitutions.append((names, [name]))
		return substitutions, string_to_name, string_to_shade, string_to_bracket

	def make_diagonal_char(self, glyph_order, cmap, glyf, hmtx, vmtx, pua, ch_names, w, h, segments):
		point, name = fresh_point(pua)
		glyph_order.append(name)
		cmap[point] = name
		pen = TTGlyphPen(ch_names)
		d = int(round(math.sqrt(2) * self.options.shadethickness))
		for x_min, y_min, x_max, y_max in segments:
			if x_max - x_min < 0:
				continue
			elif x_max - x_min <= d:
				if x_min - d < 0 and y_max - d < 0:
					pen.moveTo((x_min, y_min-self.descent + d))
					pen.lineTo((x_max + d, y_max-self.descent))
					pen.lineTo((x_min, y_max-self.descent))
				elif x_min + d > w and y_max + d > h:
					pen.moveTo((x_max, y_max-self.descent - d))
					pen.lineTo((x_min - d, y_min-self.descent))
					pen.lineTo((x_max, y_min-self.descent))
				else:
					continue
			else:
				if y_min + d <= h:
					pen.moveTo((x_min, y_min-self.descent - d))
					pen.lineTo((x_min, y_min-self.descent + d))
				else:
					if x_min - d >= 0:
						pen.moveTo((x_min - d, y_min-self.descent))
						pen.lineTo((x_min + d, y_min-self.descent))
					else:
						pen.moveTo((x_min, y_min-self.descent - d))
						pen.lineTo((x_min, y_min-self.descent))
						pen.lineTo((x_min + d, y_min-self.descent))
				if y_max - d >= 0:
					pen.lineTo((x_max, y_max-self.descent + d))
					pen.lineTo((x_max, y_max-self.descent - d))
				else:
					if x_max + d <= w:
						pen.lineTo((x_max + d, y_max-self.descent))
						pen.lineTo((x_max - d, y_max-self.descent))
					else:
						pen.lineTo((x_max, y_max-self.descent + d))
						pen.lineTo((x_max, y_max-self.descent))
						pen.lineTo((x_max - d, y_max-self.descent))
			pen.closePath()
		glyf[name] = pen.glyph()
		glyf[name].recalcBounds(glyf)
		lsb = glyf[name].xMin
		tsb = h - glyf[name].yMax
		hmtx[name] = (w, lsb)
		vmtx[name] = (h, tsb)
		ch_names.add(name)
		return name, lsb, tsb

	def make_polygon_char(self, glyph_order, cmap, glyf, hmtx, vmtx, pua, ch_names, w, h, polygons):
		point, name = fresh_point(pua)
		glyph_order.append(name)
		cmap[point] = name
		pen = TTGlyphPen(ch_names)
		for exterior, gaps in polygons:
			for i, p in enumerate(exterior):
				if i == 0:
					pen.moveTo((p[0], p[1]-self.descent))
				else:
					pen.lineTo((p[0], p[1]-self.descent))
			pen.closePath()
			for gap in gaps:
				for i, p in enumerate(gap):
					if i == 0:
						pen.moveTo((p[0], p[1]-self.descent))
					else:
						pen.lineTo((p[0], p[1]-self.descent))
				pen.closePath()
		glyf[name] = pen.glyph()
		glyf[name].recalcBounds(glyf)
		lsb = glyf[name].xMin
		tsb = h - glyf[name].yMax
		hmtx[name] = (w, lsb)
		vmtx[name] = (h, tsb)
		ch_names.add(name)
		return name, lsb, tsb
		
	def make_bracket_char(self, glyph_order, cmap, glyf, hmtx, vmtx, pua, \
				ch_names, glyph_to_name, reverse_to_name, w, h, bracket_glyphs):
		descent_affine = translate_affine(0, -self.descent)
		point, name = fresh_point(pua)
		glyph_order.append(name)
		cmap[point] = name
		pen = TTGlyphPen(ch_names)
		for ch, aff, x, y, mirror in bracket_glyphs:
			transform = multiply_affines(aff, descent_affine)
			if mirror:
				pen.addComponent(reverse_to_name[ch], transform)
			else:
				pen.addComponent(glyph_to_name[ch], transform)
		glyf[name] = pen.glyph()
		glyf[name].recalcBounds(glyf)
		lsb = glyf[name].xMin
		tsb = h - glyf[name].yMax
		hmtx[name] = (w, lsb)
		vmtx[name] = (h, tsb)
		return name, lsb, tsb

	def make_font_init(self, glyph_order, cmap, glyf, hmtx, vmtx):
		fb = FontBuilder(self.upm, isTTF=True)
		fb.setupGlyphOrder(glyph_order)
		fb.setupCharacterMap(cmap)
		fb.setupGlyf(glyf)
		fb.setupHorizontalMetrics(hmtx)
		fb.setupVerticalMetrics(vmtx)
		return fb

	def make_font_properties(self, fb):
		d = self.options.direction
		family_name = self.basename + d[0].upper() + d[1:]
		style_name = 'Regular'
		full_name = f'{family_name} {style_name}'
		ps_name = f'{family_name}-{style_name}'
		fb.setupNameTable({
				'familyName': family_name,
				'styleName': style_name,
				'fullName': full_name,
				'uniqueFontIdentifier': ps_name,
				'psName': ps_name,
				'version': f'Version {self.src_version}',
				'manufacturer': 'hieropy',
			})
		fb.setupHorizontalHeader(ascent=self.ascent, descent=-self.descent, lineGap=self.gap)
		fb.setupVerticalHeader(ascent=self.ascent, descent=-self.descent)
		fb.setupOS2(sTypoAscender=self.ascent, sTypoDescender=-self.descent,
				TypoLineGap=self.gap,
				usWinAscent=self.ascent, usWinDescent=self.descent)
		fb.setupPost()
		fb.setupHead()
		fb.font['head'].created = timestampNow()
		fb.font['head'].modified = timestampNow()

	def make_font_colors(self, fb, string_to_name, string_to_shade, string_to_bracket):
		if len(string_to_shade) > 0 or len(string_to_bracket) > 0:
			palette = [ color_name_to_palette(self.options.signcolor, 255),
				color_name_to_palette(self.options.bracketcolor, 255), 
				color_name_to_palette(self.options.shadecolor, self.options.shadealpha) ]
			fb.font['CPAL'] = buildCPAL([palette])
			layers = {}
			for s, name in string_to_name.items():
				layers[name] = [ (name, 0) ]
				if s in string_to_bracket:
					layers[name].append((string_to_bracket[s], 1))
				if s in string_to_shade:
					layers[name].append((string_to_shade[s], 2))
			fb.font['COLR'] = buildCOLR(layers)

	def make_font_features(self, fb, substitutions):
		tt = fb.font
		feats_pref = 'languagesystem DFLT dflt;\n'
		feat_pref = 'feature liga {\n'
		feat_suf = '} liga;'
		feature_text = feats_pref + feat_pref + make_substitutions(substitutions) + feat_suf
		addOpenTypeFeaturesFromString(tt, feature_text)
		return tt

def reverse_winding_direction(glyph, glyphSet):
	if glyph.isComposite():
		glyph.expand(glyphSet)
	pen = TTGlyphPen(glyphSet)
	reverse_pen = ReverseContourPen(pen)
	glyph.draw(reverse_pen, glyphSet)
	return pen.glyph()
