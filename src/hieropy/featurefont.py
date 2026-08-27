import io
import math
import random
import webcolors
import importlib.resources as resources
from collections import defaultdict
from fontTools.ttLib import TTFont, newTable
from fontTools.ttLib.tables import otTables
from fontTools.ttLib.tables.otBase import OTLOffsetOverflowError
from fontTools.ttLib.tables._c_m_a_p import CmapSubtable
from fontTools.fontBuilder import FontBuilder
from fontTools.feaLib.builder import Builder
from fontTools.feaLib.parser import Parser
from fontTools.colorLib.builder import buildCOLR, buildCPAL
from fontTools.pens.ttGlyphPen import TTGlyphPen
from fontTools.pens.transformPen import TransformPen
from fontTools.pens.reverseContourPen import ReverseContourPen
from fontTools.feaLib import ast
from fontTools.feaLib.builder import addOpenTypeFeaturesFromString
from fontTools.misc.timeTools import timestampNow
from fontTools.misc.transform import Transform

from .uniconstants import HIERO_FONT_FILENAME
from .affine import *

DEBUG_FONT_FILENAME = 'OpenSans-Regular.ttf'

BOX_MARGIN = 50
BOX_THICKNESS = 50

# glyph class values
UNDEF = 0
BASE = 1
LIGATURE = 2
MARK = 3

PUA = 0xF0000

def rectangular_pen(upm, margin, thickness):
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
	return pen

def rectangular_glyph(upm, margin, thickness):
	return rectangular_pen(upm, margin, thickness).glyph()

def fresh_point(pua):
	point = PUA + pua['size']
	short_name = hex(point)[-4:]
	pua['size'] += 1
	return point, f'p{point & 0xFFFF:04X}'

def color_alpha_to_palette(color, alpha):
	rgb = webcolors.name_to_rgb(color)
	return (rgb.red / 255.0, rgb.green / 255.0, rgb.blue / 255.0, alpha / 255.0)

# GSUB type 1, 2, 4
def simple_sub_rule(target, replace):
	return ' '.join(['\tsub'] + target + ['by'] + replace) + ';'

# GSUB type 6, 8 (with replacement and one input)
def context_sub_rule(before, target, after, replace, reverse=False):
	cmd = '\trsub' if reverse else '\tsub'
	return ' '.join([cmd] + before + [f'{target}\''] + after + ['by'] + [replace]) + ';'

# GSUB type 6 (with lookups)
def chain_sub_rule(before, targets, after):
	def chain_target(target, lookups):
		return ' '.join([f'{target}\''] + [f'lookup {lookup}' for lookup in lookups])
	cmd = '\tsub'
	target_str = ' '.join([chain_target(target, lookups) for (target, lookups) in targets])
	return ' '.join([cmd] + before + [target_str] + after) + ';'

# GSUB type 6, 8 (ignore)
def ignore_sub_rule(before, targets, after, reverse=False):
	cmd = '\tignore rsub' if reverse else '\tignore sub'
	target_str = ' '.join(f'{target}\'' for target in targets)
	return ' '.join([cmd] + before + [target_str] + after) + ';'

# GPOS type 1
def pos_rule1(glyph, x_pos, y_pos, x_adv, y_adv):
	value = f'<{x_pos} {y_pos} {x_adv} {y_adv}>'
	return f'\tpos {glyph} {value};'

# GPOS type 2
def pos_rule2(glyph1, glyph2, x_pos, y_pos, x_adv, y_adv):
	value1 = f'<{0} {0} {0} {0}>'
	value2 = f'<{x_pos} {y_pos} {x_adv} {y_adv}>'
	return f'\tpos {glyph1} {value1} {glyph2} {value2};'

# GPOS type 3
def cursive_pos_rule(glyph, x1, y1, x2, y2):
	anchor_entry = f'<anchor {x1} {y1}>'
	anchor_exit = f'<anchor {x2} {y2}>'
	return f'\tpos cursive {glyph} {anchor_entry} {anchor_exit}>;'

# GPOS type 4
def base_pos_rule(glyph1, glyph2, x, y):
	anchor = f'<anchor {x} {y}>'
	return f'\tpos base {glyph1} {anchor} mark {glyph2};'

# GPOS type 6
def mark_pos_rule(glyph1, glyph2, x, y):
	anchor = f'<anchor {x} {y}>'
	return f'\tpos mark {glyph1} {anchor} mark {glyph2};'

# GPOS type 8
def chain_pos_rule(before, target, lookup):
	b = ' '.join(before)
	return f'\tpos {b} {target}\' lookup {lookup}'

# flags:
# IgnoreBaseGlyphs
# IgnoreLigatures
# IgnoreMarks
# UseMarkFilteringSet @class
def lookup(name, rules, flags=None):
	f = ' '.join(flags) if flags else '0'
	flag = f'\tlookupflag {f};\n'
	body = flag + '\n'.join(rules)
	return f'lookup {name} useExtension {{\n{body}\n}} {name};\n\n'

def feature(tag, lookups, script='DFLT', language='dflt'):
	body = f'\tscript {script};\n\tlanguage {language};\n' + '\n'.join(f'\tlookup {lookup};' for lookup in lookups)
	return f'feature {tag} {{\n{body}\n}} {tag};\n\n'

def named_class(name, glyphs):
	glyphs_str = ' '.join(glyphs)
	return f'{name} = [{glyphs_str}];\n'

def named_markclass(name, glyphs, x=0, y=0):
	glyphs_str = ' '.join(glyphs)
	return f'markClass [{glyphs_str}] <anchor {x} {y}> {name};\n'

class FeatureFontBuilder:
	def __init__(self, font_name, sep, descent, gap):
		self.font_name = font_name
		self.read_src_font()
		self.descent = int(round(descent * self.src_upm))
		self.ascent = int(round(self.src_upm * (1 + sep - descent)))
		self.total_height = self.descent + self.ascent
		self.gap = int(round(gap * self.src_upm))
		self.ch_names = set()
		self.pua = {'size': 0}
		self.uvsDict = {}
		self.make_empty_font()
		self.preamble_text = ''
		self.feature_text = ''
		self.lookups = []
		self.lookup_to_feature = {}
		# self.feature_to_lookups = defaultdict(list)
		self.debug_font = None

	def read_src_font(self):
		with resources.files('hieropy.resources').joinpath(HIERO_FONT_FILENAME).open('rb') as f:
			self.src_font = TTFont(f)
			self.src_cmap = self.src_font.getBestCmap()
			self.src_glyf = self.src_font['glyf']
			self.src_hmtx = self.src_font['hmtx']
			self.src_version = round(self.src_font['head'].fontRevision, 2)
			self.src_upm = self.src_font['head'].unitsPerEm

	def read_debug_font(self):
		if self.debug_font:
			return
		with resources.files('hieropy.resources').joinpath(DEBUG_FONT_FILENAME).open('rb') as f:
			self.debug_font = TTFont(f)
			self.debug_cmap = self.debug_font.getBestCmap()
			self.debug_glyf = self.debug_font['glyf']
			self.debug_hmtx = self.debug_font['hmtx']
			self.debug_upm = self.debug_font['head'].unitsPerEm

	def make_empty_font(self):
		notdef_glyph = rectangular_glyph(self.src_upm, BOX_MARGIN, BOX_THICKNESS)

		self.glyph_order = ['.notdef']
		self.cmap = {}
		self.glyf = {'.notdef': notdef_glyph}
		self.hmtx = {'.notdef': (self.src_upm, BOX_MARGIN)}
		self.vmtx = {'.notdef': (self.src_upm, BOX_MARGIN)}
		self.color_alpha = {}
		self.class_defs = {}

	def ch_name(self, ch):
		return self.src_cmap[ord(ch)]

	def copy_glyph(self, ch, color='black', alpha=255):
		point = ord(ch)
		name = self.src_cmap[point]
		self.glyph_order.append(name)
		self.cmap[point] = name
		self.glyf[name] = self.src_glyf[name]
		w = self.glyf[name].xMax - self.glyf[name].xMin
		h = self.glyf[name].yMax - self.glyf[name].yMin
		self.hmtx[name] = self.src_hmtx[name]
		self.vmtx[name] = (self.src_upm, 0)
		self.color_alpha[name] = (color, alpha)
		self.ch_names.add(name)
		self.class_defs[name] = MARK
		return name, w, h

	def copy_glyph_scale(self, ch, factor, color='black', alpha=255):
		point = ord(ch)
		name = self.src_cmap[point]
		pen = TTGlyphPen(None)
		tpen = TransformPen(pen, (factor, 0, 0, factor, 0, 0))
		self.src_glyf[name].draw(tpen, self.src_glyf)
		self.glyph_order.append(name)
		self.cmap[point] = name
		self.glyf[name] = pen.glyph()
		self.glyf[name].recalcBounds(self.glyf)
		w = self.glyf[name].xMax - self.glyf[name].xMin
		h = self.glyf[name].yMax - self.glyf[name].yMin
		self.hmtx[name] = self.src_hmtx[name]
		self.vmtx[name] = (self.src_upm, 0)
		self.color_alpha[name] = (color, alpha)
		self.ch_names.add(name)
		self.class_defs[name] = MARK
		return name, w, h

	def copy_control(self, ch):
		point = ord(ch)
		name = self.src_cmap[point]
		self.glyph_order.append(name)
		self.cmap[point] = name
		self.glyf[name] = TTGlyphPen(self.glyf).glyph()
		self.hmtx[name] = (0, 0)
		self.vmtx[name] = (0, 0)
		self.color_alpha[name] = ('black', 255)
		self.ch_names.add(name)
		self.class_defs[name] = MARK
		return name

	def copy_base(self, ch):
		point = ord(ch)
		point_base, _ = fresh_point(self.pua)
		name = self.src_cmap[point]
		name_base = name + '_base'
		self.glyph_order.append(name_base)
		self.cmap[point_base] = name_base
		self.glyf[name_base] = self.src_glyf[name]
		self.hmtx[name_base] = self.src_hmtx[name]
		self.vmtx[name_base] = (self.src_upm, 0)
		self.color_alpha[name] = ('black', 255)
		self.ch_names.add(name_base)
		self.class_defs[name_base] = BASE
		return name_base

	def add_aux(self, name=None, x_advance=0, y_advance=0, cls=MARK):
		point, short_name = fresh_point(self.pua)
		name = name or short_name
		self.glyph_order.append(name)
		self.cmap[point] = name
		self.glyf[name] = TTGlyphPen(self.glyf).glyph()
		self.hmtx[name] = (x_advance, 0)
		self.vmtx[name] = (y_advance, 0)
		self.color_alpha[name] = ('black', 255)
		self.ch_names.add(name)
		self.class_defs[name] = cls
		return name

	def add_aux_base(self, name, text1, text2):
		self.read_debug_font()
		point, _ = fresh_point(self.pua)
		name_base = name + '_base'
		self.glyph_order.append(name_base)
		self.cmap[point] = name_base
		self.glyf[name_base] = self.debug_composition(BOX_MARGIN, BOX_THICKNESS, text1, text2)
		self.hmtx[name_base] = (self.src_upm, BOX_MARGIN)
		self.vmtx[name_base] = (self.src_upm, 0)
		self.color_alpha[name] = ('black', 255)
		self.ch_names.add(name_base)
		self.class_defs[name_base] = BASE
		return name_base

	def debug_composition(self, margin, thickness, text1, text2):
		for ch in text1 + text2:
			self.copy_debug_glyph(ch)
		pen = TTGlyphPen(self.glyf)
		pen.addComponent('.notdef', Transform())
		scale = 1 / 5.5
		widths1 = [self.ch_to_hmtx(ch)[0] for ch in text1]
		widths2 = [self.ch_to_hmtx(ch)[0] for ch in text2]
		w1 = sum(widths1)
		w2 = sum(widths2)
		w1_scaled = w1 * scale
		w2_scaled = w2 * scale
		margin_1 = (self.src_upm - w1_scaled) / 2
		margin_2 = (self.src_upm - w2_scaled) / 2
		x = margin_1
		y = self.src_upm - BOX_MARGIN - BOX_THICKNESS - self.debug_upm * scale
		for i, ch in enumerate(text1):
			name = self.debug_cmap[ord(ch)]
			t = Transform().translate(x, y).scale(scale, scale)
			x += widths1[i] * scale
			pen.addComponent(name, t)
		x = margin_2
		y = 3 * BOX_MARGIN + BOX_THICKNESS
		for i, ch in enumerate(text2):
			name = self.debug_cmap[ord(ch)]
			t = Transform().translate(x, y).scale(scale, scale)
			x += widths2[i] * scale
			pen.addComponent(name, t)
		return pen.glyph()
	
	def copy_debug_glyph(self, ch):
		point = ord(ch)
		name = self.debug_cmap[point]
		if name in self.ch_names:
			return
		self.glyph_order.append(name)
		self.cmap[point] = name
		self.glyf[name] = self.debug_glyf[name]
		self.hmtx[name] = self.debug_hmtx[name]
		self.vmtx[name] = (self.src_upm, 0)
		self.color_alpha[name] = ('black', 255)
		self.ch_names.add(name)
		self.class_defs[name] = BASE
		return name

	def add_transform(self, source_name, factor, rotate, mirror, shift=True, color='black', alpha=255):
		point, name = fresh_point(self.pua)
		transform = chain_affines(\
			scale_affine(-factor if mirror else factor, factor), \
			rotate_affine(-rotate)) 
		pen = TTGlyphPen(self.glyph_order)
		pen.addComponent(source_name, transform)
		self.glyf[name] = pen.glyph()
		self.glyf[name].recalcBounds(self.glyf)
		if shift:
			dx = -self.glyf[name].xMin
			dy = -self.glyf[name].yMin
		else:
			dx = 0
			dy = 0
		w = self.glyf[name].xMax - self.glyf[name].xMin
		h = self.glyf[name].yMax - self.glyf[name].yMin
		transform_norm = chain_affines(\
			translate_affine(dx, dy),
			scale_affine(-factor if mirror else factor, factor), \
			rotate_affine(-rotate)) 
		pen = TTGlyphPen(self.glyph_order)
		pen.addComponent(source_name, transform_norm)
		self.glyph_order.append(name)
		self.cmap[point] = name
		self.glyf[name] = pen.glyph()
		self.hmtx[name] = (0, 0)
		self.vmtx[name] = (0, 0)
		self.color_alpha[name] = (color, alpha)
		self.ch_names.add(name)
		self.class_defs[name] = MARK
		return name, w, h

	def add_copy(self, source_name, color='black', alpha=255):
		point, name = fresh_point(self.pua)
		pen = TTGlyphPen(self.glyph_order)
		pen.addComponent(source_name, Transform())
		self.glyph_order.append(name)
		self.cmap[point] = name
		self.glyf[name] = pen.glyph()
		self.glyf[name].recalcBounds(self.glyf)
		w = self.glyf[name].xMax - self.glyf[name].xMin
		h = self.glyf[name].yMax - self.glyf[name].yMin
		self.hmtx[name] = (0, 0)
		self.vmtx[name] = (0, 0)
		self.color_alpha[name] = (color, alpha)
		self.ch_names.add(name)
		self.class_defs[name] = MARK
		return name, w, h

	def add_shade_diagonal(self, w, h, resolution, name=None, ch=None, color='black', alpha=255):
		if ch:
			point = ord(ch)
			name = self.src_cmap[point]
		else:
			point, short_name = fresh_point(self.pua)
			name = name or short_name
		pen = TTGlyphPen(None)
		d = math.ceil(resolution / 4)
		for y in range(0, h, resolution):
			if y == 0:
				pen.moveTo((d, 0))
				pen.lineTo((0, 0))
				pen.lineTo((0, d))
			else:
				pen.moveTo((0, y - d))
				pen.lineTo((0, y + d))
			if h-y == w:
				pen.lineTo((w - d, h))
				pen.lineTo((w, h))
				pen.lineTo((w, h - d))
			elif h-y < w:
				pen.lineTo((h-y - d, h))
				pen.lineTo((h-y + d, h))
			else:
				pen.lineTo((w, w+y + d))
				pen.lineTo((w, w+y - d))
			pen.closePath()
		for x in range(resolution, w, resolution):
			pen.moveTo((x + d, 0))
			pen.lineTo((x - d, 0))
			if w-x == h:
				pen.lineTo((w - d, h))
				pen.lineTo((w, h))
				pen.lineTo((w, h - d))
			elif w-x < h:
				pen.lineTo((w, w-x + d))
				pen.lineTo((w, w-x - d))
			else:
				pen.lineTo((h+x - d, h))
				pen.lineTo((h+x + d, h))
			pen.closePath()
		pen.moveTo((0, h-d))
		pen.lineTo((0, h))
		pen.lineTo((d, h))
		pen.closePath()
		pen.moveTo((w-d, 0))
		pen.lineTo((w, d))
		pen.lineTo((w, 0))
		pen.closePath()

		self.glyph_order.append(name)
		self.cmap[point] = name
		self.glyf[name] = pen.glyph()
		self.hmtx[name] = (0, 0)
		self.vmtx[name] = (0, 0)
		self.color_alpha[name] = (color, alpha)
		self.ch_names.add(name)
		self.class_defs[name] = MARK
		return name

	def add_shade_uniform(self, w, h, name=None, ch=None, color='black', alpha=255):
		if ch:
			point = ord(ch)
			name = self.src_cmap[point]
		else:
			point, short_name = fresh_point(self.pua)
			name = name or short_name
		pen = TTGlyphPen(None)
		pen.moveTo((0, 0))
		pen.lineTo((0, h))
		pen.lineTo((w, h))
		pen.lineTo((w, 0))
		pen.closePath()

		self.glyph_order.append(name)
		self.cmap[point] = name
		self.glyf[name] = pen.glyph()
		self.hmtx[name] = (0, 0)
		self.vmtx[name] = (0, 0)
		self.color_alpha[name] = (color, alpha)
		self.ch_names.add(name)
		self.class_defs[name] = MARK
		return name

	def add_shade_random(self, w, h, resolution, name=None, ch=None, color='black', alpha=255):
		if ch:
			point = ord(ch)
			name = self.src_cmap[point]
		else:
			point, short_name = fresh_point(self.pua)
			name = name or short_name
		pen = TTGlyphPen(None)
		for x in range(-resolution, w+resolution, resolution):
			for y in range(-resolution, h+resolution, resolution):
				if random.random() < 0.3:
					x_from = max(x, 0)
					x_to = min(x + resolution, w)
					y_from = max(y, 0)
					y_to = min(y + resolution, w)
					if x_to - x_from > 0 and y_to - y_from > 0:
						pen.moveTo((x_from, y_from))
						pen.lineTo((x_from, y_to))
						pen.lineTo((x_to, y_to))
						pen.lineTo((x_to, y_from))
						pen.closePath()
		pen.moveTo((0, 0))
		pen.lineTo((0, 1))
		pen.lineTo((1, 1))
		pen.lineTo((0, 1))
		pen.closePath()
		pen.moveTo((w-1, h-1))
		pen.lineTo((w-1, h))
		pen.lineTo((w, h))
		pen.lineTo((w, h-1))
		pen.closePath()

		self.glyph_order.append(name)
		self.cmap[point] = name
		self.glyf[name] = pen.glyph()
		self.hmtx[name] = (0, 0)
		self.vmtx[name] = (0, 0)
		self.color_alpha[name] = (color, alpha)
		self.ch_names.add(name)
		self.class_defs[name] = MARK
		return name

	def add_outline_p(self, w, h, thickness, name=None, color='black', alpha=255):
		point, short_name = fresh_point(self.pua)
		name = name or short_name
		pen = TTGlyphPen(None)
		pen.moveTo((0, h-thickness))
		pen.lineTo((0, h))
		pen.lineTo((w, h))
		pen.lineTo((w, h-thickness))
		pen.closePath()
		pen.moveTo((0, 0))
		pen.lineTo((0, thickness))
		pen.lineTo((w, thickness))
		pen.lineTo((w, 0))
		pen.closePath()

		self.glyph_order.append(name)
		self.cmap[point] = name
		self.glyf[name] = pen.glyph()
		self.hmtx[name] = (0, 0)
		self.vmtx[name] = (0, 0)
		self.color_alpha[name] = (color, alpha)
		self.ch_names.add(name)
		self.class_defs[name] = MARK
		return name

	def add_outline_p_rot(self, w, h, thickness, name=None, color='black', alpha=255):
		point, short_name = fresh_point(self.pua)
		name = name or short_name
		pen = TTGlyphPen(None)
		pen.moveTo((0, 0))
		pen.lineTo((0, h))
		pen.lineTo((thickness, h))
		pen.lineTo((thickness, 0))
		pen.closePath()
		pen.moveTo((w-thickness, 0))
		pen.lineTo((w-thickness, h))
		pen.lineTo((w, h))
		pen.lineTo((w, 0))
		pen.closePath()

		self.glyph_order.append(name)
		self.cmap[point] = name
		self.glyf[name] = pen.glyph()
		self.hmtx[name] = (0, 0)
		self.vmtx[name] = (0, 0)
		self.color_alpha[name] = (color, alpha)
		self.ch_names.add(name)
		self.class_defs[name] = MARK
		return name

	def add_outline_w(self, w, h, thickness, brick_thickness, brick_length, brick_interval, 
				name=None, color='black', alpha=255):
		point, short_name = fresh_point(self.pua)
		name = name or short_name
		pen = TTGlyphPen(None)
		pen.moveTo((0, h-thickness-brick_thickness))
		pen.lineTo((0, h-brick_thickness))
		pen.lineTo((w, h-brick_thickness))
		pen.lineTo((w, h-thickness-brick_thickness))
		pen.closePath()
		pen.moveTo((0, brick_thickness))
		pen.lineTo((0, thickness+brick_thickness))
		pen.lineTo((w, thickness+brick_thickness))
		pen.lineTo((w, brick_thickness))
		pen.closePath()
		for x_from in range(brick_interval, w, brick_interval):
			x_to = min(x_from + brick_length, w)
			pen.moveTo((x_from, h-brick_thickness))
			pen.lineTo((x_from, h))
			pen.lineTo((x_to, h))
			pen.lineTo((x_to, h-brick_thickness))
			pen.closePath()
			pen.moveTo((x_from, 0))
			pen.lineTo((x_from, brick_thickness))
			pen.lineTo((x_to, brick_thickness))
			pen.lineTo((x_to, 0))
			pen.closePath()
		if brick_interval >= w:
			x_from = 0
			x_to = min(x_from + brick_length, w)
			pen.moveTo((x_from, h-brick_thickness))
			pen.lineTo((x_from, h))
			pen.lineTo((x_to, h))
			pen.lineTo((x_to, h-brick_thickness))
			pen.closePath()
			pen.moveTo((x_from, 0))
			pen.lineTo((x_from, brick_thickness))
			pen.lineTo((x_to, brick_thickness))
			pen.lineTo((x_to, 0))
			pen.closePath()
		self.glyph_order.append(name)
		self.cmap[point] = name
		self.glyf[name] = pen.glyph()
		self.hmtx[name] = (0, 0)
		self.vmtx[name] = (0, 0)
		self.color_alpha[name] = (color, alpha)
		self.ch_names.add(name)
		self.class_defs[name] = MARK
		return name

	def add_outline_w_rot(self, w, h, thickness, brick_thickness, brick_length, brick_interval, 
				name=None, color='black', alpha=255):
		point, short_name = fresh_point(self.pua)
		name = name or short_name
		pen = TTGlyphPen(None)
		pen.moveTo((brick_thickness, 0))
		pen.lineTo((brick_thickness, h))
		pen.lineTo((brick_thickness+thickness, h))
		pen.lineTo((brick_thickness+thickness, 0))
		pen.closePath()
		pen.moveTo((w-thickness-brick_thickness, 0))
		pen.lineTo((w-thickness-brick_thickness, h))
		pen.lineTo((w-brick_thickness, h))
		pen.lineTo((w-brick_thickness, 0))
		pen.closePath()
		for y_from in range(brick_interval, h, brick_interval):
			y_to = min(y_from + brick_length, h)
			pen.moveTo((0, y_from))
			pen.lineTo((0, y_to))
			pen.lineTo((brick_thickness, y_to))
			pen.lineTo((brick_thickness, y_from))
			pen.closePath()
			pen.moveTo((w-brick_thickness, y_from))
			pen.lineTo((w-brick_thickness, y_to))
			pen.lineTo((w, y_to))
			pen.lineTo((w, y_from))
			pen.closePath()
		if brick_interval >= h:
			y_from = 0
			y_to = min(y_from + brick_length, h)
			pen.moveTo((0, y_from))
			pen.lineTo((0, y_to))
			pen.lineTo((brick_thickness, y_to))
			pen.lineTo((brick_thickness, y_from))
			pen.closePath()
			pen.moveTo((w-brick_thickness, y_from))
			pen.lineTo((w-brick_thickness, y_to))
			pen.lineTo((w, y_to))
			pen.lineTo((w, y_from))
			pen.closePath()
		self.glyph_order.append(name)
		self.cmap[point] = name
		self.glyf[name] = pen.glyph()
		self.hmtx[name] = (1, 1)
		self.vmtx[name] = (0, 0)
		self.color_alpha[name] = (color, alpha)
		self.ch_names.add(name)
		self.class_defs[name] = MARK
		return name

	def ch_to_hmtx(self, ch):
		point = ord(ch)
		name = self.cmap[point]
		return self.hmtx[name]

	def add_vs(self, vs_point, base_point, target_name):
		if vs_point not in self.uvsDict:
			self.uvsDict[vs_point] = []
		self.uvsDict[vs_point].append((base_point, target_name))

	def add_class(self, cls, marks):
		self.preamble_text += named_class(cls, marks)

	def add_markclass(self, cls, marks, x=0, y=0):
		self.preamble_text += named_markclass(cls, marks, x=x, y=y)

	def add_lookup(self, name, rules, filt=None):
		flags = [f'UseMarkFilteringSet {filt}'] if filt else None
		self.feature_text += lookup(name, rules, flags)

	def add_lookup_name(self, feat_name, lookup_name):
		self.lookups.append(lookup_name)
		self.lookup_to_feature[lookup_name] = feat_name

	def add_features(self):
		last_feat = None
		lookups = []
		for lookup in self.lookups:
			feat = self.lookup_to_feature[lookup]
			if feat == last_feat:
				lookups.append(lookup)
			else:
				if last_feat is not None:
					self.feature_text += feature(last_feat, lookups)
				lookups = [lookup]
				last_feat = feat
		if len(lookups) > 0:
			self.feature_text += feature(last_feat, lookups)

	def features(self):
		return list(set(self.lookup_to_feature.values()))

	def all_text(self):
		return '\n'.join(s for s in [self.preamble_text, self.feature_text] if s)

	def make_font(self, path, log=False):
		self.add_features()
		fb = self.make_font_init()
		if self.color_needed():
			self.make_font_colors(fb)
		text = self.all_text()
		if text:
			tt = fb.font
			feature_file = io.StringIO(text)
			builder = Builder(tt, feature_file)
			builder.build()
			if 'GDEF' in tt:
				gcd = otTables.GlyphClassDef()
				gcd.classDefs = self.class_defs
				tt["GDEF"].table.GlyphClassDef = gcd
			try:
				tt.save(path)
			except OTLOffsetOverflowError as e:
				print("Overflow record:", e.overflowErrorRecord)
		else:
			fb.save(path)
		if log:
			print(f'{self.pua["size"]} auxiliary characters')
			if text:
				print(f'{text.count("\tsub")} sub rules')
				print(f'{text.count("\tpos")} pos rules')
				print(f'{len(self.lookups)} lookups')
				print('features: ' + ','.join(self.features()))

	def make_font_init(self):
		fb = FontBuilder(self.src_upm, isTTF=True)
		fb.setupGlyphOrder(self.glyph_order)
		fb.setupCharacterMap(self.cmap)
		fb.setupGlyf(self.glyf)
		fb.setupHorizontalMetrics(self.hmtx)
		fb.setupVerticalMetrics(self.vmtx)

		family_name = self.font_name
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
				'manufacturer': 'hieropy'
			})
		fb.setupHorizontalHeader(ascent=self.ascent, descent=-self.descent, lineGap=self.gap)
		half = self.total_height // 2
		fb.setupVerticalHeader(ascent=half, descent=-half)
		fb.setupOS2(version=4, sTypoAscender=self.ascent, sTypoDescender=-self.descent,
				sTypoLineGap=self.gap, fsSelection=0x80,
				usWinAscent=self.ascent, usWinDescent=self.descent)
		fb.setupPost()
		fb.setupHead(unitsPerEm=self.total_height)
		fb.font['head'].created = timestampNow()
		fb.font['head'].modified = timestampNow()
		if self.uvsDict:
			fb.font['cmap'].tables.append(self.uvs_table())
		return fb

	def make_font_colors(self, fb):
		colors = list(set(self.color_alpha.values()))
		color_to_index = {color_alpha: i for i, color_alpha in enumerate(colors)}
		palette = [color_alpha_to_palette(color, alpha) for (color, alpha) in colors]
		fb.font['CPAL'] = buildCPAL([palette])
		fb.font['COLR'] = buildCOLR({name: [(name, color_to_index[color_alpha])] \
				for name, color_alpha in self.color_alpha.items()})

	def color_needed(self):
		for color, alpha in self.color_alpha.values():
			if alpha != 255 or color != 'black':
				return True
		return False

	def uvs_table(self):
		cmap14 = CmapSubtable.newSubtable(14)
		cmap14.platformID = 0
		cmap14.platEncID = 5
		cmap14.language = 0
		cmap14.uvsDict = self.uvsDict
		cmap14.cmap = {}
		return cmap14
