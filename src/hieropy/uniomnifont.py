import importlib.resources as resources
from fontTools.ttLib import TTFont
from collections import defaultdict
import math
from itertools import chain, combinations

from .featurefont import FeatureFontBuilder, BASE, MARK, \
	simple_sub_rule, context_sub_rule, chain_sub_rule, ignore_sub_rule, \
	base_pos_rule, mark_pos_rule, \
	named_class, lookup, feature 
from .uniconstants import HIERO_FONT_OMNI_NAME, HIERO_FONT_FILENAME, \
	VER, HOR, INSERT_TS, INSERT_BS, INSERT_TE, INSERT_BE, INSERT_M, INSERT_T, INSERT_B, \
	OVERLAY, BINARY_OPS, BEGIN_SEGMENT, END_SEGMENT, \
	MIRROR, FULL_BLANK, HALF_BLANK, FULL_LOST, HALF_LOST, TALL_LOST, WIDE_LOST, \
	BEGIN_ENCLOSURE, END_ENCLOSURE, BEGIN_WALLED_ENCLOSURE, END_WALLED_ENCLOSURE, \
	OPENING_CHARS, CLOSING_CHARS, \
	OPENING_PLAIN_CHARS, OPENING_WALLED_CHARS, CLOSING_PLAIN_CHARS, CLOSING_WALLED_CHARS, \
	OPEN_BRACKETS, CLOSE_BRACKETS, OUTLINE_THICKNESS, WALLED_OUTLINE_THICKNESS, \
	INSERTION_CHARS, INSERTION_PLACES, \
	num_to_damage, num_to_variation, rotate_to_num, insertion_position, Rectangle
from .options import Options, MeasureOptions
from .uninames import all_chars
from .uniproperties import allowed_rotations, rotation_adjustment, \
	overlay_ligatures, vertical_ligatures, horizontal_ligatures, insertion_list, \
	lr_symmetric_chars, tb_symmetric_chars, circular_chars
from .printables import em_size_of, PrintedPilWithoutExtras, PlaneRestricted

import logging
logging.getLogger("fontTools").setLevel(logging.DEBUG)

# Levels in operator precedence:
# v = vertical group
# h = horizontal group
# i = insertion
# o = overlay
# p = plain enclosure
# w = walled enclosure
# b = basic (literal, blank, lost, singleton), also brackets (only during parsing)
all_levels = list('vhiopwb')
upper_levels = list('vhiopw')
bottom_levels = list('pwb')
level_seq = 'vhio'

# Counts (of subgroups within group) up to small number
MAX_COUNT = 10
all_counts = list(range(MAX_COUNT+1))
nonzero_counts = list(range(1, MAX_COUNT+1))
all_remainders = list(range(MAX_COUNT))

# Dimensions are in octal (least-significant digit first)
all_digits = list(range(8))
odd_digits = [d for d in all_digits if d%2 == 1]

def int_to_binary(n):
	return f'{n:03b}'

def quotient_remain(n, divisor):
	q = n // divisor
	r = n - q * divisor
	return q, r

# Scaling s means scaling by (3/4)^s; s=0 means no scaling.
SCALEDOWN = 3/4
# In multiplication with 3/4, what potential values to add to current digit
# depending on the more significant octal digit?
all_down_carry = [0, 2, 4, 6]

def iterate_scaledown(val, sc):
	out = int(val)
	for _ in range(sc):
		out = int(SCALEDOWN * out)
	return out

class MeasuredInsertion:
	def __init__(self, place, x, y):
		self.place = place
		self.x = x
		self.y = y
		self.w = 1
		self.h = 1
		self.ext_left = 0
		self.ext_right = 0
		self.ext_top = 0
		self.ext_bottom = 0

	def x_max(self):
		return self.x + self.w - 1

	def y_max(self):
		return self.y + self.h - 1

	def x_center(self):
		return self.x + self.w / 2

	def y_center(self):
		return self.y + self.h / 2

	def left_strip(self):
		return (self.x-1, self.y, self.y+self.h-1)

	def right_strip(self):
		return (self.x+self.w, self.y, self.y+self.h-1)

	def top_strip(self):
		return (self.x, self.x+self.w-1, self.y-1)

	def bottom_strip(self):
		return (self.x, self.x+self.w-1, self.y+self.h)

	def extend_left(self):
		self.x -= 1
		self.w += 1
		self.ext_left += 1

	def extend_right(self):
		self.w += 1
		self.ext_right += 1

	def extend_top(self):
		self.y -= 1
		self.h += 1
		self.ext_top += 1

	def extend_bottom(self):
		self.h += 1
		self.ext_bottom += 1

class UniOmniFontBuilder:
	def __init__(self, ndigits=3, sep=0.08, maxdepth=4, nscales=5,
			signcolor='black', bracketcolor='black', shadecolor='black', shadealpha=255, shadepattern='diagonal', 
			fontname=HIERO_FONT_OMNI_NAME, gap=0.1, debug=False, log=False):
		self.len_oct = ndigits
		self.max_octal_int = 8 ** self.len_oct - 1
		self.all_poss = list(range(self.len_oct))
		FONT_UNITS_EXCLUSIVE = 1000 # as in NewGardiner
		self.em_exclusive = 50 if ndigits == 3 else 25
		self.resolution = 1000 // self.em_exclusive
		self.em = self.em_exclusive + round(sep * self.em_exclusive)
		self.font_units = self.em * self.resolution
		self.margin = self.font_units - FONT_UNITS_EXCLUSIVE
		self.sep = self.margin / FONT_UNITS_EXCLUSIVE
		self.max_depth = maxdepth
		self.n_scales = nscales
		self.signcolor = signcolor
		self.bracketcolor = bracketcolor
		self.shadecolor = shadecolor
		self.shadealpha = shadealpha
		self.shadepattern = shadepattern
		self.fontname = fontname
		self.gap = gap
		self.debug = debug
		self.log = log
		self.all_depths = list(range(self.max_depth))
		self.all_scales = list(range(self.n_scales))

	def enclosure_descent(self, sc):
		outer_scale = SCALEDOWN ** sc * self.em * self.resolution
		inner_scale = SCALEDOWN ** (sc+1) * self.em * self.resolution
		return round((outer_scale - inner_scale) / 2)

	def font_units_to_int(self, n):
		return round(n / self.resolution)

	def make_font(self, path):
		self.make_font_initial()
		self.syntax_analysis()
		self.local_analysis()
		self.scale_analysis()
		self.padding_analysis()
		self.substitution()
		self.shading_analysis()
		self.positioning()
		self.make_font_final(path)

	def make_font_initial(self):
		self.builder = FeatureFontBuilder(self.fontname, self.sep, 0.0, self.gap)
		self.repeat_lookups_num = defaultdict(int)
		self.lookup_to_marks = {}
		self.sym = {}
		self.base = {}
		self.make_chars()
		self.make_controls()
		self.make_aux()
		self.make_classes()

	def make_font_final(self, path):
		if self.debug:
			chunk_size = 1000
			items = list(self.base.items())
			for i in range(0, len(items), chunk_size):
				self.add_main_lookup(*self.visible_rules(i, items[i:i + chunk_size]))
		self.builder.make_font(path, log=self.log)

	def add_char(self, ch, color, expand=False):
		if expand:
			name, w, h = self.builder.copy_glyph_scale(ch, self.em / self.em_exclusive, color=color)
		else:
			name, w, h = self.builder.copy_glyph(ch, color=color)
		self.sym[ch] = name
		if self.debug:
			self.base[name] = self.builder.copy_base(ch)
		return name, w, h

	def add_control(self, ch):
		name = self.builder.copy_control(ch)
		self.sym[ch] = name
		if self.debug:
			self.base[name] = self.builder.copy_base(ch)
		return name

	def add_aux(self, name, label1, label2, x_advance=0, y_advance=0, cls=MARK):
		if self.debug:
			name_font = self.builder.add_aux(name=name, x_advance=x_advance, y_advance=y_advance, cls=cls)
			self.sym[name] = name_font
			self.base[name] = self.builder.add_aux_base(name, label1, label2)
			return name
		else:
			name_font = self.builder.add_aux(x_advance=x_advance, y_advance=y_advance, cls=cls)
			self.sym[name] = name_font
			return name_font

	def add_shade(self, w, h, name, label1, label2):
		if self.debug:
			name_font = self.builder.add_shade_diagonal(w, h, self.resolution, name=name)
			self.sym[name] = name_font
			self.base[name] = self.builder.add_aux_base(name, label1, label2)
			return name
		else:
			if self.shadepattern == 'diagonal':
				name_font = self.builder.add_shade_diagonal(w, h, self.resolution, 
						color=self.shadecolor, alpha=self.shadealpha)
			elif self.shadepattern == 'uniform':
				name_font = self.builder.add_shade_uniform(w, h,
						color=self.shadecolor, alpha=self.shadealpha)
			else:
				name_font = self.builder.add_shade_random(w, h, 3 * self.resolution,
						color=self.shadecolor, alpha=self.shadealpha)
			self.sym[name] = name_font
			return name_font

	def add_lost(self, width, height, ch):
		w = round(width * self.em) * self.resolution
		h = round(height * self.em) * self.resolution
		if self.shadepattern == 'diagonal':
			name = self.builder.add_shade_diagonal(w, h, self.resolution, ch=ch)
		elif self.shadepattern == 'uniform':
			name = self.builder.add_shade_uniform(w, h, ch=ch)
		else:
			name = self.builder.add_shade_random(w, h, 3 * self.resolution, ch=ch)
		self.sym[ch] = name
		if self.debug:
			self.base[name] = self.builder.copy_base(ch)
		return name

	def add_outline(self, typ, rot, w, h, thickness, name, label1, label2):
		debug_name = name if self.debug else None
		if typ == 'plain':
			if rot:
				name_font = self.builder.add_outline_p_rot(w, h, thickness, name=debug_name, color=self.signcolor)
			else:
				name_font = self.builder.add_outline_p(w, h, thickness, name=debug_name, color=self.signcolor)
		else:
			brick_thickness = round(thickness)
			brick_length = round(self.em / 8 * self.resolution)
			brick_interval = round(self.em / 5 * self.resolution)
			if rot:
				name_font = self.builder.add_outline_w_rot(w, h, \
						thickness, brick_thickness, brick_length, brick_interval, name=debug_name, color=self.signcolor)
			else:
				name_font = self.builder.add_outline_w(w, h, \
						thickness, brick_thickness, brick_length, brick_interval, name=debug_name, color=self.signcolor)
		self.sym[name] = name_font
		if self.debug:
			self.base[name] = self.builder.add_aux_base(name, label1, label2)
			return name
		else:
			return name_font

	def add_class(self, class_name, char_names):
		if not class_name in self.class_names:
			self.builder.add_class(class_name, char_names)
			self.class_names.add(class_name)

	def add_markclass(self, class_name, char_names, x=0, y=0):
		self.builder.add_markclass(class_name, char_names, x=x, y=y)

	def add_main_lookup(self, lookup_name, rules, filt=None, feat='liga'):
		if lookup_name in self.repeat_lookups_num:
			marks = self.lookup_to_marks[lookup_name]
			num = self.repeat_lookups_num[lookup_name]
			self.repeat_lookups_num[lookup_name] += 1
			rules = [chain_sub_rule([], [(marks, [lookup_name])], [])]
			new_name = lookup_name + str(num)
			self.builder.add_lookup(new_name, rules)
			self.builder.add_lookup_name(feat, new_name)
		else:
			self.builder.add_lookup(lookup_name, rules, filt)
			self.builder.add_lookup_name(feat, lookup_name)
			self.lookup_to_marks[lookup_name] = filt
			self.repeat_lookups_num[lookup_name] = 0

	def add_sub_lookup(self, lookup_name, rules, filt=None):
		self.builder.add_lookup(lookup_name, rules, filt)

	def add_pos_lookup(self, lookup_name, rules, filt=None, feat='mark'):
		self.builder.add_lookup(lookup_name, rules, filt)
		self.builder.add_lookup_name(feat, lookup_name)

	def make_chars(self):
		self.unmirrored_signs = []
		self.name_to_mirrored = {}
		self.unscaled_sign_to_size = {}
		self.name_rotate_to_name = {}
		for ch in all_chars():
			name, width, height = self.add_char(ch, self.signcolor)
			self.unmirrored_signs.append(name)
			self.unscaled_sign_to_size[name] = (width, height, 0, 0)
			if ch not in lr_symmetric_chars() and ch not in circular_chars():
				name_mir = self.builder.add_transform(name, 1, 0, True, color=self.signcolor)[0]
				self.unscaled_sign_to_size[name_mir] = (width, height, 0, 0)
				self.name_to_mirrored[name] = name_mir
			for rot in allowed_rotations(ch):
				rot_fine = rot + rotation_adjustment(ch, rot)
				vs = ord(num_to_variation(rotate_to_num(rot)))
				name_rot, width_rot, height_rot = self.builder.add_transform(name, 1, rot_fine, False, color=self.signcolor)
				self.name_rotate_to_name[(name, rot)] = name_rot
				self.builder.add_vs(vs, ord(ch), name_rot)
				self.unmirrored_signs.append(name_rot)
				self.unscaled_sign_to_size[name_rot] = (width_rot, height_rot, 0, 0)
				if rot not in [90,270] or ch not in tb_symmetric_chars():
					name_rot_mir = self.builder.add_transform(name, 1, rot_fine, True, color=self.signcolor)[0]
					self.unscaled_sign_to_size[name_rot_mir] = (width_rot, height_rot, 0, 0)
					self.name_to_mirrored[name_rot] = name_rot_mir

		for lig in overlay_ligatures() + vertical_ligatures() + horizontal_ligatures():
			if lig.ch not in self.sym:
				name, width, height = self.add_char(lig.ch, self.signcolor)
				self.unmirrored_signs.append(name)
				self.unscaled_sign_to_size[name] = (width, height, 0, 0)

		self.insertion_bases = []
		self.name_to_insertion_copy1 = {}
		self.name_to_insertion_copy2 = {}
		self.name_place_to_pair = {}
		self.name_place_to_geom = {}
		self.name_places_variant = []
		self.name_rot_to_places_variant = defaultdict(list)
		self.name_with_insertion_variants = set()
		for ch, insertion in insertion_list():
			rot = insertion.rot or 0
			if ch not in self.sym: # needed during debugging
				continue
			base_name = self.sym[ch]
			if rot:
				if (base_name, rot) not in self.name_rotate_to_name:
					continue
				base_name = self.name_rotate_to_name[(base_name, rot)]
			self.insertion_bases.append(base_name)
			if insertion.ch is not None:
				if insertion.ch not in self.sym:
					name, width, height = self.add_char(insertion.ch, self.signcolor)
					self.unmirrored_signs.append(name)
					self.unscaled_sign_to_size[name] = (width, height, 0, 0)
					# For right to left text, this would have to be extended.
					# name_mir = self.builder.add_transform(name, 1, 0, True, color=self.signcolor)[0]
					# self.unscaled_sign_to_size[name_mir] = (width, height, 0, 0)
					# self.name_to_mirrored[name] = name_mir
				else:
					name = self.sym[insertion.ch]
				if rot:
					name, width, height = self.builder.add_transform(name, 1, rot, False, color=self.signcolor)
					self.unmirrored_signs.append(name)
					self.unscaled_sign_to_size[name] = (width, height, 0, 0)
				ch = insertion.ch
			else:
				name = base_name
			geoms, s, e, t, b = self.geometries(ch, rot, insertion.places, insertion.out)
			if not geoms:
				continue
			if s or e or t or b:
				name, w, h = self.builder.add_copy(name, color=self.signcolor)
				width, height = w + s + e, h + b + t
				self.unmirrored_signs.append(name)
				self.unscaled_sign_to_size[name] = (width, height, -s, -b)
				# For right to left text, this would have to be extended.
				#name_mir = self.builder.add_transform(name, 1, 0, True, color=self.signcolor)[0]
				#self.unscaled_sign_to_size[name_mir] = (width, height, -e, -b)
				#self.name_to_mirrored[name] = name_mir
			#else:
				#name_mir = self.name_to_mirrored[name]
			if name not in self.name_to_insertion_copy1:
				self.name_to_insertion_copy1[name] = self.add_aux(f'ins_copy1_{name}', 'in1', name[-2:])
				self.name_to_insertion_copy2[name] = self.add_aux(f'ins_copy2_{name}', 'in2', name[-2:])
				#self.name_to_insertion_copy1[name_mir] = self.add_aux(f'ins_copy1_{name_mir}', 'in1', name_mir[-2:])
				#self.name_to_insertion_copy2[name_mir] = self.add_aux(f'ins_copy2_{name_mir}', 'in2', name_mir[-2:])
			self.name_places_variant.append((base_name, list(insertion.places.keys()), name))
			self.name_rot_to_places_variant[(base_name, rot)].append((list(insertion.places.keys()), name))
			if name != base_name:
				self.name_with_insertion_variants.add(base_name)
			for place, (x, y, w, h) in geoms.items():
				if (name, place) not in self.name_place_to_pair:
					self.name_place_to_pair[(name, place)] = self.add_aux(f'ins_{name}_{place}', 'nm', 'pl')
					self.name_place_to_geom[(name, place)] = (x + s/2 - e/2, y + b/2 - t/2, w, h)
		self.insertion_base_list = list(self.name_to_insertion_copy1.keys())
		self.insertion_base_overlay_list = list(set(self.sym[lig.ch] for lig in overlay_ligatures() \
						if lig.ch in self.sym and self.sym[lig.ch] in self.insertion_base_list))

		self.name_scale_to_name = {}
		for name in self.unscaled_sign_to_size.keys():
			for sc in range(1, self.n_scales):
				factor = SCALEDOWN ** sc
				self.name_scale_to_name[(name, sc)] = self.builder.add_transform(name, factor, 0, False, color=self.signcolor)[0]
		self.insertion_bases = list(set(self.insertion_bases))

		self.unscaled_cap_to_size = {}
		self.unscaled_cap_rot_to_size = {}
		self.cap_to_rotate = {}
		def add_caps(chars):
			name_list = []
			name_rot_list = []
			for ch in chars:
				name, width, height = self.add_char(ch, self.signcolor, expand=True)
				name_list.append(name)
				self.unscaled_cap_to_size[name] = (width, height)
				name_mir = self.builder.add_transform(name, 1, 0, True, color=self.signcolor)[0]
				self.unscaled_cap_to_size[name_mir] = (width, height)
				self.name_to_mirrored[name] = name_mir
				name_rot = self.builder.add_transform(name, 1, 90, False, color=self.signcolor)[0]
				name_rot_list.append(name_rot)
				self.unscaled_cap_rot_to_size[name_rot] = (height, width)
				self.cap_to_rotate[name] = name_rot
				name_rot_mir = self.builder.add_transform(name, 1, 90, True, color=self.signcolor)[0]
				self.unscaled_cap_rot_to_size[name_rot_mir] = (height, width)
				self.name_to_mirrored[name_rot] = name_rot_mir
			return name_list, name_rot_list
		self.openings_plain, self.openings_plain_rot = add_caps(OPENING_PLAIN_CHARS)
		self.openings_walled, self.openings_walled_rot = add_caps(OPENING_WALLED_CHARS)
		self.closings_plain, self.closings_plain_rot = add_caps(CLOSING_PLAIN_CHARS)
		self.closings_walled, self.closings_walled_rot = add_caps(CLOSING_WALLED_CHARS)
		self.openings = self.openings_plain + self.openings_walled
		self.closings = self.closings_plain + self.closings_walled
		self.openings_rot = self.openings_plain_rot + self.openings_walled_rot
		self.closings_rot = self.closings_plain_rot + self.closings_walled_rot
		self.caps = self.openings + self.closings
		self.caps_rot = self.openings_rot + self.closings_rot
		self.cap_scale_to_cap = {}
		self.cap_rot_scale_to_cap = {}
		for name in self.unscaled_cap_to_size.keys():
			for sc in self.all_scales:
				factor = SCALEDOWN ** sc
				self.cap_scale_to_cap[(name, sc)] = self.builder.add_transform(name, factor, 0, False, color=self.signcolor)[0]
		for name in self.unscaled_cap_rot_to_size.keys():
			for sc in self.all_scales:
				factor = SCALEDOWN ** sc
				self.cap_rot_scale_to_cap[(name, sc)] = self.builder.add_transform(name, factor, 0, False, color=self.signcolor)[0]

		self.open_brackets = []
		self.close_brackets = []
		self.bracket_width = {}
		self.bracket_scale_to_bracket = {}
		for ch in OPEN_BRACKETS:
			name, width, _ = self.add_char(ch, self.bracketcolor, expand=True)
			self.open_brackets.append(name)
			self.bracket_scale_to_bracket[(name, 0)] = name
			self.bracket_width[name] = width
			for sc in range(1, self.n_scales):
				scaled = self.builder.add_transform(name, factor, 0, False, shift=False, color=self.bracketcolor)[0]
				self.bracket_scale_to_bracket[(name, sc)] = scaled
				self.bracket_width[scaled] = round(width * SCALEDOWN ** sc)
		for ch in CLOSE_BRACKETS:
			name, width, _ = self.add_char(ch, self.bracketcolor, expand=True)
			self.close_brackets.append(name)
			self.bracket_scale_to_bracket[(name, 0)] = name
			self.bracket_width[name] = width
			for sc in range(1, self.n_scales):
				scaled = self.builder.add_transform(name, factor, 0, False, shift=False, color=self.bracketcolor)[0]
				self.bracket_scale_to_bracket[(name, sc)] = scaled
				self.bracket_width[scaled] = round(width * SCALEDOWN ** sc)
		self.brackets = self.open_brackets + self.close_brackets
		self.brackets_scaled = self.bracket_scale_to_bracket.values()

	def make_controls(self):
		self.ver = self.add_control(VER)
		self.hor = self.add_control(HOR)
		self.place_to_insertion = {}
		self.place_to_insertion['ts'] = self.add_control(INSERT_TS)
		self.place_to_insertion['bs'] = self.add_control(INSERT_BS)
		self.place_to_insertion['te'] = self.add_control(INSERT_TE)
		self.place_to_insertion['be'] = self.add_control(INSERT_BE)
		self.place_to_insertion['m'] = self.add_control(INSERT_M)
		self.place_to_insertion['t'] = self.add_control(INSERT_T)
		self.place_to_insertion['b'] = self.add_control(INSERT_B)
		self.insertions = [self.sym[ch] for ch in INSERTION_CHARS]
		self.overlay = self.add_control(OVERLAY)
		self.bin_ops = [self.sym[ch] for ch in BINARY_OPS]
		self.begin_segment = self.add_control(BEGIN_SEGMENT)
		self.end_segment = self.add_control(END_SEGMENT)
		self.full_blank = self.add_control(FULL_BLANK)
		self.half_blank = self.add_control(HALF_BLANK)
		self.blanks = [self.full_blank, self.half_blank]
		self.full_lost = self.add_lost(1, 1, ch=FULL_LOST)
		self.half_lost = self.add_lost(0.5, 0.5, ch=HALF_LOST)
		self.tall_lost = self.add_lost(0.5, 1, ch=TALL_LOST)
		self.wide_lost = self.add_lost(1, 0.5, ch=WIDE_LOST)
		self.full_lost_exp = self.add_aux('fl_exp', 'fl', 'exp')
		self.half_lost_exp = self.add_aux('hl_exp', 'hl', 'exp')
		self.tall_lost_exp = self.add_aux('tl_exp', 'tl', 'exp')
		self.wide_lost_exp = self.add_aux('wl_exp', 'wl', 'exp')
		self.losts = [self.full_lost, self.half_lost, self.tall_lost, self.wide_lost, \
			self.full_lost_exp, self.half_lost_exp, self.tall_lost_exp, self.wide_lost_exp]
		self.unscaled_lost_to_size = {}
		self.unscaled_lost_to_size[self.full_lost] = (1, 1)
		self.unscaled_lost_to_size[self.half_lost] = (0.5, 0.5)
		self.unscaled_lost_to_size[self.tall_lost] = (0.5, 1)
		self.unscaled_lost_to_size[self.wide_lost] = (1, 0.5)
		self.lost_scale_to_lost = {}
		for lost, (w,h) in self.unscaled_lost_to_size.items():
			for sc in range(1, self.n_scales):
				factor = SCALEDOWN ** sc
				width = round(factor * w * self.em) * self.resolution
				height = round(factor * h * self.em) * self.resolution
				self.lost_scale_to_lost[(lost, sc)] = self.add_shade(width, height, \
						f'lost_{w}_{h}_{sc}', 'lost', f'{sc}')
		vs1 = ord(num_to_variation(1))
		self.builder.add_vs(vs1, ord(FULL_LOST), self.full_lost_exp)
		self.builder.add_vs(vs1, ord(HALF_LOST), self.half_lost_exp)
		self.builder.add_vs(vs1, ord(TALL_LOST), self.tall_lost_exp)
		self.builder.add_vs(vs1, ord(WIDE_LOST), self.wide_lost_exp )
		self.mirror = self.add_control(MIRROR)
		self.damaged = [self.add_control(num_to_damage(n)) for n in range(1, 16)]
		self.modifiers = [self.mirror] + self.damaged
		self.begin_plain_enclosure = self.add_control(BEGIN_ENCLOSURE)
		self.end_plain_enclosure = self.add_control(END_ENCLOSURE)
		self.begin_walled_enclosure = self.add_control(BEGIN_WALLED_ENCLOSURE)
		self.end_walled_enclosure = self.add_control(END_WALLED_ENCLOSURE)
		self.begin_any_enclosure = [self.begin_plain_enclosure, self.begin_walled_enclosure]
		self.end_any_enclosure = [self.end_plain_enclosure, self.end_walled_enclosure]

	def make_aux(self):
		# for parsing
		for level in all_levels:
			self.add_aux(f'open_{level}', f'({level}', '')
			self.add_aux(f'open_do_{level}', f'({level}', 'do')
			self.add_aux(f'open_outer_{level}', f'({level}', 'ou')
			self.add_aux(f'open_inner_{level}', f'({level}', 'in')
			self.add_aux(f'close_{level}', f'{level})', '')
			self.add_aux(f'close_do_{level}', f'{level})', 'do')
			self.add_aux(f'close_outer_{level}', f'{level})', 'ou')
			self.add_aux(f'close_inner_{level}', f'{level})', 'in')
		for depth in self.all_depths:
			self.add_aux(f'depth_{depth}', f'd{depth}', '')
			self.add_aux(f'depth_active_{depth}', f'd{depth}', 'ac')
		self.nil = self.add_aux('nil', 'nil', '')
		# for local analysis
		self.record = self.add_aux('record', 'rec', '')
		self.record_active = self.add_aux('record_active', 'rec', 'ac')
		self.size_limits = self.add_aux('size_limits', 's', 'lim')
		self.size_top_limits = self.add_aux('size_top_limits', 's', 'lim')
		self.flat = self.add_aux('flat', 'flat', '')
		self.horizontal = self.add_aux('horizontal', 'hor', '')
		self.vertical = self.add_aux('vertical', 'ver', '')
		self.horizontal_active = self.add_aux('horizontal_active', 'hor', 'ac')
		self.vertical_active = self.add_aux('vertical_active', 'hor', 'ac')
		self.insertions_active = [self.add_aux(f'insertion_active_{pl}', pl, 'act') for pl in INSERTION_PLACES]
		self.unknown_places = [self.add_aux(f'place_unknown_{pl}', pl, 'unk') for pl in INSERTION_PLACES]
		self.unused_places = [self.add_aux(f'place_unused_{pl}', pl, 'no') for pl in INSERTION_PLACES]
		self.used_places = [self.add_aux(f'place_used_{pl}', pl, 'yes') for pl in INSERTION_PLACES]
		self.insertion_base = self.add_aux('insertion_base', 'ins', 'ba')
		for c in all_counts:
			self.add_aux(f'count_{c}', f'c{c}', '')
		for c in nonzero_counts:
			self.add_aux(f'length_{c}', f'l{c}', '')
		self.overlay_alt = self.add_aux('overlay_alt', 'ov', 'alt')
		self.hor_alt = self.add_aux('hor_alt', 'hor', 'alt')
		self.ver_alt = self.add_aux('ver_alt', 'ver', 'alt')
		self.alt_start = self.add_aux('alt_start', 'sta', 'alt')
		self.alt_end = self.add_aux('alt_end', 'ena', 'alt')
		self.alt_start_active = self.add_aux('alt_start_active', 'st', 'alt')
		self.alt_end_active = self.add_aux('alt_end_active', 'en', 'alt')
		self.absent_sign = self.add_aux('absent_sign', 'abs', 'si')
		# for scale analysis
		for d in all_digits:
			self.add_aux(f'width_{d}', f'{d}', 'wi')
			self.add_aux(f'height_{d}', f'{d}', 'hi')
			self.add_aux(f'width_scaled_{d}', f'{d}', 'swi')
			self.add_aux(f'height_scaled_{d}', f'{d}', 'shi')
			self.add_aux(f'width_scaled_latent_{d}', f'ws{d}', 'lat')
			self.add_aux(f'height_scaled_latent_{d}', f'hs{d}', 'lat')
			self.add_aux(f'width_scaled_active_{d}', f'ws{d}', 'act')
			self.add_aux(f'height_scaled_active_{d}', f'hs{d}', 'act')
			self.add_aux(f'width_scaled_latent_active_{d}', f'ws{d}', 'lac')
			self.add_aux(f'height_scaled_latent_active_{d}', f'hs{d}', 'lac')
			self.add_aux(f'size_{d}', f'{d}', 'si')
			self.add_aux(f'size_reverse_{d}', f'{d}', 'sir')
			self.add_aux(f'size_first_{d}', f'{d}', 'sif')
			self.add_aux(f'carry_{d}', f'{d}', 'car')
			self.add_aux(f'lt_{d}', f'{d}', 'lt')
			self.add_aux(f'gt_{d}', f'{d}', 'gt')
			self.add_aux(f'eq_{d}', f'{d}', 'eq')
			self.add_aux(f'size_scaled_{d}', f'{d}', 'ss')
			self.add_aux(f'size_scaled_carry_{d}', f'{d}', 'ssc')
			self.add_aux(f'limit_size_{d}', f'{d}', 'sl')
			self.add_aux(f'limit_width_{d}', f'{d}', 'lwi')
			self.add_aux(f'limit_height_{d}', f'{d}', 'lhi')
			self.add_aux(f'insert_{d}', f'{d}', 'ins')
			self.add_aux(f'insert_x_{d}', f'x{d}', 'ins')
			self.add_aux(f'insert_y_{d}', f'y{d}', 'ins')
		self.minus_insert = self.add_aux(f'minus_insert', 'min', 'in')
		for d in all_digits[1:]:
			for p in self.all_poss:
				self.add_aux(f'insert_w_{d}_{p}', f'{d}.{p}', 'inw')
				self.add_aux(f'insert_h_{d}_{p}', f'{d}.{p}', 'inh')
				self.add_aux(f'insert_w_{-d}_{p}', f'{-d}.{p}', 'inw')
				self.add_aux(f'insert_h_{-d}_{p}', f'{-d}.{p}', 'inh')
				self.add_aux(f'insert_half_w_{d}_{p}', f'{d}h{p}', 'inw')
				self.add_aux(f'insert_half_h_{d}_{p}', f'{d}h{p}', 'inh')
		self.inserted_width = self.add_aux('inserted_width', 'ins', 'wid')
		self.inserted_height = self.add_aux('inserted_height', 'ins', 'hei')
		self.insert_sep = self.add_aux(f'insert_sep', 'ins', 'sep')
		self.size_sep = self.add_aux('size_sep', 's', 'sep')
		self.size_reverse_sep = self.add_aux('size_reverse_sep', 'rev', 'sep')
		self.size_first_sep = self.add_aux('size_first_sep', 'fir', 'sep')
		self.nil_scale = self.add_aux('nil_scale', 'nil', 'sc')
		for p in self.all_poss:
			self.add_aux(f'pos_reverse_{p}', f'{p}', 'rev')
			self.add_aux(f'pos_reverse_final_{p}', f'{p}', 'rvf')
		for s in self.all_scales + [self.n_scales]:
			self.add_aux(f'scale_{s}', f'{s}', 'sca')
			self.add_aux(f'scale_hidden_{s}', f'{s}', 'sch')
			self.add_aux(f'scale_group_{s}', f'{s}', 'sg')
			self.add_aux(f'scale_group_active_{s}', f'{s}', 'sga')
			self.add_aux(f'width_scale_{s}', f'{s}', 'ws')
			self.add_aux(f'width_scale_latent_{s}', f'{s}', 'wsl')
			self.add_aux(f'width_scale_active_{s}', f'{s}', 'wsa')
			self.add_aux(f'width_scale_latent_active_{s}', f'{s}', 'wsla')
			self.add_aux(f'height_scale_{s}', f'{s}', 'hs')
			self.add_aux(f'height_scale_latent_{s}', f'{s}', 'hsl')
			self.add_aux(f'height_scale_active_{s}', f'{s}', 'hsa')
			self.add_aux(f'height_scale_latent_active_{s}', f'{s}', 'hsla')
		for s in self.all_scales:
			self.add_aux(f'cap_scale_{s}', f'{s}', 'cas')
			self.add_aux(f'cap_scale_active_{s}', f'{s}', 'csa')
			self.add_aux(f'enclosure_scale_{s}', f'{s}', 'es')
			self.add_aux(f'enclosure_scale_active_{s}', f'{s}', 'esa')
			self.add_aux(f'enclosure_scale_vertical_{s}', f'{s}', 'esv')
			self.add_aux(f'insert_x_scale_{s}', f'x{s}', 'in')
			self.add_aux(f'insert_y_scale_{s}', f'y{s}', 'in')
			self.add_aux(f'insert_x_scale_active_{s}', f'x{s}', 'ina')
			self.add_aux(f'insert_y_scale_active_{s}', f'y{s}', 'ina')
		self.to_scale = self.add_aux('to_scale', '?', 'sc')
		self.cap_marker = self.add_aux('cap_marker', 'cap', 'mar')
		self.cap_anchor_start = self.add_aux(f'cap_anchor_start', f'cap', 'ans')
		self.cap_anchor_end = self.add_aux(f'cap_anchor_end', f'cap', 'ane')
		for d in self.all_depths:
			self.add_aux(f'cap_anchor_start_{d}', f'{d}', 'cas')
			self.add_aux(f'cap_anchor_end_{d}', f'{d}', 'cae')
		# for padding analysis
		for sc in self.all_scales[1:]:
			self.add_aux(f'content_width_{sc}', f'{sc}', 'cw')
			self.add_aux(f'content_height_{sc}', f'{sc}', 'ch')
			self.add_aux(f'content_width_active_{sc}', f'{sc}', 'cwa')
			self.add_aux(f'content_height_active_{sc}', f'{sc}', 'cha')
		self.size_full_sep = self.add_aux('size_full_sep', 'fll', 'sep')
		self.to_diff = self.add_aux('to_diff', '?', 'di')
		self.to_full = self.add_aux('to_full', '?', 'fu')
		self.size_unreverse_sep = self.add_aux('size_unreverse_sep', 'unr', 'sep')
		self.inner_pad = self.add_aux('inner_pad', 'inn', 'pad')
		self.first_pad = self.add_aux('first_pad', 'fst', 'pad')
		self.last_pad = self.add_aux('last_pad', 'lst', 'pad')
		for d in all_digits:
			self.add_aux(f'width_full_{d}', f'w{d}', 'ful')
			self.add_aux(f'height_full_{d}', f'h{d}', 'ful')
			self.add_aux(f'size_full_{d}', f'{d}', 'ful')
			self.add_aux(f'diff_{d}', f'{d}', 'dif')
			self.add_aux(f'width_full_scaled_{d}', f'w{d}', 'fls')
			self.add_aux(f'height_full_scaled_{d}', f'h{d}', 'fls')
			self.add_aux(f'size_full_scaled_{d}', f's{d}', 'fls')
		for b in [0,1]:
			self.add_aux(f'bit_{b}', f'{b}', 'bit')
			self.add_aux(f'quotient_{b}', f'{b}', 'quo')
		for d in all_remainders:
			self.add_aux(f'remain_{d}', f'{d}', 're')
			self.add_aux(f'remain_final_{d}', f'{d}', 'ref')
		for p in self.all_poss:
			self.add_aux(f'pos_unreverse_{p}', f'{p}', 'urv')
		# for shading
		for p in self.all_poss:
			self.add_aux(f'left_shade_pos_{p}', f'{p}', 'l')
			self.add_aux(f'half_left_shade_pos_{p}', f'{p}', 'hl')
			self.add_aux(f'half_right_shade_pos_{p}', f'{p}', 'hr')
			self.add_aux(f'down_shade_pos_{p}', f'{p}', 'd')
			self.add_aux(f'half_down_shade_pos_{p}', f'{p}', 'hd')
			self.add_aux(f'w_shade_pos_{p}', f'{p}', 'wp')
			self.add_aux(f'h_shade_pos_{p}', f'{p}', 'hp')
			self.add_aux(f'half_w_shade_pos_{p}', f'{p}', 'hwp')
			self.add_aux(f'half_h_shade_pos_{p}', f'{p}', 'hhp')
			for d in all_digits:
				self.add_aux(f'left_shade_{d}_{p}', f'{d}.{p}', 'l')
				self.add_aux(f'right_shade_{d}_{p}', f'{d}.{p}', 'r')
				self.add_aux(f'down_shade_{d}_{p}', f'{d}.{p}', 'd')
				self.add_aux(f'w_shade_{d}_{p}', f'{d}.{p}', 'wp')
				self.add_aux(f'h_shade_{d}_{p}', f'{d}.{p}', 'hp')
		self.shade_combinations = []
		for p1 in self.all_poss:
			for d1 in all_digits:
				w = d1 * 8**p1
				if d1 > 0 and w <= 1.5 * self.em:
					for p2 in self.all_poss:
						for d2 in all_digits:
							h = d2 * 8**p2
							if d2 > 0 and h <= 1.5 * self.em:
								self.shade_combinations.append((p1, d1, w, p2, d2, h))
		for p1, d1, w, p2, d2, h in self.shade_combinations:
			self.add_shade(w * self.resolution, h * self.resolution, f'shade_{d1}_{d2}_{p1}_{p2}', f'{d1}.{d2}', f'{p1}.{p2}')
		# for substitution
		self.no_mirror = self.add_aux(f'no_mirror', f'no', 'mir')
		for p in self.all_poss:
			self.add_aux(f'pos_bracket_{p}', f'{p}', 'br')
		for d in self.all_depths:
			self.add_aux(f'bracket_anchor_{d}', f'{d}', 'ba')
		for d in all_digits[1:]:
			PLAIN_THICKNESS = 45
			WALLED_THICKNESS = 40
			for p in self.all_poss:
				if p == self.len_oct-1 and d > 1:
					continue
				size = round(d * 8**p) * self.resolution
				for sc in self.all_scales:
					unit = round(SCALEDOWN**sc * self.em) * self.resolution
					plain_thickness = round(SCALEDOWN**sc * PLAIN_THICKNESS)
					walled_thickness = round(SCALEDOWN**sc * WALLED_THICKNESS)
					self.add_outline('plain', False, size, unit, plain_thickness, \
							f'p_outline_{sc}_hor_{d}_{p}', f'o{sc}', f'{d}.{p}')
					self.add_outline('plain', True, unit, size, plain_thickness, \
							f'p_outline_{sc}_ver_{d}_{p}', f'o{sc}', f'{d}.{p}')
					self.add_outline('walled', False, size, unit, walled_thickness, \
							f'w_outline_{sc}_hor_{d}_{p}', f'o{sc}', f'{d}.{p}')
					self.add_outline('walled', True, unit, size, walled_thickness, \
							f'w_outline_{sc}_ver_{d}_{p}', f'o{sc}', f'{d}.{p}')
		for d in all_digits[2:]:
			p = self.len_oct-1
			for sc in self.all_scales:
				for level in 'pw':
					for direction in ['hor', 'ver']:
						self.add_aux(f'{level}_outline_{sc}_{direction}_{d}_{p}', f'o{sc}', f'{d}.{p}')
		for p in self.all_poss:
			for sc in self.all_scales:
				for level in 'pw':
					for direction in ['hor', 'ver']:
						self.add_aux(f'{level}_outline_pos_{sc}_{direction}_{p}', f'o{sc}', f'{p}{level}')
		# for positioning
		self.start_hor = self.add_aux('start_hor', 'st', 'hor', cls=BASE)
		self.start_ver = self.add_aux('start_ver', 'st', 'ver', cls=BASE)
		for p in self.all_poss:
			self.add_aux(f'to_advance_{p}', 'to', f'{p}')
		self.to_anchor_start = self.add_aux('to_anchor_start', 'to', 'ans')
		self.to_anchor_end = self.add_aux('to_anchor_end', 'to', 'ane')
		self.to_anchor_size = self.add_aux('to_anchor_size', 'to', 'siz')
		for d in all_digits:
			for p in self.all_poss:
				adv = d * 8**p
				if p != 0 and adv == 0:
					continue
				adv_units = self.resolution * adv
				self.add_aux(f'advance_w_{adv}', f'{adv}', 'adw')
				self.add_aux(f'advance_h_{adv}', f'{adv}', 'adh')
				self.add_aux(f'advance_w_base_{adv}', f'{adv}', 'awb', cls=BASE, x_advance=adv_units)
				self.add_aux(f'advance_h_base_{adv}', f'{adv}', 'ahb', cls=BASE, y_advance=adv_units)
				self.add_aux(f'anchor_pad_w_{adv}', f'{adv}', 'w')
				self.add_aux(f'anchor_pad_h_{adv}', f'{adv}', 'h')
				self.add_aux(f'mid_w_{adv}', f'{adv}', 'mw')
				self.add_aux(f'mid_h_{adv}', f'{adv}', 'mh')
		for depth in self.all_depths:
			self.add_aux(f'anchor_start_{depth}', f'a{depth}', 's')
			self.add_aux(f'anchor_end_{depth}', f'a{depth}', 'e')
			self.add_aux(f'anchor_end_w_{depth}', f'a{depth}', 'ew')
			self.add_aux(f'anchor_end_h_{depth}', f'a{depth}', 'eh')
			self.add_aux(f'anchor_start_insert_{depth}', f'a{depth}', 'si')
			self.add_aux(f'anchor_end_insert_{depth}', f'a{depth}', 'ei')
		for depth in self.all_depths[:-1]:
			self.add_aux(f'anchor_insert_mid_{depth}', f'{depth}', 'aim')
		self.anchor_basic_mid = self.add_aux('anchor_basic_mid', f'bas', 'mid')
		self.anchor_end_insert = self.add_aux('anchor_end_insert', 'ane', 'ins')
		self.anchor_start_insert_active = self.add_aux('anchor_start_insert_active', 'asa', 'ins')
		self.anchor_end_insert_active = self.add_aux('anchor_end_insert_active', 'ana', 'ins')
		self.content_marker = self.add_aux('content_marker', 'co', 'ma')

	# for syntactic analysis
	def open_(self, level):
		return self.sym[f'open_{level}']
	def open_do_(self, level):
		return self.sym[f'open_do_{level}']
	def open_outer_(self, level):
		return self.sym[f'open_outer_{level}']
	def open_inner_(self, level):
		return self.sym[f'open_inner_{level}']
	def close_(self, level):
		return self.sym[f'close_{level}']
	def close_do_(self, level):
		return self.sym[f'close_do_{level}']
	def close_outer_(self, level):
		return self.sym[f'close_outer_{level}']
	def close_inner_(self, level):
		return self.sym[f'close_inner_{level}']
	def depth_(self, d):
		return self.sym[f'depth_{d}']
	def depth_active_(self, d):
		return self.sym[f'depth_active_{d}']
	def insertion_(self, pl):
		return self.place_to_insertion[pl]

	# for local analysis
	def count_(self, c):
		return self.sym[f'count_{c}']
	def length_(self, c):
		return self.sym[f'length_{c}']
	def insertion_active_(self, pl):
		return self.sym[f'insertion_active_{pl}']
	def used_place_(self, pl):
		return self.sym[f'place_used_{pl}']

	# for scale analysis
	def width_(self, d):
		return self.sym[f'width_{d}']
	def height_(self, d):
		return self.sym[f'height_{d}']
	def width_scaled_(self, d):
		return self.sym[f'width_scaled_{d}']
	def height_scaled_(self, d):
		return self.sym[f'height_scaled_{d}']
	def width_scaled_latent_(self, d):
		return self.sym[f'width_scaled_latent_{d}']
	def height_scaled_latent_(self, d):
		return self.sym[f'height_scaled_latent_{d}']
	def width_scaled_active_(self, d):
		return self.sym[f'width_scaled_active_{d}']
	def height_scaled_active_(self, d):
		return self.sym[f'height_scaled_active_{d}']
	def width_scaled_latent_active_(self, d):
		return self.sym[f'width_scaled_latent_active_{d}']
	def height_scaled_latent_active_(self, d):
		return self.sym[f'height_scaled_latent_active_{d}']
	def size_(self, d):
		return self.sym[f'size_{d}']
	def size_reverse_(self, d):
		return self.sym[f'size_reverse_{d}']
	def size_first_(self, d):
		return self.sym[f'size_first_{d}']
	def carry_(self, d):
		return self.sym[f'carry_{d}']
	def lt_(self, d):
		return self.sym[f'lt_{d}']
	def gt_(self, d):
		return self.sym[f'gt_{d}']
	def eq_(self, d):
		return self.sym[f'eq_{d}']
	def size_scaled_(self, d):
		return self.sym[f'size_scaled_{d}']
	def size_scaled_carry_(self, d):
		return self.sym[f'size_scaled_carry_{d}']
	def limit_size_(self, d):
		return self.sym[f'limit_size_{d}']
	def limit_width_(self, d):
		return self.sym[f'limit_width_{d}']
	def limit_height_(self, d):
		return self.sym[f'limit_height_{d}']
	def insert_(self, d):
		return self.sym[f'insert_{d}']
	def insert_x_(self, d):
		return self.sym[f'insert_x_{d}']
	def insert_y_(self, d):
		return self.sym[f'insert_y_{d}']
	def insert_w_(self, d, p):
		return self.sym[f'insert_w_{d}_{p}']
	def insert_h_(self, d, p):
		return self.sym[f'insert_h_{d}_{p}']
	def insert_half_w_(self, d, p):
		return self.sym[f'insert_half_w_{d}_{p}']
	def insert_half_h_(self, d, p):
		return self.sym[f'insert_half_h_{d}_{p}']
	def pos_reverse_(self, p):
		return self.sym[f'pos_reverse_{p}']
	def pos_reverse_final_(self, p):
		return self.sym[f'pos_reverse_final_{p}']
	def scale_(self, s):
		return self.sym[f'scale_{s}']
	def scale_hidden_(self, s):
		return self.sym[f'scale_hidden_{s}']
	def scale_group_(self, s):
		return self.sym[f'scale_group_{s}']
	def scale_group_active_(self, s):
		return self.sym[f'scale_group_active_{s}']
	def width_scale_(self, s):
		return self.sym[f'width_scale_{s}']
	def width_scale_latent_(self, s):
		return self.sym[f'width_scale_latent_{s}']
	def width_scale_active_(self, s):
		return self.sym[f'width_scale_active_{s}']
	def width_scale_latent_active_(self, s):
		return self.sym[f'width_scale_latent_active_{s}']
	def height_scale_(self, s):
		return self.sym[f'height_scale_{s}']
	def height_scale_latent_(self, s):
		return self.sym[f'height_scale_latent_{s}']
	def height_scale_active_(self, s):
		return self.sym[f'height_scale_active_{s}']
	def height_scale_latent_active_(self, s):
		return self.sym[f'height_scale_latent_active_{s}']
	def cap_scale_(self, s):
		return self.sym[f'cap_scale_{s}']
	def cap_scale_active_(self, s):
		return self.sym[f'cap_scale_active_{s}']
	def enclosure_scale_(self, s):
		return self.sym[f'enclosure_scale_{s}']
	def enclosure_scale_active_(self, s):
		return self.sym[f'enclosure_scale_active_{s}']
	def enclosure_scale_vertical_(self, s):
		return self.sym[f'enclosure_scale_vertical_{s}']
	def insert_x_scale_(self, s):
		return self.sym[f'insert_x_scale_{s}']
	def insert_y_scale_(self, s):
		return self.sym[f'insert_y_scale_{s}']
	def insert_x_scale_active_(self, s):
		return self.sym[f'insert_x_scale_active_{s}']
	def insert_y_scale_active_(self, s):
		return self.sym[f'insert_y_scale_active_{s}']
	def cap_anchor_start_(self, d):
		return self.sym[f'cap_anchor_start_{d}']
	def cap_anchor_end_(self, d):
		return self.sym[f'cap_anchor_end_{d}']

	def int_to_octal(self, n):
		return f'{n:0{self.len_oct}o}'
	def font_units_to_octal(self, n):
		return self.int_to_octal(self.font_units_to_int(n))
	def font_units_to_octal_reverse(self, n):
		return list(reversed(self.font_units_to_octal(n)))
	def int_to_octal_reverse(self, n):
		return list(reversed(self.int_to_octal(n)))
	def to_octal_width(self, n):
		return [self.width_(d) for d in self.font_units_to_octal_reverse(n)] # , exclusive=exclusive)]
	def to_octal_height(self, n):
		return [self.height_(d) for d in self.font_units_to_octal_reverse(n)] # , exclusive=exclusive)]
	def to_octal_width_full(self, n):
		return [self.width_full_(d) for d in self.font_units_to_octal_reverse(n)]
	def to_octal_height_full(self, n):
		return [self.height_full_(d) for d in self.font_units_to_octal_reverse(n)]
	def to_octal_limit_width(self, n):
		return [self.limit_width_(d) for d in self.font_units_to_octal_reverse(n)]
	def to_octal_limit_height(self, n):
		return [self.limit_height_(d) for d in self.font_units_to_octal_reverse(n)]
	def to_octal_insert_signed(self, n):
		sign = [self.minus_insert] if n < 0 else []
		return sign + [self.insert_(d) for d in self.font_units_to_octal_reverse(abs(n))]
	def to_octal_size_full_scaled(self, n):
		return [self.size_full_scaled_(d) for d in self.font_units_to_octal_reverse(n)]
	def octal_max_width(self):
		return self.len_oct * [self.limit_width_(7)]
	def octal_max_height(self):
		return self.len_oct * [self.limit_height_(7)]
	def to_octal_size(self, n):
		return [self.size_(d) for d in self.font_units_to_octal_reverse(n)]
	def int_to_octal_size(self, n):
		return [self.size_(d) for d in self.int_to_octal_reverse(n)]

	# for padding analysis
	def content_width_(self, sc):
		return self.sym[f'content_width_{sc}']
	def content_height_(self, sc):
		return self.sym[f'content_height_{sc}']
	def content_width_active_(self, sc):
		return self.sym[f'content_width_active_{sc}']
	def content_height_active_(self, sc):
		return self.sym[f'content_height_active_{sc}']
	def width_full_(self, d):
		return self.sym[f'width_full_{d}']
	def height_full_(self, d):
		return self.sym[f'height_full_{d}']
	def size_full_(self, d):
		return self.sym[f'size_full_{d}']
	def diff_(self, d):
		return self.sym[f'diff_{d}']
	def width_full_scaled_(self, d):
		return self.sym[f'width_full_scaled_{d}']
	def height_full_scaled_(self, d):
		return self.sym[f'height_full_scaled_{d}']
	def size_full_scaled_(self, d):
		return self.sym[f'size_full_scaled_{d}']
	def bit_(self, b):
		return self.sym[f'bit_{b}']
	def quotient_(self, b):
		return self.sym[f'quotient_{b}']
	def remain_(self, n):
		return self.sym[f'remain_{n}']
	def remain_final_(self, n):
		return self.sym[f'remain_final_{n}']
	def pos_unreverse_(self, p):
		return self.sym[f'pos_unreverse_{p}']

	def to_binary(self, n):
		return [self.bit_(b) for b in int_to_binary(n)]
	def to_binary_quotient(self, n):
		return [self.quotient_(b) for b in int_to_binary(n)]

	# for shading
	def left_shade_pos_(self, p):
		return self.sym[f'left_shade_pos_{p}']
	def half_left_shade_pos_(self, p):
		return self.sym[f'half_left_shade_pos_{p}']
	def half_right_shade_pos_(self, p):
		return self.sym[f'half_right_shade_pos_{p}']
	def down_shade_pos_(self, p):
		return self.sym[f'down_shade_pos_{p}']
	def half_down_shade_pos_(self, p):
		return self.sym[f'half_down_shade_pos_{p}']
	def w_shade_pos_(self, p):
		return self.sym[f'w_shade_pos_{p}']
	def h_shade_pos_(self, p):
		return self.sym[f'h_shade_pos_{p}']
	def half_w_shade_pos_(self, p):
		return self.sym[f'half_w_shade_pos_{p}']
	def half_h_shade_pos_(self, p):
		return self.sym[f'half_h_shade_pos_{p}']
	def left_shade_(self, d, p):
		return self.sym[f'left_shade_{d}_{p}']
	def right_shade_(self, d, p):
		return self.sym[f'right_shade_{d}_{p}']
	def down_shade_(self, d, p):
		return self.sym[f'down_shade_{d}_{p}']
	def w_shade_(self, d, p):
		return self.sym[f'w_shade_{d}_{p}']
	def h_shade_(self, d, p):
		return self.sym[f'h_shade_{d}_{p}']
	def shade_(self, d1, d2, p1, p2):
		return self.sym[f'shade_{d1}_{d2}_{p1}_{p2}']

	# for substitution
	def pos_bracket_(self, p):
		return self.sym[f'pos_bracket_{p}']
	def bracket_anchor_(self, d):
		return self.sym[f'bracket_anchor_{d}']
	def outline_(self, level, sc, direction, d, p):
		return self.sym[f'{level}_outline_{sc}_{direction}_{d}_{p}']
	def outline_pos_(self, level, sc, direction, p):
		return self.sym[f'{level}_outline_pos_{sc}_{direction}_{p}']

	# for positioning
	def to_advance_(self, p):
		return self.sym[f'to_advance_{p}']
	def advance_w_(self, d, p):
		adv = d * 8**p
		return self.sym[f'advance_w_{adv}']
	def advance_h_(self, d, p):
		adv = d * 8**p
		return self.sym[f'advance_h_{adv}']
	def advance_w_base_(self, d, p):
		adv = d * 8**p
		return self.sym[f'advance_w_base_{adv}']
	def advance_h_base_(self, d, p):
		adv = d * 8**p
		return self.sym[f'advance_h_base_{adv}']
	def anchor_pad_w_(self, d, p):
		adv = d * 8**p
		return self.sym[f'anchor_pad_w_{adv}']
	def anchor_pad_h_(self, d, p):
		adv = d * 8**p
		return self.sym[f'anchor_pad_h_{adv}']
	def mid_w_(self, d, p):
		adv = d * 8**p
		return self.sym[f'mid_w_{adv}']
	def mid_h_(self, d, p):
		adv = d * 8**p
		return self.sym[f'mid_h_{adv}']
	def anchor_start_(self, depth):
		return self.sym[f'anchor_start_{depth}']
	def anchor_end_(self, depth):
		return self.sym[f'anchor_end_{depth}']
	def anchor_end_w_(self, depth):
		return self.sym[f'anchor_end_w_{depth}']
	def anchor_end_h_(self, depth):
		return self.sym[f'anchor_end_h_{depth}']
	def anchor_start_insert_(self, depth):
		return self.sym[f'anchor_start_insert_{depth}']
	def anchor_end_insert_(self, depth):
		return self.sym[f'anchor_end_insert_{depth}']
	def anchor_insert_mid_(self, depth):
		return self.sym[f'anchor_insert_mid_{depth}']

	def make_classes(self):

		self.class_names = set()

		# for syntactic analysis

		self.add_class('@OpeningPlain', self.openings_plain + self.openings_plain_rot)
		self.add_class('@OpeningWalled', self.openings_walled + self.openings_walled_rot)
		self.add_class('@Opening', ['@OpeningPlain', '@OpeningWalled'])
		self.add_class('@ClosingPlain', self.closings_plain + self.closings_plain_rot)
		self.add_class('@ClosingWalled', self.closings_walled + self.closings_walled_rot)
		self.add_class('@Closing', ['@ClosingPlain', '@ClosingWalled'])
		self.add_class('@Cap', self.caps + self.caps_rot)
		self.add_class('@OpenBracket', self.open_brackets)
		self.add_class('@CloseBracket', self.close_brackets)
		self.add_class('@Bracket', self.brackets)

		self.add_class('@Insertion', self.insertions)
		self.add_class('@BinOp', self.bin_ops)
		self.add_class('@BeginAnyEnclosure', self.begin_any_enclosure)
		self.add_class('@EndAnyEnclosure', self.end_any_enclosure)

		self.add_class('@Undoneopen', [self.open_(level) for level in all_levels])
		self.add_class('@Undoneclose', [self.close_(level) for level in all_levels])
		self.add_class('@Undone', ['@Undoneopen', '@Undoneclose'])

		self.add_class('@Do', \
			[self.open_do_(level) for level in all_levels] + \
			[self.close_do_(level) for level in all_levels])
	
		self.add_class('@Outeropen', [self.open_outer_(level) for level in all_levels])
		self.add_class('@Outerclose', [self.close_outer_(level) for level in all_levels])
		self.add_class('@Outer', ['@Outeropen', '@Outerclose'])
	
		self.add_class('@Inneropen', [self.open_inner_(level) for level in all_levels])
		self.add_class('@Innerclose', [self.close_inner_(level) for level in all_levels])
		self.add_class('@Inner', ['@Inneropen', '@Innerclose'])

		self.add_class('@OuterInner', ['@Outer', '@Inner'])
		self.add_class('@UndoneDoOuter', ['@Undone', '@Do', '@Outer'])
		self.add_class('@UndoneOuterInner', ['@Undone', '@OuterInner'])

		self.add_class('@Depth', [self.depth_(depth) for depth in self.all_depths])
		self.add_class('@Depthactive', [self.depth_active_(depth) for depth in self.all_depths])
		self.add_class('@DepthAny', ['@Depth', '@Depthactive'])

		# for local analysis

		self.add_class('@Count', [self.count_(c) for c in all_counts])
		self.add_class('@Length', [self.length_(c) for c in nonzero_counts])
		self.add_class('@Limitwidth', [self.limit_width_(d) for d in all_digits])
		self.add_class('@Limitheight', [self.limit_height_(d) for d in all_digits])
		self.add_class('@Limitsize', [self.limit_size_(d) for d in all_digits])
		self.add_class('@Insertionactive', self.insertions_active)
		self.add_class('@Usedplace', self.used_places)

		self.add_class('@OuterCount', ['@Outer', '@Count'])

		self.add_class('@Recordactive', [self.record_active])
		self.add_class('@RecordNil', [self.record, self.nil])

		self.add_class('@Direction', [self.horizontal, self.vertical])
		self.add_class('@Directionactive', [self.horizontal_active, self.vertical_active])

		self.add_class('@InsertionBase', self.insertion_base_list)
		self.add_class('@InsertionBaseOverlay', self.insertion_base_overlay_list)
		self.add_class('@InsertionCopy1', [self.name_to_insertion_copy1[name] for name in self.insertion_base_list])

		# for scale analysis

		self.add_class('@Width', [self.width_(d) for d in all_digits])
		self.add_class('@Height', [self.height_(d) for d in all_digits])
		self.add_class('@Widthscaled', [self.width_scaled_(d) for d in all_digits])
		self.add_class('@Heightscaled', [self.height_scaled_(d) for d in all_digits])
		self.add_class('@Widthscaledactive', [self.width_scaled_active_(d) for d in all_digits])
		self.add_class('@Heightscaledactive', [self.height_scaled_active_(d) for d in all_digits])
		self.add_class('@Widthscaledlatent', [self.width_scaled_latent_(d) for d in all_digits])
		self.add_class('@Heightscaledlatent', [self.height_scaled_latent_(d) for d in all_digits])
		self.add_class('@Widthscaledlatentactive', [self.width_scaled_latent_active_(d) for d in all_digits])
		self.add_class('@Heightscaledlatentactive', [self.height_scaled_latent_active_(d) for d in all_digits])

		self.add_class('@Size', [self.size_(d) for d in all_digits])
		self.add_class('@Sizereverse', [self.size_reverse_(d) for d in all_digits])
		self.add_class('@Sizefirst', [self.size_first_(d) for d in all_digits])
		self.add_class('@Sizescaled', [self.size_scaled_(d) for d in all_digits])

		self.add_class('@Scale', [self.scale_(s) for s in self.all_scales + [self.n_scales]])
		self.add_class('@Scalehidden', [self.scale_hidden_(s) for s in self.all_scales + [self.n_scales]])
		self.add_class('@ScalehiddenNonlast', [self.scale_hidden_(s) for s in self.all_scales[:-1]])

		self.add_class('@Widthscale', [self.width_scale_(s) for s in self.all_scales])
		self.add_class('@Heightscale', [self.height_scale_(s) for s in self.all_scales])
		self.add_class('@Widthscaleactive', [self.width_scale_active_(s) for s in self.all_scales])
		self.add_class('@Heightscaleactive', [self.height_scale_active_(s) for s in self.all_scales])
		self.add_class('@Widthscalelatent', [self.width_scale_latent_(s) for s in self.all_scales])
		self.add_class('@Heightscalelatent', [self.height_scale_latent_(s) for s in self.all_scales])
		self.add_class('@Widthscalelatentactive', [self.width_scale_latent_active_(s) for s in self.all_scales])
		self.add_class('@Heightscalelatentactive', [self.height_scale_latent_active_(s) for s in self.all_scales])

		self.add_class('@Scalegroup', [self.scale_group_(s) for s in self.all_scales])
		self.add_class('@Scalegroupactive', [self.scale_group_active_(s) for s in self.all_scales])

		self.add_class('@Capscale', [self.cap_scale_(s) for s in self.all_scales])
		self.add_class('@Capscaleactive', [self.cap_scale_active_(s) for s in self.all_scales])
		self.add_class('@Enclosurescale', [self.enclosure_scale_(s) for s in self.all_scales])
		self.add_class('@Enclosurescaleactive', [self.enclosure_scale_active_(s) for s in self.all_scales])
		self.add_class('@Insert', [self.insert_(d) for d in all_digits])
		self.add_class('@Insertxscale', [self.insert_x_scale_(s) for s in self.all_scales])
		self.add_class('@Insertyscale', [self.insert_y_scale_(s) for s in self.all_scales])
		self.add_class('@Insertxscaleactive', [self.insert_x_scale_active_(s) for s in self.all_scales])
		self.add_class('@Insertyscaleactive', [self.insert_y_scale_active_(s) for s in self.all_scales])

		self.add_class('@OuterWidth', ['@Outer', '@Width'])
		self.add_class('@OuterHeight', ['@Outer', '@Height'])
		self.add_class('@OuterSize', ['@Outer', '@Size'])
		self.add_class('@OuterNil', ['@Outer', self.nil])
		self.add_class('@Posreverse', [self.pos_reverse_(p) for p in self.all_poss])
		self.add_class('@Posreversefinal', [self.pos_reverse_final_(p) for p in self.all_poss])

		self.add_class('@Carry', [self.carry_(d) for d in all_digits])
		self.add_class('@NoCarry', ['@Size', self.size_sep])
		self.add_class('@MaybeCarry', ['@Carry', '@NoCarry'])
		self.add_class('@Sizescaledcarry', [self.size_scaled_carry_(d) for d in all_digits])
		for d in all_down_carry:
			self.add_class(f'@DownCarry{d}', (['@Scale'] if d == 0 else []) + \
				[self.size_scaled_(n) for n in all_digits if n * 6 % 8 == d] + \
				[self.size_scaled_carry_(n) for n in all_digits if n * 6 % 8 == d])

		self.add_class('@Lt', [self.lt_(d) for d in all_digits])
		self.add_class('@Gt', [self.gt_(d) for d in all_digits])
		self.add_class('@Eq', [self.eq_(d) for d in all_digits])
		self.add_class('@Cmp', ['@Lt', '@Gt', '@Eq'])
		for d in all_digits:
			self.add_class(f'@MaxAny{d}', [self.size_reverse_(d), self.lt_(d), self.gt_(d)])
		self.add_class('@MaxAny', [f'@MaxAny{d}' for d in all_digits] + [self.size_reverse_sep])

		# for padding analysis

		self.add_class('@Bit', [self.bit_(b) for b in [0,1]])
		self.add_class('@Quotient', [self.quotient_(b) for b in [0,1]])
		self.add_class('@Remain', [self.remain_(n) for n in all_remainders])
		self.add_class('@RemainFinal', [self.remain_final_(n) for n in all_remainders])
		self.add_class('@Posunreverse', [self.pos_unreverse_(p) for p in self.all_poss])
		self.add_class('@SizeFull', [self.size_full_(d) for d in all_digits])
		self.add_class('@WidthFull', [self.width_full_(d) for d in all_digits])
		self.add_class('@HeightFull', [self.height_full_(d) for d in all_digits])
		self.add_class('@WidthFullScaled', [self.width_full_scaled_(d) for d in all_digits])
		self.add_class('@HeightFullScaled', [self.height_full_scaled_(d) for d in all_digits])
		self.add_class('@SizeFullScaled', [self.size_full_scaled_(d) for d in all_digits])
		self.add_class('@Contentwidthactive', [self.content_width_active_(sc) for sc in self.all_scales[1:]])
		self.add_class('@Contentheightactive', [self.content_height_active_(sc) for sc in self.all_scales[1:]])

		# for substitution

		self.add_class('@PosBracket', [self.pos_bracket_(p) for p in self.all_poss])
		self.add_class('@BracketScaled', self.brackets_scaled)
		self.add_class('@BracketScaledLarger', [self.bracket_scale_to_bracket[(bracket, sc)] \
				for bracket in self.brackets for sc in self.all_scales if sc+1 < self.n_scales])

		# for shading

		self.add_class('@WShadePos', \
			[self.left_shade_pos_(p) for p in self.all_poss] +
			[self.half_left_shade_pos_(p) for p in self.all_poss] +
			[self.half_right_shade_pos_(p) for p in self.all_poss] +
			[self.w_shade_pos_(p) for p in self.all_poss] +
			[self.half_w_shade_pos_(p) for p in self.all_poss])
		self.add_class('@HShadePos', \
			[self.down_shade_pos_(p) for p in self.all_poss] +
			[self.half_down_shade_pos_(p) for p in self.all_poss] +
			[self.h_shade_pos_(p) for p in self.all_poss] +
			[self.half_h_shade_pos_(p) for p in self.all_poss])
		self.add_class('@WidthFullOdd', [self.width_full_(d) for d in odd_digits])
		self.add_class('@HeightFullOdd', [self.height_full_(d) for d in odd_digits])

		# for positioning

		self.add_class('@AnchorStart', [self.anchor_start_(depth) for depth in self.all_depths])
		self.add_class('@AnchorEnd', [self.anchor_end_(depth) for depth in self.all_depths])
		self.add_class('@AnchorEndW', [self.anchor_end_w_(depth) for depth in self.all_depths])
		self.add_class('@AnchorEndH', [self.anchor_end_h_(depth) for depth in self.all_depths])
		self.add_class('@Anchorinsertmid', [self.anchor_insert_mid_(depth) for depth in self.all_depths[:-1]])
		self.add_class('@ToAdvance', [self.to_advance_(p) for p in self.all_poss])
		self.add_class('@CapAnchorStart', [self.cap_anchor_start_(d) for d in self.all_depths])
		self.add_class('@CapAnchorEnd', [self.cap_anchor_end_(d) for d in self.all_depths])
		self.add_class('@Outlinepos', [self.outline_pos_(level, sc, direction, p) \
			for level in 'pw' for sc in self.all_scales for direction in ['hor', 'ver'] \
			for p in self.all_poss])
		self.add_class('@InsertW', [self.insert_w_(d, p) for d in all_digits[1:] for p in self.all_poss] + \
				[self.insert_w_(-d, p) for d in all_digits[1:] for p in self.all_poss])
		self.add_class('@InsertH', [self.insert_h_(d, p) for d in all_digits[1:] for p in self.all_poss] + \
				[self.insert_h_(-d, p) for d in all_digits[1:] for p in self.all_poss])

	###### Insertions

	def default_geom(self, pl):
		match pl:
			case 'ts': x, y, w, h = -400, 400, 400, 400
			case 'bs': x, y, w, h = -400, -400, 400, 400
			case 'te': x, y, w, h = 400, 400, 400, 400
			case 'be': x, y, w, h = 400, -400, 400, 400
			case 'm': x, y, w, h = 0, 0, 400, 400
			case 't': x, y, w, h = 0, 400, 400, 400
			case 'b': x, y, w, h = 0, -400, 400, 400
		return x, y, w, h

	def geometries(self, ch, rotate, insertion_places, out):
		options = Options(fontsize=self.em_exclusive)
		w_em, h_em = em_size_of(ch, options, 1, 1, rotate, False)
		printed = PrintedPilWithoutExtras(options, 3, 3)
		printed.add_sign(ch, 1, 1, 1, rotate, False, Rectangle(1, 1, w_em, h_em))
		plane = PlaneRestricted(printed.im)
		x_min, y_min, w, h = plane.bbox()
		x_max = x_min + w - 1
		y_max = y_min + h - 1
		x_center = x_min + w // 2
		y_center = y_min + h // 2
		if x_min is None:
			return {}, 0, 0, 0, 0
		insertions = []
		for place, adjustments in insertion_places.items():
			x_relative, y_relative = insertion_position(place, adjustments)
			x_absolute = min(x_min + round(x_relative * w), x_max)
			y_absolute = min(y_min + round(y_relative * h), y_max)
			insertions.append(MeasuredInsertion(place, x_absolute, y_absolute))
		change = True
		while change:
			change = False
			for ins in insertions:
				if x_min < ins.x or ('s' in out and ins.ext_left <= ins.ext_right):
					left = ins.left_strip()
					if plane.topmost_dark(*left) is None:
						ins.extend_left()
						for y in range(left[1], left[2]+1): plane.set_dark(left[0], y)
						change = True
				if ins.x_max() < x_max or ('e' in out and ins.ext_right <= ins.ext_left):
					right = ins.right_strip()
					if plane.topmost_dark(*right) is None:
						ins.extend_right()
						for y in range(right[1], right[2]+1): plane.set_dark(right[0], y)
						change = True
				if y_min < ins.y or ('t' in out and ins.ext_top <= ins.ext_bottom):
					top = ins.top_strip()
					if plane.leftmost_dark(*top) is None:
						ins.extend_top()
						for x in range(top[0], top[1]+1): plane.set_dark(x, top[2])
						change = True
				if ins.y_max() < y_max or ('b' in out and ins.ext_bottom <= ins.ext_top):
					bottom = ins.bottom_strip()
					if plane.leftmost_dark(*bottom) is None:
						ins.extend_bottom()
						for x in range(bottom[0], bottom[1]+1): plane.set_dark(x, bottom[2])
						change = True
		s_margin = max(0, max((x_min - ins.x) for ins in insertions))
		e_margin = max(0, max((ins.x_max() - x_max) for ins in insertions))
		t_margin = max(0, max((y_min - ins.y) for ins in insertions))
		b_margin = max(0, max((ins.y_max() - y_max) for ins in insertions))
		return {ins.place: ( (ins.x_center() - x_center) * self.resolution, (y_center - ins.y_center()) * self.resolution, \
					ins.w * self.resolution, ins.h * self.resolution ) for ins in insertions}, \
				s_margin * self.resolution, e_margin * self.resolution, t_margin * self.resolution, b_margin * self.resolution

	def name_rot_places_to_variant(self, name, rot, places):
		for alt_places, alt_name in self.name_rot_to_places_variant[(name, rot)]:
			if all(place in alt_places for place in places):
				return alt_name
		return name

	###### Syntax analysis

	def syntax_analysis(self):
		"""
		basic: put brackets around basic elements, and add bracket-close after modifier, and
			add horizontal joiners before/after parentheses.
		modifier: remove joiner before, to join it with basic element.
		enclosure_combine: combine caps with bare enclosure.
		top_group: add brackets at start and end of top group.
		empty_parenthesis1 and empty_parenthesis2: remove inner part of enclosure with empty content.
		parenthesis: replace parentheses with brackets.
		operator: replace operators by brackets.
		literal: make all literals depth 0.
		compress_bracket: remove unit rules from parse.
		do: pick bracket pair, not considered before, around finished subparse.
		depth: allow depths to be updated (make them active).
		inner: within picked bracket pair, turn outer bracket into inner brackets and increment all depths.
		outer: turn picked bracket pair to outer bracket pair.
		bracket_reset: remove outer/inner from brackets.
		depth_reset: remove active from depths.
		simplify: remove brackets around parentheses.
		compress_nil: turn sequences of removed symbols (nils) into single nils.
		nil: remove nils.
		"""
		chunk_size = 1000
		for i in range(0, len(self.unmirrored_signs), chunk_size):
			self.add_main_lookup(*self.sign_rules(i, self.unmirrored_signs[i:i + chunk_size]))
		self.add_main_lookup(*self.basic_rules())
		self.add_main_lookup(*self.modifier_rules())
		self.add_sub_lookup(*self.plain_enclosure_replace_begin_subrules())
		self.add_sub_lookup(*self.plain_enclosure_replace_end_subrules())
		self.add_sub_lookup(*self.walled_enclosure_replace_begin_subrules())
		self.add_sub_lookup(*self.walled_enclosure_replace_end_subrules())
		self.add_main_lookup(*self.enclosure_combine_rules())
		self.add_sub_lookup(*self.top_open_subrules())
		self.add_sub_lookup(*self.top_close_subrules())
		self.add_main_lookup(*self.top_group_rules())
		self.add_main_lookup(*self.empty_parenthesis1_rules())
		self.add_main_lookup(*self.empty_parenthesis2_rules())
		self.add_main_lookup(*self.parenthesis_rules())
		self.add_main_lookup(*self.operator_rules())
		self.add_main_lookup(*self.literal_rules())
		self.add_sub_lookup(*self.del_subrules())
		self.add_main_lookup(*self.compress_bracket_rules())
		self.add_sub_lookup(*self.make_do_subrules())
		for d in range(self.max_depth-1):
			self.add_main_lookup(*self.do_rules())
			self.add_main_lookup(*self.depth_rules())
			self.add_main_lookup(*self.inner_rules())
			self.add_main_lookup(*self.outer_rules())
			self.add_main_lookup(*self.compress_bracket_rules())
		self.add_main_lookup(*self.bracket_reset_rules())
		self.add_main_lookup(*self.depth_reset_rules())
		self.add_main_lookup(*self.simplify_rules())
		self.add_main_lookup(*self.compress_nil_rules())
		self.add_main_lookup(*self.nil_rules())
		self.add_sub_lookup(*self.add_record_subrules())
		self.add_main_lookup(*self.record_rules())

	def sign_rules(self, i, signs):
		name, rules = f'sign-{i}', []
		for sign in signs:
			rules.append(simple_sub_rule([sign], [self.open_('b'), sign, self.close_('b')]))
		return name, rules

	def basic_rules(self):
		name, rules = 'basic', []
		for extra in self.caps + self.blanks + self.losts:
			rules.append(simple_sub_rule([extra], [self.open_('b'), extra, self.close_('b')]))
		for mod in self.modifiers:
			rules.append(simple_sub_rule([mod], [mod, self.close_('b')]))
		for bracket in self.open_brackets:
			rules.append(simple_sub_rule([bracket], [self.open_('b'), bracket, self.close_('b'), self.hor]))
		for bracket in self.close_brackets:
			rules.append(simple_sub_rule([bracket], [self.hor, self.open_('b'), bracket, self.close_('b')]))
		return name, rules

	def modifier_rules(self):
		name, rules = 'modifier', []
		for mod in self.modifiers:
			rules.append(simple_sub_rule([self.close_('b'), mod], [mod]))
		return name, rules

	def plain_enclosure_replace_begin_subrules(self):
		name, rules = 'plain-enclosure-replace-begin', []
		rules.append(simple_sub_rule([self.open_('b')], [self.open_('p')]))
		rules.append(simple_sub_rule([self.close_('b')], [self.nil]))
		rules.append(simple_sub_rule([self.begin_plain_enclosure], [self.open_('p'), self.begin_plain_enclosure]))
		return name, rules

	def plain_enclosure_replace_end_subrules(self):
		name, rules = 'plain-enclosure-replace-end', []
		rules.append(simple_sub_rule([self.open_('b')], [self.nil]))
		rules.append(simple_sub_rule([self.close_('b')], [self.close_('p')]))
		rules.append(simple_sub_rule([self.end_plain_enclosure], [self.end_plain_enclosure, self.close_('p')]))
		return name, rules

	def walled_enclosure_replace_begin_subrules(self):
		name, rules = 'walled-enclosure-replace-begin', []
		rules.append(simple_sub_rule([self.open_('b')], [self.open_('w')]))
		rules.append(simple_sub_rule([self.close_('b')], [self.nil]))
		rules.append(simple_sub_rule([self.begin_walled_enclosure], [self.open_('w'), self.begin_walled_enclosure]))
		return name, rules

	def walled_enclosure_replace_end_subrules(self):
		name, rules = 'walled-enclosure-replace-end', []
		rules.append(simple_sub_rule([self.open_('b')], [self.nil]))
		rules.append(simple_sub_rule([self.close_('b')], [self.close_('w')]))
		rules.append(simple_sub_rule([self.end_walled_enclosure], [self.end_walled_enclosure, self.close_('w')]))
		return name, rules

	def enclosure_combine_rules(self):
		name, rules, filt = 'enclosure-combine', [], '@AuxEnclosureCombine'
		self.add_class(filt, [self.open_('b'), self.close_('b'), '@Cap',
			'@BeginAnyEnclosure', '@EndAnyEnclosure', self.begin_segment, self.end_segment])
		for begin, lookup in [\
					(self.begin_plain_enclosure, 'plain-enclosure-replace-begin'),
					(self.begin_walled_enclosure, 'walled-enclosure-replace-begin')]:
			rules.append(chain_sub_rule([], [\
				(self.open_('b'), [lookup]), ('@Opening', []), (self.close_('b'), [lookup]), (begin, [])], []))
			rules.append(chain_sub_rule([], [(begin, [lookup])], []))
		for end, lookup in [\
					(self.end_plain_enclosure, 'plain-enclosure-replace-end'),
					(self.end_walled_enclosure, 'walled-enclosure-replace-end')]:
			rules.append(chain_sub_rule([], [\
				(end, []), (self.open_('b'), [lookup]), ('@Closing', []), (self.close_('b'), [lookup])], []))
			rules.append(chain_sub_rule([], [(end, [lookup])], []))
		return name, rules, filt

	def top_open_subrules(self):
		name, rules = 'top-open', []
		firsts = [self.open_(level) for level in bottom_levels] + [self.begin_segment]
		open_seq = [self.open_(level) for level in level_seq]
		for first in firsts:
			rules.append(simple_sub_rule([first], open_seq + [first]))
		return name, rules

	def top_close_subrules(self):
		name, rules = 'top-close', []
		lasts = [self.close_(level) for level in bottom_levels] + [self.end_segment]
		close_seq = list(reversed([self.close_(level) for level in level_seq]))
		for last in lasts:
			rules.append(simple_sub_rule([last], [last] + close_seq))
		return name, rules

	def top_group_rules(self):
		name, rules = 'top-group', []
		self.add_class('@AuxTopGroupOpen', ['@BinOp', self.begin_segment, '@BeginAnyEnclosure'])
		self.add_class('@AuxTopGroupClose', ['@BinOp', self.end_segment, '@EndAnyEnclosure'])
		for first in [self.open_(level) for level in bottom_levels] + [self.begin_segment]:
			rules.append(ignore_sub_rule(['@AuxTopGroupOpen'], [first], []))
			rules.append(chain_sub_rule([], [(first, ['top-open'])], []))
		for last in [self.close_(level) for level in bottom_levels] + [self.end_segment]:
			rules.append(ignore_sub_rule([], [last], ['@AuxTopGroupClose']))
			rules.append(chain_sub_rule([], [(last, ['top-close'])], []))
		return name, rules

	def empty_parenthesis1_rules(self):
		name, rules = 'empty-parenthesis1', []
		rules.append(simple_sub_rule([self.begin_plain_enclosure, self.end_plain_enclosure], [self.nil]))
		rules.append(simple_sub_rule([self.begin_walled_enclosure, self.end_walled_enclosure], [self.nil]))
		return name, rules

	def empty_parenthesis2_rules(self):
		name, rules = 'empty-parenthesis2', []
		for level in 'pw':
			rules.append(simple_sub_rule([self.open_(level), self.nil], [self.open_(level)]))
		return name, rules

	def parenthesis_rules(self):
		name, rules = 'parenthesis', []
		open_seq = [self.open_(level) for level in level_seq]
		close_seq = list(reversed([self.close_(level) for level in level_seq]))
		for begin in self.begin_any_enclosure + [self.begin_segment]:
			rules.append(simple_sub_rule([begin], open_seq))
		for end in self.end_any_enclosure + [self.end_segment]:
			rules.append(simple_sub_rule([end], close_seq))
		return name, rules

	def operator_rules(self):
		name, rules = 'operator', []
		for op, rev_levels, levels in [(self.ver, 'oih', 'hio'), (self.hor, 'oi', 'io')]:
			rules.append(simple_sub_rule([op], 
				[self.close_(level) for level in rev_levels] + [self.open_(level) for level in levels]))
		for op in self.insertions:
			rules.append(simple_sub_rule([op], [self.close_('o'), op, self.open_('o')]))
		rules.append(simple_sub_rule([self.overlay], [self.nil]))
		return name, rules

	def literal_rules(self):
		name, rules = 'literal', []
		rules.append(simple_sub_rule([self.open_('b')], [self.open_outer_('b'), self.depth_('0')]))
		rules.append(simple_sub_rule([self.close_('b')], [self.depth_('0'), self.close_outer_('b')]))
		return name, rules

	def del_subrules(self):
		name, rules = 'del', []
		rules.append(simple_sub_rule(['@Undone'], [self.nil]))
		return name, rules

	def compress_bracket_rules(self):
		# A -> vhiob
		# A+B -> vhio
		# A^B -> ob vhi
		# A*B -> iob vh
		# A:B -> hiob 
		#
		# A^B+C -> ob vhi
		# A^B*C -> ob iob vh
		# A^B:C -> ob hi hiob
		# A+B*C -> io iob vh
		# A+B:C -> hio hiob
		#
		# A^(B:C) -> ov
		# A^(B*C) -> ovh
		# A^(A^B) -> ovhi
		# A*(B:C) -> iov
		# A+(A:B) -> vhio ob hiob
		# (A*B)+C -> vhio iob ovh
		name, rules, filt = 'compress-bracket', [], '@UndoneDoOuter'
		sequences = ['ov', 'ovh', 'ovhi', 'iov']
		for level in bottom_levels:
			levels = level_seq + level
			n = len(levels)
			for i in range(n-1):
				for j in range(n-i, 1, -1):
					sequences.append(levels[i:i+j])
		for seq in sorted(set(sequences), key=len, reverse=True):
			init = seq[:-1]
			fin = seq[-1]
			prefix = [(self.open_(level), ['del']) for level in init] + \
				[(self.open_outer_(fin), [])]
			suffix = list(reversed([(self.close_(level), ['del']) for level in init] + \
				[(self.close_outer_(fin), [])]))
			rules.append(chain_sub_rule([], prefix + suffix, []))
		return name, rules, filt

	def make_do_subrules(self):
		name, rules = 'make-do', []
		for level in upper_levels:
			rules.append(simple_sub_rule([self.open_(level)], [self.open_do_(level)]))
			rules.append(simple_sub_rule([self.close_(level)], [self.close_do_(level)]))
		return name, rules

	def do_rules(self):
		name, rules, filt = 'do', [], '@Undone'
		for level in upper_levels:
			rules.append(chain_sub_rule([], \
				[(self.open_(level), ['make-do']), (self.close_(level), ['make-do'])], []))
		return name, rules, filt

	def depth_rules(self):
		name, rules, filt = 'depth', [], '@DepthAny'
		for depth in self.all_depths:
			rules.append(simple_sub_rule([self.depth_(depth)], [self.depth_active_(depth)]))
		return name, rules, filt

	def inner_rules(self):
		name, rules, filt = 'inner', [], '@AuxInner'
		self.add_class(filt, ['@Do', '@Outer', '@Depthactive'])
		for level1 in upper_levels:
			for level2 in all_levels:
				rules.append(context_sub_rule([self.open_do_(level1)], self.open_outer_(level2), [], self.open_inner_(level2)))
				rules.append(context_sub_rule([self.open_do_(level1)], self.close_outer_(level2), [], self.close_inner_(level2)))
			for depth in self.all_depths[:-1]:
				rules.append(context_sub_rule([self.open_do_(level1)], self.depth_active_(depth), [], self.depth_(depth+1)))
		return name, rules, filt

	def outer_rules(self):
		name, rules, filt = 'outer', [], '@UndoneDoOuter'
		for level in upper_levels:
			rules.append(simple_sub_rule([self.open_do_(level)], [self.open_outer_(level), self.depth_('0')]))
			rules.append(simple_sub_rule([self.close_do_(level)], [self.depth_('0'), self.close_outer_(level)]))
		return name, rules, filt

	def bracket_reset_rules(self):
		name, rules, filt = 'bracket-reset', [], '@AuxBracketReset'
		self.add_class(filt, ['@Outer', '@Inner', '@Directionactive', self.record_active])
		for level in all_levels:
			rules.append(simple_sub_rule([self.open_outer_(level)], [self.open_(level)]))
			rules.append(simple_sub_rule([self.open_inner_(level)], [self.open_(level)]))
			rules.append(simple_sub_rule([self.close_outer_(level)], [self.close_(level)]))
			rules.append(simple_sub_rule([self.close_inner_(level)], [self.close_(level)]))
		rules.append(simple_sub_rule([self.record_active], [self.record]))
		rules.append(simple_sub_rule([self.horizontal_active], [self.horizontal]))
		rules.append(simple_sub_rule([self.vertical_active], [self.vertical]))
		return name, rules, filt

	def depth_reset_rules(self):
		name, rules = 'depth-reset', []
		for depth in self.all_depths:
			rules.append(simple_sub_rule([self.depth_active_(depth)], [self.depth_(depth)]))
		return name, rules

	def simplify_rules(self):
		name, rules = 'simplify', []
		for bracket in self.brackets:
			rules.append(simple_sub_rule([self.open_('b'), '@Depth', bracket, '@Depth', self.close_('b')], [bracket]))
		return name, rules

	def compress_nil_rules(self):
		# largest number of nils to replace 3 brackets on each side of ":".
		name, rules = 'compress-nil', []
		for i in range(2, 7):
			rules.append(simple_sub_rule(i * [self.nil], [self.nil]))
		return name, rules

	def nil_rules(self):
		name, rules, filt = 'nil', [], '@AuxNil'
		self.add_class(filt, [self.nil, '@Undone', '@Bracket', '@Cap'])
		for level in all_levels:
				rules.append(simple_sub_rule([self.nil, self.open_(level)], [self.open_(level)]))
				rules.append(simple_sub_rule([self.close_(level), self.nil], [self.close_(level)]))
		for opening in self.openings:
			rules.append(simple_sub_rule([opening, self.nil], [opening]))
		for closing in self.closings:
			rules.append(simple_sub_rule([self.nil, closing], [closing]))
		for bracket in self.open_brackets:
			rules.append(simple_sub_rule([self.nil, bracket], [bracket]))
		for bracket in self.close_brackets:
			rules.append(simple_sub_rule([bracket, self.nil], [bracket]))
		return name, rules, filt

	def add_record_subrules(self):
		name, rules = 'add-record', []
		for depth in self.all_depths:
			rules.append(simple_sub_rule([self.depth_(depth)], [self.depth_(depth), self.record]))
		return name, rules

	def record_rules(self):
		name, rules, filt = 'record', [], '@AuxRecord'
		self.add_class(filt, ['@Undone', '@Depth', self.record])
		for level in all_levels:
			rules.append(chain_sub_rule([self.open_(level)], [('@Depth', ['add-record'])], []))
		return name, rules, filt

	###### Local analysis

	def local_analysis(self):
		"""
		overlay_flat: add 'flat' to horizontal and vertical subgroups of overlay.
		insertion_expand: in insertion, initially assume there are no places.
		inner_depth: select inner brackets.
		outer_depth: select outer brackets.
		make_places: highlight insertion operators at inner brackets.
		place: record all places of insertions.
		unmake_places: unhighlight insertion operators at inner brackets.
		group_length_init: for horizontal and vertical outer groups, set to receive accumulated count of subgroups.
			and for inner groups, set count 1.
		group_length_sum: sum counts of subgroups.
		group_length_cleanup1: remove counts of inner groups.
		group_length_copy: copy count from close to open of outer group, and make it the length.
		group_length_cleanup2: remove counts of outer groups.
		unused_places1_rules: change unused markers to nils.
		unused_places2_rules: remove these nils.

		overlay_alt_init: add placeholder for variant glyph.
		make_overlay_alt: replace placeholder by variant glyph.
		recur_overlay_alt: remove base glyphs from child elements.
		overlay_alt_fin: remove placeholders.
		[same for 'hor' and 'ver']

		insertion_variant: replace glyph depending on insertions.

		enclosure_hor: add horizontal marker to each enclosure 
		enclosure_ver: change horizontal marker by vertical marker for vertical text direction.
		init_limits: at inner brackets, insert placeholders for limits.
		insertion_copy: highlight base sign of insertion.
		insertion_limits: prepare for limits of subgroups of insertions to be set, by placeholders for base and place.
		insertion_transfer: copy base sign of insertion to each of the inserted groups.
		limits: depending on outer bracket, set limit of inner brackets. Also unhighlight insertion operators.
		top_direction: for top-level groups (other than enclosures, which were already done), add horizontal marker.
		top_init_limits: highlight limits in top group.

		insertion_uncopy: remove highlight of base sign.
		insertion_join: join copy of base sign and place into one character.
		insertion_geom: replace that character with the geometry.
		insertion_default: if no combination of base sign and place could be found, take default geometry.
		insertion_cleanup1: turn unused base sign into nil.
		insertion_cleanup2: clean up nil.
		topgroup_ver_limits: for vertical text, set limits of top group. 
			And turn horizontal markers into vertical markers. Also rotate caps. 
		topgroup_hor_limits: for horizontal text, set limits of top group.
		"""
		self.add_sub_lookup(*self.overlay_flat_record_subrules())
		self.add_main_lookup(*self.overlay_flat_rules())
		self.add_main_lookup(*self.insertion_expand_rules())
		for d in range(self.max_depth-1, 0, -1):
			self.add_main_lookup(*self.inner_depth_rules(d))
			self.add_main_lookup(*self.outer_depth_rules(d-1))
			self.add_main_lookup(*self.make_places_rules())
			self.add_main_lookup(*self.place_rules())
			self.add_main_lookup(*self.unmake_places_rules())
			self.add_main_lookup(*self.group_length_init_rules())
			self.add_main_lookup(*self.group_length_sum_rules())
			self.add_main_lookup(*self.group_length_cleanup1_rules())
			self.add_main_lookup(*self.group_length_copy_rules())
			self.add_main_lookup(*self.group_length_cleanup2_rules())
			self.add_main_lookup(*self.bracket_reset_rules())
		self.add_main_lookup(*self.unused_places1_rules())
		self.add_main_lookup(*self.unused_places2_rules())

		self.add_sub_lookup(*self.overlay_alt_subrules())
		self.add_main_lookup(*self.overlay_alt_init_rules())
		self.add_main_lookup(*self.make_overlay_alt_rules())
		self.add_main_lookup(*self.recur_overlay_alt_rules())
		self.add_main_lookup(*self.overlay_alt_fin_rules())

		self.add_sub_lookup(*self.hor_alt_subrules())
		self.add_main_lookup(*self.hor_alt_init_rules())
		self.add_main_lookup(*self.make_hor_alt_rules())
		self.add_main_lookup(*self.recur_hor_alt_rules())
		self.add_main_lookup(*self.hor_alt_fin_rules())

		self.add_sub_lookup(*self.ver_alt_subrules())
		self.add_main_lookup(*self.ver_alt_init_rules())
		self.add_main_lookup(*self.make_ver_alt_rules())
		self.add_main_lookup(*self.recur_ver_alt_rules())
		self.add_main_lookup(*self.ver_alt_fin_rules())

		self.add_main_lookup(*self.insertion_variant_rules())

		self.add_sub_lookup(*self.insert_limit_subrules())
		self.add_sub_lookup(*self.insert_top_limit_subrules())
		self.add_sub_lookup(*self.no_limits_subrules())
		self.add_sub_lookup(*self.width_limits_subrules())
		self.add_sub_lookup(*self.height_limits_subrules())
		self.add_sub_lookup(*self.width_height_limits_subrules())
		self.add_sub_lookup(*self.enclosure_width_limits_subrules())
		self.add_sub_lookup(*self.enclosure_height_limits_subrules())
		for i in range(len(self.unused_places)):
			self.add_sub_lookup(*self.pair_limits_subrules(i))
		self.add_main_lookup(*self.enclosure_hor_rules())
		self.add_main_lookup(*self.enclosure_ver_rules())
		self.add_sub_lookup(*self.insertion_duplicate_subrules())
		self.add_sub_lookup(*self.unmake_place_subrules())
		for d in range(1, self.max_depth):
			self.add_main_lookup(*self.inner_depth_rules(d))
			self.add_main_lookup(*self.outer_depth_rules(d-1))
			self.add_main_lookup(*self.init_limits_rules())
			self.add_main_lookup(*self.make_places_rules())
			self.add_main_lookup(*self.insertion_copy_rules())
			self.add_main_lookup(*self.insertion_limits_rules())
			self.add_main_lookup(*self.insertion_transfer_rules())
			self.add_main_lookup(*self.limits_rules())
			if d-1 == 0:
				self.add_main_lookup(*self.top_direction_rules())
				self.add_main_lookup(*self.top_init_limits_rules())
			self.add_main_lookup(*self.bracket_reset_rules())
		self.add_main_lookup(*self.insertion_uncopy_rules())
		self.add_main_lookup(*self.insertion_join_rules())
		self.add_main_lookup(*self.insertion_geom_rules())
		self.add_main_lookup(*self.insertion_default_rules())
		self.add_main_lookup(*self.insertion_cleanup1_rules())
		self.add_main_lookup(*self.insertion_cleanup2_rules())
		self.add_main_lookup(*self.topgroup_ver_limits_rules())
		self.add_main_lookup(*self.topgroup_hor_limits_rules())

	def overlay_flat_record_subrules(self):
		name, rules = 'overlay-flat-record', []
		rules.append(simple_sub_rule([self.open_('h')], [self.open_('h'), self.flat]))
		rules.append(simple_sub_rule([self.open_('v')], [self.open_('v'), self.flat]))
		return name, rules

	def overlay_flat_rules(self):
		name, rules, filt = 'overlay-flat', [], '@AuxOverlayFlat'
		self.add_class(filt, [self.open_('o'), self.close_('o'), self.open_('h'), self.open_('v')])
		rules.append(chain_sub_rule([self.open_('o')], [(self.open_('h'), ['overlay-flat-record'])], []))
		rules.append(chain_sub_rule([], [(self.open_('v'), ['overlay-flat-record'])], [self.close_('o')]))
		return name, rules, filt

	def insertion_expand_rules(self):
		name, rules = 'insertion-expand', []
		rules.append(simple_sub_rule([self.open_('i')], [self.open_('i')] + self.unknown_places))
		return name, rules

	def inner_depth_rules(self, d):
		name, rules, filt = f'inner-depth-{d}', [], '@AuxInnerDepth'
		self.add_class(filt, ['@Undone', '@Depth'])
		for level in all_levels:
			rules.append(context_sub_rule([], self.open_(level), [self.depth_(d)], self.open_inner_(level)))
			rules.append(context_sub_rule([self.depth_(d)], self.close_(level), [], self.close_inner_(level)))
		return name, rules, filt

	def outer_depth_rules(self, d):
		name, rules, filt = f'outer-depth-{d}', [], '@AuxOuterDepth'
		self.add_class(filt, ['@Undone', '@Depth', self.record, '@Direction'])
		for level in all_levels:
			rules.append(context_sub_rule([], self.open_(level), [self.depth_(d)], self.open_outer_(level)))
			rules.append(context_sub_rule([], self.open_(level), ['@Direction', self.depth_(d)], self.open_outer_(level)))
			rules.append(context_sub_rule([], self.horizontal, [self.depth_(d)], self.horizontal_active))
			rules.append(context_sub_rule([], self.vertical, [self.depth_(d)], self.vertical_active))
			rules.append(context_sub_rule([self.depth_(d)], self.record, [], self.record_active))
			rules.append(context_sub_rule([self.depth_(d)], self.close_(level), [], self.close_outer_(level)))
		return name, rules, filt

	def make_places_rules(self):
		name, rules, filt = 'make-places', [], '@AuxMakePlaces'
		self.add_class(filt, ['@OuterInner', '@Insertion'])
		for pl in INSERTION_PLACES:
			rules.append(context_sub_rule([], self.insertion_(pl), ['@Inneropen'], self.insertion_active_(pl)))
		return name, rules, filt

	def place_rules(self):
		name, rules, filt = 'place', [], '@AuxPlace'
		self.add_class(filt, ['@Outer', '@Insertionactive'] + self.unknown_places)
		for i in range(len(self.unused_places)):
			unknown = self.unknown_places[i]
			unused = self.unused_places[i]
			rest = self.unknown_places[i+1:]
			insert = self.insertions_active[i]
			used = self.used_places[i]
			for j in range(i+1):
				prev_insertions = j * ['@Insertionactive']
				rules.append(context_sub_rule([self.open_outer_('i')], unknown, rest + prev_insertions + [insert], used))
			rules.append(context_sub_rule([self.open_outer_('i')], unknown, [], unused))
		return name, rules, filt

	def unmake_places_rules(self):
		name, rules, filt = 'unmake-places', [], '@Insertionactive'
		for pl in INSERTION_PLACES:
			rules.append(context_sub_rule([], self.insertion_active_(pl), [], self.insertion_(pl)))
		return name, rules, filt

	def group_length_init_rules(self):
		name, rules, filt = 'group-length-init', [], '@OuterInner'
		for level in all_levels:
			rules.append(simple_sub_rule([self.close_inner_(level)], [self.count_(1), self.close_inner_(level)]))
		for level in ['v', 'h']:
			rules.append(simple_sub_rule([self.open_outer_(level)], [self.open_outer_(level), self.count_(0)]))
			rules.append(simple_sub_rule([self.close_outer_(level)], [self.count_(0), self.close_outer_(level)]))
		return name, rules, filt

	def group_length_sum_rules(self):
		name, rules, filt = 'group-length-sum', [], '@OuterCount'
		for n in nonzero_counts:
			if n-1 >= 0:
				rules.append(context_sub_rule([self.count_(n-1)], self.count_(1), [], self.count_(n)))
			rules.append(context_sub_rule([self.count_(MAX_COUNT)], self.count_(1), [], self.count_(MAX_COUNT)))
			rules.append(context_sub_rule([self.count_(n)], self.count_(0), [], self.count_(n)))
		return name, rules, filt

	def group_length_cleanup1_rules(self):
		name, rules, filt = 'group-length-cleanup1', [], '@AuxGroupLengthCleanup1'
		self.add_class(filt, ['@Inner', '@Count', self.record])
		for n in nonzero_counts:
			rules.append(simple_sub_rule([self.record, self.count_(n)], [self.record]))
		return name, rules, filt

	def group_length_copy_rules(self):
		name, rules, filt = 'group-length-copy', [], '@OuterCount'
		for n in nonzero_counts:
			rules.append(context_sub_rule([], self.count_(0), [self.count_(n)], self.length_(n)))
		return name, rules, filt

	def group_length_cleanup2_rules(self):
		name, rules, filt = 'group-length-cleanup2', [], '@AuxGroupLengthCleanup2'
		self.add_class(filt, ['@OuterCount', self.record_active])
		for n in nonzero_counts:
			rules.append(simple_sub_rule([self.record_active, self.count_(n)], [self.record_active]))
		return name, rules, filt

	def unused_places1_rules(self):
		name, rules = 'unused-places1', []
		for unused in self.unused_places:
			rules.append(simple_sub_rule([unused], [self.nil]))
		return name, rules

	def unused_places2_rules(self):
		name, rules, filt = 'unused-places2', [], '@AuxUnusedPlaces2'
		self.add_class(filt, [self.open_('i'), self.nil])
		for i in range(1, len(self.unused_places)):
			rules.append(simple_sub_rule([self.open_('i')] + i * [self.nil], [self.open_('i')]))
		return name, rules, filt

	def overlay_alt_subrules(self):
		name, rules = 'overlay-alt', []
		rules.append(simple_sub_rule([self.record], [self.record, self.alt_start, self.overlay_alt, self.alt_end]))
		return name, rules

	def hor_alt_subrules(self):
		name, rules = 'hor-alt', []
		rules.append(simple_sub_rule([self.record], [self.record, self.alt_start, self.hor_alt, self.alt_end]))
		return name, rules

	def ver_alt_subrules(self):
		name, rules = 'ver-alt', []
		rules.append(simple_sub_rule([self.record], [self.record, self.alt_start, self.ver_alt, self.alt_end]))
		return name, rules

	def overlay_alt_init_rules(self):
		name, rules, filt = 'overlay-alt-init', [], '@AuxOverlayAltInit' 
		self.add_class(filt, [self.open_('o'), self.close_('o'), self.record])
		rules.append(chain_sub_rule([self.open_('o')], [(self.record, ['overlay-alt'])], []))
		return name, rules, filt

	def hor_alt_init_rules(self):
		name, rules, filt = 'hor-alt-init', [], '@AuxHorAltInit' 
		self.add_class(filt, [self.open_('h'), self.close_('h'), self.record])
		rules.append(chain_sub_rule([self.open_('h')], [(self.record, ['hor-alt'])], []))
		return name, rules, filt

	def ver_alt_init_rules(self):
		name, rules, filt = 'ver-alt-init', [], '@AuxVerAltInit' 
		self.add_class(filt, [self.open_('v'), self.close_('v'), self.record])
		rules.append(chain_sub_rule([self.open_('v')], [(self.record, ['ver-alt'])], []))
		return name, rules, filt

	def ligature_elem_to_name(self, elem):
		if elem.ch not in self.sym:
			return [None, False]
		ch_name = self.sym[elem.ch]
		if elem.rot:
			ch_name = self.name_rotate_to_name[(ch_name, elem.rot)]
		if elem.mirror:
			return [ch_name, self.mirror]
		else:
			return [ch_name]

	def make_overlay_alt_rules(self):
		name, rules, filt = 'make-overlay-alt', [], '@AuxMakeOverlayAlt'
		overlay_names = [self.ligature_elem_to_name(elem)[0] for lig in overlay_ligatures() \
						for elem in lig.horizontal + lig.vertical if not lig.alt]
		overlay_names = [elem for elem in overlay_names if elem is not None]
		base_names = list(set(overlay_names))
		self.add_class(filt, ['@Undone', self.overlay_alt, self.mirror] + base_names)
		for lig in overlay_ligatures():
			if lig.ch not in self.sym:
				continue
			base_name = self.sym[lig.ch]
			horizontal_pairs = [self.ligature_elem_to_name(elem) for elem in lig.horizontal]
			vertical_pairs = [self.ligature_elem_to_name(elem) for elem in lig.vertical]
			horizontal_names = [pair[0] for pair in horizontal_pairs]
			vertical_names = [pair[0] for pair in vertical_pairs]
			if base_name not in self.unscaled_sign_to_size or lig.alt or None in horizontal_names + vertical_names:
				continue
			if len(horizontal_names) == 1:
				pattern1 = [self.open_('b')] + horizontal_pairs[0] + [self.close_('b')]
			else:
				pattern1 = [self.open_('h')] + \
					[sym for pair in horizontal_pairs for sym in [self.open_('b')] + pair + [self.close_('b')]] + \
					[self.close_('h')]
			if len(vertical_names) == 1:
				pattern2 = [self.open_('b')] + vertical_pairs[0] + [self.close_('b')]
			else:
				pattern2 = [self.open_('v')] + \
					[sym for pair in vertical_pairs for sym in [self.open_('b')] + pair + [self.close_('b')]] + \
					[self.close_('v')]
			rules.append(context_sub_rule([], self.overlay_alt, pattern1 + pattern2 + [self.close_('o')], base_name))
			if len(horizontal_names) == 1 and len(vertical_names) == 1:
				rules.append(context_sub_rule([], self.overlay_alt, pattern2 + pattern1 + [self.close_('o')], base_name))
		return name, rules, filt

	def make_hor_alt_rules(self):
		name, rules, filt = 'make-hor-alt', [], '@AuxMakeHorAlt'
		horizontal_names = [self.ligature_elem_to_name(elem)[0] for lig in horizontal_ligatures() for elem in lig.groups]
		horizontal_names = [elem for elem in horizontal_names if elem is not None]
		base_names = list(set(horizontal_names))
		self.add_class(filt, ['@Undone', self.hor_alt, self.mirror] + base_names)
		for lig in horizontal_ligatures():
			if lig.ch not in self.sym:
				continue
			base_name = self.sym[lig.ch]
			pairs = [self.ligature_elem_to_name(elem) for elem in lig.groups]
			names = [pair[0] for pair in pairs]
			if base_name not in self.unscaled_sign_to_size or None in names:
				continue
			pattern = [sym for pair in pairs for sym in [self.open_('b')] + pair + [self.close_('b')]] + [self.close_('h')]
			rules.append(context_sub_rule([], self.hor_alt, pattern, base_name))
		return name, rules, filt

	def make_ver_alt_rules(self):
		name, rules, filt = 'make-ver-alt', [], '@AuxMakeVerAlt'
		vertical_names = [self.ligature_elem_to_name(elem)[0] for lig in vertical_ligatures() for elem in lig.groups]
		vertical_names = [elem for elem in vertical_names if elem is not None]
		base_names = list(set(vertical_names))
		self.add_class(filt, ['@Undone', self.ver_alt, self.mirror] + base_names)
		for lig in vertical_ligatures():
			if lig.ch not in self.sym:
				continue
			base_name = self.sym[lig.ch]
			pairs = [self.ligature_elem_to_name(elem) for elem in lig.groups]
			names = [pair[0] for pair in pairs]
			if base_name not in self.unscaled_sign_to_size or None in names:
				continue
			pattern = [sym for pair in pairs for sym in [self.open_('b')] + pair + [self.close_('b')]] + [self.close_('v')]
			rules.append(context_sub_rule([], self.ver_alt, pattern, base_name))
		return name, rules, filt

	def recur_overlay_alt_rules(self):
		name, rules, filt = 'recur-overlay-alt', [], '@AuxRecurOverlayAlt'
		overlay_names = [self.ligature_elem_to_name(elem)[0] for lig in overlay_ligatures() \
						for elem in lig.horizontal + lig.vertical if not lig.alt]
		overlay_names = [elem for elem in overlay_names if elem is not None]
		self.add_class(filt, [self.open_('o'), self.close_('o'), self.overlay_alt] + overlay_names)
		for base_name in overlay_names:
			rules.append(context_sub_rule([self.open_('o')], base_name, [], self.absent_sign))
		return name, rules, filt

	def recur_hor_alt_rules(self):
		name, rules, filt = 'recur-hor-alt', [], '@AuxRecurHorAlt'
		horizontal_names = [self.ligature_elem_to_name(elem)[0] for lig in horizontal_ligatures() for elem in lig.groups]
		horizontal_names = [elem for elem in horizontal_names if elem is not None]
		self.add_class(filt, [self.open_('h'), self.close_('h'), self.hor_alt] + horizontal_names)
		for base_name in horizontal_names:
			rules.append(context_sub_rule([self.open_('h')], base_name, [], self.absent_sign))
		return name, rules, filt

	def recur_ver_alt_rules(self):
		name, rules, filt = 'recur-ver-alt', [], '@AuxRecurVerAlt'
		vertical_names = [self.ligature_elem_to_name(elem)[0] for lig in vertical_ligatures() for elem in lig.groups]
		vertical_names = [elem for elem in vertical_names if elem is not None]
		self.add_class(filt, [self.open_('v'), self.close_('v'), self.ver_alt] + vertical_names)
		for base_name in vertical_names:
			rules.append(context_sub_rule([self.open_('v')], base_name, [], self.absent_sign))
		return name, rules, filt

	def overlay_alt_fin_rules(self):
		name, rules = 'overlay-alt-fin', []
		rules.append(simple_sub_rule([self.record, self.alt_start, self.overlay_alt, self.alt_end], [self.record]))
		return name, rules

	def hor_alt_fin_rules(self):
		name, rules = 'hor-alt-fin', []
		rules.append(simple_sub_rule([self.record, self.alt_start, self.hor_alt, self.alt_end], [self.record]))
		return name, rules

	def ver_alt_fin_rules(self):
		name, rules = 'ver-alt-fin', []
		rules.append(simple_sub_rule([self.record, self.alt_start, self.ver_alt, self.alt_end], [self.record]))
		return name, rules

	def insertion_variant_rules(self):
		name, rules, filt = 'insertion-variant', [], '@AuxInsertionVariant'
		self.add_class(filt, ['@Undone', '@Usedplace'] + self.insertion_bases)
		for name, places, variant_name in self.name_places_variant:
			if name in self.name_with_insertion_variants:
				for n in range(len(places)):
					for places_selection in combinations(places, n+1):
						place_names = [self.used_place_(pl) for pl in places_selection]
						if variant_name != name:
							rules.append(context_sub_rule([self.open_('i')] + place_names + [self.open_('b')], \
									name, [], variant_name))
						else:
							rules.append(ignore_sub_rule([self.open_('i')] + place_names + [self.open_('b')], \
									[name], []))
		return name, rules, filt

	def insert_limit_subrules(self):
		name, rules = 'insert-limit', []
		rules.append(simple_sub_rule([self.record], [self.size_limits, self.record]))
		rules.append(simple_sub_rule([self.record_active], [self.size_limits, self.record_active]))
		return name, rules

	def insert_top_limit_subrules(self):
		name, rules = 'insert-top-limit', []
		rules.append(simple_sub_rule([self.record_active], [self.size_top_limits, self.record_active]))
		return name, rules

	def no_limits_subrules(self):
		name, rules = 'no-limits', []
		rules.append(simple_sub_rule([self.size_limits], self.octal_max_width() + self.octal_max_height()))
		return name, rules

	def width_limits_subrules(self):
		name, rules = 'width-limits', []
		rules.append(simple_sub_rule([self.size_limits], self.to_octal_limit_width(self.font_units) + self.octal_max_height()))
		return name, rules

	def height_limits_subrules(self):
		name, rules = 'height-limits', []
		rules.append(simple_sub_rule([self.size_limits], self.octal_max_width() + self.to_octal_limit_height(self.font_units)))
		return name, rules

	def width_height_limits_subrules(self):
		name, rules = 'width-height-limits', []
		rules.append(simple_sub_rule([self.size_limits], self.to_octal_limit_width(self.font_units) + self.to_octal_limit_height(self.font_units)))
		return name, rules

	def enclosure_width_limits_subrules(self):
		name, rules = 'enclosure-width-limits', []
		rules.append(simple_sub_rule([self.size_limits], self.to_octal_limit_width(SCALEDOWN * self.font_units) + self.octal_max_height()))
		return name, rules

	def enclosure_height_limits_subrules(self):
		name, rules = 'enclosure-height-limits', []
		rules.append(simple_sub_rule([self.size_limits], self.octal_max_width() + self.to_octal_limit_height(SCALEDOWN * self.font_units)))
		return name, rules

	def pair_limits_subrules(self, i):
		name, rules = f'pair-limits-{i}', []
		unused = self.unused_places[i]
		rules.append(simple_sub_rule([self.size_limits], [self.insertion_base, unused]))
		return name, rules

	def enclosure_hor_rules(self):
		name, rules = 'enclosure-hor', []
		for level in 'pw':
			rules.append(simple_sub_rule([self.open_(level)], [self.open_(level), self.horizontal]))
		return name, rules

	def enclosure_ver_rules(self):
		name, rules, filt, feat = 'enclosure-ver', [], None, 'vert'
		rules.append(simple_sub_rule([self.horizontal], [self.vertical]))
		return name, rules, filt, feat

	def insertion_duplicate_subrules(self):
		name, rules = 'insertion-duplicate', []
		for sign in self.insertion_base_list:
			copy1 = self.name_to_insertion_copy1[sign]
			rules.append(simple_sub_rule([sign], [sign, copy1]))
		return name, rules

	def unmake_place_subrules(self):
		name, rules = 'unmake-place', []
		for pl in INSERTION_PLACES:
			rules.append(simple_sub_rule([self.insertion_active_(pl)], [self.insertion_(pl)]))
		return name, rules

	def init_limits_rules(self):
		name, rules, filt = 'init-limits', [], '@AuxInitLimits'
		self.add_class(filt, ['@Inner', self.record])
		rules.append(chain_sub_rule(['@Inneropen'], [(self.record, ['insert-limit'])], []))
		return name, rules, filt

	def insertion_copy_rules(self):
		name, rules, filt = 'insertion-copy', [], '@AuxInsertionCopy' 
		self.add_class(filt, ['@UndoneOuterInner', '@InsertionBase'])
		rules.append(chain_sub_rule([self.open_outer_('i'), self.open_inner_('b')], \
				[('@InsertionBase', ['insertion-duplicate'])], []))
		if self.insertion_base_overlay_list:
			rules.append(chain_sub_rule([self.open_outer_('i'), self.open_inner_('o')], \
					[('@InsertionBaseOverlay', ['insertion-duplicate'])], []))
		return name, rules, filt

	def insertion_limits_rules(self):
		name, rules, filt = 'insertion-limits', [], '@AuxInsertionLimits'
		self.add_class(filt, ['@Outer', '@Insertionactive', self.size_limits])
		rules.append(chain_sub_rule([self.open_outer_('i')], [(self.size_limits, ['no-limits'])], []))
		for i, active in enumerate(self.insertions_active):
			rules.append(chain_sub_rule([self.open_outer_('i')],
				[(active, ['unmake-place']), (self.size_limits, [f'pair-limits-{i}'])], []))
		return name, rules, filt

	def insertion_transfer_rules(self):
		name, rules, filt = 'insertion-transfer', [], '@AuxInsertionTransfer' 
		self.add_class(filt, ['@Outer', '@InsertionCopy1', self.insertion_base])
		for sign in self.insertion_base_list:
			copy1 = self.name_to_insertion_copy1[sign]
			copy2 = self.name_to_insertion_copy2[sign]
			rules.append(context_sub_rule([self.open_outer_('i'), self.insertion_base, copy1], self.insertion_base, [], copy2))
			rules.append(context_sub_rule([self.open_outer_('i'), copy1], self.insertion_base, [], copy2))
		return name, rules, filt

	def limits_rules(self):
		name, rules, filt = 'limits', [], '@AuxLimits'
		self.add_class(filt, ['@Outer', '@Directionactive', self.size_limits])
		rules.append(chain_sub_rule([self.open_outer_('h')], [(self.size_limits, ['height-limits'])], []))
		rules.append(chain_sub_rule([self.open_outer_('v')], [(self.size_limits, ['width-limits'])], []))
		rules.append(chain_sub_rule([self.open_outer_('o')], [(self.size_limits, ['width-height-limits'])], []))
		for level in 'pw':
			rules.append(chain_sub_rule([self.open_outer_(level), self.horizontal_active], 
					[(self.size_limits, ['enclosure-height-limits'])], []))
			rules.append(chain_sub_rule([self.open_outer_(level), self.vertical_active], 
					[(self.size_limits, ['enclosure-width-limits'])], []))
		rules.append(chain_sub_rule([], [(self.size_limits, ['no-limits'])], []))
		return name, rules, filt

	def top_direction_rules(self):
		name, rules = 'top-direction', []
		for level in 'vhiob':
			rules.append(simple_sub_rule([self.open_outer_(level)], [self.open_outer_(level), self.horizontal]))
		return name, rules

	def top_init_limits_rules(self):
		name, rules, filt = 'top-init-limits', [], '@AuxTopInitLimits'
		self.add_class(filt, ['@Outeropen', self.record_active])
		rules.append(chain_sub_rule(['@Outeropen'], [(self.record_active, ['insert-top-limit'])], [])) 
		return name, rules, filt

	def insertion_uncopy_rules(self):
		name, rules = 'insertion-uncopy', []
		for sign in self.insertion_base_list:
			copy1 = self.name_to_insertion_copy1[sign]
			rules.append(simple_sub_rule([sign, copy1], [sign]))
		return name, rules

	def insertion_join_rules(self):
		name, rules = 'insertion-join', []
		for sign in self.insertion_base_list:
			for i, pl in enumerate(INSERTION_PLACES):
				if (sign, pl) in self.name_place_to_geom:
					insertion_pair = self.name_place_to_pair[(sign, pl)]
					copy2 = self.name_to_insertion_copy2[sign]
					rules.append(simple_sub_rule([copy2, self.unused_places[i]], [insertion_pair]))
		return name, rules

	def insertion_geom_rules(self):
		name, rules = 'insertion-geom', []
		for (sign, pl), insertion_pair in self.name_place_to_pair.items():
			x, y, w, h = self.name_place_to_geom[(sign, pl)]
			rules.append(simple_sub_rule([insertion_pair], \
				[self.insert_x_scale_(0)] + self.to_octal_insert_signed(x) + [self.insert_sep] + \
				[self.insert_y_scale_(0)] + self.to_octal_insert_signed(y) + [self.insert_sep] + \
				[self.anchor_end_insert] + \
				self.to_octal_limit_width(w) + self.to_octal_limit_height(h)))
		return name, rules

	def insertion_default_rules(self):
		name, rules = 'insertion-default', []
		for i, pl in enumerate(INSERTION_PLACES):
			x, y, w, h = self.default_geom(pl)
			rules.append(simple_sub_rule([self.unused_places[i]], [self.nil] + \
				[self.insert_x_scale_(0)] + self.to_octal_insert_signed(x) + [self.insert_sep] + \
				[self.insert_y_scale_(0)] + self.to_octal_insert_signed(y) + [self.insert_sep] + \
				[self.anchor_end_insert] + \
				self.to_octal_limit_width(w) + self.to_octal_limit_height(h)))
		return name, rules

	def insertion_cleanup1_rules(self):
		name, rules = 'insertion-cleanup1', []
		for sign in self.insertion_base_list:
			copy2 = self.name_to_insertion_copy2[sign]
			rules.append(simple_sub_rule([copy2, self.nil], [self.nil]))
			rules.append(simple_sub_rule([self.insertion_base, self.nil], [self.nil]))
		return name, rules

	def insertion_cleanup2_rules(self):
		name, rules, filt = 'insertion-cleanup2', [], '@AuxInsertionCleanup2'
		self.add_class(filt, ['@Undone', self.nil])
		for level in all_levels:
			rules.append(simple_sub_rule([self.open_(level), self.nil], [self.open_(level)]))
		return name, rules, filt

	def topgroup_ver_limits_rules(self):
		name, rules, filt, feat = 'topgroup-ver-limits', [], None, 'vert'
		rules.append(simple_sub_rule([self.size_top_limits], self.to_octal_limit_width(self.font_units) + self.octal_max_height()))
		rules.append(simple_sub_rule([self.horizontal], [self.vertical]))
		for cap, cap_rot in self.cap_to_rotate.items():
			rules.append(simple_sub_rule([cap], [cap_rot]))
		return name, rules, filt, feat

	def topgroup_hor_limits_rules(self):
		name, rules = 'topgroup-hor-limits', []
		rules.append(simple_sub_rule([self.size_top_limits], self.octal_max_width() + self.to_octal_limit_height(self.font_units)))
		return name, rules

	###### Scale analysis

	def scale_analysis(self):
		"""
		size_sign: append dimensions behind sign.
		size_basic: append dimensions behind basic element (other than sign).
		init_scale_cap: make cap inside enclosure initially have scaling 0.

		width_size/height_size: highlight width or height of basic element of outer group.
		cap_width_size1/cap_height_size1: highlight width or height of cap of outer group and add marker at end.
		cap_width_size2/cap_height_size2: add extra marker at front.
		receive_width/receive_height: set up placeholders for intended sum/max/first at end of outer group.
		init_size: prepare to copy value from inner group, by adding placeholders in 3 different formats.
		init_width/init_height: copy width or height from inner group as is (for summing).
		init_first: copy the width/height in different format.
		init_reverse: copy the width/height in reverse order.
		summing: sum values.
		maxing: max values.
		first: propagate first of values.
		normalize_arithmetic: turn resulting values into normal sizes.
		fin_size: turn copied values into nils.
		fin_size_cleanup: remove those nils.
		fin_cap_size: remove size of cap inside enclosure.
		enclosure_width/enclosure_height: make width/height of enclosure 1 EM for vertical/horizontal text
		empty_scaling: add placeholder for accumulated size of subgroups, and for different scalings thereof.
		copy_front: transfer value from back to front, as 0th scaling.
		fill_scaling: compute the scalings.
		normalize_scale: remove carry and replaces sizes by nils.
		size_cleanup: remove nils at back of outer group (from unscaled size).
		width_size_limit/height_size_limit: turn width or height into generic size.
		compare_scale: compare these sizes to the scalings, for each digit separately.
		big_scale: remove scalings that are too big.
		limit_cleanup: replace size limit by placeholder for scale.
		scale_copy: copy biggest scale to the front.
		scale_width/scale_height: turn generic scalings into width or height.

		inactive_scale: make scalings from inner groups inactive. Also activate group scales from inner groups.
		max_scale: compute maximum of scalings from width and height.
		prop_inner: propagate scale to inner groups.
		prop_max: propagate that maximum to the scaled widths and heights.
		scale_cleanup1: turn one combination of scaling and sizes into nils.
		scale_cleanup2: remove sequence of such nils.
		latent_cleanup1: replace latent dimensions by nils.
		latent_cleanup2: replace sequence of nils, for one scale, by single nil.
		latent_cleanup3: absorb these nils into open bracket.
		scale_cleanup3: remove width and height scale, and turn active into inactive scales.
		empty_insertion_scaling: for position of inserted group, prepare for scalings.
		copy_insertion: copy the positions to start of the scalings.
		[ reuse fill_scaling ]
		filter_insertion_scale: find the right scaling, erase previous and following scalings.
		filter_insert_cleanup1: replace more parts of the irrelevant scalings by nils.
		filter_insert_cleanup2: remove the nils from the scaling.
		"""
		chunk_size = 1000
		basics = [(sign, self.unscaled_sign_to_size[sign]) for sign in self.unmirrored_signs]
		for i in range(0, len(basics), chunk_size):
			self.add_main_lookup(*self.size_sign_rules(i, basics[i:i + chunk_size]))
		self.add_main_lookup(*self.size_basic_rules())
		self.add_sub_lookup(*self.insert_cap_scale_subrules())
		self.add_sub_lookup(*self.insert_enclosure_scale_subrules())
		self.add_main_lookup(*self.init_scale_cap_rules())

		self.add_sub_lookup(*self.restore_scale_subrules())
		self.add_sub_lookup(*self.remove_scale_subrules())
		self.add_sub_lookup(*self.width_scale_subrules())
		self.add_sub_lookup(*self.height_scale_subrules())
		self.add_sub_lookup(*self.rescale_subrules())
		self.add_sub_lookup(*self.activate_scale_subrules())
		self.add_sub_lookup(*self.width_scale_latent_subrules())
		self.add_sub_lookup(*self.height_scale_latent_subrules())
		self.add_sub_lookup(*self.to_size_subrules())
		self.add_sub_lookup(*self.to_size_marker_subrules())
		self.add_sub_lookup(*self.to_size_sep_subrules())
		for d in range(self.max_depth, 0, -1):
			if d < self.max_depth:
				self.add_main_lookup(*self.inner_depth_rules(d))
			self.add_main_lookup(*self.outer_depth_rules(d-1))
			self.add_main_lookup(*self.active_alt_rules())
			for do_width in [True, False]:
				if do_width:
					self.add_main_lookup(*self.width_size_rules())
					self.add_main_lookup(*self.cap_width_size1_rules())
					self.add_main_lookup(*self.cap_width_size2_rules())
					self.add_main_lookup(*self.receive_width_rules())
					self.add_main_lookup(*self.copy_ligature_sum_rules())
					self.add_main_lookup(*self.copy_ligature_max_rules())
					self.add_main_lookup(*self.remove_alt_size_rules())
					if d < self.max_depth:
						self.add_main_lookup(*self.init_size_rules())
						self.add_main_lookup(*self.init_width_rules())
				else:
					self.add_main_lookup(*self.height_size_rules())
					self.add_main_lookup(*self.cap_height_size1_rules())
					self.add_main_lookup(*self.cap_height_size2_rules())
					self.add_main_lookup(*self.receive_height_rules())
					self.add_main_lookup(*self.copy_ligature_sum_rules())
					self.add_main_lookup(*self.copy_ligature_max_rules())
					self.add_main_lookup(*self.remove_alt_size_rules())
					self.add_main_lookup(*self.remove_alt_rules())
					if d < self.max_depth:
						self.add_main_lookup(*self.init_size_rules())
						self.add_main_lookup(*self.init_height_rules())
				if d < self.max_depth:
					self.add_main_lookup(*self.init_first_rules())
					self.add_main_lookup(*self.init_reverse_rules())
				self.add_main_lookup(*self.summing_rules())
				self.add_main_lookup(*self.maxing_rules())
				self.add_main_lookup(*self.first_rules())
				self.add_main_lookup(*self.normalize_arithmetic_rules())
				if d < self.max_depth:
					self.add_main_lookup(*self.fin_size_rules())
					self.add_main_lookup(*self.fin_size_cleanup_rules())
				self.add_main_lookup(*self.fin_cap_size_rules())
				self.add_main_lookup(*(self.enclosure_width_rules() if do_width else self.enclosure_height_rules()))
				self.add_main_lookup(*self.empty_scaling_rules())
				self.add_main_lookup(*self.copy_front_rules())
				self.add_main_lookup(*self.fill_scaling_rules())
				self.add_main_lookup(*self.normalize_scale_rules())
				self.add_main_lookup(*self.size_cleanup_rules())
				self.add_main_lookup(*(self.width_size_limit_rules() if do_width else self.height_size_limit_rules()))
				self.add_main_lookup(*self.compare_scale_rules())
				self.add_main_lookup(*self.big_scale_rules())
				self.add_main_lookup(*self.limit_cleanup_rules())
				self.add_main_lookup(*self.scale_copy_rules())
				self.add_main_lookup(*(self.scale_width_rules() if do_width else self.scale_height_rules()))
			self.add_main_lookup(*self.inactive_scale_rules())
			self.add_main_lookup(*self.max_scale_rules())
			if d < self.max_depth:
				self.add_main_lookup(*self.prop_inner_rules())
			self.add_main_lookup(*self.prop_max_rules())
			self.add_main_lookup(*self.scale_cleanup1_rules())
			self.add_main_lookup(*self.scale_cleanup2_rules())
			self.add_main_lookup(*self.bracket_reset_rules())
		self.add_main_lookup(*self.inactive_scale_rules())
		self.add_main_lookup(*self.prop_max_rules())
		self.add_main_lookup(*self.latent_cleanup1_rules())
		self.add_main_lookup(*self.latent_cleanup2_rules())
		self.add_main_lookup(*self.latent_cleanup3_rules())
		self.add_main_lookup(*self.scale_cleanup3_rules())

		self.add_main_lookup(*self.empty_insertion_scaling_rules())
		self.add_main_lookup(*self.copy_insertion_rules())
		self.add_main_lookup(*self.fill_scaling_rules())
		self.add_main_lookup(*self.normalize_scale_rules())
		self.add_main_lookup(*self.filter_insertion_scale_rules())
		self.add_main_lookup(*self.filter_insert_cleanup1_rules())
		self.add_main_lookup(*self.filter_insert_cleanup2_rules())

	def size_sign_rules(self, i, basics):
		name, rules = f'size-sign-{i}', []
		for (sign, (w, h, _, _)) in basics:
			width = self.to_octal_width(w + self.margin)
			height = self.to_octal_height(h + self.margin)
			rules.append(simple_sub_rule([sign], [sign] + width + height))
		return name, rules

	def size_basic_rules(self):
		name, rules = 'size-basic', []
		for cap in self.caps:
			w, h = self.unscaled_cap_to_size[cap]
			width = self.to_octal_width(w + self.margin / 2)
			height = self.to_octal_height(h)
			rules.append(simple_sub_rule([cap], [cap] + width + height))
		for cap in self.caps_rot:
			w, h = self.unscaled_cap_rot_to_size[cap]
			width = self.to_octal_width(w)
			height = self.to_octal_height(h + self.margin / 2)
			rules.append(simple_sub_rule([cap], [cap] + width + height))
		zero_width = self.to_octal_width(0)
		zero_height = self.to_octal_height(0)
		rules.append(simple_sub_rule([self.absent_sign], [self.absent_sign] + zero_width + zero_height))
		for (placeholder, w, h) in [\
				(self.full_lost, 1, 1),
				(self.half_lost, 0.5, 0.5),
				(self.tall_lost, 0.5, 1),
				(self.wide_lost, 1, 0.5),
				(self.full_lost_exp, 1, 1),
				(self.half_lost_exp, 0.5, 0.5),
				(self.tall_lost_exp, 0.5, 1),
				(self.wide_lost_exp, 1, 0.5),
				(self.full_blank, 1, 1),
				(self.half_blank, 0.5, 0.5)]:
			width = self.to_octal_width(w * self.font_units)
			height = self.to_octal_height(h * self.font_units)
			rules.append(simple_sub_rule([placeholder], [placeholder] + width + height))
		return name, rules

	def insert_cap_scale_subrules(self):
		name, rules = 'insert-cap-scale', []
		for cap in self.caps + self.caps_rot:
			rules.append(simple_sub_rule([cap], [self.cap_anchor_start, self.cap_scale_(0), self.cap_anchor_end, cap]))
		return name, rules

	def insert_enclosure_scale_subrules(self):
		name, rules = 'insert-enclosure-scale', []
		rules.append(simple_sub_rule([self.record], 
				[self.record, self.cap_anchor_start, self.enclosure_scale_(0), self.cap_anchor_end]))
		return name, rules

	def init_scale_cap_rules(self):
		name, rules, filt = 'init_scale_cap', [], '@AuxInitScaleCap'
		self.add_class(filt, ['@Undone', '@Cap', self.record])
		for level in 'pw':
			rules.append(chain_sub_rule([self.open_(level)], [(self.record, ['insert-enclosure-scale'])], []))
			rules.append(chain_sub_rule([self.open_(level), self.record], [('@Opening', ['insert-cap-scale'])], []))
			rules.append(chain_sub_rule([], [('@Closing', ['insert-cap-scale'])], [self.close_(level)]))
		return name, rules, filt

	def restore_scale_subrules(self):
		name, rules = 'restore-scale', []
		for s in self.all_scales + [self.n_scales]:
			rules.append(simple_sub_rule([self.scale_hidden_(s)], [self.scale_(s)]))
		for d in all_digits:
			rules.append(simple_sub_rule([self.lt_(d)], [self.size_scaled_(d)]))
			rules.append(simple_sub_rule([self.gt_(d)], [self.size_scaled_(d)]))
			rules.append(simple_sub_rule([self.eq_(d)], [self.size_scaled_(d)]))
		return name, rules

	def remove_scale_subrules(self):
		name, rules = 'remove-scale', []
		rules.append(simple_sub_rule(['@Gt'], [self.nil_scale]))
		rules.append(simple_sub_rule(['@Lt'], [self.nil_scale]))
		rules.append(simple_sub_rule(['@Eq'], [self.nil_scale]))
		rules.append(simple_sub_rule(['@Scalehidden'], [self.nil_scale]))
		rules.append(simple_sub_rule(['@Scale'], [self.nil_scale]))
		rules.append(simple_sub_rule([self.scale_hidden_(self.n_scales), self.record_active], [self.record_active]))
		rules.append(simple_sub_rule(['@Widthscale'], [self.nil_scale]))
		rules.append(simple_sub_rule(['@Heightscale'], [self.nil_scale]))
		rules.append(simple_sub_rule(['@Widthscalelatent'], [self.nil_scale]))
		rules.append(simple_sub_rule(['@Heightscalelatent'], [self.nil_scale]))
		rules.append(simple_sub_rule(['@Widthscaled'], [self.nil_scale]))
		rules.append(simple_sub_rule(['@Widthscaledlatent'], [self.nil_scale]))
		rules.append(simple_sub_rule(['@Heightscaled'], [self.nil_scale]))
		rules.append(simple_sub_rule(['@Heightscaledlatent'], [self.nil_scale]))
		return name, rules

	def width_scale_subrules(self):
		name, rules = 'width-scale', []
		for s in self.all_scales:
			rules.append(simple_sub_rule([self.scale_(s)], [self.width_scale_(s)]))
		for d in all_digits:
			rules.append(simple_sub_rule([self.size_scaled_(d)], [self.width_scaled_(d)]))
		return name, rules

	def height_scale_subrules(self):
		name, rules = 'height-scale', []
		for s in self.all_scales:
			rules.append(simple_sub_rule([self.scale_(s)], [self.height_scale_(s)]))
		for d in all_digits:
			rules.append(simple_sub_rule([self.size_scaled_(d)], [self.height_scaled_(d)]))
		return name, rules

	def rescale_subrules(self):
		name, rules = 'rescale', []
		for s in self.all_scales:
			rules.append(simple_sub_rule([self.width_scale_(s)], [self.width_scale_active_(s)]))
			rules.append(simple_sub_rule([self.height_scale_(s)], [self.height_scale_active_(s)]))
			rules.append(simple_sub_rule([self.width_scale_latent_(s)], [self.width_scale_active_(s)]))
			rules.append(simple_sub_rule([self.height_scale_latent_(s)], [self.height_scale_active_(s)]))
		for d in all_digits:
			rules.append(simple_sub_rule([self.width_scaled_(d)], [self.width_scaled_active_(d)]))
			rules.append(simple_sub_rule([self.height_scaled_(d)], [self.height_scaled_active_(d)]))
			rules.append(simple_sub_rule([self.width_scaled_latent_(d)], [self.width_scaled_active_(d)]))
			rules.append(simple_sub_rule([self.height_scaled_latent_(d)], [self.height_scaled_active_(d)]))
		return name, rules

	def activate_scale_subrules(self):
		name, rules = 'activate-scale', []
		for s in self.all_scales:
			rules.append(simple_sub_rule([self.width_scale_latent_(s)], [self.width_scale_latent_active_(s)]))
			rules.append(simple_sub_rule([self.height_scale_latent_(s)], [self.height_scale_latent_active_(s)]))
		for d in all_digits:
			rules.append(simple_sub_rule([self.width_scaled_latent_(d)], [self.width_scaled_latent_active_(d)]))
			rules.append(simple_sub_rule([self.height_scaled_latent_(d)], [self.height_scaled_latent_active_(d)]))
		return name, rules

	def width_scale_latent_subrules(self):
		name, rules = 'width-scale-latent', []
		for s in self.all_scales:
			rules.append(simple_sub_rule([self.scale_(s)], [self.width_scale_latent_(s)]))
		for d in all_digits:
			rules.append(simple_sub_rule([self.size_scaled_(d)], [self.width_scaled_latent_(d)]))
		return name, rules

	def height_scale_latent_subrules(self):
		name, rules = 'height-scale-latent', []
		for s in self.all_scales:
			rules.append(simple_sub_rule([self.scale_(s)], [self.height_scale_latent_(s)]))
		for d in all_digits:
			rules.append(simple_sub_rule([self.size_scaled_(d)], [self.height_scaled_latent_(d)]))
		return name, rules

	def to_size_subrules(self):
		name, rules = 'to-size', []
		for d in all_digits:
			rules.append(simple_sub_rule([self.height_(d)], [self.size_(d)]))
			rules.append(simple_sub_rule([self.width_(d)], [self.size_(d)]))
		for c in self.caps + self.caps_rot:
			rules.append(simple_sub_rule([c], [c, self.size_sep]))
		return name, rules

	def to_size_marker_subrules(self):
		name, rules = 'to-size-marker', []
		for d in all_digits:
			rules.append(simple_sub_rule([self.height_(d)], [self.size_(d), self.cap_marker]))
			rules.append(simple_sub_rule([self.width_(d)], [self.size_(d), self.cap_marker]))
		return name, rules

	def to_size_sep_subrules(self):
		name, rules = 'to-size-sep', []
		for c in self.caps + self.caps_rot:
			rules.append(simple_sub_rule([c], [c, self.size_sep]))
		return name, rules

	def active_alt_rules(self):
		name, rules, filt = 'active-alt', [], '@AuxActiveAlt'
		self.add_class(filt, ['@OuterInner', self.alt_start, self.alt_end])
		rules.append(context_sub_rule(['@Outeropen'], self.alt_start, [], self.alt_start_active))
		rules.append(context_sub_rule(['@Outeropen'], self.alt_end, [], self.alt_end_active))
		return name, rules, filt

	def width_size_rules(self):
		name, rules, filt = 'width-size', [], '@OuterWidth'
		for level in 'bvho':
			rules.append(chain_sub_rule([self.open_outer_(level)], [('@Width', ['to-size'])], []))
		return name, rules, filt

	def height_size_rules(self):
		name, rules, filt = 'height-size', [], '@OuterHeight'
		for level in 'bvho':
			rules.append(chain_sub_rule([self.open_outer_(level)], [('@Height', ['to-size'])], []))
		return name, rules, filt

	def cap_width_size1_rules(self):
		name, rules, filt = 'cap-width-size1', [], '@AuxCapWidthSize1'
		self.add_class(filt, ['@OuterInner', '@Cap', '@Width'])
		rules.append(chain_sub_rule([self.open_outer_('p'), '@OpeningPlain'], 
			(self.len_oct-1) * [('@Width', ['to-size'])] + [('@Width', ['to-size-marker'])], []))
		rules.append(chain_sub_rule(['@ClosingPlain'], 
			(self.len_oct-1) * [('@Width', ['to-size'])] + [('@Width', ['to-size-marker'])], [self.close_outer_('p')]))
		rules.append(chain_sub_rule([self.open_outer_('w'), '@OpeningWalled'], 
			(self.len_oct-1) * [('@Width', ['to-size'])] + [('@Width', ['to-size-marker'])], []))
		rules.append(chain_sub_rule(['@ClosingWalled'], 
			(self.len_oct-1) * [('@Width', ['to-size'])] + [('@Width', ['to-size-marker'])], [self.close_outer_('w')]))
		return name, rules, filt

	def cap_width_size2_rules(self):
		name, rules, filt = 'cap-width-size2', [], '@AuxCapWidthSize2'
		self.add_class(filt, ['@OuterInner', '@Cap'])
		rules.append(chain_sub_rule([self.open_outer_('p')], [('@OpeningPlain', ['to-size-sep'])], []))
		rules.append(chain_sub_rule([], [('@ClosingPlain', ['to-size-sep'])], [self.close_outer_('p')]))
		rules.append(chain_sub_rule([self.open_outer_('w')], [('@OpeningWalled', ['to-size-sep'])], []))
		rules.append(chain_sub_rule([], [('@ClosingWalled', ['to-size-sep'])], [self.close_outer_('w')]))
		return name, rules, filt

	def cap_height_size1_rules(self):
		name, rules, filt = 'cap-height-size1', [], '@AuxCapHeightSize1'
		self.add_class(filt, ['@OuterInner', '@Cap', '@Height'])
		for level in 'pw':
			rules.append(chain_sub_rule([self.open_outer_(level), '@Cap'], 
				(self.len_oct-1) * [('@Height', ['to-size'])] + [('@Height', ['to-size-marker'])], []))
			rules.append(chain_sub_rule(['@Cap'], 
				(self.len_oct-1) * [('@Height', ['to-size'])] + [('@Height', ['to-size-marker'])], [self.close_outer_(level)]))
		return name, rules, filt

	def cap_height_size2_rules(self):
		name, rules, filt = 'cap-height-size2', [], '@AuxCapHeightSize2'
		self.add_class(filt, ['@OuterInner', '@Cap'])
		rules.append(chain_sub_rule([self.open_outer_('p')], [('@OpeningPlain', ['to-size-sep'])], []))
		rules.append(chain_sub_rule([], [('@ClosingPlain', ['to-size-sep'])], [self.close_outer_('p')]))
		rules.append(chain_sub_rule([self.open_outer_('w')], [('@OpeningWalled', ['to-size-sep'])], []))
		rules.append(chain_sub_rule([], [('@ClosingWalled', ['to-size-sep'])], [self.close_outer_('w')]))
		return name, rules, filt

	def receive_width_rules(self):
		name, rules, filt = 'receive-width', [], '@Outer'
		summing_receiver = [self.size_sep] + self.len_oct * [self.size_(0)]
		maxing_receiver = [self.size_reverse_sep] + [self.pos_reverse_final_(p) for p in self.all_poss]
		first_receiver = [self.size_first_sep] + self.len_oct * [self.size_first_(0)]
		rules.append(simple_sub_rule([self.close_outer_('h')], summing_receiver + [self.close_outer_('h')]))
		rules.append(simple_sub_rule([self.close_outer_('v')], maxing_receiver + [self.close_outer_('v')]))
		rules.append(simple_sub_rule([self.close_outer_('i')], first_receiver + [self.close_outer_('i')]))
		rules.append(simple_sub_rule([self.close_outer_('o')], maxing_receiver + [self.close_outer_('o')]))
		rules.append(simple_sub_rule([self.close_outer_('p')], summing_receiver + [self.close_outer_('p')]))
		rules.append(simple_sub_rule([self.close_outer_('w')], summing_receiver + [self.close_outer_('w')]))
		return name, rules, filt

	def receive_height_rules(self):
		name, rules, filt = 'receive-height', [], '@Outer'
		summing_receiver = [self.size_sep] + self.len_oct * [self.size_(0)]
		maxing_receiver = [self.size_reverse_sep] + [self.pos_reverse_final_(p) for p in self.all_poss]
		first_receiver = [self.size_first_sep] + self.len_oct * [self.size_first_(0)]
		rules.append(simple_sub_rule([self.close_outer_('h')], maxing_receiver + [self.close_outer_('h')]))
		rules.append(simple_sub_rule([self.close_outer_('v')], summing_receiver + [self.close_outer_('v')]))
		rules.append(simple_sub_rule([self.close_outer_('i')], first_receiver + [self.close_outer_('i')]))
		rules.append(simple_sub_rule([self.close_outer_('o')], maxing_receiver + [self.close_outer_('o')]))
		rules.append(simple_sub_rule([self.close_outer_('p')], summing_receiver + [self.close_outer_('p')]))
		rules.append(simple_sub_rule([self.close_outer_('w')], summing_receiver + [self.close_outer_('w')]))
		return name, rules, filt

	def copy_ligature_sum_rules(self):
		name, rules, filt = 'copy-ligature-sum', [], '@AuxCopyLigatureSum'
		self.add_class(filt, ['@Outer', self.alt_end_active, '@Size'])
		for p in self.all_poss:
			for d in all_digits:
				rules.append(context_sub_rule([self.size_(d)] + (self.len_oct-1-p) * ['@Size'] + [self.alt_end_active] + \
					p * ['@Size'], self.size_(0), [], self.size_(d)))
		return name, rules, filt
		
	def copy_ligature_max_rules(self):
		name, rules, filt = 'copy-ligature-max', [], '@AuxCopyLigatureMax'
		self.add_class(filt, ['@Outer', self.alt_end_active, '@Size', '@Posreversefinal'])
		for p in self.all_poss:
			for d in all_digits:
				rules.append(context_sub_rule([self.size_(d)] + (self.len_oct-1-p) * ['@Size'] + [self.alt_end_active] + \
					p * ['@Size'], self.pos_reverse_final_(p), [], self.size_(d)))
		return name, rules, filt

	def remove_alt_size_rules(self):
		name, rules, filt = 'remove-alt-size', [], '@AuxRemoveAltSize'
		self.add_class(filt, [self.alt_start_active, self.alt_end_active, '@Size'])
		rules.append(simple_sub_rule([self.alt_start_active] + self.len_oct * ['@Size'], [self.alt_start_active]))
		return name, rules, filt

	def remove_alt_rules(self):
		name, rules, filt = 'remove-alt', [], '@AuxRemoveAlt'
		self.add_class(filt, [self.record_active, self.alt_start_active, self.alt_end_active])
		rules.append(simple_sub_rule([self.record_active, self.alt_start_active, self.alt_end_active], [self.record_active]))
		return name, rules, filt

	def init_size_rules(self):
		name, rules, filt = 'init-size', [], '@Inner'
		for level in all_levels:
			rules.append(simple_sub_rule([self.close_inner_(level)], 
				[self.size_sep] + self.len_oct * [self.size_(0)] + \
				[self.size_first_sep] + self.len_oct * [self.size_first_(0)] + \
				[self.size_reverse_sep] + [self.pos_reverse_(p) for p in self.all_poss] + \
				[self.close_inner_(level)]))
		return name, rules, filt

	def init_width_rules(self):
		name, rules, filt = 'init-width', [], '@AuxInitWidth'
		self.add_class(filt, ['@Inner', '@Widthscaledactive', '@Size'])
		for d in all_digits:
			rules.append(context_sub_rule([self.width_scaled_active_(d)] + (self.len_oct-1) * ['@AuxInitWidth'], self.size_(0), [], self.size_(d)))
		return name, rules, filt

	def init_height_rules(self):
		name, rules, filt = 'init-height', [], '@AuxInitHeight'
		self.add_class(filt, ['@Inner', '@Heightscaledactive', '@Size'])
		for d in all_digits:
			rules.append(context_sub_rule([self.height_scaled_active_(d)] + (self.len_oct-1) * ['@AuxInitHeight'], self.size_(0), [], self.size_(d)))
		return name, rules, filt

	def init_first_rules(self):
		name, rules, filt = 'init-first', [], '@AuxInitFirst'
		self.add_class(filt, ['@Inner', '@Size', '@Sizefirst'])
		for d in all_digits:
			rules.append(context_sub_rule([self.size_(d)] + (self.len_oct-1) * ['@AuxInitFirst'], self.size_first_(0), [], self.size_first_(d)))
		return name, rules, filt

	def init_reverse_rules(self):
		name, rules, filt = 'init-reverse', [], '@AuxInitReverse'
		self.add_class(filt, ['@Inner', '@Size', '@Posreverse'])
		for d in all_digits:
			for p in self.all_poss:
				rules.append(context_sub_rule([self.size_(d)] + p * ['@Size'], self.pos_reverse_(p), [], self.size_reverse_(d)))
		return name, rules, filt

	def summing_rules(self):
		name, rules, filt = 'summing', [], '@AuxSumming'
		self.add_class(filt, ['@Outer', '@MaybeCarry', self.size_full_sep])
		def sum_carry(d):
			return d % 8, d >= 8
		for d1 in all_digits:
			d1_sym = self.size_(d1)
			d1_car = self.carry_(d1)
			for d2 in all_digits:
				d2_sym = self.size_(d2)
				s, c = sum_carry(d1+d2)
				carry_s, carry_c = sum_carry(1+d1+d2)
				out = self.carry_(s) if c else self.size_(s)
				carry_out = self.carry_(carry_s) if carry_c else self.size_(carry_s)
				rules.append(context_sub_rule([d1_sym] + (self.len_oct-1) * ['@MaybeCarry'] + ['@NoCarry'],
					d2_sym, [], out))
				rules.append(context_sub_rule([d1_car] + (self.len_oct-1) * ['@MaybeCarry'] + ['@NoCarry'],
					d2_sym, [], out))
				rules.append(context_sub_rule([d1_sym] + (self.len_oct-1) * ['@MaybeCarry'] + ['@Carry'],
					d2_sym, [], carry_out))
				rules.append(context_sub_rule([d1_car] + (self.len_oct-1) * ['@MaybeCarry'] + ['@Carry'],
					d2_sym, [], carry_out))
		return name, rules, filt

	def maxing_rules(self):
		name, rules, filt = 'maxing', [], '@AuxMaxing'
		self.add_class(filt, ['@Outer', '@MaxAny', '@Posreversefinal'])
		for d1 in all_digits:
			rules.append(context_sub_rule(['@Lt'], self.size_reverse_(d1), [], self.lt_(d1)))
			rules.append(context_sub_rule([f'@MaxAny{d1}'] + (self.len_oct-1) * ['@MaxAny'] + ['@Gt'], '@Sizereverse', 
					[], self.gt_(d1)))
			for p in self.all_poss:
				rules.append(context_sub_rule([f'@MaxAny{d1}'] + p * ['@MaxAny'] + [self.size_reverse_sep], 
						self.pos_reverse_final_(p), [], self.size_(d1)))
		for d1 in all_digits:
			for d2 in all_digits:
				if d1 < d2:
					rules.append(context_sub_rule([f'@MaxAny{d1}'] + (self.len_oct) * ['@MaxAny'], self.size_reverse_(d2), 
							[], self.lt_(d2)))
				elif d1 > d2:
					rules.append(context_sub_rule([f'@MaxAny{d1}'] + (self.len_oct) * ['@MaxAny'], self.size_reverse_(d2), 
							[], self.gt_(d1)))
				else:
					rules.append(context_sub_rule([f'@MaxAny{d1}'] + (self.len_oct) * ['@MaxAny'], self.size_reverse_(d2), 
							[], self.size_reverse_(d1)))
		return name, rules, filt

	def first_rules(self):
		name, rules, filt = 'first', [], '@AuxFirst'
		self.add_class('@SizefirstAny', ['@Sizefirst', self.size_first_sep])
		self.add_class(filt, ['@Outer', '@SizefirstAny'])
		for d1 in all_digits:
			for d2 in all_digits:
				rules.append(context_sub_rule([self.size_first_(d1)] + (self.len_oct) * ['@SizefirstAny'], self.size_first_(d2), 
						[], self.size_first_(d1)))
		return name, rules, filt

	def normalize_arithmetic_rules(self):
		name, rules, filt = 'normalize-arithmetic', [], '@AuxNormalizeArithmetic'
		self.add_class(filt, ['@Carry', '@Sizefirst'])
		for d in all_digits:
			rules.append(simple_sub_rule([self.carry_(d)], [self.size_(d)]))
			rules.append(simple_sub_rule([self.size_first_(d)], [self.size_(d)]))
		return name, rules, filt

	def fin_size_rules(self):
		name, rules, filt = 'fin-size', [], '@AuxFinSize'
		self.add_class(filt, ['@Inner', '@Size', '@Sizefirst', '@MaxAny', self.size_sep, self.size_first_sep])
		for level in all_levels:
			rules.append(context_sub_rule([self.open_inner_(level)], self.size_sep, [], self.nil))
			rules.append(context_sub_rule([self.open_inner_(level)], self.size_first_sep, [], self.nil))
			rules.append(context_sub_rule([self.open_inner_(level)], self.size_reverse_sep, [], self.nil))
			rules.append(context_sub_rule([self.open_inner_(level)], '@Size', [], self.nil))
			rules.append(context_sub_rule([self.open_inner_(level)], '@Sizefirst', [], self.nil))
			rules.append(context_sub_rule([self.open_inner_(level)], '@MaxAny', [], self.nil))
		return name, rules, filt

	def fin_size_cleanup_rules(self):
		name, rules, filt = 'fin-size-cleanup', [], '@RecordNil'
		rules.append(simple_sub_rule([self.record] + (3 * (self.len_oct+1)) * [self.nil], [self.record]))
		return name, rules, filt

	def fin_cap_size_rules(self):
		name, rules, filt = 'fin-cap-size', [], '@AuxFinCapSize'
		self.add_class(filt, ['@OuterInner', '@Cap', '@Size', self.size_sep, self.cap_marker])
		for c in self.caps + self.caps_rot:
			rules.append(simple_sub_rule([c, self.size_sep] + self.len_oct * ['@Size'] + [self.cap_marker], [c]))
		return name, rules, filt

	def enclosure_width_rules(self):
		name, rules, filt = 'enclosure-width', [], '@AuxEnclosureWidth'
		self.add_class(filt, ['@OuterSize', self.vertical_active])
		unit_size = self.to_octal_size(self.font_units)
		for level in 'pw':
			for i in range(self.len_oct):
				rules.append(context_sub_rule([self.open_outer_(level), self.vertical_active] + i * ['@Size'], '@Size', [], unit_size[i]))
		return name, rules, filt

	def enclosure_height_rules(self):
		name, rules, filt = 'enclosure-height', [], '@AuxEnclosureHeight'
		self.add_class(filt, ['@OuterSize', self.horizontal_active])
		unit_size = self.to_octal_size(self.font_units)
		for level in 'pw':
			for i in range(self.len_oct):
				rules.append(context_sub_rule([self.open_outer_(level), self.horizontal_active] + i * ['@Size'], '@Size', [], unit_size[i]))
		return name, rules, filt

	def empty_scaling_rules(self):
		name, rules, filt = 'empty-scaling', [], '@Recordactive'
		rules.append(simple_sub_rule([self.record_active], 
				[sym for s in self.all_scales for sym in [self.scale_(s)] + 
						self.len_oct * [self.to_scale if s > 0 else self.size_(0)]] + 
						[self.scale_(self.n_scales), self.record_active]))
		return name, rules, filt

	def copy_front_rules(self):
		name, rules, filt = 'copy-front', [], '@OuterSize'
		for d in all_digits:
			rules.append(context_sub_rule([], self.size_(0), (self.len_oct-1) * ['@Size'] + [self.size_(d)], self.size_scaled_(d)))
		return name, rules, filt

	def fill_scaling_rules(self):
		name, rules, filt = 'fill-scaling', [], '@AuxScaling'
		self.add_class('@SizescaledScale', ['@Sizescaled', '@Scale'])
		self.add_class('@SizescaledScaleSizescaledcarry', ['@SizescaledScale', '@Sizescaledcarry'])
		self.add_class(filt, ['@Outer', '@SizescaledScaleSizescaledcarry', self.to_scale])
		inter = (self.len_oct-2) * ['@SizescaledScaleSizescaledcarry']
		for d in all_digits:
			for down_carry in all_down_carry:
				nex = f'@DownCarry{down_carry}'
				for carry in [0, 1]:
					d_total = d * 3 // 4 + down_carry + carry
					d_mod = d_total % 8
					d_carry = d_total // 8
					d_out = self.size_scaled_carry_(d_mod) if d_carry else self.size_scaled_(d_mod)
					prev = '@Sizescaledcarry' if carry else '@SizescaledScale'
					rules.append(context_sub_rule([self.size_scaled_(d), nex] + inter + [prev], 
							self.to_scale, [], d_out))
					rules.append(context_sub_rule([self.size_scaled_carry_(d), nex] + inter + [prev], 
							self.to_scale, [], d_out))
		return name, rules, filt

	def normalize_scale_rules(self):
		name, rules, filt = 'normalize-scale', [], '@AuxNormalizeScale'
		self.add_class(filt, ['@Sizescaledcarry', '@Size'])
		for d in all_digits:
			rules.append(simple_sub_rule([self.size_scaled_carry_(d)], [self.size_scaled_(d)]))
			rules.append(simple_sub_rule([self.size_(d)], [self.nil]))
		return name, rules, filt

	def size_cleanup_rules(self):
		name, rules, filt = 'size-cleanup', [], '@AuxSizeCleanup'
		self.add_class(filt, [self.record_active, self.nil, self.size_sep, self.size_reverse_sep, self.size_first_sep])
		for sep in [self.size_sep, self.size_reverse_sep, self.size_first_sep]:
			rules.append(simple_sub_rule([self.record_active, sep] + self.len_oct * [self.nil], [self.record_active]))
		rules.append(simple_sub_rule([self.record_active] + self.len_oct * [self.nil], [self.record_active]))
		return name, rules, filt

	def width_size_limit_rules(self):
		name, rules, filt = 'width-size-limit', [], '@AuxWidthSizeLimit'
		self.add_class(filt, ['@Outer', '@Limitwidth', self.record_active])
		for d in all_digits:
			rules.append(context_sub_rule(['@Outeropen'], self.limit_width_(d), [], self.limit_size_(d)))
		return name, rules, filt

	def height_size_limit_rules(self):
		name, rules, filt = 'height-size-limit', [], '@AuxHeightSizeLimit'
		self.add_class(filt, ['@Outer', '@Limitheight', self.record_active])
		for d in all_digits:
			rules.append(context_sub_rule(['@Outeropen'], self.limit_height_(d), [], self.limit_size_(d)))
		return name, rules, filt

	def compare_scale_rules(self):
		name, rules, filt = 'compare-scale', [], '@AuxCompareScale'
		self.add_class(filt, ['@Outer', '@Limitsize', '@Sizescaled', '@Scale'])
		for s in self.all_scales + [self.n_scales]:
			rules.append(context_sub_rule([], self.scale_(s), [], self.scale_hidden_(s)))
		for d1 in all_digits:
			for d2 in all_digits:
				if d1 < d2:
					target = self.gt_(d2)
				elif d1 > d2:
					target = self.lt_(d2)
				else:
					target = self.eq_(d2)
				for p in reversed(self.all_poss):
					rules.append(context_sub_rule(
							[self.limit_size_(d1)] + p * ['@Limitsize'], 
							self.size_scaled_(d2), p * ['@Sizescaled'] + ['@Scale'], target))
		return name, rules, filt

	def big_scale_rules(self):
		name, rules, filt = 'big-scale', [], '@AuxBigScale'
		self.add_class(filt, ['@Outer', '@Scalehidden', '@Cmp', self.record_active])
		for p in self.all_poss:
			rules.append(chain_sub_rule([], [('@ScalehiddenNonlast', ['remove-scale'])] + \
					p * [('@Cmp', ['remove-scale'])] + \
					[('@Gt', ['remove-scale'])] + \
					(self.len_oct-p-1) * [('@Eq', ['remove-scale'])], []))
		rules.append(chain_sub_rule([], [('@Scalehidden', ['restore-scale'])] + 
				self.len_oct * [('@Cmp', ['restore-scale'])], []))
		rules.append(chain_sub_rule([], [(self.scale_hidden_(self.n_scales), ['remove-scale'])], []))
		return name, rules, filt

	def limit_cleanup_rules(self):
		name, rules, filt = 'limit-cleanup', [], '@Limitsize'
		rules.append(simple_sub_rule(self.len_oct * ['@Limitsize'], [self.to_scale]))
		return name, rules, filt

	def scale_copy_rules(self):
		name, rules, filt = 'scale-copy', [], '@AuxScaleCopy'
		self.add_class(filt, ['@Outer', '@Scale', self.to_scale])
		for s in self.all_scales:
			rules.append(context_sub_rule([], self.to_scale, [self.scale_(s)], self.scale_group_(s)))
		return name, rules, filt

	def scale_width_rules(self):
		name, rules, filt = 'scale-width', [], '@AuxScaleWidth'
		self.add_class(filt, ['@Outer', '@Scale', '@Sizescaled', '@Widthscaled'])
		rules.append(chain_sub_rule(['@Outeropen'], [('@Scale', ['width-scale'])] + 
				self.len_oct * [('@Sizescaled', ['width-scale'])], []))
		rules.append(chain_sub_rule([], [('@Scale', ['width-scale-latent'])] + 
				self.len_oct * [('@Sizescaled', ['width-scale-latent'])], []))
		return name, rules, filt

	def scale_height_rules(self):
		name, rules, filt = 'scale-height', [], '@AuxScaleHeight'
		self.add_class(filt, ['@Outer', '@Scale', '@Sizescaled', '@Heightscaled'])
		rules.append(chain_sub_rule(['@Outeropen'], [('@Scale', ['height-scale'])] + 
				self.len_oct * [('@Sizescaled', ['height-scale'])], []))
		rules.append(chain_sub_rule([], [('@Scale', ['height-scale-latent'])] + 
				self.len_oct * [('@Sizescaled', ['height-scale-latent'])], []))
		return name, rules, filt

	def inactive_scale_rules(self):
		name, rules, filt = 'inactive-scale', [], '@AuxInactiveScale'
		self.add_class(filt, ['@Scalegroup', '@Capscale', '@Enclosurescale', 
				'@Insertxscale', '@Insertyscale',
				'@Widthscaleactive', '@Widthscalelatentactive',
				'@Widthscaledactive', '@Widthscaledlatentactive',
				'@Heightscaleactive', '@Heightscalelatentactive',
				'@Heightscaledactive', '@Heightscaledlatentactive'])
		for s in self.all_scales:
			rules.append(simple_sub_rule([self.width_scale_active_(s)], [self.width_scale_(s)]))
			rules.append(simple_sub_rule([self.width_scale_latent_active_(s)], [self.width_scale_latent_(s)]))
			rules.append(simple_sub_rule([self.height_scale_active_(s)], [self.height_scale_(s)]))
			rules.append(simple_sub_rule([self.height_scale_latent_active_(s)], [self.height_scale_latent_(s)]))
			rules.append(simple_sub_rule([self.scale_group_(s)], [self.scale_group_active_(s)]))
			rules.append(simple_sub_rule([self.cap_scale_(s)], [self.cap_scale_active_(s)]))
			rules.append(simple_sub_rule([self.enclosure_scale_(s)], [self.enclosure_scale_active_(s)]))
			rules.append(simple_sub_rule([self.insert_x_scale_(s)], [self.insert_x_scale_active_(s)]))
			rules.append(simple_sub_rule([self.insert_y_scale_(s)], [self.insert_y_scale_active_(s)]))
		for d in all_digits:
			rules.append(simple_sub_rule([self.width_scaled_active_(d)], [self.width_scaled_(d)]))
			rules.append(simple_sub_rule([self.width_scaled_latent_active_(d)], [self.width_scaled_latent_(d)]))
			rules.append(simple_sub_rule([self.height_scaled_active_(d)], [self.height_scaled_(d)]))
			rules.append(simple_sub_rule([self.height_scaled_latent_active_(d)], [self.height_scaled_latent_(d)]))
		return name, rules, filt

	def max_scale_rules(self):
		name, rules, filt = 'max-scale', [], '@MaxScale'
		self.add_class(filt, ['@UndoneOuterInner', '@Scalegroupactive'])
		for s1 in self.all_scales:
			for s2 in self.all_scales:
				target = self.scale_group_active_(s2) if s1 < s2 else self.scale_group_active_(s1)
				rules.append(simple_sub_rule([self.scale_group_active_(s1), self.scale_group_active_(s2)], [target]))
		return name, rules, filt

	def prop_inner_rules(self):
		name, rules, filt = 'prop-inner', [], '@AuxPropInner'
		self.add_class(filt, ['@Outer', '@Scalegroupactive', '@Capscaleactive', '@Enclosurescaleactive', \
				'@Contentwidthactive', '@Contentheightactive', '@Insertxscaleactive', '@Insertyscaleactive', \
				self.record_active])
		for s1 in self.all_scales:
			for s2 in self.all_scales:
				prod = min(s1+s2, self.n_scales-1)
				rules.append(context_sub_rule([self.scale_group_active_(s1), self.record_active], \
						self.scale_group_active_(s2), [], self.scale_group_(prod)))
				rules.append(context_sub_rule([self.scale_group_active_(s1), self.record_active], \
						self.cap_scale_active_(s2), [], self.cap_scale_(prod)))
				rules.append(context_sub_rule([self.scale_group_active_(s1), self.record_active], \
						self.enclosure_scale_active_(s2), [], self.enclosure_scale_(prod)))
				rules.append(context_sub_rule([self.scale_group_active_(s1), self.record_active], \
						self.insert_x_scale_active_(s2), [], self.insert_x_scale_(prod)))
				rules.append(context_sub_rule([self.scale_group_active_(s1), self.record_active], \
						self.insert_y_scale_active_(s2), [], self.insert_y_scale_(prod)))
		return name, rules, filt

	def prop_max_rules(self):
		name, rules, filt = 'prop-max', [], '@AuxPropMax'
		self.add_class(filt, ['@UndoneOuterInner', '@Scalegroupactive',
			'@Widthscale', '@Widthscaled', '@Widthscalelatent', '@Widthscaledlatent',
			'@Heightscale', '@Heightscaled', '@Heightscalelatent', '@Heightscaledlatent'])
		for s1 in self.all_scales:
			for s2 in self.all_scales:
				if s2 < s1:
					rules.append(chain_sub_rule([self.scale_group_active_(s1)],
							[(self.width_scale_(s2), ['remove-scale'])] +
							self.len_oct * [('@Widthscaled', ['remove-scale'])], []))
					rules.append(chain_sub_rule([self.scale_group_active_(s1)],
							[(self.width_scale_latent_(s2), ['remove-scale'])] +
							self.len_oct * [('@Widthscaledlatent', ['remove-scale'])], []))
					rules.append(chain_sub_rule([self.scale_group_active_(s1)],
							[(self.height_scale_(s2), ['remove-scale'])] +
							self.len_oct * [('@Heightscaled', ['remove-scale'])], []))
					rules.append(chain_sub_rule([self.scale_group_active_(s1)],
							[(self.height_scale_latent_(s2), ['remove-scale'])] +
							self.len_oct * [('@Heightscaledlatent', ['remove-scale'])], []))
				elif s1 == s2:
					rules.append(chain_sub_rule([self.scale_group_active_(s1)],
							[(self.width_scale_latent_(s2), ['rescale'])] +
							self.len_oct * [('@Widthscaledlatent', ['rescale'])], [])) 
					rules.append(chain_sub_rule([self.scale_group_active_(s1)],
							[(self.width_scale_(s2), ['rescale'])] +
							self.len_oct * [('@Widthscaled', ['rescale'])], [])) 
					rules.append(chain_sub_rule([self.scale_group_active_(s1)],
							[(self.height_scale_latent_(s2), ['rescale'])] +
							self.len_oct * [('@Heightscaledlatent', ['rescale'])], [])) 
					rules.append(chain_sub_rule([self.scale_group_active_(s1)],
							[(self.height_scale_(s2), ['rescale'])] +
							self.len_oct * [('@Heightscaled', ['rescale'])], [])) 
				else:
					rules.append(chain_sub_rule([self.scale_group_active_(s1)],
							[(self.width_scale_latent_(s2), ['activate-scale'])] +
							self.len_oct * [('@Widthscaledlatent', ['activate-scale'])], [])) 
					rules.append(chain_sub_rule([self.scale_group_active_(s1)],
							[(self.height_scale_latent_(s2), ['activate-scale'])] +
							self.len_oct * [('@Heightscaledlatent', ['activate-scale'])], [])) 
		return name, rules, filt

	def scale_cleanup1_rules(self):
		name, rules, filt = 'scale-cleanup1', [], '@OuterNil'
		rules.append(simple_sub_rule((self.len_oct + 1) * [self.nil_scale], [self.nil_scale]))
		return name, rules, filt

	def scale_cleanup2_rules(self):
		name, rules, filt = 'scale-cleanup2', [], '@OuterNil'
		for n in reversed(range(1, self.n_scales+1)):
			for level in all_levels:
				rules.append(simple_sub_rule([self.open_outer_(level)] + n * [self.nil_scale], [self.open_outer_(level)]))
		return name, rules, filt

	def latent_cleanup1_rules(self):
		name, rules = 'latent-cleanup1', []
		rules.append(simple_sub_rule(['@Widthscalelatentactive'], [self.nil_scale]))
		rules.append(simple_sub_rule(['@Widthscaledlatentactive'], [self.nil_scale]))
		rules.append(simple_sub_rule(['@Heightscalelatentactive'], [self.nil_scale]))
		rules.append(simple_sub_rule(['@Heightscaledlatentactive'], [self.nil_scale]))
		return name, rules

	def latent_cleanup2_rules(self):
		name, rules = 'latent-cleanup2', []
		rules.append(simple_sub_rule((self.len_oct + 1) * [self.nil_scale], [self.nil_scale]))
		return name, rules

	def latent_cleanup3_rules(self):
		name, rules, filt = 'latent-cleanup3', [], '@AuxLatentCleanup3'
		self.add_class(filt, ['@Undone', self.nil_scale])
		for n in reversed(range(1, 2 * self.n_scales)):
			for level in all_levels:
				rules.append(simple_sub_rule([self.open_(level)] + n * [self.nil_scale], [self.open_(level)]))
		return name, rules, filt

	def scale_cleanup3_rules(self):
		name, rules, filt = 'scale-cleanup3', [], '@AuxScaleCleanup3'
		self.add_class(filt, ['@Scalegroupactive', '@Widthscaleactive', '@Heightscaleactive', 
				'@Capscaleactive', '@Enclosurescaleactive', '@Insertxscaleactive', '@Insertyscaleactive'])
		for sc in self.all_scales:
			rules.append(simple_sub_rule(\
					[self.scale_group_active_(sc), self.width_scale_active_(sc), self.height_scale_active_(sc)],
					[self.scale_group_active_(sc)]))
			rules.append(simple_sub_rule([self.cap_scale_active_(sc)], [self.cap_scale_(sc)]))
			rules.append(simple_sub_rule([self.enclosure_scale_active_(sc)], [self.enclosure_scale_(sc)]))
			rules.append(simple_sub_rule([self.insert_x_scale_active_(sc)], [self.insert_x_scale_(sc)]))
			rules.append(simple_sub_rule([self.insert_y_scale_active_(sc)], [self.insert_y_scale_(sc)]))
		return name, rules, filt

	def empty_insertion_scaling_rules(self):
		name, rules = 'empty-insertion-scaling', []
		rules.append(simple_sub_rule([self.insert_sep], 
				[sym for s in self.all_scales for sym in [self.scale_(s)] + 
						self.len_oct * [self.to_scale]]))
		return name, rules

	def copy_insertion_rules(self):
		name, rules = 'copy-insertion', []
		for p in self.all_poss:
			for d in all_digits:
				rules.append(context_sub_rule(\
					[self.insert_(d)] + (self.len_oct-1-p) * ['@Insert'] + [self.scale_(0)] + p * ['@Sizescaled'], self.to_scale, [], 
					self.size_scaled_(d)))
		return name, rules

	def filter_insertion_scale_rules(self):
		name, rules, filt = 'filter-insertion-scale', [], '@AuxFilterInsertionScale'
		self.add_class(filt, ['@Insertxscale', '@Insertyscale', '@Sizescaled', '@Scale', self.nil_scale])
		for sc in self.all_scales:
			rules.append(context_sub_rule([self.insert_x_scale_(sc)], '@Sizescaled', [], self.nil))
			for sc_small in range(sc):
				rules.append(context_sub_rule([self.insert_x_scale_(sc)], self.scale_(sc_small), [], self.nil))
		for sc in self.all_scales:
			rules.append(context_sub_rule([self.insert_y_scale_(sc)], '@Sizescaled', [], self.nil))
			for sc_small in range(sc):
				rules.append(context_sub_rule([self.insert_y_scale_(sc)], self.scale_(sc_small), [], self.nil))
		for sc in self.all_scales:
			for d in all_digits:
				rules.append(context_sub_rule([self.insert_x_scale_(sc), self.scale_(sc)],
					self.size_scaled_(d), [], self.insert_x_(d)))
				rules.append(context_sub_rule([self.insert_y_scale_(sc), self.scale_(sc)],
					self.size_scaled_(d), [], self.insert_y_(d)))
		for sc in self.all_scales:
			rules.append(context_sub_rule([self.nil_scale], '@Sizescaled', [], self.nil_scale))
			for sc_greater in range(sc+1, self.n_scales):
				rules.append(context_sub_rule([self.scale_(sc)], self.scale_(sc_greater), [], self.nil_scale))
		rules.append(context_sub_rule([self.nil_scale], '@Scale', [], self.nil_scale))
		return name, rules, filt

	def filter_insert_cleanup1_rules(self):
		name, rules = 'filter-insertion-cleanup1', []
		for sc in self.all_scales:
			rules.append(simple_sub_rule([self.insert_x_scale_(sc)], [self.nil]))
			rules.append(simple_sub_rule([self.insert_y_scale_(sc)], [self.nil]))
			rules.append(simple_sub_rule([self.scale_(sc)], [self.insert_sep]))
		for d in all_digits:
			rules.append(simple_sub_rule([self.insert_(d)], [self.nil]))
		rules.append(simple_sub_rule([self.nil_scale], [self.nil]))
		return name, rules

	def filter_insert_cleanup2_rules(self):
		name, rules, filt = 'filter-insertion-cleanup2', [], '@AuxFilterInsertCleanup2'
		self.add_class(filt, ['@Undone', self.nil])
		for level in all_levels:
			rules.append(simple_sub_rule([self.open_(level)] + self.n_scales * 2 * (self.len_oct+1) * [self.nil], [self.open_(level)]))
		return name, rules, filt

	###### Padding analysis

	def padding_analysis(self):
		"""
		Before width_to_size, we have either:
		(1) outeropen width_scaled_active height_active size_sep size [and then size is part of padding]
		or
		(2) outeropen width_scaled_active height_active size_full_sep size [and then size is full size]
		or
		(3) outeropen width_scaled_active height_active size_full_sep size_full_scaled [which is content size of enclosure]
		After width_to_size the width_scaled_active becomes size. After summing we get:
		(1) outeropen size height_active size_sep size [=sum, which becomes the full size]
		or
		(2) outeropen size height_active size_full_sep size [=still full size from before]
		or
		(3) unchanged.
		After size_full, (2) and (3) have same form as (1).
		"""
		"""
		top_width_pad/top_height_pad: set full dimensions on top-level groups, or initialize padding to 0.
		width_to_size/height_to_size: get dimension.
		[add padding to full size, unless full dimension already established].
		size_full: Establish full dimension.
		width_diff_init/height_diff_init: prepare for subtracting dimension from full dimension and doing division.
		diff: subtract dimension from full dimension.
		nonnegative: for non-negative difference (borrow in most significant digit), set to 0.
		[remove borrow (carry) tags]
		size_to_width/size_to_height: keep dimension and full dimension for width/height.
		reverse_pad: reverse dimension.
		binarize: turn octal into binary.
		division: divide difference by group length.
		division_final: tag remainder of division.
		clean_remain: remove difference before division and remove intermediate remainders.
		unbinarize: turn quotient from binary into octal.
		unreverse: reverse quotient.
		clean_pad1: remove separators, nils and quotient before reversal.
		init_inner_pad: add tags to inner groups, for receiving difference or full dimensions.
		init_first_pad: for insertion and overlay, prepare for copying full dimension.
		init_last_pad_width/init_last_pad_height: prepare for adding remainder to last subgroup, or
			for copying full dimension.
		remain_pad: copy remainder.
		clean_pad2: replace remainder by nil.
		zero: prepare for copying quotient or full dimension.
		copy_full_size: copy full dimension.
		full_size_to_width/full_size_to_height: keep full dimension of outer group as width/height.
		expand_remain: turn remainder into digits.
		[adding quotient across subgroups]
		clean_pad3: remove quotient, nil and separator.
		inner_full_size: put full dimension in proper format.
		"""
		self.add_sub_lookup(*self.zero_pad_subrules())
		self.add_sub_lookup(*self.unit_pad_subrules())
		self.add_sub_lookup(*self.inner_pad_subrules())
		self.add_sub_lookup(*self.init_diff_subrules())
		self.add_sub_lookup(*self.init_full_subrules())
		self.add_sub_lookup(*self.size_to_width_digit_subrules())
		self.add_sub_lookup(*self.size_to_height_digit_subrules())
		self.add_sub_lookup(*self.size_to_full_digit_subrules())
		self.add_sub_lookup(*self.make_zero_subrules())
		for b in [0,1]:
			for r in all_remainders:
				self.add_sub_lookup(*self.quotient_remain_subrules(b, r))
		for r in all_remainders:
			self.add_sub_lookup(*self.remain_subrules(r))
		for sc in self.all_scales:
			self.add_sub_lookup(*self.insert_content_subrules(sc))

		for do_width in [True, False]:
			self.add_main_lookup(*(self.top_width_pad_rules() if do_width else self.top_height_pad_rules()))
			for d in range(0, self.max_depth):
				if d+1 < self.max_depth:
					self.add_main_lookup(*self.inner_depth_rules(d+1))
				self.add_main_lookup(*self.outer_depth_rules(d))

				self.add_main_lookup(*(self.width_to_size_rules() if do_width else self.height_to_size_rules()))
				self.add_main_lookup(*self.summing_rules())
				self.add_main_lookup(*self.normalize_arithmetic_rules())
				self.add_main_lookup(*self.size_full_rules())
				self.add_main_lookup(*(self.width_diff_init_rules() if do_width else self.height_diff_init_rules()))
				self.add_main_lookup(*self.diff_rules())
				if do_width and d == 0:
					pass
				self.add_main_lookup(*self.nonnegative_rules())
				self.add_main_lookup(*self.normalize_arithmetic_rules())
				self.add_main_lookup(*(self.size_to_width_rules() if do_width else self.size_to_height_rules()))
				self.add_main_lookup(*self.reverse_pad_rules())
				self.add_main_lookup(*self.binarize_rules())
				self.add_main_lookup(*self.division_rules())
				self.add_main_lookup(*self.division_final_rules())
				self.add_main_lookup(*self.clean_remain_rules())
				self.add_main_lookup(*self.unbinarize_rules())
				self.add_main_lookup(*self.unreverse_rules())
				self.add_main_lookup(*self.clean_pad1_rules())
				if d+1 < self.max_depth:
					self.add_main_lookup(*self.init_inner_pad_rules())
					self.add_main_lookup(*(self.init_enclosure_width_pad_rules() if do_width else self.init_enclosure_height_pad_rules()))
					self.add_main_lookup(*self.init_first_pad_rules())
					self.add_main_lookup(*(self.init_last_pad_width_rules() if do_width else self.init_last_pad_height_rules()))
					self.add_main_lookup(*self.remain_pad_rules())
				self.add_main_lookup(*self.clean_pad2_rules())
				self.add_main_lookup(*self.zero_rules())
				self.add_main_lookup(*self.copy_full_size_rules())
				self.add_main_lookup(*(self.full_size_to_width_rules() if do_width else self.full_size_to_height_rules()))
				self.add_main_lookup(*self.expand_remain_rules())
				self.add_main_lookup(*self.summing_rules())
				self.add_main_lookup(*self.normalize_arithmetic_rules())
				self.add_main_lookup(*self.clean_pad3_rules())
				if d+1 < self.max_depth:
					self.add_main_lookup(*self.inner_full_size_rules())

				self.add_main_lookup(*self.bracket_reset_rules())
		
	def zero_pad_subrules(self):
		name, rules = 'zero-pad', []
		rules.append(simple_sub_rule([self.record], [self.size_sep] + self.len_oct * [self.size_(0)] + [self.record]))
		return name, rules

	def unit_pad_subrules(self):
		name, rules = 'unit-pad', []
		rules.append(simple_sub_rule([self.record], [self.size_full_sep] + self.to_octal_size(self.font_units) + [self.record]))
		return name, rules

	def inner_pad_subrules(self):
		name, rules = 'inner-pad', []
		rules.append(simple_sub_rule([self.record], [self.inner_pad, self.record]))
		return name, rules

	def init_diff_subrules(self):
		name, rules = 'init-diff', []
		rules.append(simple_sub_rule([self.record_active], \
			[self.size_sep] + self.len_oct * [self.to_diff] + \
			[self.size_reverse_sep] + [self.pos_reverse_(p) for p in self.all_poss] + \
			[self.size_unreverse_sep] + [self.pos_unreverse_(p) for p in self.all_poss] + [self.record_active]))
		return name, rules

	def init_full_subrules(self):
		name, rules = 'init-full', []
		rules.append(simple_sub_rule([self.record_active], \
			[self.size_sep] + self.len_oct * [self.to_full] + \
			[self.size_reverse_sep] + [self.pos_reverse_(p) for p in self.all_poss] + \
			[self.size_unreverse_sep] + [self.pos_unreverse_(p) for p in self.all_poss] + [self.record_active]))
		return name, rules

	def size_to_width_digit_subrules(self):
		name, rules = 'size-to-width-digit', []
		for d in all_digits:
			rules.append(simple_sub_rule([self.size_(d)], [self.width_(d)]))
		return name, rules

	def size_to_height_digit_subrules(self):
		name, rules = 'size-to-height-digit', []
		for d in all_digits:
			rules.append(simple_sub_rule([self.size_(d)], [self.height_(d)]))
		return name, rules

	def size_to_full_digit_subrules(self):
		name, rules = 'size-to-full-digit', []
		for d in all_digits:
			rules.append(simple_sub_rule([self.size_(d)], [self.size_full_(d)]))
		return name, rules

	def make_zero_subrules(self):
		name, rules = 'make-zero', []
		rules.append(simple_sub_rule(['@MaybeCarry'], [self.size_(0)]))
		return name, rules

	def quotient_remain_subrules(self, b, r):
		name, rules = f'quotient-remain-{b}-{r}', []
		rules.append(simple_sub_rule(['@Bit'], [self.quotient_(b), self.remain_(r)]))
		return name, rules
	
	def remain_subrules(self, r0):
		name, rules, filt = f'remain-{r0}', [], '@AuxRemain'
		self.add_class(filt, ['@Length', '@Bit'])
		for divisor in range(r0+1, MAX_COUNT+1):
			for b in [0,1]:
				q, r1 = quotient_remain(r0 * 2 + b, divisor)
				rules.append(chain_sub_rule([self.length_(divisor)], [(self.bit_(b), [f'quotient-remain-{q}-{r1}'])], []))
		return name, rules, filt

	def top_width_pad_rules(self):
		name, rules, filt = 'top-width-pad', [], '@AuxTopWidthPad'
		self.add_class(filt, ['@Undone', self.depth_(0), '@Direction', self.record])
		rules.append(chain_sub_rule(['@Undoneopen', self.horizontal, self.depth_(0)], [(self.record, ['zero-pad'])], []))
		rules.append(chain_sub_rule(['@Undoneopen', self.vertical, self.depth_(0)], [(self.record, ['unit-pad'])], []))
		return name, rules, filt

	def top_height_pad_rules(self):
		name, rules, filt = 'top-height-pad', [], '@AuxTopHeightPad'
		self.add_class(filt, ['@Undone', self.depth_(0), '@Direction', self.record])
		rules.append(chain_sub_rule(['@Undoneopen', self.horizontal, self.depth_(0)], [(self.record, ['unit-pad'])], []))
		rules.append(chain_sub_rule(['@Undoneopen', self.vertical, self.depth_(0)], [(self.record, ['zero-pad'])], []))
		return name, rules, filt

	def width_to_size_rules(self):
		name, rules, filt = 'width-to-size', [], '@AuxWidthToSize'
		self.add_class(filt, ['@Outeropen', '@WidthFullScaled', '@Scalegroupactive', '@Widthscaledactive', self.record_active])
		for d in all_digits:
			rules.append(context_sub_rule(['@Outeropen'], self.width_scaled_active_(d), [], self.size_(d)))
		for sc in self.all_scales:
			rules.append(context_sub_rule(['@Outeropen'], self.scale_group_active_(sc), [], self.scale_group_(sc)))
		return name, rules, filt

	def height_to_size_rules(self):
		name, rules, filt = 'height-to-size', [], '@AuxHeightToSize'
		self.add_class(filt, ['@Outeropen', '@HeightFullScaled', '@Scalegroupactive', '@Heightscaledactive', self.record_active])
		for d in all_digits:
			rules.append(context_sub_rule(['@Outeropen'], self.height_scaled_active_(d), [], self.size_(d)))
		for sc in self.all_scales:
			rules.append(context_sub_rule(['@Outeropen'], self.scale_group_active_(sc), [], self.scale_group_(sc)))
		return name, rules, filt

	def size_full_rules(self):
		name, rules, filt = 'size-full', [], '@AuxSizeFull'
		self.add_class(filt, [self.size_full_sep, '@SizeFullScaled'])
		rules.append(simple_sub_rule([self.size_full_sep], [self.size_sep]))
		for d in all_digits:
			rules.append(simple_sub_rule([self.size_full_scaled_(d)], [self.size_(d)]))
		return name, rules, filt

	def width_diff_init_rules(self):
		name, rules, filt = 'width-diff-init', [], '@AuxWidthDiffInit'
		base_names = list(set(self.sym[lig.ch] for lig in horizontal_ligatures()))
		self.add_class(filt, ['@Outer', '@Inner', '@Recordactive'] + base_names)
		for base_name in base_names:
			rules.append(chain_sub_rule([self.open_outer_('h')], [(self.record_active, ['init-full'])], [base_name]))
		rules.append(chain_sub_rule([self.open_outer_('h')], [(self.record_active, ['init-diff'])], []))
		return name, rules, filt

	def height_diff_init_rules(self):
		name, rules, filt = 'height-diff-init', [], '@AuxHeightDiffInit'
		base_names = list(set(self.sym[lig.ch] for lig in vertical_ligatures()))
		self.add_class(filt, ['@Outer', '@Inner', '@Recordactive'] + base_names)
		for base_name in base_names:
			rules.append(chain_sub_rule([self.open_outer_('v')], [(self.record_active, ['init-full'])], [base_name]))
		rules.append(chain_sub_rule([self.open_outer_('v')], [(self.record_active, ['init-diff'])], []))
		return name, rules, filt

	def diff_rules(self):
		name, rules, filt = 'diff', [], '@AuxDiff'
		self.add_class(filt, ['@Outer', '@MaybeCarry', self.to_diff, self.to_full, self.record_active])
		def subtract_borrow(d):
			return d % 8, d < 0
		for d2 in all_digits:
			rules.append(context_sub_rule([self.size_(d2)] + self.len_oct * ['@NoCarry'], self.to_full, [], self.size_(d2)))
		for d1 in all_digits:
			d1_sym = self.size_(d1)
			for d2 in all_digits:
				s, b = subtract_borrow(d2-d1)
				borrow_s, borrow_b = subtract_borrow(d2-d1-1)
				out = self.carry_(s) if b else self.size_(s)
				borrow_out = self.carry_(borrow_s) if borrow_b else self.size_(borrow_s)
				rules.append(context_sub_rule([self.size_(d1)] + self.len_oct * ['@NoCarry'] + \
						[self.size_(d2)] + (self.len_oct-1) * ['@MaybeCarry'] + ['@NoCarry'], \
						self.to_diff, [], out))
				rules.append(context_sub_rule([self.size_(d1)] + self.len_oct * ['@NoCarry'] + \
						[self.size_(d2)] + (self.len_oct-1) * ['@MaybeCarry'] + ['@Carry'], \
						self.to_diff, [], borrow_out))
		return name, rules, filt

	def nonnegative_rules(self):
		name, rules, filt = 'nonnegative', [], '@MaybeCarry'
		rules.append(chain_sub_rule([self.size_sep], \
				(self.len_oct-1) * [('@MaybeCarry', ['make-zero'])] + [('@Carry', ['make-zero'])], []))
		return name, rules, filt

	def size_to_width_rules(self):
		name, rules, filt = 'size-to-width', [], '@AuxSizeToWidth'
		self.add_class(filt, ['@Outeropen', '@Size', self.size_sep, self.record_active])
		rules.append(chain_sub_rule(['@Outeropen'], self.len_oct * [('@Size', ['size-to-width-digit'])], []))
		rules.append(chain_sub_rule(['@Outeropen', self.size_sep], self.len_oct * [('@Size', ['size-to-full-digit'])], []))
		return name, rules, filt

	def size_to_height_rules(self):
		name, rules, filt = 'size-to-height', [], '@AuxSizeToHeight'
		self.add_class(filt, ['@Outeropen', '@Size', self.size_sep, self.record_active])
		rules.append(chain_sub_rule(['@Outeropen'], self.len_oct * [('@Size', ['size-to-height-digit'])], []))
		rules.append(chain_sub_rule(['@Outeropen', self.size_sep], self.len_oct * [('@Size', ['size-to-full-digit'])], []))
		return name, rules, filt

	def reverse_pad_rules(self):
		name, rules, filt = 'reverse-pad', [], '@AuxReversePad'
		self.add_class(filt, [self.size_reverse_sep, '@Size', '@Posreverse'])
		for d in all_digits:
			for p in self.all_poss:
				rules.append(context_sub_rule([self.size_(d)] + p * ['@Size'] + [self.size_reverse_sep],
					self.pos_reverse_(p), [], self.size_reverse_(d)))
		return name, rules, filt

	def binarize_rules(self):
		name, rules, filt = 'binarize', [], '@AuxBinarize'
		self.add_class(filt, [self.size_reverse_sep, '@Sizereverse'])
		rules.append(simple_sub_rule([self.size_reverse_sep], [self.size_reverse_sep, self.remain_(0)]))
		for d in all_digits:
			rules.append(simple_sub_rule([self.size_reverse_(d)], self.to_binary(d)))
		return name, rules, filt

	def division_rules(self):
		name, rules, filt = 'division', [], '@AuxDivision'
		self.add_class(filt, ['@Length', '@Remain', '@Bit'])
		for r in all_remainders:
			rules.append(chain_sub_rule([self.remain_(r)], [('@Bit', [f'remain-{r}'])], []))
		return name, rules, filt

	def division_final_rules(self):
		name, rules, filt = 'division-final', [], '@AuxDivisionFinal'
		self.add_class(filt, ['@Remain', self.size_unreverse_sep])
		for r in all_remainders:
			rules.append(context_sub_rule([], self.remain_(r), [self.size_unreverse_sep], self.remain_final_(r)))
		return name, rules, filt

	def clean_remain_rules(self):
		name, rules, filt = 'clean-remain', [], '@AuxCleanRemain'
		self.add_class(filt, [self.size_sep, '@Size', self.size_reverse_sep, '@Remain'])
		rules.append(simple_sub_rule([self.size_sep] + self.len_oct * ['@Size'], [self.nil]))
		rules.append(simple_sub_rule(['@Remain'], [self.nil]))
		return name, rules, filt

	def unbinarize_rules(self):
		name, rules, filt = 'unbinarize', [], '@Quotient'
		for d in all_digits:
			rules.append(simple_sub_rule(self.to_binary_quotient(d), [self.size_reverse_(d)]))
		return name, rules, filt

	def unreverse_rules(self):
		name, rules, filt = 'unreverse', [], '@AuxUnreverse'
		self.add_class(filt, [self.size_unreverse_sep, '@Sizereverse', '@Posunreverse'])
		for d in all_digits:
			for p in self.all_poss:
				rules.append(context_sub_rule([self.size_reverse_(d)] + p * ['@Sizereverse'] + [self.size_unreverse_sep],
					self.pos_unreverse_(p), [], self.size_(d)))
		return name, rules, filt

	def clean_pad1_rules(self):
		name, rules, filt = 'clean-pad1', [], '@AuxCleanPad1'
		self.add_class(filt, ['@Outer', self.size_sep, self.nil, self.size_reverse_sep, '@Size', '@Sizereverse'])
		for level in 'hv':
			rules.append(simple_sub_rule([self.open_outer_(level), self.size_sep, self.nil, self.size_reverse_sep] + \
					self.len_oct * [self.nil, '@Sizereverse', self.nil, self.nil], [self.open_outer_(level)]))
		for level in all_levels:
			rules.append(simple_sub_rule([self.open_outer_(level), self.size_sep], [self.open_outer_(level)]))
		return name, rules, filt

	def init_inner_pad_rules(self):
		name, rules, filt = 'init-inner-pad', [], '@AuxInitInnerPad'
		self.add_class(filt, ['@Inner', self.record])
		rules.append(chain_sub_rule(['@Inneropen'], [(self.record, ['inner-pad'])], []))
		return name, rules, filt

	def insert_content_subrules(self, sc):
		name, rules = f'insert-content-{sc}', []
		n = SCALEDOWN ** (sc+1) * self.font_units
		rules.append(simple_sub_rule([self.inner_pad], \
			[self.size_full_sep] + self.to_octal_size_full_scaled(n)))
		return name, rules

	def init_enclosure_width_pad_rules(self):
		name, rules, filt = 'init-enclosure-width-pad', [], '@AuxInitEnclosureWidthPad'
		self.add_class(filt, ['@Outer', '@Directionactive', '@Scalegroup', self.inner_pad])
		for level in 'pw':
			for sc in self.all_scales:
				rules.append(chain_sub_rule([self.open_outer_(level), self.vertical_active, self.scale_group_(sc)],
					[(self.inner_pad, [f'insert-content-{sc}'])], []))
		return name, rules, filt

	def init_enclosure_height_pad_rules(self):
		name, rules, filt = 'init-enclosure-height-pad', [], '@AuxInitEnclosureHeightPad'
		self.add_class(filt, ['@Outer', '@Directionactive', '@Scalegroup', self.inner_pad])
		for level in 'pw':
			for sc in self.all_scales:
				rules.append(chain_sub_rule([self.open_outer_(level), self.horizontal_active, self.scale_group_(sc)],
					[(self.inner_pad, [f'insert-content-{sc}'])], []))
		return name, rules, filt

	def init_first_pad_rules(self):
		name, rules, filt = 'init-first-pad', [], '@AuxInitFirstPad'
		self.add_class(filt, ['@OuterInner', self.inner_pad])
		rules.append(context_sub_rule([self.open_outer_('i'), '@Inneropen'], self.inner_pad, [], self.first_pad))
		rules.append(context_sub_rule([self.open_outer_('o'), '@Inneropen'], self.inner_pad, [], self.first_pad))
		rules.append(context_sub_rule([], self.inner_pad, ['@Innerclose', self.close_outer_('o')], self.first_pad))
		return name, rules, filt

	def init_last_pad_width_rules(self):
		name, rules, filt = 'init-last-pad-width', [], '@AuxInitLastPad'
		self.add_class(filt, ['@Outer', self.inner_pad])
		rules.append(context_sub_rule([], self.inner_pad, [self.close_outer_('h')], self.last_pad))
		rules.append(context_sub_rule([self.open_outer_('v')], self.inner_pad, [], self.first_pad))
		return name, rules, filt

	def init_last_pad_height_rules(self):
		name, rules, filt = 'init-last-pad-height', [], '@AuxInitLastPad'
		self.add_class(filt, ['@Outer', self.inner_pad])
		rules.append(context_sub_rule([], self.inner_pad, [self.close_outer_('v')], self.last_pad))
		rules.append(context_sub_rule([self.open_outer_('h')], self.inner_pad, [], self.first_pad))
		return name, rules, filt

	def remain_pad_rules(self):
		name, rules, filt = 'remain-pad', [], '@AuxRemainPad'
		self.add_class(filt, ['@Outer', '@RemainFinal', self.last_pad])
		for n in all_remainders:
			rules.append(context_sub_rule([self.remain_final_(n)], self.last_pad, [], self.remain_(n)))
		return name, rules, filt

	def clean_pad2_rules(self):
		name, rules, filt = 'clean-pad2', [], '@AuxCleanPad2'
		self.add_class(filt, ['@RemainFinal', '@Scalegroup'])
		rules.append(simple_sub_rule(['@RemainFinal'], [self.nil]))
		for sc in self.all_scales:
			rules.append(simple_sub_rule([self.scale_group_(sc)], [self.scale_group_active_(sc)]))
		return name, rules, filt

	def zero_rules(self):
		name, rules, filt = 'zero', [], '@AuxZero'
		self.add_class(filt, [self.inner_pad, self.first_pad, self.last_pad])
		rules.append(simple_sub_rule([self.inner_pad], [self.size_sep] + self.len_oct * [self.size_(0)]))
		rules.append(simple_sub_rule([self.first_pad], [self.size_full_sep] + self.len_oct * [self.size_full_(0)]))
		return name, rules, filt

	def copy_full_size_rules(self):
		name, rules, filt = 'copy-full-size', [], '@AuxCopyFullSize'
		self.add_class(filt, ['@Outer', '@SizeFull'])
		for d in all_digits:
			rules.append(context_sub_rule([self.size_full_(d)] + (self.len_oct-1) * ['@SizeFull'], \
					self.size_full_(0), [], self.size_full_(d)))
		return name, rules, filt

	def full_size_to_width_rules(self):
		name, rules, filt = 'full-size-to-width', [], '@FullSizeToWidth'
		self.add_class(filt, ['@Outer', '@SizeFull', self.record_active])
		for d in all_digits:
			rules.append(context_sub_rule(['@Outeropen'], self.size_full_(d), [], self.width_full_(d)))
		return name, rules, filt

	def full_size_to_height_rules(self):
		name, rules, filt = 'full-size-to-height', [], '@FullSizeToHeight'
		self.add_class(filt, ['@Outer', '@SizeFull', self.record_active])
		for d in all_digits:
			rules.append(context_sub_rule(['@Outeropen'], self.size_full_(d), [], self.height_full_(d)))
		return name, rules, filt

	def expand_remain_rules(self):
		name, rules, filt = 'expand-remain', [], '@Remain'
		for n in all_remainders:
			rules.append(simple_sub_rule([self.remain_(n)], [self.size_sep] + self.int_to_octal_size(n)))
		return name, rules, filt

	def clean_pad3_rules(self):
		name, rules, filt = 'clean-pad3', [], '@AuxCleanPad3'
		self.add_class(filt, [self.open_outer_(level) for level in 'hv'] + \
				[self.nil, self.size_unreverse_sep, '@Size'])
		for level in 'hv':
			rules.append(simple_sub_rule([self.open_outer_(level), self.nil, self.size_unreverse_sep] + \
					self.len_oct * ['@Size'], [self.open_outer_(level)]))
		return name, rules, filt

	def inner_full_size_rules(self):
		name, rules, filt = 'inner-full-size', [], '@AuxInnerFullSize'
		self.add_class(filt, ['@Inner', '@SizeFull'])
		for d in all_digits:
			rules.append(context_sub_rule(['@Inneropen'], self.size_full_(d), [], self.size_(d)))
		return name, rules, filt

	###### Substitution

	def substitution(self):
		"""
		mirror: replace mirrored signs.
		lost: add control that will lead to shading for expanding lost signs.
		scale_duplication: break up scaling into units.
		scaled_glyph: repeatedly scale down glyph.
		bracket_anchor: place anchor indicating depth in front of bracket.
		bracket_duplicate: replace brackets by scaled brackets and their sizes, 
			preceded by placeholder for height of enclosed group.
			Also select height of enclosed group for subsequent copying.
		bracket_size_copy: copy height of following or preceding group.
		bracket_size_compare: compare group height to each of heights of scaled brackets, digit-by-digit.
		bracket_size_normalize: limit attention to comparisons.
		big_bracket: erase scalings that are too big and remove trailing scalings.
		cleanup_size_copy1: replace copied size by nils.
		cleanup_size_copy2: compress series of nils into single nil.
		cleanup_bracket: restore height of group and assimilate nils into chosen bracket.
		cap: replace a cap with its scaled form.
		enclosure: add depth to the markers for anchors of caps.
		"""
		if False: # to become relevant for right-to-left text
			self.add_sub_lookup(*self.add_mirror_subrules())
			self.add_main_lookup(*self.rtlm1_rules())
			self.add_main_lookup(*self.rtlm2_rules())
		self.add_main_lookup(*self.mirror_rules())
		self.add_main_lookup(*self.lost_rules())
		for sc in self.all_scales[1:]:
			self.add_sub_lookup(*self.scale_insert_subrules(sc))
		self.add_main_lookup(*self.scale_duplication_rules())
		for sc in self.all_scales[1:]:
			self.add_main_lookup(*self.scaled_glyph_rules(sc))

		self.add_sub_lookup(*self.bracket_duplicate_subrules())
		for d in self.all_depths:
			self.add_sub_lookup(*self.bracket_insert_anchor_subrules(d))
		self.add_sub_lookup(*self.height_select_subrules())
		self.add_sub_lookup(*self.remove_bracket_cmp_subrules())
		for d in range(1, self.max_depth):
			self.add_main_lookup(*self.bracket_anchor_rules(d))
			self.add_main_lookup(*self.bracket_duplicate_rules(d))
			self.add_main_lookup(*self.bracket_size_copy_rules())
			self.add_main_lookup(*self.bracket_size_compare_rules())
			self.add_main_lookup(*self.bracket_size_normalize_rules())
			self.add_main_lookup(*self.big_bracket_rules())
			self.add_main_lookup(*self.cleanup_size_copy1_rules())
			self.add_main_lookup(*self.cleanup_size_copy2_rules())
			self.add_main_lookup(*self.cleanup_bracket_rules())
		self.add_main_lookup(*self.cap_rules())
		self.add_main_lookup(*self.enclosure_rules())

	def add_mirror_subrules(self):
		name, rules, filt = 'add-mirror', [], '@Depth'
		for d in self.all_depths:
			rules.append(simple_sub_rule([self.depth_(d)], [self.mirror, self.depth_(d)]))
		return name, rules, filt

	def rtlm1_rules(self):
		name, rules, filt, feat = 'rtlm1', [], '@AuxRtlm1', 'rtlm'
		self.add_class(filt, ['@Depth', '@Undone'])
		rules.append(chain_sub_rule([], [('@Depth', ['add-mirror'])], [self.close_('b')]))
		return name, rules, filt, feat

	def rtlm2_rules(self):
		name, rules, filt, feat = 'rtlm2', [], '@AuxRtlm2', 'rtlm'
		self.add_class(filt, ['@Undone', self.mirror])
		rules.append(simple_sub_rule([self.mirror, self.mirror], [self.no_mirror]))
		return name, rules, filt, feat

	def mirror_rules(self):
		name, rules = 'mirror', []
		for sign, mirrored in self.name_to_mirrored.items():
			rules.append(simple_sub_rule([sign, self.mirror], [mirrored]))
		return name, rules

	def lost_rules(self):
		name, rules = 'lost', []
		rules.append(simple_sub_rule([self.full_lost_exp], [self.damaged[-1]]))
		rules.append(simple_sub_rule([self.half_lost_exp], [self.damaged[-1]]))
		rules.append(simple_sub_rule([self.tall_lost_exp], [self.damaged[-1]]))
		rules.append(simple_sub_rule([self.wide_lost_exp], [self.damaged[-1]]))
		return name, rules

	def scale_insert_subrules(self, sc):
		name, rules = f'scale-insert-{sc}', []
		rules.append(simple_sub_rule([self.record], [self.record] + sc * [self.scale_group_active_(1)]))
		return name, rules

	def scale_duplication_rules(self):
		name, rules, filt = 'scale-duplication', [], '@AuxScaleDuplication'
		self.add_class(filt, [self.open_('b'), '@Scalegroupactive', self.record])
		for sc in self.all_scales[1:]:
			rules.append(chain_sub_rule([self.open_('b'), self.scale_group_active_(sc)], [(self.record, [f'scale-insert-{sc}'])], []))
		return name, rules, filt

	def scaled_glyph_rules(self, sc):
		name, rules = f'scaled-glyph-{sc}', []
		for (sign, scale), smaller in self.name_scale_to_name.items():
			if scale == sc:
				bigger = sign if sc == 1 else self.name_scale_to_name[(sign, sc-1)]
				rules.append(simple_sub_rule([self.scale_group_active_(1), bigger], [smaller]))
		for (lost, scale), smaller in self.lost_scale_to_lost.items():
			if scale == sc:
				bigger = lost if sc == 1 else self.lost_scale_to_lost[(lost, sc-1)]
				rules.append(simple_sub_rule([self.scale_group_active_(1), bigger], [smaller]))
		return name, rules

	def bracket_duplicate_subrules(self):
		name, rules = 'bracket-duplicate', []
		for bracket in self.brackets:
			bracket_list = [self.pos_bracket_(i) for i in self.all_poss]
			for sc in self.all_scales:
				bracket_scaled = self.bracket_scale_to_bracket[(bracket, sc)]
				size = self.to_octal_limit_height(SCALEDOWN ** sc * self.font_units)
				bracket_list.extend([bracket_scaled] + size)
			bracket_list.append(self.nil_scale)
			rules.append(simple_sub_rule([bracket], bracket_list))
		return name, rules

	def bracket_insert_anchor_subrules(self, d):
		name, rules = f'bracket-insert-anchor-{d}', []
		for bracket in self.brackets:
			rules.append(simple_sub_rule([bracket], [self.bracket_anchor_(d), bracket]))
		return name, rules

	def height_select_subrules(self):
		name, rules = 'height-select', []
		for d in all_digits:
			rules.append(simple_sub_rule([self.height_full_(d)], [self.height_full_scaled_(d)]))
		return name, rules

	def remove_bracket_cmp_subrules(self):
		name, rules = 'remove-bracket-cmp', []
		rules.append(simple_sub_rule(['@BracketScaled'], [self.nil]))
		rules.append(simple_sub_rule([self.lt_(0)], [self.nil]))
		rules.append(simple_sub_rule([self.gt_(0)], [self.nil]))
		rules.append(simple_sub_rule([self.eq_(0)], [self.nil]))
		return name, rules

	def bracket_anchor_rules(self, d):
		name, rules, filt = f'bracket-anchor-{d}', [], '@AuxBracketAnchor'
		self.add_class('@AuxBracketAnchor', ['@Undone', '@Depth', self.record, '@Bracket'])
		rules.append(chain_sub_rule([], [('@OpenBracket', [f'bracket-insert-anchor-{d}'])], ['@Undoneopen', self.depth_(d)]))
		rules.append(chain_sub_rule([self.depth_(d), '@Undoneclose'], [('@CloseBracket', [f'bracket-insert-anchor-{d}'])], []))
		return name, rules, filt

	def bracket_duplicate_rules(self, d):
		name, rules, filt = f'bracket-duplicate-{d}', [], '@AuxOpenBracketDuplicate'
		self.add_class(filt, ['@Undone', '@Depth', self.record, '@Bracket', '@HeightFull'])
		rules.append(chain_sub_rule([], [('@OpenBracket', ['bracket-duplicate'])], ['@Undoneopen', self.depth_(d)]))
		rules.append(chain_sub_rule(['@Undoneopen', self.depth_(d)], [('@HeightFull', ['height-select'])], []))
		rules.append(chain_sub_rule([self.depth_(d), '@Undoneclose'], [('@CloseBracket', ['bracket-duplicate'])], []))
		return name, rules, filt

	def bracket_size_copy_rules(self):
		name, rules, filt = 'bracket-size-copy', [], '@AuxBracketSizeCopy'
		self.add_class(filt, ['@PosBracket', '@Bracket', '@HeightFullScaled'])
		for p in self.all_poss:
			follow_poss = [self.pos_bracket_(follow) for follow in range(p+1, self.len_oct)]
			for d in all_digits:
				rules.append(context_sub_rule([], self.pos_bracket_(p), \
					follow_poss + ['@OpenBracket'] + p * ['@HeightFullScaled'] + [self.height_full_scaled_(d)], \
					self.size_(d)))
			for d in all_digits:
				rules.append(context_sub_rule([self.height_full_scaled_(d)] + (self.len_oct-1-p) * ['@HeightFullScaled'], \
					self.pos_bracket_(p), \
					follow_poss + ['@CloseBracket'], self.size_(d)))
		return name, rules, filt

	def bracket_size_compare_rules(self):
		name, rules, filt = 'bracket-size-compare', [], '@AuxBracketSizeCompare'
		self.add_class(filt, ['@Size', '@Limitheight', '@Cmp'])
		for d1 in all_digits:
			for d2 in all_digits:
				if d1 < d2:
					target = self.gt_(d1)
				elif d1 > d2:
					target = self.lt_(d1)
				else:
					target = self.eq_(d1)
				rules.append(context_sub_rule(
						[self.size_(d1)] + (self.len_oct-1) * ['@AuxBracketSizeCompare'], 
						self.limit_height_(d2), [], target))
				rules.append(context_sub_rule(
						[self.lt_(d1)] + (self.len_oct-1) * ['@AuxBracketSizeCompare'], 
						self.limit_height_(d2), [], target))
				rules.append(context_sub_rule(
						[self.gt_(d1)] + (self.len_oct-1) * ['@AuxBracketSizeCompare'], 
						self.limit_height_(d2), [], target))
				rules.append(context_sub_rule(
						[self.eq_(d1)] + (self.len_oct-1) * ['@AuxBracketSizeCompare'], 
						self.limit_height_(d2), [], target))
		return name, rules, filt

	def bracket_size_normalize_rules(self):
		name, rules, filt = 'bracket-size-normalize', [], '@Cmp'
		for d in all_digits:
			rules.append(simple_sub_rule([self.lt_(d)], [self.lt_(0)]))
			rules.append(simple_sub_rule([self.gt_(d)], [self.gt_(0)]))
			rules.append(simple_sub_rule([self.eq_(d)], [self.eq_(0)]))
		return name, rules, filt

	def big_bracket_rules(self):
		name, rules, filt = 'big-bracket', [], '@AuxBigBracket'
		self.add_class('@BracketCmp', [self.lt_(0), self.gt_(0), self.eq_(0)])
		self.add_class(filt, ['@Size', '@BracketScaled', '@BracketCmp', self.nil_scale])
		for p in self.all_poss:
			rules.append(chain_sub_rule([], [('@BracketScaledLarger', ['remove-bracket-cmp'])] + \
					p * [('@BracketCmp', ['remove-bracket-cmp'])] + \
					[(self.gt_(0), ['remove-bracket-cmp'])] + \
					(self.len_oct-p-1) * [(self.eq_(0), ['remove-bracket-cmp'])], []))
		rules.append(chain_sub_rule(['@Size', '@BracketScaled'], [(self.lt_(0), ['remove-bracket-cmp'])], []))
		rules.append(chain_sub_rule(['@Size', '@BracketScaled'], [(self.gt_(0), ['remove-bracket-cmp'])], []))
		rules.append(chain_sub_rule(['@Size', '@BracketScaled'], [(self.eq_(0), ['remove-bracket-cmp'])], []))
		rules.append(chain_sub_rule(['@Size', '@BracketScaled'], [('@BracketScaled', ['remove-bracket-cmp'])], []))
		return name, rules, filt

	def cleanup_size_copy1_rules(self):
		name, rules, filt = 'cleanup-size-copy1', [], '@Size'
		for d in all_digits:
			rules.append(simple_sub_rule([self.size_(d)], [self.nil]))
		return name, rules, filt

	def cleanup_size_copy2_rules(self):
		name, rules, filt = 'cleanup-size-copy2', [], '@AuxCleanupSizeCopy2'
		self.add_class(filt, ['@Undone', self.nil, '@BracketScaled'])
		for sc in range(self.n_scales-1, -1, -1):
			l = self.len_oct + sc * (1 + self.len_oct)
			rules.append(simple_sub_rule(l * [self.nil] + [self.nil_scale], [self.nil]))
			rules.append(simple_sub_rule(l * [self.nil], [self.nil]))
		return name, rules, filt

	def cleanup_bracket_rules(self):
		name, rules, filt = 'height-unselect', [], '@AuxCleanupBracket'
		self.add_class(filt, [self.nil, '@HeightFullScaled', '@BracketScaled', self.nil])
		for d in all_digits:
			rules.append(simple_sub_rule([self.height_full_scaled_(d)], [self.height_full_(d)]))
		for bracket in self.brackets_scaled:
			rules.append(simple_sub_rule([self.nil, bracket, self.nil], [bracket]))
		return name, rules, filt

	def cap_rules(self):
		name, rules, filt = 'cap', [], '@AuxCap'
		self.add_class(filt, ['@Capscale', '@Cap'])
		for sc in self.all_scales:
			for cap in self.caps:
				cap_scaled = self.cap_scale_to_cap[(cap, sc)]
				rules.append(simple_sub_rule([self.cap_scale_(sc), cap], [cap_scaled]))
			for cap in self.caps_rot:
				cap_scaled = self.cap_rot_scale_to_cap[(cap, sc)]
				rules.append(simple_sub_rule([self.cap_scale_(sc), cap], [cap_scaled]))
		return name, rules, filt

	def enclosure_rules(self):
		name, rules, filt = 'enclosure', [], '@AuxEnclosure'
		self.add_class(filt, ['@Undone', '@Depth', self.cap_anchor_start, self.cap_anchor_end])
		for level in 'pw':
			for d in self.all_depths[:-1]:
				rules.append(context_sub_rule([self.open_(level), self.depth_(d)], \
					self.cap_anchor_start, [], self.cap_anchor_start_(d+1)))
				rules.append(context_sub_rule([self.open_(level), self.depth_(d)], \
					self.cap_anchor_end, [], self.cap_anchor_end_(d+1)))
				rules.append(context_sub_rule([], self.cap_anchor_start, 
						[self.cap_anchor_end, self.depth_(d), self.close_(level)], self.cap_anchor_start_(d+1)))
				rules.append(context_sub_rule([], self.cap_anchor_end, 
						[self.depth_(d), self.close_(level)], self.cap_anchor_end_(d+1)))
		return name, rules, filt

	###### Shading

	def shading_analysis(self):
		"""
		scaled_cap_size: add dimensions after caps
		damage: break up damage surface into blocks, per pair of digits for width and height,
			first with placeholders for digits.
		damage_w/damage_h: copy digits and where necessary half, rounding up.
		damage_combine: for subblocks of shading combine width and height.
		"""
		self.add_main_lookup(*self.scaled_cap_size_rules())
		self.add_main_lookup(*self.damage_rules())
		self.add_main_lookup(*self.damage_w_rules())
		self.add_main_lookup(*self.damage_h_rules())
		self.add_main_lookup(*self.damage_combine_rules())

	def scaled_cap_size_rules(self):
		name, rules = 'scaled-cap-size', []
		for (sign, sc), scaled in self.cap_scale_to_cap.items():
			factor = SCALEDOWN ** sc
			w, h = self.unscaled_cap_to_size[sign]
			width = factor * (w + self.margin / 2)
			height = factor * h
			rules.append(simple_sub_rule([scaled], [scaled] + self.to_octal_width_full(width) + self.to_octal_height_full(height)))
		for (sign, sc), scaled in self.cap_rot_scale_to_cap.items():
			factor = SCALEDOWN ** sc
			w, h = self.unscaled_cap_rot_to_size[sign]
			width = factor * w
			height = factor * (h + self.margin / 2)
			rules.append(simple_sub_rule([scaled], [scaled] + self.to_octal_width_full(width) + self.to_octal_height_full(height)))
		return name, rules

	def damage_rules(self):
		name, rules = 'damage', []

		half_width = [self.half_right_shade_pos_(i) for i in self.all_poss]
		half_width_last = [self.half_right_shade_pos_(self.all_poss[-1])]
		half_height = [self.half_down_shade_pos_(j) for j in self.all_poss]
		back_width = [self.left_shade_pos_(i) for i in self.all_poss[:-1]]
		half_back_width = [self.half_left_shade_pos_(i) for i in self.all_poss[:-1]]
		half_back_width_full = [self.half_left_shade_pos_(i) for i in self.all_poss]

		full = []
		for j in self.all_poss:
			full.append(self.down_shade_pos_(j))
			for i in self.all_poss:
				full.append(self.w_shade_pos_(i))
				full.append(self.h_shade_pos_(j))
			if j+1 < self.len_oct:
				full.extend(back_width)

		quarter = []
		for j in self.all_poss:
			quarter.append(self.half_down_shade_pos_(j))
			for i in self.all_poss:
				quarter.append(self.half_w_shade_pos_(i))
				quarter.append(self.half_h_shade_pos_(j))
			if j+1 < self.len_oct:
				quarter.extend(half_back_width)

		flat = []
		for j in self.all_poss:
			flat.append(self.half_down_shade_pos_(j))
			for i in self.all_poss:
				flat.append(self.w_shade_pos_(i))
				flat.append(self.half_h_shade_pos_(j))
			if j+1 < self.len_oct:
				flat.extend(back_width)
			
		narrow = []
		for j in self.all_poss:
			narrow.append(self.down_shade_pos_(j))
			for i in self.all_poss:
				narrow.append(self.half_w_shade_pos_(i))
				narrow.append(self.h_shade_pos_(j))
			if j+1 < self.len_oct:
				narrow.extend(half_back_width)

		rules.append(simple_sub_rule([self.damaged[0]], quarter))
		rules.append(simple_sub_rule([self.damaged[1]], half_height + quarter))
		rules.append(simple_sub_rule([self.damaged[2]], narrow))
		rules.append(simple_sub_rule([self.damaged[3]], half_width + quarter))
		rules.append(simple_sub_rule([self.damaged[4]], flat))
		rules.append(simple_sub_rule([self.damaged[5]], 
				half_width + quarter + half_back_width + half_back_width_full + quarter))
		rules.append(simple_sub_rule([self.damaged[6]], flat + back_width + quarter))
		rules.append(simple_sub_rule([self.damaged[7]], half_height + half_width + quarter))
		rules.append(simple_sub_rule([self.damaged[8]], quarter + half_width_last + quarter))
		rules.append(simple_sub_rule([self.damaged[9]], half_height + flat))
		rules.append(simple_sub_rule([self.damaged[10]], quarter + half_back_width + flat))
		rules.append(simple_sub_rule([self.damaged[11]], half_width + narrow))
		rules.append(simple_sub_rule([self.damaged[12]], flat + back_width + half_width + quarter))
		rules.append(simple_sub_rule([self.damaged[13]], 
				half_width + quarter + half_back_width + half_back_width_full + flat))
		rules.append(simple_sub_rule([self.damaged[14]], full))
		return name, rules

	def damage_w_rules(self):
		name, rules, filt = 'damage-w', [], '@AuxDamageW'
		self.add_class(filt, ['@WidthFull', '@WShadePos'])
		for p in self.all_poss:
			for d in all_digits:
				rules.append(context_sub_rule([self.width_full_(d)] + (self.len_oct-1-p) * ['@WidthFull'], 
						self.left_shade_pos_(p), [], self.left_shade_(d, p)))
				rules.append(context_sub_rule([self.width_full_(d)] + (self.len_oct-1-p) * ['@WidthFull'], 
						self.w_shade_pos_(p), [], self.w_shade_(d, p)))
				d_half = d // 2
				d_half_carry = d // 2 + 4
				d_half_ceil = d // 2 + 1
				d_half_carry_ceil = (d // 2 + 4 + 1) % 8
				if p+1 < self.len_oct:
					if d % 2 == 1:
						rules.append(context_sub_rule(\
								p * [self.width_full_(7)] + [self.width_full_(d)] + ['@WidthFullOdd'] + (self.len_oct-2-p) * ['@WidthFull'], 
								self.half_left_shade_pos_(p), [], self.left_shade_(d_half_carry_ceil, p)))
						rules.append(context_sub_rule(\
								p * [self.width_full_(7)] + [self.width_full_(d)] + ['@WidthFullOdd'] + (self.len_oct-2-p) * ['@WidthFull'], 
								self.half_right_shade_pos_(p), [], self.right_shade_(d_half_carry_ceil, p)))
						rules.append(context_sub_rule(\
								p * [self.width_full_(7)] + [self.width_full_(d)] + ['@WidthFullOdd'] + (self.len_oct-2-p) * ['@WidthFull'], 
								self.half_w_shade_pos_(p), [], self.w_shade_(d_half_carry_ceil, p)))
					rules.append(context_sub_rule([self.width_full_(d)] + ['@WidthFullOdd'] + (self.len_oct-2-p) * ['@WidthFull'], 
							self.half_left_shade_pos_(p), [], self.left_shade_(d_half_carry, p)))
					rules.append(context_sub_rule([self.width_full_(d)] + ['@WidthFullOdd'] + (self.len_oct-2-p) * ['@WidthFull'], 
							self.half_right_shade_pos_(p), [], self.right_shade_(d_half_carry, p)))
					rules.append(context_sub_rule([self.width_full_(d)] + ['@WidthFullOdd'] + (self.len_oct-2-p) * ['@WidthFull'], 
							self.half_w_shade_pos_(p), [], self.w_shade_(d_half_carry, p)))
				if d % 2 == 1:
					rules.append(context_sub_rule(\
							p * [self.width_full_(7)] + [self.width_full_(d)] + (self.len_oct-1-p) * ['@WidthFull'], 
							self.half_left_shade_pos_(p), [], self.left_shade_(d_half_ceil, p)))
					rules.append(context_sub_rule(\
							p * [self.width_full_(7)] + [self.width_full_(d)] + (self.len_oct-1-p) * ['@WidthFull'], 
							self.half_right_shade_pos_(p), [], self.right_shade_(d_half_ceil, p)))
					rules.append(context_sub_rule(\
							p * [self.width_full_(7)] + [self.width_full_(d)] + (self.len_oct-1-p) * ['@WidthFull'], 
							self.half_w_shade_pos_(p), [], self.w_shade_(d_half_ceil, p)))
				rules.append(context_sub_rule([self.width_full_(d)] + (self.len_oct-1-p) * ['@WidthFull'], 
						self.half_left_shade_pos_(p), [], self.left_shade_(d_half, p)))
				rules.append(context_sub_rule([self.width_full_(d)] + (self.len_oct-1-p) * ['@WidthFull'], 
						self.half_right_shade_pos_(p), [], self.right_shade_(d_half, p)))
				rules.append(context_sub_rule([self.width_full_(d)] + (self.len_oct-1-p) * ['@WidthFull'], 
						self.half_w_shade_pos_(p), [], self.w_shade_(d_half, p)))
		return name, rules, filt

	def damage_h_rules(self):
		name, rules, filt = 'damage-h', [], '@AuxDamageH'
		self.add_class(filt, ['@HeightFull', '@HShadePos'])
		for p in self.all_poss:
			for d in all_digits:
				rules.append(context_sub_rule([self.height_full_(d)] + (self.len_oct-1-p) * ['@HeightFull'], 
						self.down_shade_pos_(p), [], self.down_shade_(d, p)))
				rules.append(context_sub_rule([self.height_full_(d)] + (self.len_oct-1-p) * ['@HeightFull'], 
						self.h_shade_pos_(p), [], self.h_shade_(d, p)))
				d_half = d // 2
				d_half_carry = d // 2 + 4
				d_half_ceil = d // 2 + 1
				d_half_carry_ceil = (d // 2 + 4 + 1) % 8
				if p+1 < self.len_oct:
					if d % 2 == 1:
						rules.append(context_sub_rule(\
								p * [self.height_full_(7)] + [self.height_full_(d)] + ['@HeightFullOdd'] + (self.len_oct-2-p) * ['@HeightFull'], 
								self.half_down_shade_pos_(p), [], self.down_shade_(d_half_carry_ceil, p)))
						rules.append(context_sub_rule(\
								p * [self.height_full_(7)] + [self.height_full_(d)] + ['@HeightFullOdd'] + (self.len_oct-2-p) * ['@HeightFull'], 
								self.half_h_shade_pos_(p), [], self.h_shade_(d_half_carry_ceil, p)))
					rules.append(context_sub_rule([self.height_full_(d)] + ['@HeightFullOdd'] + (self.len_oct-2-p) * ['@HeightFull'], 
							self.half_down_shade_pos_(p), [], self.down_shade_(d_half_carry, p)))
					rules.append(context_sub_rule([self.height_full_(d)] + ['@HeightFullOdd'] + (self.len_oct-2-p) * ['@HeightFull'], 
							self.half_h_shade_pos_(p), [], self.h_shade_(d_half_carry, p)))
				if d % 2 == 1:
					rules.append(context_sub_rule(\
							p * [self.height_full_(7)] + [self.height_full_(d)] + (self.len_oct-1-p) * ['@HeightFull'], 
							self.half_down_shade_pos_(p), [], self.down_shade_(d_half_ceil, p)))
					rules.append(context_sub_rule(\
							p * [self.height_full_(7)] + [self.height_full_(d)] + (self.len_oct-1-p) * ['@HeightFull'], 
							self.half_h_shade_pos_(p), [], self.h_shade_(d_half_ceil, p)))
				rules.append(context_sub_rule([self.height_full_(d)] + (self.len_oct-1-p) * ['@HeightFull'], 
						self.half_down_shade_pos_(p), [], self.down_shade_(d_half, p)))
				rules.append(context_sub_rule([self.height_full_(d)] + (self.len_oct-1-p) * ['@HeightFull'], 
						self.half_h_shade_pos_(p), [], self.h_shade_(d_half, p)))
		return name, rules, filt

	def damage_combine_rules(self):
		name, rules = 'damage-combine', []
		for p1 in self.all_poss:
			for d1 in all_digits:
				w = d1 * 8**p1
				for p2 in self.all_poss:
					for d2 in all_digits:
						h = d2 * 8**p2
						if w <= 1.5 * self.em and h <= 1.5 * self.em:
							if d1 > 0 and d2 > 0:
								rules.append(simple_sub_rule([self.w_shade_(d1, p1), self.h_shade_(d2, p2)], 
										[self.shade_(d1, d2, p1, p2)]))
							elif p1 + 1 < self.len_oct:
								rules.append(simple_sub_rule([self.w_shade_(d1, p1), self.h_shade_(d2, p2)], 
										[self.right_shade_(d1, p1)]))
							else:
								rules.append(simple_sub_rule([self.w_shade_(d1, p1), self.h_shade_(d2, p2)], 
										[self.right_shade_(0, p1)]))
		return name, rules

	###### Positioning

	def positioning(self):
		"""
		anchor_init: place two anchors within group, for position of start and end,
			with placeholders for copy of width/height in between.
		anchor: add depth to these anchors, and customize them to enclosing group, so it is clear
			whether the stringing together is horizontal or vertical.
		anchor_width/anchor_height: replace placeholders by actual sizes.
		content: to prepare for drawing outlines, place marker in each group (potentially top-level group in enclosure).
		set_content: replace marker of actual top-level groups of enclosures by placeholders for sizes,
			 noting type of enclosure, scaling and direction.
		width_content/height_content: substitute placeholders by outlines, with dimensions copied from width/height.
		remove_content: remove unused markers of groups that are not top-level groups of enclosures.
		top_anchor: for top-level group, add placeholders for advance.
		width_active/height_active: select size of top-level group.
		width_advance/height_advance: copy size of top-level group to anchor of advance.
		size_unactive: unselect size of top-level group.
		advance_base: turn advance anchors into base signs.
		insertion_width/insertion_height: copy full width/height (halved) to determine corner given centre.
		anchor_basic_insert: for glyph, as well as for insertion, create anchors to middle of area.
		anchor_basic_mid: place anchor for middle of basic group.
		anchor_insert_mid: place anchor for middle of core group of insertion.
		duplicate_content: if unusually large outlines are needed, break them up into units.
		insertion_dist: turn octal digits of insertions into distances.

		anchor_start: connect to top of top-level group.
		anchor_general: connect padding within group.
		anchor_depth: connect neighboring groups.
		anchor_depth_insert: connect starts of multiple inserted groups.
		anchor_cross_depth: connect to deeper groups, including center of core group to first inserted group.
		anchor_mid: connect to middle of basic group.
		anchor_insertion: connect positions of insertions.
		anchor_scaled: connect middle to sign.
		anchor_shade: connecting shading.
		anchor_bracket: connecting bracket to anchor.
		anchor_bracket_depth: connecting anchor within same depth.
		anchor_bracket_cross_depth: connecting anchor from higher-level group if bracket is first element in group.
		anchor_cap: connect caps of enclosures.
		outline_hor: connect horizontal outlines.
		outline_ver: connect vertical outlines.
		"""
		self.make_markclasses()
		self.add_sub_lookup(*self.anchor_insert_marker_subrules())
		self.add_sub_lookup(*self.anchor_marker_subrules())
		self.add_sub_lookup(*self.content_marker_subrules())
		for level in 'pw':
			for sc in self.all_scales:
				for direction in ['hor', 'ver']:
					self.add_sub_lookup(*self.set_content_subrules(level, sc, direction))
		for d in range(self.max_depth-1, 0, -1):
			self.add_main_lookup(*self.inner_depth_rules(d))
			self.add_main_lookup(*self.outer_depth_rules(d-1))
			self.add_main_lookup(*self.anchor_init_rules())
			self.add_main_lookup(*self.anchor_rules(d))
			self.add_main_lookup(*self.anchor_width_rules())
			self.add_main_lookup(*self.anchor_height_rules())
			self.add_main_lookup(*self.content_rules())
			self.add_main_lookup(*self.set_content_rules())
			self.add_main_lookup(*self.width_content_rules())
			self.add_main_lookup(*self.height_content_rules())
			self.add_main_lookup(*self.remove_content_rules())
			if d-1 == 0:
				self.add_sub_lookup(*self.top_hor_anchor_subrules())
				self.add_sub_lookup(*self.top_ver_anchor_subrules())
				self.add_sub_lookup(*self.top_end_anchor_subrules())
				self.add_main_lookup(*self.top_anchor_rules())
				self.add_main_lookup(*self.width_active_rules())
				self.add_main_lookup(*self.height_active_rules())
				self.add_main_lookup(*self.width_advance_rules())
				self.add_main_lookup(*self.height_advance_rules())
				self.add_main_lookup(*self.size_unactive_rules())
			self.add_main_lookup(*self.bracket_reset_rules())
		self.add_main_lookup(*self.advance_base_rules())
		self.add_main_lookup(*self.insertion_width_rules())
		self.add_main_lookup(*self.insertion_height_rules())
		self.add_main_lookup(*self.anchor_basic_insert_rules())
		self.add_main_lookup(*self.anchor_basic_mid_rules())
		self.add_main_lookup(*self.anchor_insert_mid_rules())
		self.add_main_lookup(*self.duplicate_content_rules())
		self.add_main_lookup(*self.insertion_dist_rules())
		self.add_main_lookup(*self.rotate_enclosure_scale_rules())

		self.add_pos_lookup(*self.anchor_start_rules())
		self.add_pos_lookup(*self.anchor_general_rules())
		for depth in range(1, self.max_depth):
			self.add_pos_lookup(*self.anchor_depth_rules(depth))
			self.add_pos_lookup(*self.anchor_depth_insert_rules(depth))
		self.add_pos_lookup(*self.anchor_cross_depth_rules())
		self.add_pos_lookup(*self.anchor_cross_depth_insert_rules())
		self.add_pos_lookup(*self.anchor_mid_rules())
		self.add_pos_lookup(*self.anchor_insertion_rules())
		# the reason for distinguishing scales is because otherwise the mark
		# class becomes too big.
		for sc in self.all_scales:
			self.add_pos_lookup(*self.anchor_scaled_rules(sc))
		self.add_pos_lookup(*self.anchor_shade_rules())
		self.add_pos_lookup(*self.anchor_bracket_rules())
		for depth in range(1, self.max_depth):
			self.add_pos_lookup(*self.anchor_bracket_depth_rules(depth))
		self.add_pos_lookup(*self.anchor_bracket_cross_depth_rules())
		self.add_pos_lookup(*self.anchor_cap_rules())
		self.add_pos_lookup(*self.outline_hor_rules())
		self.add_pos_lookup(*self.outline_ver_rules())

	def make_markclasses(self):
		for sign, (w, h, dx, dy) in self.unscaled_sign_to_size.items():
			x = round(w/2+dx)
			y = round(h/2+dy)
			self.add_markclass('@SignScaled0Mark', [sign], x=x, y=y)
		for opening in self.openings:
			w,h = self.unscaled_cap_to_size[opening]
			x = round((w-self.margin/2)/2)
			y = round(h/2)
			self.add_markclass('@SignScaled0Mark', [opening], x=x, y=y)
		for closing in self.closings:
			w,h = self.unscaled_cap_to_size[closing]
			x = round((w+self.margin/2)/2)
			y = round(h/2)
			self.add_markclass('@SignScaled0Mark', [closing], x=x, y=y)
		for opening in self.openings_rot:
			w,h = self.unscaled_cap_rot_to_size[opening]
			x = round(w/2)
			y = round((h+self.margin/2)/2)
			self.add_markclass('@SignScaled0Mark', [opening], x=x, y=y)
		for closing in self.closings_rot:
			w,h = self.unscaled_cap_rot_to_size[closing]
			x = round(w/2)
			y = round((h-self.margin/2)/2)
			self.add_markclass('@SignScaled0Mark', [closing], x=x, y=y)
		for lost, (w,h) in self.unscaled_lost_to_size.items():
			x = round(w * self.em / 2) * self.resolution
			y = round(h * self.em / 2) * self.resolution
			self.add_markclass('@SignScaled0Mark', [lost], x=x, y=y)
		for (sign, sc), scaled in self.name_scale_to_name.items():
			factor = SCALEDOWN ** sc
			(w, h, dx, dy) = self.unscaled_sign_to_size[sign]
			x = round(factor * (w/2+dx))
			y = round(factor * (h/2+dy))
			self.add_markclass(f'@SignScaled{sc}Mark', [scaled], x=x, y=y)
		for opening in self.openings:
			for sc in self.all_scales:
				scaled = self.cap_scale_to_cap[(opening, sc)]
				factor = SCALEDOWN ** sc
				x = -round(factor * self.margin / 2 / self.resolution) * self.resolution
				y = round(factor * self.em) * self.resolution - self.enclosure_descent(sc)
				self.add_markclass(f'@CapScaledMark', [scaled], x=x, y=y)
		for closing in self.closings:
			for sc in self.all_scales:
				scaled = self.cap_scale_to_cap[(closing, sc)]
				factor = SCALEDOWN ** sc
				y = round(factor * self.em) * self.resolution - self.enclosure_descent(sc)
				self.add_markclass(f'@CapScaledMark', [scaled], x=0, y=y)
		for opening in self.openings_rot:
			for sc in self.all_scales:
				scaled = self.cap_rot_scale_to_cap[(opening, sc)]
				factor = SCALEDOWN ** sc
				(_, h) = self.unscaled_cap_rot_to_size[opening]
				y = round(factor * (h + self.margin / 2) / self.resolution) * self.resolution
				self.add_markclass(f'@CapRotScaledMark', [scaled], x=self.enclosure_descent(sc), y=y)
		for closing in self.closings_rot:
			for sc in self.all_scales:
				scaled = self.cap_rot_scale_to_cap[(closing, sc)]
				factor = SCALEDOWN ** sc
				(_, h) = self.unscaled_cap_rot_to_size[closing]
				y = round(factor * h / self.resolution) * self.resolution
				self.add_markclass(f'@CapRotScaledMark', [scaled], x=self.enclosure_descent(sc), y=y)
		for (lost, sc), scaled in self.lost_scale_to_lost.items():
			factor = SCALEDOWN ** sc
			(w, h) = self.unscaled_lost_to_size[lost]
			x = round(factor * w * self.em / 2) * self.resolution
			y = round(factor * h * self.em / 2) * self.resolution
			self.add_markclass(f'@SignScaled{sc}Mark', [scaled], x=x, y=y)
		self.add_class('@EnclosureScale', \
				[self.enclosure_scale_(sc) for sc in self.all_scales] + \
				[self.enclosure_scale_vertical_(sc) for sc in self.all_scales])
		for sc in self.all_scales:
			self.add_markclass(f'@EnclosureScaleHorizontal{sc}Mark', [self.enclosure_scale_(sc)])
			self.add_markclass(f'@EnclosureScaleVertical{sc}Mark', [self.enclosure_scale_vertical_(sc)])
		for bracket in self.open_brackets:
			for sc in self.all_scales:
				bracket_scaled = self.bracket_scale_to_bracket[(bracket, sc)]
				x = self.bracket_width[bracket_scaled]
				y = round(SCALEDOWN ** sc * self.font_units)
				self.add_markclass(f'@BracketMark', [bracket_scaled], x=x, y=y)
		for bracket in self.close_brackets:
			for sc in self.all_scales:
				bracket_scaled = self.bracket_scale_to_bracket[(bracket, sc)]
				y = round(SCALEDOWN ** sc * self.font_units)
				self.add_markclass(f'@BracketMark', [bracket_scaled], x=0, y=y)
		for depth in self.all_depths:
			self.add_markclass(f'@AnchorStart{depth}Mark', [self.anchor_start_(depth)])
			self.add_class(f'@AnchorEndAny{depth}', \
					[self.anchor_end_(depth), self.anchor_end_w_(depth), self.anchor_end_h_(depth)])
			self.add_markclass(f'@CapAnchorStart{depth}Mark', [self.cap_anchor_start_(depth)], x=0, y=0)
			self.add_markclass(f'@CapAnchorEnd{depth}Mark', [self.cap_anchor_end_(depth)], x=0, y=0)
		self.add_markclass('@AnchorGroupMark', \
				list(set(self.anchor_pad_w_(d, p) for d in all_digits for p in self.all_poss)) + \
				list(set(self.anchor_pad_h_(d, p) for d in all_digits for p in self.all_poss)) + \
				[f'@AnchorEndAny{depth}' for depth in self.all_depths])
		self.add_class('@AnchorSymbol', \
				[self.anchor_start_(depth) for depth in self.all_depths] + ['@AnchorGroupMark'])
		self.add_markclass('@MidMark', \
				list(set(self.mid_w_(d, p) for d in all_digits for p in self.all_poss)) + \
				list(set(self.mid_h_(d, p) for d in all_digits for p in self.all_poss)))
		self.add_markclass('@AnchorInsertMidMark', [self.anchor_insert_mid_(depth) for depth in self.all_depths[:-1]])
		self.add_markclass('@AnchorBasicMidMark', [self.anchor_basic_mid])
		self.add_class('@AnchorStartInsert', [self.anchor_start_insert_(depth) for depth in self.all_depths])
		self.add_class('@AnchorEndInsert', [self.anchor_end_insert_(depth) for depth in self.all_depths])
		for depth in self.all_depths:
			self.add_markclass(f'@AnchorStartInsert{depth}Mark', [self.anchor_start_insert_(depth)])
		self.add_markclass('@InsertMark', \
				[self.insert_w_(d, p) for d in all_digits[1:] for p in self.all_poss] + \
				[self.insert_h_(d, p) for d in all_digits[1:] for p in self.all_poss] + \
				[self.insert_w_(-d, p) for d in all_digits[1:] for p in self.all_poss] + \
				[self.insert_h_(-d, p) for d in all_digits[1:] for p in self.all_poss] + \
				[self.insert_half_w_(d, p) for d in all_digits[1:] for p in self.all_poss] + \
				[self.insert_half_h_(d, p) for d in all_digits[1:] for p in self.all_poss] + \
				[self.anchor_end_insert_(depth) for depth in self.all_depths])
		self.add_class('@Shade', \
				[self.shade_(d1, d2, p1, p2) for (p1, d1, _, p2, d2, _) in self.shade_combinations])
		self.add_markclass('@ShadeMark', \
				[self.left_shade_(d, p) for d in all_digits for p in self.all_poss] + \
				[self.right_shade_(d, p) for d in all_digits for p in self.all_poss] + \
				[self.down_shade_(d, p) for d in all_digits for p in self.all_poss] + \
				['@Shade'])
		self.add_class('@BracketAnchor', [self.bracket_anchor_(d) for d in self.all_depths])
		for depth in self.all_depths:
			self.add_markclass(f'@BracketAnchor{depth}Mark', [self.bracket_anchor_(depth)])
		for sc in self.all_scales:
			offset = round(SCALEDOWN ** sc * self.em) * self.resolution - self.enclosure_descent(sc)
			for d in all_digits[1:]:
				for p in self.all_poss:
					if p == self.len_oct-1 and d > 1:
						continue
					size = int(d) * 8**p * self.resolution
					self.add_markclass('@OutlineHorMark', [self.outline_(level, sc, 'hor', d, p) for level in 'pw'],
							x=0, y=offset)
					self.add_markclass('@OutlineVerMark', [self.outline_(level, sc, 'ver', d, p) for level in 'pw'],
							x=self.enclosure_descent(sc), y=size)

	def anchor_insert_marker_subrules(self):
		name, rules = 'anchor-insert-marker', []
		for level in all_levels:
			rules.append(simple_sub_rule([self.open_inner_(level)], \
					[self.open_inner_(level), self.anchor_start_insert_active]))
		rules.append(simple_sub_rule([self.anchor_end_insert], + \
				self.len_oct * [self.inserted_width] + self.len_oct * [self.inserted_height] + \
				[self.anchor_end_insert_active, self.to_anchor_start]))
		return name, rules

	def anchor_marker_subrules(self):
		name, rules = 'anchor-marker', []
		for level in all_levels:
			rules.append(simple_sub_rule([self.open_inner_(level)], [self.open_inner_(level), self.to_anchor_start]))
		rules.append(simple_sub_rule([self.record], \
				self.len_oct * [self.to_anchor_size] + [self.to_anchor_end, self.record]))
		return name, rules

	def anchor_init_rules(self):
		name, rules, filt = 'anchor-init', [], '@AuxAnchorInit'
		self.add_class(filt, ['@Inner', self.anchor_end_insert, self.record])
		rules.append(chain_sub_rule([], [('@Inneropen', ['anchor-insert-marker'])], [self.anchor_end_insert]))
		rules.append(chain_sub_rule([], [('@Inneropen', ['anchor-marker'])], []))
		rules.append(chain_sub_rule(['@Inneropen'], [(self.anchor_end_insert, ['anchor-insert-marker'])], []))
		rules.append(chain_sub_rule(['@Inneropen'], [(self.record, ['anchor-marker'])], []))
		return name, rules, filt

	def anchor_rules(self, depth):
		name, rules, filt = f'anchor-{depth}', [], '@AuxAnchor'
		self.add_class(filt, ['@Outer', '@Directionactive', self.to_anchor_start, self.to_anchor_end, \
				self.anchor_start_insert_active, self.anchor_end_insert_active])
		for level in level_seq:
			if depth-1 == 0:
				rules.append(context_sub_rule([self.open_outer_(level), '@Directionactive'], 
						self.to_anchor_start, [], self.anchor_start_(depth)))
			else:
				rules.append(context_sub_rule([self.open_outer_(level)],
						self.to_anchor_start, [], self.anchor_start_(depth)))
		if depth-1 == 0:
			rules.append(context_sub_rule([self.open_outer_('h'), '@Directionactive'], 
					self.to_anchor_end, [], self.anchor_end_w_(depth)))
		else:
			rules.append(context_sub_rule([self.open_outer_('h')], 
					self.to_anchor_end, [], self.anchor_end_w_(depth)))
		if depth-1 == 0:
			rules.append(context_sub_rule([self.open_outer_('v'), '@Directionactive'], 
					self.to_anchor_end, [], self.anchor_end_h_(depth)))
		else:
			rules.append(context_sub_rule([self.open_outer_('v')], 
					self.to_anchor_end, [], self.anchor_end_h_(depth)))
		if depth-1 == 0:
			rules.append(context_sub_rule([self.open_outer_('i'), '@Directionactive'], 
					self.to_anchor_end, [], self.anchor_end_(depth)))
		else:
			rules.append(context_sub_rule([self.open_outer_('i')], 
					self.to_anchor_end, [], self.anchor_end_(depth)))
		if depth-1 == 0:
			rules.append(context_sub_rule([self.open_outer_('o'), '@Directionactive'], 
					self.to_anchor_end, [], self.anchor_end_(depth)))
		else:
			rules.append(context_sub_rule([self.open_outer_('o')], 
					self.to_anchor_end, [], self.anchor_end_(depth)))
		for level in 'pw':
			rules.append(context_sub_rule([self.open_outer_(level), '@Directionactive'], 
					self.to_anchor_start, [], self.anchor_start_(depth)))
			rules.append(context_sub_rule([self.open_outer_(level), self.horizontal_active], \
					self.to_anchor_end, [], self.anchor_end_w_(depth)))
			rules.append(context_sub_rule([self.open_outer_(level), self.vertical_active], \
					self.to_anchor_end, [], self.anchor_end_h_(depth)))
		rules.append(context_sub_rule([], self.anchor_end_insert_active, [], self.anchor_end_insert_(depth)))
		rules.append(context_sub_rule([], self.anchor_start_insert_active, [], self.anchor_start_insert_(depth)))
		return name, rules, filt

	def anchor_width_rules(self):
		name, rules, filt = 'anchor-width', [], '@AuxAnchorWidth'
		self.add_class(filt, ['@Inner', '@WidthFull', '@AnchorEndW', self.record, self.to_anchor_size])
		for p in self.all_poss:
			for d in all_digits:
				rules.append(context_sub_rule([self.width_full_(d)] + (self.len_oct - 1 - p) * ['@WidthFull'], \
						self.to_anchor_size, (self.len_oct - 1 - p) * [self.to_anchor_size] + ['@AnchorEndW'], \
						self.anchor_pad_w_(d, p)))
		return name, rules, filt

	def anchor_height_rules(self):
		name, rules, filt = 'anchor-height', [], '@AuxAnchorHeight'
		self.add_class(filt, ['@Inner', '@HeightFull', '@AnchorEndH', self.record, self.to_anchor_size])
		for p in self.all_poss:
			for d in all_digits:
				rules.append(context_sub_rule([self.height_full_(d)] + (self.len_oct - 1 - p) * ['@HeightFull'], \
						self.to_anchor_size, (self.len_oct - 1 - p) * [self.to_anchor_size] + ['@AnchorEndH'], \
						self.anchor_pad_h_(d, p)))
		return name, rules, filt

	def content_marker_subrules(self):
		name, rules = 'content-marker', []
		rules.append(simple_sub_rule([self.record], [self.content_marker, self.record]))
		rules.append(simple_sub_rule(['@Scalegroupactive'], [self.nil]))
		return name, rules

	def set_content_subrules(self, level, sc, direction):
		name, rules = f'set-content-{level}-{sc}-{direction}', []
		poss = [self.outline_pos_(level, sc, direction, p) for p in self.all_poss]
		rules.append(simple_sub_rule([self.content_marker], poss))
		return name, rules

	def content_rules(self):
		name, rules, filt = 'content', [], '@AuxContent'
		self.add_class(filt, ['@Inner', self.record, '@Scalegroupactive'])
		rules.append(chain_sub_rule(['@Inneropen'], [(self.record, ['content-marker'])], []))
		rules.append(chain_sub_rule(['@Inneropen'], [('@Scalegroupactive', ['content-marker'])], []))
		return name, rules, filt

	def set_content_rules(self):
		name, rules, filt = 'set-content', [], '@AuxSetContent'
		self.add_class(filt, ['@Outer', '@Directionactive', '@Scalegroupactive', self.content_marker])
		for level in 'pw':
			for sc in self.all_scales:
				for direction, dir_char in [('hor', self.horizontal_active), ('ver', self.vertical_active)]:
					rules.append(chain_sub_rule([self.open_outer_(level), dir_char, self.scale_group_active_(sc)], 
						[(self.content_marker, [f'set-content-{level}-{sc}-{direction}'])], []))
		return name, rules, filt

	def width_content_rules(self):
		name, rules, filt = 'width-content', [], '@AuxWidthContent'
		self.add_class(filt, ['@Outer', '@Outlinepos', '@Width'])
		for level in 'pw':
			for sc in self.all_scales:
				for p in self.all_poss:
					rules.append(context_sub_rule([self.width_(0)] + (self.len_oct-1-p) * ['@Width'],
						self.outline_pos_(level, sc, 'hor', p), [], self.nil))
					for d in all_digits[1:]:
						rules.append(context_sub_rule([self.width_(d)] + (self.len_oct-1-p) * ['@Width'],
							self.outline_pos_(level, sc, 'hor', p), [], self.outline_(level, sc, 'hor', d, p)))
		return name, rules, filt

	def height_content_rules(self):
		name, rules, filt = 'height-content', [], '@AuxHeightContent'
		self.add_class(filt, ['@Outer', '@Outlinepos', '@Height'])
		for level in 'pw':
			for sc in self.all_scales:
				for p in self.all_poss:
					rules.append(context_sub_rule([self.height_(0)] + (self.len_oct-1-p) * ['@Height'],
						self.outline_pos_(level, sc, 'ver', p), [], self.nil))
					for d in all_digits[1:]:
						rules.append(context_sub_rule([self.height_(d)] + (self.len_oct-1-p) * ['@Height'],
							self.outline_pos_(level, sc, 'ver', p), [], self.outline_(level, sc, 'ver', d, p)))
		return name, rules, filt

	def remove_content_rules(self):
		name, rules, filt = 'remove-content', [], '@AuxRemoveContent'
		self.add_class(filt, [self.content_marker, self.record])
		rules.append(simple_sub_rule([self.content_marker, self.record], [self.record]))
		return name, rules, filt

	def top_hor_anchor_subrules(self):
		name, rules, filt = 'top-hor-anchor', [], '@Outer'
		for level in all_levels:
			rules.append(simple_sub_rule([self.open_outer_(level)], \
					[self.start_hor, self.open_outer_(level), self.anchor_start_(0)]))
		return name, rules, filt

	def top_ver_anchor_subrules(self):
		name, rules, filt = 'top-ver-anchor', [], '@Outer'
		for level in all_levels:
			rules.append(simple_sub_rule([self.open_outer_(level)], \
					[self.start_ver, self.open_outer_(level), self.anchor_start_(0)]))
		return name, rules, filt

	def top_end_anchor_subrules(self):
		name, rules, filt = 'top-end-anchor', [], '@Outer'
		to_advance = [self.to_advance_(p) for p in self.all_poss]
		for level in all_levels:
			rules.append(simple_sub_rule([self.close_outer_(level)], to_advance + [self.close_outer_(level)]))
		return name, rules, filt

	def top_anchor_rules(self):
		name, rules, filt = 'top-anchor', [], '@AuxTopAnchor'
		self.add_class(filt, ['@Outer', '@Directionactive'])
		rules.append(chain_sub_rule([], [('@Outeropen', ['top-hor-anchor'])], [self.horizontal_active]))
		rules.append(chain_sub_rule([], [('@Outeropen', ['top-ver-anchor'])], [self.vertical_active]))
		rules.append(chain_sub_rule([], [('@Outerclose', ['top-end-anchor'])], []))
		return name, rules, filt

	def width_active_rules(self):
		name, rules, filt = 'width-active', [], '@AuxWidthActive'
		self.add_class(filt, ['@Outer', '@Directionactive', '@WidthFull', self.record_active])
		for p in self.all_poss:
			for d in all_digits:
				rules.append(context_sub_rule(['@Outeropen',  self.horizontal_active],
						self.width_full_(d), [], self.width_full_scaled_(d)))
		return name, rules, filt

	def height_active_rules(self):
		name, rules, filt = 'height-active', [], '@AuxHeightActive'
		self.add_class(filt, ['@Outer', '@Directionactive', '@HeightFull', self.record_active])
		for p in self.all_poss:
			for d in all_digits:
				rules.append(context_sub_rule(['@Outeropen',  self.vertical_active],
						self.height_full_(d), [], self.height_full_scaled_(d)))
		return name, rules, filt

	def width_advance_rules(self):
		name, rules, filt = 'width-advance', [], '@AuxWidthAdvance'
		self.add_class(filt, ['@WidthFullScaled', '@ToAdvance'])
		for p in self.all_poss:
			for d in all_digits:
				rules.append(context_sub_rule(\
						[self.width_full_scaled_(d)] + (self.len_oct - 1 - p) * ['@WidthFullScaled'], \
						self.to_advance_(p), [], self.advance_w_(d, p)))
		return name, rules, filt

	def height_advance_rules(self):
		name, rules, filt = 'height-advance', [], '@AuxHeightAdvance'
		self.add_class(filt, ['@HeightFullScaled', '@ToAdvance'])
		for p in self.all_poss:
			for d in all_digits:
				rules.append(context_sub_rule(\
						[self.height_full_scaled_(d)] + (self.len_oct - 1 - p) * ['@HeightFullScaled'], \
						self.to_advance_(p), [], self.advance_h_(d, p)))
		return name, rules, filt

	def size_unactive_rules(self):
		name, rules = 'size_unactive', []
		for d in all_digits:
			rules.append(simple_sub_rule([self.width_full_scaled_(d)], [self.width_full_(d)]))
			rules.append(simple_sub_rule([self.height_full_scaled_(d)], [self.height_full_(d)]))
		return name, rules

	def advance_base_rules(self):
		name, rules = 'advance-base', []
		for p in self.all_poss:
			for d in all_digits:
				if p > 0 and d == 0:
					continue
				rules.append(simple_sub_rule([self.advance_w_(d, p)], [self.advance_w_base_(d, p)]))
				rules.append(simple_sub_rule([self.advance_h_(d, p)], [self.advance_h_base_(d, p)]))
		return name, rules

	def insertion_width_rules(self):
		name, rules, filt = 'insertion-width', [], '@AuxInsertionWidth'
		self.add_class(filt, [self.inserted_width, '@WidthFull'])
		for p in self.all_poss:
			for d in all_digits[1:]:
				rules.append(context_sub_rule([], self.inserted_width, \
						(self.len_oct-1-p) * [self.inserted_width] + p * ['@WidthFull'] + [self.width_full_(d)], 
						self.insert_half_w_(d, p)))
		return name, rules, filt

	def insertion_height_rules(self):
		name, rules, filt = 'insertion-height', [], '@AuxInsertionHeight'
		self.add_class(filt, [self.inserted_height, '@HeightFull'])
		for p in self.all_poss:
			for d in all_digits[1:]:
				rules.append(context_sub_rule([], self.inserted_height, \
						(self.len_oct-1-p) * [self.inserted_height] + p * ['@HeightFull'] + [self.height_full_(d)], 
						self.insert_half_h_(d, p)))
		return name, rules, filt

	def anchor_basic_insert_rules(self):
		name, rules, filt = 'anchor-basic-insert', [], '@AuxAnchorBasicInsert'
		self.add_class(filt, ['@Undone', '@WidthFull', '@HeightFull'])
		for p in self.all_poss:
			for d in all_digits:
				for level in 'bihvo':
					rules.append(context_sub_rule([self.open_(level)], self.width_full_(d), 
						(self.len_oct - 1 - p) * ['@WidthFull'], self.mid_w_(d, p)))
					rules.append(context_sub_rule([self.open_(level)], self.height_full_(d), 
						(self.len_oct - 1 - p) * ['@HeightFull'], self.mid_h_(d, p)))
		return name, rules, filt

	def anchor_basic_mid_rules(self):
		name, rules, filt = 'anchor-basic-mid', [], '@AuxAnchorBasicMid'
		self.add_class(filt, ['@Undone', self.record])
		for level in 'bhvo':
			rules.append(context_sub_rule([self.open_(level)], self.record, [], self.anchor_basic_mid))
		return name, rules, filt

	def anchor_insert_mid_rules(self):
		name, rules, filt = 'anchor-insert-mid', [], '@AuxAnchorInsertMid'
		self.add_class(filt, ['@Undone', '@Depth', self.record])
		for d in self.all_depths[:-1]:
			rules.append(context_sub_rule([self.open_('i'), self.depth_(d)], 
					self.record, [], self.anchor_insert_mid_(d)))
		return name, rules, filt

	def duplicate_content_rules(self):
		name, rules = 'duplicate-content', []
		for d in all_digits[2:]:
			p = self.len_oct-1
			for sc in self.all_scales:
				for level in 'pw':
					for direction in ['hor', 'ver']:
						rules.append(simple_sub_rule([self.outline_(level, sc, direction, d, p)],
							d * [self.outline_(level, sc, direction, 1, p)]))
		return name, rules

	def insertion_dist_rules(self):
		name, rules = 'insertion-dist', []
		self.add_class('@AuxInsertionDist', \
			[self.insert_x_(d) for d in all_digits] + [self.insert_y_(d) for d in all_digits] + \
			['@InsertW', '@InsertH', self.minus_insert, self.insert_sep])
		for p in self.all_poss:
			for d in all_digits[1:]:
				rules.append(context_sub_rule([self.minus_insert, self.insert_sep] + p * ['@AuxInsertionDist'], self.insert_x_(d), [], self.insert_w_(-d, p)))
				rules.append(context_sub_rule([self.minus_insert, self.insert_sep] + p * ['@AuxInsertionDist'], self.insert_y_(d), [], self.insert_h_(-d, p)))
				rules.append(context_sub_rule([self.insert_sep] + p * ['@AuxInsertionDist'], self.insert_x_(d), [], self.insert_w_(d, p)))
				rules.append(context_sub_rule([self.insert_sep] + p * ['@AuxInsertionDist'], self.insert_y_(d), [], self.insert_h_(d, p)))
		return name, rules

	def rotate_enclosure_scale_rules(self):
		name, rules, filt, feat = 'rotate_enclosure_scale', [], None, 'vert'
		for sc in self.all_scales:
			rules.append(simple_sub_rule([self.enclosure_scale_(sc)], [self.enclosure_scale_vertical_(sc)]))
		return name, rules, filt, feat

	def anchor_start_rules(self):
		name, rules, filt = 'anchor-start', [], '@AuxAnchorStart'
		self.add_class(filt, [self.start_hor, self.start_ver, '@AnchorStart0Mark'])
		rules.append(base_pos_rule(self.start_hor, '@AnchorStart0Mark', 0, self.font_units))
		rules.append(base_pos_rule(self.start_ver, '@AnchorStart0Mark', - self.font_units // 2, 0))
		return name, rules, filt

	def anchor_general_rules(self):
		name, rules, filt = 'anchor-general', [], '@AuxAnchorGeneral'
		self.add_class(filt, [self.start_hor, self.start_ver, '@AnchorSymbol'])
		for depth in range(0, self.max_depth):
			rules.append(mark_pos_rule(self.anchor_start_(depth), '@AnchorGroupMark', 0, 0))
		for p in self.all_poss:
			for d in all_digits:
				if p > 0 and d == 0:
					continue
				adv = int(d * 8**p) * self.resolution
				rules.append(mark_pos_rule(self.anchor_pad_w_(d, p), '@AnchorGroupMark', adv, 0))
				rules.append(mark_pos_rule(self.anchor_pad_h_(d, p), '@AnchorGroupMark', 0, -adv))
		return name, rules, filt

	def anchor_depth_rules(self, depth):
		name, rules, filt = f'anchor-depth-{depth}', [], f'@AuxAnchorDepth{depth}'
		self.add_class(filt, [self.depth_(depth-1), self.anchor_end_insert_(depth), \
				f'@AnchorStart{depth}Mark', f'@AnchorEndAny{depth}', \
				f'@CapAnchorStart{depth}Mark', f'@CapAnchorEnd{depth}Mark'])
		rules.append(mark_pos_rule(self.anchor_end_insert_(depth), f'@AnchorStart{depth}Mark', 0, 0))
		rules.append(mark_pos_rule(f'@AnchorEndAny{depth}', f'@AnchorStart{depth}Mark', 0, 0))
		rules.append(mark_pos_rule(f'@AnchorEndAny{depth}', f'@CapAnchorStart{depth}Mark', 0, 0))
		rules.append(mark_pos_rule(f'@CapAnchorEnd{depth}Mark', f'@AnchorStart{depth}Mark', 0, 0))
		rules.append(mark_pos_rule(f'@CapAnchorEnd{depth}Mark', f'@CapAnchorStart{depth}Mark', 0, 0))
		return name, rules, filt

	def anchor_depth_insert_rules(self, depth):
		name, rules, filt = f'anchor-depth-insert-{depth}', [], f'@AuxAnchorDepthInsert{depth}'
		self.add_class(filt, [self.depth_(depth-1), f'@AnchorStartInsert{depth}Mark'])
		rules.append(mark_pos_rule(self.anchor_start_insert_(depth), f'@AnchorStartInsert{depth}Mark', 0, 0))
		return name, rules, filt

	def anchor_cross_depth_rules(self):
		name, rules, filt = 'anchor-cross-depth', [], '@AuxAnchorCrossDepth'
		self.add_class(filt, ['@AnchorStart', '@CapAnchorStart', '@AnchorStartInsert'])
		for depth in range(1, self.max_depth):
			rules.append(mark_pos_rule(self.anchor_start_(depth-1), f'@AnchorStart{depth}Mark', 0, 0))
			rules.append(mark_pos_rule(self.anchor_start_(depth-1), f'@CapAnchorStart{depth}Mark', 0, 0))
		return name, rules, filt

	def anchor_cross_depth_insert_rules(self):
		name, rules, filt = f'anchor-cross-depth-insert', [], f'@AuxAnchorCrossDepthInsert'
		self.add_class(filt, ['@AnchorInsertMidMark', f'@AnchorStartInsert'])
		for depth in range(1, self.max_depth):
			rules.append(mark_pos_rule(self.anchor_insert_mid_(depth-1), f'@AnchorStartInsert{depth}Mark', 0, 0))
		return name, rules, filt

	def anchor_mid_rules(self):
		name, rules, filt = 'anchor-mid', [], '@AuxAnchorMid'
		self.add_class(filt, ['@AnchorStart', '@MidMark', '@AnchorBasicMidMark', '@AnchorInsertMidMark'])
		rules.append(mark_pos_rule('@AnchorStart', '@MidMark', 0, 0))
		rules.append(mark_pos_rule('@AnchorStart', '@AnchorBasicMidMark', 0, 0))
		rules.append(mark_pos_rule('@AnchorStart', '@AnchorInsertMidMark', 0, 0))
		for p in self.all_poss:
			for d in all_digits:
				if p > 0 and d == 0:
					continue
				adv = int(d * 8**p / 2) * self.resolution 
				rules.append(mark_pos_rule(self.mid_w_(d,p), '@MidMark', adv, 0))
				rules.append(mark_pos_rule(self.mid_h_(d,p), '@MidMark', 0, -adv))
				rules.append(mark_pos_rule(self.mid_w_(d,p), '@AnchorBasicMidMark', adv, 0))
				rules.append(mark_pos_rule(self.mid_h_(d,p), '@AnchorBasicMidMark', 0, -adv))
				rules.append(mark_pos_rule(self.mid_w_(d,p), '@AnchorInsertMidMark', adv, 0))
				rules.append(mark_pos_rule(self.mid_h_(d,p), '@AnchorInsertMidMark', 0, -adv))
		return name, rules, filt

	def anchor_insertion_rules(self):
		name, rules, filt = 'anchor-insertion', [], '@AuxAnchorInsertion'
		self.add_class(filt, ['@AnchorStartInsert', '@InsertMark'])
		rules.append(mark_pos_rule('@AnchorStartInsert', '@InsertMark', 0, 0))
		for p in self.all_poss:
			for d in all_digits[1:]:
				size = round(d * 8**p) * self.resolution
				half_size = int(d * 8**p / 2) * self.resolution
				rules.append(mark_pos_rule(self.insert_w_(-d, p), '@InsertMark', -size, 0))
				rules.append(mark_pos_rule(self.insert_h_(-d, p), '@InsertMark', 0, -size))
				rules.append(mark_pos_rule(self.insert_w_(d, p), '@InsertMark', size, 0))
				rules.append(mark_pos_rule(self.insert_h_(d, p), '@InsertMark', 0, size))
				rules.append(mark_pos_rule(self.insert_half_w_(d, p), '@InsertMark', -half_size, 0))
				rules.append(mark_pos_rule(self.insert_half_h_(d, p), '@InsertMark', 0, half_size))
		return name, rules, filt

	def anchor_scaled_rules(self, sc):
		name, rules, filt = f'anchor-scaled-{sc}', [], f'@AuxAnchorScaled{sc}'
		self.add_class(filt, [self.anchor_basic_mid, f'@SignScaled{sc}Mark'])
		rules.append(mark_pos_rule(self.anchor_basic_mid, f'@SignScaled{sc}Mark', 0, 0))
		return name, rules, filt

	def anchor_shade_rules(self):
		name, rules, filt = 'anchor-shade', [], '@AuxAnchorShade'
		self.add_class(filt, ['@AnchorStart', '@CapScaledMark', '@CapRotScaledMark', '@ShadeMark'])
		rules.append(mark_pos_rule('@AnchorStart', '@ShadeMark', 0, 0))
		for (sign, sc), scaled in self.cap_scale_to_cap.items():
			factor = SCALEDOWN ** sc
			(_, h) = self.unscaled_cap_to_size[sign]
			margin = -round(factor * self.margin / 2 / self.resolution) * self.resolution if sign in self.openings else 0
			y = round(factor * h / self.resolution) * self.resolution
			rules.append(mark_pos_rule(scaled, '@ShadeMark', margin, y))
		for (sign, sc), scaled in self.cap_rot_scale_to_cap.items():
			factor = SCALEDOWN ** sc
			(_, h) = self.unscaled_cap_rot_to_size[sign]
			margin = self.margin/2 if sign in self.openings_rot else 0
			y = round(factor * (h+margin) / self.resolution) * self.resolution
			rules.append(mark_pos_rule(scaled, '@ShadeMark', 0, y))
		for p in self.all_poss:
			for d in all_digits: 
				adv = d * 8**p * self.resolution
				rules.append(mark_pos_rule(self.left_shade_(d,p), '@ShadeMark', -adv, 0))
				rules.append(mark_pos_rule(self.right_shade_(d,p), '@ShadeMark', adv, 0))
				rules.append(mark_pos_rule(self.down_shade_(d,p), '@ShadeMark', 0, -adv))
		for p1, d1, w, p2, d2, _ in self.shade_combinations:
			adv = w * self.resolution if p1+1 < self.len_oct else 0
			rules.append(mark_pos_rule(self.shade_(d1, d2, p1, p2), '@ShadeMark', adv, 0))
		return name, rules, filt

	def anchor_bracket_rules(self):
		name, rules = 'anchor-bracket', []
		rules.append(mark_pos_rule(f'@BracketAnchor', '@BracketMark', 0, 0))
		return name, rules

	def anchor_bracket_depth_rules(self, depth):
		name, rules, filt = f'anchor-bracket-depth-{depth}', [], f'@AuxAnchorBracketDepth{depth}'
		self.add_class(filt, [self.depth_(depth-1), f'@AnchorEndAny{depth}', f'@BracketAnchor{depth}Mark'])
		rules.append(mark_pos_rule(f'@AnchorEndAny{depth}', f'@BracketAnchor{depth}Mark', 0, 0))
		rules.append(mark_pos_rule(f'@BracketAnchor{depth}Mark', f'@BracketAnchor{depth}Mark', 0, 0))
		return name, rules, filt

	def anchor_bracket_cross_depth_rules(self):
		name, rules, filt = 'anchor-bracket-cross-depth', [], '@AuxAnchorBracketCrossDepth'
		self.add_class(filt, ['@AnchorStart', '@BracketAnchor'])
		for depth in range(1, self.max_depth):
			rules.append(mark_pos_rule(f'@AnchorStart{depth-1}Mark', f'@BracketAnchor{depth}Mark', 0, 0))
		return name, rules, filt

	def anchor_cap_rules(self):
		name, rules, filt = 'anchor-cap', [], '@AuxAnchorCap'
		self.add_class(filt, ['@CapAnchorStart', '@CapAnchorEnd', \
				'@CapScaledMark', '@CapRotScaledMark', '@EnclosureScale'])
		rules.append(mark_pos_rule(f'@CapAnchorStart', '@CapScaledMark', 0, 0))
		rules.append(mark_pos_rule(f'@CapAnchorStart', '@CapRotScaledMark', 0, 0))
		for (sign, sc), scaled in self.cap_scale_to_cap.items():
			factor = SCALEDOWN ** sc
			(w, h) = self.unscaled_cap_to_size[sign]
			x = round(factor * w / self.resolution) * self.resolution
			y = round(factor * h / self.resolution) * self.resolution - self.enclosure_descent(sc)
			for depth in range(1, self.max_depth):
				rules.append(mark_pos_rule(scaled, f'@CapAnchorEnd{depth}Mark', x, y))
		for (_, sc), scaled in self.cap_rot_scale_to_cap.items():
			for depth in range(1, self.max_depth):
				rules.append(mark_pos_rule(scaled, f'@CapAnchorEnd{depth}Mark', self.enclosure_descent(sc), 0))
		for sc in self.all_scales:
			descent = self.enclosure_descent(sc)
			rules.append(mark_pos_rule('@CapAnchorStart', f'@EnclosureScaleHorizontal{sc}Mark', 0, -descent))
			rules.append(mark_pos_rule('@CapAnchorStart', f'@EnclosureScaleVertical{sc}Mark', descent, 0))
		for depth in range(1, self.max_depth):
			rules.append(mark_pos_rule('@EnclosureScale', f'@CapAnchorEnd{depth}Mark', 0, 0))
		return name, rules, filt

	def outline_hor_rules(self):
		name, rules, filt = 'outline-hor', [], '@AuxOutlineHor'
		self.add_class(filt, ['@AnchorStart', '@OutlineHorMark'])
		rules.append(mark_pos_rule('@AnchorStart', '@OutlineHorMark', 0, 0))
		for sc in self.all_scales:
			offset = round(SCALEDOWN ** sc * self.em) * self.resolution - self.enclosure_descent(sc)
			for d in all_digits[1:]:
				for p in self.all_poss:
					if p == self.len_oct-1 and d > 1:
						continue
					size = int(d * 8**p * self.resolution)
					x = size
					y = offset
					for level in 'pw':
						rules.append(mark_pos_rule(self.outline_(level, sc, 'hor', d, p), 
								f'@OutlineHorMark', x, y))
		return name, rules, filt

	def outline_ver_rules(self):
		name, rules, filt = 'outline-ver', [], '@AuxOutlineVer'
		self.add_class(filt, ['@AnchorStart', '@OutlineVerMark'])
		rules.append(mark_pos_rule('@AnchorStart', '@OutlineVerMark', 0, 0))
		for sc in self.all_scales:
			offset = round(SCALEDOWN ** sc * self.em) * self.resolution - self.enclosure_descent(sc)
			for d in all_digits[1:]:
				for p in self.all_poss:
					if p == self.len_oct-1 and d > 1:
						continue
					size = int(d) * 8**p * self.resolution
					x = self.enclosure_descent(sc)
					for level in 'pw':
						rules.append(mark_pos_rule(self.outline_(level, sc, 'ver', d, p), 
								'@OutlineVerMark', x, 0))
		return name, rules, filt

	###### Debugging 

	def visible_rules(self, i, items):
		name, rules = f'visible-{i}', []
		for (mark, base) in items:
			rules.append(simple_sub_rule([mark], [base]))
		return name, rules
