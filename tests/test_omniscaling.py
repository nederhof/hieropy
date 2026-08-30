# coding: utf-8
# vim: set syntax=python 
import unittest
import re
import math

from hieropy import UniParser
from hieropy.uniconstants import *
from hieropy.unistructure import *
from hieropy.unirandom import UniGenerator
from hieropy.uniomnifont import *

from tests.fontemulation import FontEmulator
from tests.omniaux import make_page, first_difference

DIR = 'tests/tmp/'
FONTFILE = 'omnifont'

class TestOmni(unittest.TestCase):

	@classmethod
	def setUpClass(cls):
		cls.builder = UniOmniFontBuilder(debug=True, ndigits=3)
		cls.builder.make_font_initial()
		cls.builder.syntax_analysis()
		cls.builder.local_analysis()
		cls.builder.scale_analysis()
		cls.builder.make_font_final(f'{DIR}/{FONTFILE}.ttf')
		cls.fontname = cls.builder.fontname
		cls.info = cls.builder.builder.all_text()
		cls.features = cls.builder.builder.features()
		cls.emulator = FontEmulator(f'{DIR}/{FONTFILE}.ttf')
		cls.parser = UniParser()

	def various_encodings(self):
		with open('tests/resources/omni.txt', 'r') as f:
			return f.readlines()

	def test_single(self):
		encodings = self.various_encodings()
		make_page(FONTFILE, f'{DIR}/omnitest2.html', self.fontname, encodings, 'hlr', self.info)

	def test_encodings(self):
		encodings = sorted(self.various_encodings(), key=len)
		for encoding in encodings:
			if not self.compare(encoding, 'hlr'):
				return

	def test_generation(self):
		generator = UniGenerator(depth_limit=5, chars=[chr(0x13000), chr(0x13001), chr(0x13002)])
		generator.weights['fragment'] = [0, 1]
		fragments = [generator.generate_fragment() for _ in range(30000)]
		encodings = [str(f) for f in fragments]
		encodings = sorted(set(encodings), key=len)
		for i, encoding in enumerate(encodings):
			with open(f'{DIR}/randomomni.txt', 'a', encoding='utf-8') as f:
				f.write(encoding + '\n')
			print(i, encoding)
			if not self.compare(encoding, 'hlr'):
				return
	
	def no_test_generation_vertical(self):
		generator = UniGenerator(depth_limit=5, chars=[chr(0x13000), chr(0x13001), chr(0x13002)])
		generator.weights['fragment'] = [0, 1]
		fragments = [generator.generate_fragment() for _ in range(30000)]
		encodings = [str(f) for f in fragments]
		encodings = sorted(set(encodings), key=len)
		for i, encoding in enumerate(encodings):
			with open(f'{DIR}/randomomni.txt', 'a', encoding='utf-8') as f:
				f.write(encoding + '\n')
			print(i, encoding)
			if not self.compare(encoding, 'vlr'):
				return
	
	def compare(self, encoding, direction):
		fragment = self.parser.parse(encoding)
		depth = fragment_max_depth(fragment)
		if depth > self.builder.max_depth:
			print(f'Depth {depth} exceeds {self.builder.max_depth}')
			return True
		fragment_sizing(fragment, self.builder, direction)
		names_tree = fragment_tree(fragment, self.builder)
		raw_names, _ = self.emulator.run(encoding, direction)
		names_emulator = [re.sub(r'_base$', '', s) for s in raw_names]
		i = first_difference(names_tree, names_emulator)
		if i is not None:
			print(fragment)
			print(names_tree[i])
			print(names_emulator[i])
			print(names_tree)
			print(names_emulator)
			print(names_tree[:i])
			with open(f'{DIR}/omni.txt', 'a', encoding='utf-8') as f:
				f.write(str(fragment) + '\n')
			return False
		else:
			return True

##### sizing

def fragment_sizing(frag, builder, direction):
	w_limit = builder.em if direction == 'vlr' else builder.max_octal_int
	h_limit = builder.max_octal_int if direction == 'vlr' else builder.em
	for g in frag.groups:
		top_group_sizing(g, builder, direction, w_limit, h_limit)

def top_group_sizing(group, builder, direction, w_limit, h_limit):
	group_sizing(group, builder, direction, w_limit, h_limit)

def group_sizing(group, builder, direction, w_limit, h_limit):
	group.ver = direction == 'vlr'
	group.content_width = None
	group.content_height = None
	group.insert_x = None
	group.insert_y = None
	group.parent_sc = None
	match group:
		case Vertical():
			return vertical_sizing(group, builder, direction, w_limit, h_limit)
		case Horizontal():
			return horizontal_sizing(group, builder, direction, w_limit, h_limit)
		case Enclosure():
			return enclosure_sizing(group, builder, direction, w_limit, h_limit)
		case Basic():
			return basic_sizing(group, builder, direction, w_limit, h_limit)
		case Overlay():
			return overlay_sizing(group, builder, direction, w_limit, h_limit)
		case Literal():
			return literal_sizing(group, builder, direction, w_limit, h_limit)
		case Singleton():
			return singleton_sizing(group, builder, direction, w_limit, h_limit)
		case Blank():
			return blank_sizing(group, builder, direction, w_limit, h_limit)
		case Lost():
			return lost_sizing(group, builder, direction, w_limit, h_limit)
		case BracketOpen():
			return bracket_open_sizing(group, builder, direction, w_limit, h_limit)
		case BracketClose():
			return bracket_close_sizing(group, builder, direction, w_limit, h_limit)

def group_no_sizing(group, direction):
	group.is_absent = True
	group.w = 0
	group.h = 0
	group.ver = direction == 'vlr'
	group.content_width = None
	group.content_height = None
	group.insert_x = None
	group.insert_y = None
	group.sc = 0
	group.parent_sc = None

def vertical_sizing(group, builder, direction, w_limit, h_limit):
	group.length = len(group.groups)
	if group.alt:
		name = builder.sym[group.alt.ch]
		w, h, _, _ = builder.unscaled_sign_to_size[name]
		group.w = builder.font_units_to_int(w + builder.margin)
		group.h = builder.font_units_to_int(h + builder.margin)
		scaledown_to_fit(group, builder, w_limit, h_limit)
		for g in group.groups:
			group_no_sizing(g, direction)
		scaledown_to_fit(group, builder, w_limit, h_limit)
		return
	for g in group.groups:
		group_sizing(g, builder, direction, builder.em, builder.max_octal_int)
	group.w = max(g.w for g in group.groups)
	group.h = sum(g.h for g in group.groups) % (builder.max_octal_int+1)
	scaledown_to_fit(group, builder, w_limit, h_limit)
	for g in group.groups:
		group_scaledown(g, builder, group.sc)

def horizontal_sizing(group, builder, direction, w_limit, h_limit):
	group.length = sum(1 for g in group.groups if not isinstance(g, (BracketOpen, BracketClose)))
	if group.alt:
		name = builder.sym[group.alt.ch]
		w, h, _, _ = builder.unscaled_sign_to_size[name]
		group.w = builder.font_units_to_int(w + builder.margin)
		group.h = builder.font_units_to_int(h + builder.margin)
		scaledown_to_fit(group, builder, w_limit, h_limit)
		for g in group.groups:
			group_no_sizing(g, direction)
		scaledown_to_fit(group, builder, w_limit, h_limit)
		return
	for g in group.groups:
		group_sizing(g, builder, direction, builder.max_octal_int, builder.em)
	group.w = sum(g.w for g in group.groups if not isinstance(g, (BracketOpen, BracketClose))) % (builder.max_octal_int+1)
	group.h = max(g.h for g in group.groups if not isinstance(g, (BracketOpen, BracketClose)))
	scaledown_to_fit(group, builder, w_limit, h_limit)
	for g in group.groups:
		if not isinstance(g, (BracketOpen, BracketClose)):
			group_scaledown(g, builder, group.sc)

def enclosure_sizing(group, builder, direction, w_limit, h_limit):
	scaledown_int = int(SCALEDOWN * builder.em)
	w_limit_sub = scaledown_int if group.ver else builder.max_octal_int
	h_limit_sub = builder.max_octal_int if group.ver else scaledown_int
	for g in group.groups:
		group_sizing(g, builder, direction, w_limit_sub, h_limit_sub)
	if group.ver:
		group.w = builder.em
		group.h = sum(g.h for g in group.groups)
		if group.delim_open:
			name = builder.sym[group.delim_open]
			group.open_name = builder.cap_to_rotate[name]
			w, h = builder.unscaled_cap_rot_to_size[group.open_name]
			group.delim_open_unscaled_w_exclusive = w
			group.delim_open_unscaled_h_exclusive = h
			h += builder.margin / 2
			group.delim_open_unscaled_w = w
			group.delim_open_unscaled_h = h
			group.h += builder.font_units_to_int(h)
		if group.delim_close:
			name = builder.sym[group.delim_close]
			group.close_name = builder.cap_to_rotate[name]
			w, h = builder.unscaled_cap_rot_to_size[group.close_name]
			group.delim_close_unscaled_w_exclusive = w
			group.delim_close_unscaled_h_exclusive = h
			h += builder.margin / 2
			group.delim_close_unscaled_w = w
			group.delim_close_unscaled_h = h
			group.h += builder.font_units_to_int(h)
		group.h = group.h % (builder.max_octal_int+1)
	else:
		group.w = sum(g.w for g in group.groups)
		group.h = builder.em
		if group.delim_open:
			group.open_name = builder.sym[group.delim_open]
			w, h = builder.unscaled_cap_to_size[group.open_name]
			group.delim_open_unscaled_w_exclusive = w
			group.delim_open_unscaled_h_exclusive = h
			w += builder.margin / 2
			group.delim_open_unscaled_w = w
			group.delim_open_unscaled_h = h
			group.w += builder.font_units_to_int(w)
		if group.delim_close:
			group.close_name = builder.sym[group.delim_close]
			w, h = builder.unscaled_cap_to_size[group.close_name]
			group.delim_close_unscaled_w_exclusive = w
			group.delim_close_unscaled_h_exclusive = h
			w += builder.margin / 2
			group.delim_close_unscaled_w = w
			group.delim_close_unscaled_h = h
			group.w += builder.font_units_to_int(w)
		group.w = group.w % (builder.max_octal_int+1)
	scaledown_to_fit(group, builder, w_limit, h_limit)
	for g in group.groups:
		group_scaledown(g, builder, group.sc)
		g.content_width = group.sc+1 if group.ver else None
		g.content_height = None if group.ver else group.sc+1

def basic_sizing(group, builder, direction, w_limit, h_limit):
	if isinstance(group.core, Literal):
		ch = group.core.ch
		name = builder.sym.get(ch)
		name = builder.name_rot_places_to_variant(name, group.core.rotation_coarse(), \
				list(group.insertions.keys()))
		group.core.alt_name = name
	else:
		name = builder.sym.get(group.core.alt.ch) if group.core.alt else None
	group_sizing(group.core, builder, direction, builder.max_octal_int, builder.max_octal_int)
	for pl, g in group.insertions.items():
		if name and (name, pl) in builder.name_place_to_geom:
			g.insert_geom = builder.name_place_to_geom[(name, pl)]
		else:
			g.insert_geom = builder.default_geom(pl)
		x, y, w, h = g.insert_geom
		x_int = builder.font_units_to_int(x)
		y_int = builder.font_units_to_int(y)
		w_int = builder.font_units_to_int(w)
		h_int = builder.font_units_to_int(h)
		group_sizing(g, builder, direction, w_int, h_int)
		g.insert_x = x_int
		g.insert_y = y_int
	group.w = group.core.w
	group.h = group.core.h
	scaledown_to_fit(group, builder, w_limit, h_limit)
	group_scaledown(group.core, builder, group.sc)
	for _, g in group.insertions.items():
		g.parent_sc = group.sc
		group_scaledown(g, builder, group.sc)

def overlay_sizing(group, builder, direction, w_limit, h_limit):
	if group.alt:
		name = builder.sym[group.alt.ch]
		w, h, _, _ = builder.unscaled_sign_to_size[name]
		group.w = builder.font_units_to_int(w + builder.margin) 
		group.h = builder.font_units_to_int(h + builder.margin)
		for g in group.lits1:
			group_no_sizing(g, direction)
		group.w1 = 0
		group.h1 = 0
		for g in group.lits2:
			group_no_sizing(g, direction)
		group.w2 = 0
		group.h2 = 0
		scaledown_to_fit(group, builder, w_limit, h_limit)
		return
	if len(group.lits1) > 1:
		for g in group.lits1:
			group_sizing(g, builder, direction, builder.max_octal_int, builder.em)
	else:
		group_sizing(group.lits1[0], builder, direction, builder.max_octal_int, builder.max_octal_int)
	group.w1 = sum(g.w for g in group.lits1) % (builder.max_octal_int+1)
	group.h1 = max(g.h for g in group.lits1)
	group.sc1 = 0
	while group.sc1+1 < builder.n_scales and group.w1 > builder.em:
		group.sc1 += 1
		group.w1 = math.floor(SCALEDOWN * group.w1)
		group.h1 = math.floor(SCALEDOWN * group.h1)
		for g in group.lits1:
			scaledown_factor(g, builder, 1)
	if len(group.lits2) > 1:
		for g in group.lits2:
			group_sizing(g, builder, direction, builder.em, builder.max_octal_int)
	else:
		group_sizing(group.lits2[0], builder, direction, builder.max_octal_int, builder.max_octal_int)
	group.w2 = max(g.w for g in group.lits2)
	group.h2 = sum(g.h for g in group.lits2) % (builder.max_octal_int+1)
	group.sc2 = 0
	while group.sc2+1 < builder.n_scales and group.h2 > builder.em:
		group.sc2 += 1
		group.w2 = math.floor(SCALEDOWN * group.w2)
		group.h2 = math.floor(SCALEDOWN * group.h2)
		for g in group.lits2:
			scaledown_factor(g, builder, 1)
	group.w = max(group.w1, group.w2)
	group.h = max(group.h1, group.h2)
	scaledown_to_fit(group, builder, w_limit, h_limit)
	for g in group.lits1 + group.lits2:
		group_scaledown(g, builder, group.sc)
	scaledown_overlay(group, builder)

def literal_sizing(group, builder, direction, w_limit, h_limit):
	if hasattr(group, 'alt_name'):
		name = group.alt_name
	else:
		name = builder.sym[group.ch]
	if group.vs:
		name = builder.name_rotate_to_name[(name, num_to_rotate(group.vs))]
	w, h, _, _ = builder.unscaled_sign_to_size[name]
	group.w = builder.font_units_to_int(w + builder.margin)
	group.h = builder.font_units_to_int(h + builder.margin)
	scaledown_to_fit(group, builder, w_limit, h_limit)
	group.is_absent = False

def singleton_sizing(group, builder, direction, w_limit, h_limit):
	group.name = builder.sym[group.ch]
	if group.ver:
		group.name = builder.cap_to_rotate[group.name]
		w, h = builder.unscaled_cap_rot_to_size[group.name]
	else:
		w, h = builder.unscaled_cap_to_size[group.name]
	group.w = builder.font_units_to_int(w) if group.ver else builder.font_units_to_int(w + builder.margin / 2)
	group.h = builder.font_units_to_int(h + builder.margin / 2) if group.ver else builder.font_units_to_int(h)
	scaledown_to_fit(group, builder, w_limit, h_limit)

def blank_sizing(group, builder, direction, w_limit, h_limit):
	group.name = builder.full_blank if group.dim == 1 else builder.half_blank
	group.w = builder.font_units_to_int(group.dim * builder.font_units)
	group.h = builder.font_units_to_int(group.dim * builder.font_units)
	scaledown_to_fit(group, builder, w_limit, h_limit)

def lost_sizing(group, builder, direction, w_limit, h_limit):
	if group.width == 0.5 and group.height == 0.5:
		group.name = builder.half_lost_exp if group.expand else builder.half_lost
	elif group.width == 0.5 and group.height == 1:
		group.name = builder.tall_lost_exp if group.expand else builder.tall_lost
	elif group.width == 1 and group.height == 0.5:
		group.name = builder.wide_lost_exp if group.expand else builder.wide_lost
	else:
		group.name = builder.full_lost_exp if group.expand else builder.full_lost
	group.w = builder.font_units_to_int(group.width * builder.font_units)
	group.h = builder.font_units_to_int(group.height * builder.font_units)
	scaledown_to_fit(group, builder, w_limit, h_limit)

def bracket_open_sizing(group, builder, direction, w_limit, h_limit):
	pass

def bracket_close_sizing(group, builder, direction, w_limit, h_limit):
	pass

##### recursive scaling down

def scaledown_to_fit(group, builder, w_limit, h_limit):
	group.sc = 0
	while group.sc+1 < builder.n_scales and (group.w > w_limit or group.h > h_limit):
		group.sc += 1
		group.w = math.floor(SCALEDOWN * group.w)
		group.h = math.floor(SCALEDOWN * group.h)

def scaledown_factor(group, builder, scale):
	for _ in range(scale):
		if group.sc+1 < builder.n_scales:
			group.sc += 1
			group.w = math.floor(SCALEDOWN * group.w)
			group.h = math.floor(SCALEDOWN * group.h)

def scaledown_overlay(group, builder):
	for _ in range(group.sc):
		if group.sc1+1 < builder.n_scales:
			group.sc1 += 1
			group.w1 = math.floor(SCALEDOWN * group.w1)
			group.h1 = math.floor(SCALEDOWN * group.h1)
		if group.sc2+1 < builder.n_scales:
			group.sc2 += 1
			group.w2 = math.floor(SCALEDOWN * group.w2)
			group.h2 = math.floor(SCALEDOWN * group.h2)

def group_scaledown(group, builder, scale):
	match group:
		case Vertical():
			return vertical_scaledown(group, builder, scale)
		case Horizontal():
			return horizontal_scaledown(group, builder, scale)
		case Enclosure():
			return enclosure_scaledown(group, builder, scale)
		case Basic():
			return basic_scaledown(group, builder, scale)
		case Overlay():
			return overlay_scaledown(group, builder, scale)
		case Literal():
			return literal_scaledown(group, builder, scale)
		case Singleton():
			return singleton_scaledown(group, builder, scale)
		case Blank():
			return blank_scaledown(group, builder, scale)
		case Lost():
			return lost_scaledown(group, builder, scale)

def vertical_scaledown(group, builder, scale):
	scaledown_factor(group, builder, scale)
	for g in group.groups:
		group_scaledown(g, builder, scale)

def horizontal_scaledown(group, builder, scale):
	scaledown_factor(group, builder, scale)
	for g in group.groups:
		group_scaledown(g, builder, scale)

def enclosure_scaledown(group, builder, scale):
	scaledown_factor(group, builder, scale)
	for g in group.groups:
		group_scaledown(g, builder, scale)

def basic_scaledown(group, builder, scale):
	scaledown_factor(group, builder, scale)
	group_scaledown(group.core, builder, scale)
	for _, g in group.insertions.items():
		group_scaledown(g, builder, scale)
		g.parent_sc = group.sc

def overlay_scaledown(group, builder, scale):
	scaledown_factor(group, builder, scale)
	for g in group.lits1:
		group_scaledown(g, builder, scale)
	for g in group.lits2:
		group_scaledown(g, builder, scale)

def literal_scaledown(group, builder, scale):
	scaledown_factor(group, builder, scale)

def singleton_scaledown(group, builder, scale):
	scaledown_factor(group, builder, scale)

def blank_scaledown(group, builder, scale):
	scaledown_factor(group, builder, scale)

def lost_scaledown(group, builder, scale):
	scaledown_factor(group, builder, scale)

def bracket_open_scaledown(group, builder, scale):
	pass

def bracket_close_scaledown(group, builder, scale):
	pass

##### max_depth 

def fragment_max_depth(frag):
	return max([top_group_max_depth(g) for g in frag.groups], default=0)

def top_group_max_depth(group):
	return group_max_depth(group, 0)

def group_max_depth(group, level):
	match group:
		case Vertical():
			return vertical_max_depth(group, level)
		case Horizontal():
			return horizontal_max_depth(group, level)
		case Enclosure():
			return enclosure_max_depth(group, level)
		case Basic():
			return basic_max_depth(group, level)
		case Overlay():
			return overlay_max_depth(group, level)
		case Literal():
			return literal_max_depth(group, level)
		case Singleton():
			return singleton_max_depth(group, level)
		case Blank():
			return blank_max_depth(group, level)
		case Lost():
			return lost_max_depth(group, level)
		case _:
			return level

def vertical_max_depth(group, level):
	return max([level] + [group_max_depth(g, level+1) for g in group.groups], default=0)

def horizontal_max_depth(group, level):
	return max([level] + [group_max_depth(g, level+1) for g in group.groups], default=0)

def enclosure_max_depth(group, level):
	return max([level] + [group_max_depth(g, level+1) for g in group.groups], default=0)

def basic_max_depth(group, level):
	return max([level, group_max_depth(group.core, level+1)] + \
			[group_max_depth(g, level+1) for _, g in group.insertions.items()], default=0)

def overlay_max_depth(group, level):
	return max([group_max_depth(g, level+2) for g in group.lits1 + group.lits2], default=0)

def literal_max_depth(group, level):
	return level

def singleton_max_depth(group, level):
	return level

def blank_max_depth(group, level):
	return level

def lost_max_depth(group, level):
	return level

def bracket_open_max_depth(group, level):
	return level

def bracket_close_max_depth(group, level):
	return level

##### to characters

def to_width_scaled_active(builder, n):
	oc = reversed(list(f'{n:0{builder.len_oct}o}'))
	return [builder.width_scaled_active_(d) for d in oc]

def to_height_scaled_active(builder, n):
	oc = reversed(list(f'{n:0{builder.len_oct}o}'))
	return [builder.height_scaled_active_(d) for d in oc]

def to_insert_x(builder, x, sc):
	if x is None:
		return []
	else:
		sign = [builder.minus_insert] if x < 0 else []
		x_abs = abs(x)
		x_scaled = iterate_scaledown(x_abs, sc)
		oc = reversed(list(f'{x_scaled:0{builder.len_oct}o}'))
		return sign + [builder.insert_sep] + [builder.insert_x_(d) for d in oc]

def to_insert_y(builder, y, sc):
	if y is None:
		return []
	else:
		sign = [builder.minus_insert] if y < 0 else []
		y_abs = abs(y)
		y_scaled = iterate_scaledown(y_abs, sc)
		oc = reversed(list(f'{y_scaled:0{builder.len_oct}o}'))
		return sign + [builder.insert_sep] + [builder.insert_y_(d) for d in oc] 

def to_width_full_scaled(builder, n):
	oc = reversed(list(f'{n:0{builder.len_oct}o}'))
	return [builder.width_full_scaled_(d) for d in oc]

def to_height_full_scaled(builder, n):
	oc = reversed(list(f'{n:0{builder.len_oct}o}'))
	return [builder.height_full_scaled_(d) for d in oc]

def active_dimensions(builder, group):
	return to_insert_x(builder, group.insert_x, group.parent_sc) + \
			to_insert_y(builder, group.insert_y, group.parent_sc) + \
			([builder.anchor_end_insert] if group.insert_x is not None else []) + \
			[builder.scale_group_active_(group.sc)] + \
			to_width_scaled_active(builder, group.w) + \
			to_height_scaled_active(builder, group.h)

def active_dimensions_overlay(builder, sc, w, h):
	return [builder.scale_group_active_(sc)] + \
			to_width_scaled_active(builder, w) + \
			to_height_scaled_active(builder, h)

def direction_strings(group, builder, level):
	return [builder.vertical if group.ver else builder.horizontal] if level == 0 else []

def fragment_tree(frag, builder):
	return [ch for g in frag.groups for ch in top_group_tree(g, builder)]

def top_group_tree(group, builder):
	return [ch for ch in group_tree(group, builder, 0)]

def group_tree(group, builder, level):
	match group:
		case Vertical():
			return vertical_tree(group, builder, level)
		case Horizontal():
			return horizontal_tree(group, builder, level)
		case Enclosure():
			return enclosure_tree(group, builder, level)
		case Basic():
			return basic_tree(group, builder, level)
		case Overlay():
			return overlay_tree(group, builder, level)
		case Literal():
			return literal_tree(group, builder, level)
		case Singleton():
			return singleton_tree(group, builder, level)
		case Blank():
			return blank_tree(group, builder, level)
		case Lost():
			return lost_tree(group, builder, level)
		case BracketOpen():
			return bracket_open_tree(group, builder, level)
		case BracketClose():
			return bracket_close_tree(group, builder, level)

def vertical_tree(group, builder, level):
	alt_chars = [builder.sym[group.alt.ch]] if group.alt else []
	inner = [ch for g in group.groups for ch in group_tree(g, builder, level+1)]
	return [builder.open_('v')] + \
			direction_strings(group, builder, level) + \
			[builder.length_(group.length), builder.depth_(level)] + \
			active_dimensions(builder, group) + \
			[builder.record] + alt_chars + inner + \
			[builder.depth_(level)] + \
			[builder.close_('v')]

def horizontal_tree(group, builder, level):
	alt_chars = [builder.sym[group.alt.ch]] if group.alt else []
	inner = [ch for g in group.groups for ch in group_tree(g, builder, level+1)]
	return [builder.open_('h')] + \
			direction_strings(group, builder, level) + \
			[builder.length_(group.length), builder.depth_(level)] + \
			active_dimensions(builder, group) + \
			[builder.record] + alt_chars + inner + \
			[builder.depth_(level)] + \
			[builder.close_('h')]

def enclosure_tree(group, builder, level):
	open_chars = []
	open_chars.append(builder.cap_anchor_start)
	open_chars.append(builder.enclosure_scale_(group.sc))
	open_chars.append(builder.cap_anchor_end)
	if group.delim_open:
		open_chars.append(builder.cap_anchor_start)
		open_chars.append(builder.cap_scale_(group.sc))
		open_chars.append(builder.cap_anchor_end)
		open_chars.append(group.open_name)
		if group.damage_open:
			open_chars.append(builder.damaged[group.damage_open-1])
	close_chars = []
	if group.delim_close:
		close_chars.append(builder.cap_anchor_start)
		close_chars.append(builder.cap_scale_(group.sc))
		close_chars.append(builder.cap_anchor_end)
		close_chars.append(group.close_name)
		if group.damage_close:
			close_chars.append(builder.damaged[group.damage_close-1])
	inner = [ch for g in group.groups for ch in group_tree(g, builder, level+1)]
	letter = 'w' if group.typ == 'walled' else 'p'
	direction = builder.vertical if group.ver else builder.horizontal
	return [builder.open_(letter), direction, builder.depth_(level)] + \
			active_dimensions(builder, group) + \
			[builder.record] + open_chars + inner + close_chars + \
			[builder.depth_(level)] + \
			[builder.close_(letter)]

def basic_tree(group, builder, level):
	insertions = []
	for place, g in group.insertions.items():
		place_ch = builder.sym[INSERTION_CHARS[INSERTION_PLACES.index(place)]]
		insertions.append(place_ch)
		insertions += group_tree(g, builder, level+1)
	place_uses = [builder.used_places[i] for i, pl in enumerate(INSERTION_PLACES) if pl in group.insertions]
	return [builder.open_('i')] + \
			direction_strings(group, builder, level) + \
			place_uses + \
			[builder.depth_(level)] + \
			active_dimensions(builder, group) + \
			[builder.record] + \
			group_tree(group.core, builder, level+1) + insertions + \
			[builder.depth_(level)] + \
			[builder.close_('i')]

def overlay_tree(group, builder, level):
	alt_chars = [builder.sym[group.alt.ch]] if group.alt else []
	if len(group.lits1) > 1:
		capped_len = min(len(group.lits1), MAX_COUNT)
		hor = [builder.open_('h')] + \
			[builder.length_(capped_len), builder.flat, builder.depth_(level+1)] + \
			active_dimensions_overlay(builder, group.sc1, group.w1, group.h1) + \
			[builder.record] + \
			[ch for g in group.lits1 for ch in group_tree(g, builder, level+2)] + \
			[builder.depth_(level+1), builder.close_('h')]
	else:
		hor = group_tree(group.lits1[0], builder, level+1)
	if len(group.lits2) > 1:
		capped_len = min(len(group.lits2), MAX_COUNT)
		ver = [builder.open_('v'), builder.length_(capped_len), builder.flat, builder.depth_(level+1)] + \
			active_dimensions_overlay(builder, group.sc2, group.w2, group.h2) + \
			[builder.record] + \
			[ch for g in group.lits2 for ch in group_tree(g, builder, level+2)] + \
			[builder.depth_(level+1), builder.close_('v')]
	else:
		ver = group_tree(group.lits2[0], builder, level+1)
	return [builder.open_('o')] + \
			direction_strings(group, builder, level) + \
			[builder.depth_(level)] + \
			active_dimensions(builder, group) + \
			[builder.record] + alt_chars + hor + ver + \
			[builder.depth_(level)] + \
			[builder.close_('o')]

def literal_tree(group, builder, level):
	if group.is_absent:
		name = builder.absent_sign
	elif hasattr(group, 'alt_name'):
		name = group.alt_name
	else:
		name = builder.sym[group.alt]
		if group.vs:
			name = builder.name_rotate_to_name[(name, num_to_rotate(group.vs))]
	mir = [builder.mirror] if group.mirror else []
	dam = [builder.damaged[group.damage-1]] if group.damage else []
	return [builder.open_('b')] + \
			direction_strings(group, builder, level) + \
			[builder.depth_(level)] + \
			active_dimensions(builder, group) + \
			[builder.record, name] + mir + dam + \
			[builder.depth_(level), builder.close_('b')]

def singleton_tree(group, builder, level):
	dam = [builder.damaged[group.damage-1]] if group.damage else []
	return [builder.open_('b')] + \
			direction_strings(group, builder, level) + \
			[builder.depth_(level)] + \
			active_dimensions(builder, group) + \
			[builder.record, group.name] + dam + \
			[builder.depth_(level), builder.close_('b')]

def blank_tree(group, builder, level):
	return [builder.open_('b')] + \
			direction_strings(group, builder, level) + \
			[builder.depth_(level)] + \
			active_dimensions(builder, group) + \
			[builder.record, group.name, builder.depth_(level)] + \
			[builder.close_('b')]

def lost_tree(group, builder, level):
	return [builder.open_('b')] + \
			direction_strings(group, builder, level) + \
			[builder.depth_(level)] + \
			active_dimensions(builder, group) + \
			[builder.record, group.name, builder.depth_(level)] + \
			[builder.close_('b')]

def bracket_open_tree(group, builder, level):
	return [builder.sym[group.ch]]

def bracket_close_tree(group, builder, level):
	return [builder.sym[group.ch]]
