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
from tests.test_omniscaling import fragment_sizing, fragment_max_depth
from tests.test_omnipadding import fragment_pad

DIR = 'tests/tmp/'
FONTFILE = 'omnifont'

def printables_of(builder):
	chars = set()
	chars.update(builder.unscaled_sign_to_size.keys())
	chars.update(builder.unscaled_cap_to_size.keys())
	chars.update(builder.unscaled_lost_to_size.keys())
	chars.update(builder.name_scale_to_name.values())
	chars.update(builder.unscaled_cap_to_size.keys())
	chars.update(builder.unscaled_cap_rot_to_size.keys())
	chars.update(builder.cap_scale_to_cap.values())
	chars.update(builder.cap_rot_scale_to_cap.values())
	chars.update(builder.lost_scale_to_lost.values())
	chars.update(builder.bracket_scale_to_bracket.values())
	chars.update(builder.shade_(d1, d2, p1, p2) for (p1, d1, _, p2, d2, _) in builder.shade_combinations)
	chars.update(builder.outline_(level, sc, direction, d, p) \
			for sc in builder.all_scales for d in all_digits[1:] for p in builder.all_poss \
			for direction in ['hor', 'ver'] for level in 'pw')

	# chars.add(builder.anchor_start_insert_(1))
	# chars.add(builder.anchor_insert_mid_(0))
	# chars.add(builder.anchor_start_(0))
	# chars.add(builder.anchor_start_(1))
	# chars.add(builder.anchor_basic_mid)
	#chars.add(builder.cap_anchor_start_(2))
	#chars.add(builder.cap_anchor_end_(2))
	# chars.add(builder.start_ver)
	return chars

class TestOmni(unittest.TestCase):

	@classmethod
	def setUpClass(cls):
		cls.builder = UniOmniFontBuilder(debug=False, log=True, maxdepth=3, nscales=3, ndigits=2, \
					signcolor='black', bracketcolor='black', shadealpha=255, shadepattern='diagonal')
		cls.builder.make_font_initial()
		cls.builder.syntax_analysis()
		cls.builder.local_analysis()
		cls.builder.scale_analysis()
		cls.builder.padding_analysis()
		cls.builder.substitution()
		cls.builder.shading_analysis()
		cls.builder.positioning()
		cls.builder.make_font_final(f'{DIR}/{FONTFILE}.ttf')
		cls.fontname = cls.builder.fontname
		cls.info = cls.builder.builder.all_text()
		cls.features = cls.builder.builder.features()
		cls.emulator = FontEmulator(f'{DIR}/{FONTFILE}.ttf')
		cls.parser = UniParser()
		cls.printables = printables_of(cls.builder)

	def various_encodings(self):
		with open('tests/resources/omni.txt', 'r') as f:
			return f.readlines()

	def test_single(self):
		encodings = self.various_encodings()
		#encodings = ['𓑂⸣']
		#encodings = ['𓑂⟧𓀀']
		#encodings = ['𓍹𓐼𓀀𓐽𓍺']
		encodings = ['𓀁𓐲𓉘𓑐𓐼𓀀𓑎𓐽𓍺']
		#encodings = ['𓀀𓐳𓐷[𓐷𓀀𓐰𓀁𓐸𓐸']
		make_page(FONTFILE, f'{DIR}/omnitest4.html', self.fontname, encodings, 'hlr', self.info)

	def test_encodings(self):
		encodings = sorted(self.various_encodings(), key=len)
		#encodings = ['𓑂⟧𓀀']
		#encodings = ['𓍹𓐼𓀀𓐽𓍺']
		encodings = ['𓀁𓐲𓉘𓑐𓐼𓀀𓑎𓐽𓍺']
		#encodings = ['𓀀𓐳𓐷[𓐷𓀀𓐰𓀁𓐸𓐸']
		for encoding in encodings:
			if not self.compare(encoding, 'hlr'):
				return

	def test_generation(self):
		generator = UniGenerator(depth_limit=5, chars=[chr(0x13000), chr(0x13001), chr(0x13002)])
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
			print(i, encoding)
			if not self.compare(encoding, 'vlr'):
				return
	
	def compare(self, encoding, direction):
		fragment = self.parser.parse(encoding)
		encoding = str(fragment)
		depth = fragment_max_depth(fragment)
		if depth > self.builder.max_depth:
			print(f'Depth {depth} exceeds {self.builder.max_depth}')
			return True
		if True: # temporarily omitted
			fragment_sizing(fragment, self.builder, direction)
			fragment_pad(fragment, self.builder, direction)
			fragment_position(fragment, self.builder, direction)
			try:
				poss_tree = fragment_tree(fragment, self.builder)
			except:
				with open(f'{DIR}/omni.txt', 'a', encoding='utf-8') as f:
					f.write(f'crashed on:{encoding}\n')
				print("fragment_tree crashed")
				exit(0)
		_, poss_emulator = self.emulator.run(encoding, direction)
		poss_emulator = [tupl for tupl in poss_emulator if tupl[0] in self.printables]
		# print(poss_emulator)
		end_marker = [('end', 0, 0, 0, 0)]
		poss_tree_ext = poss_tree + end_marker
		poss_emulator_ext = poss_emulator + end_marker
		i = first_difference(poss_tree + end_marker, poss_emulator + end_marker)
		if i is not None:
			print(fragment)
			print(poss_tree_ext[i])
			print(poss_emulator_ext[i])
			print(poss_tree)
			print(poss_emulator)
			print(poss_tree_ext[:i])
			with open(f'{DIR}/omni.txt', 'a', encoding='utf-8') as f:
				f.write(str(fragment) + '\n')
			return False
		else:
			return True

##### positioning

def fragment_position(frag, builder, direction):
	for g in frag.groups:
		if direction == 'vlr':
			top_group_position(g, builder, -builder.font_units // 2, 0)
		else:
			top_group_position(g, builder, 0, builder.font_units)

def top_group_position(group, builder, x, y):
	group_position(group, builder, x, y)

def group_position(group, builder, x, y):
	group.x = x
	group.y = y
	match group:
		case Vertical():
			return vertical_position(group, builder, x, y)
		case Horizontal():
			return horizontal_position(group, builder, x, y)
		case Enclosure():
			return enclosure_position(group, builder, x, y)
		case Basic():
			return basic_position(group, builder, x, y)
		case Overlay():
			return overlay_position(group, builder, x, y)
		case Literal():
			return literal_position(group, builder, x, y)
		case Singleton():
			return singleton_position(group, builder, x, y)
		case Blank():
			return blank_position(group, builder, x, y)
		case Lost():
			return lost_position(group, builder, x, y)

def vertical_position(group, builder, x, y):
	y_accum = y
	for g in group.groups:
		group_position(g, builder, x, y_accum)
		y_accum -= g.h_full * builder.resolution

def horizontal_position(group, builder, x, y):
	x_accum = x
	for i, g in enumerate(group.groups):
		if isinstance(g, BracketOpen):
			bracket_open_position(g, builder, x_accum, y, group.groups[i+1].h_full)
		elif isinstance(g, BracketClose):
			bracket_close_position(g, builder, x_accum, y, group.groups[i-1].h_full)
		else:
			group_position(g, builder, x_accum, y)
			x_accum += g.w_full * builder.resolution

def enclosure_position(group, builder, x, y):
	factor = SCALEDOWN ** group.sc
	x_accum = x
	y_accum = y
	if group.delim_open:
		if group.ver:
			group.delim_open_x = x
			h = builder.font_units_to_int(factor * group.delim_open_unscaled_h) * builder.resolution
			group.delim_open_y = y - h
			y_accum = y - h
		else:
			w = builder.font_units_to_int(factor * group.delim_open_unscaled_w_exclusive) * builder.resolution
			margin = round(factor * builder.margin / 2 / builder.resolution) * builder.resolution
			group.delim_open_x = x + margin
			x_accum = x + w + margin
			group.delim_open_y = y
	if group.ver:
		x_accum += builder.enclosure_descent(group.sc)
	else:
		y_accum -= builder.enclosure_descent(group.sc)
	for g in group.groups:
		group_position(g, builder, x_accum, y_accum)
		if group.ver:
			y_accum -= g.h_full * builder.resolution
		else:
			x_accum += g.w_full * builder.resolution
	if group.delim_close:
		group.delim_close_x = x if group.ver else x_accum
		group.delim_close_y = y_accum if group.ver else y

def basic_position(group, builder, x, y):
	group_position(group.core, builder, x, y)
	x_center_group = x + int(group.w_full / 2) * builder.resolution
	y_center_group = y - int(group.h_full / 2) * builder.resolution
	base = group.core.alt
	for pl, g in group.insertions.items():
		x_center, y_center, _, _ = g.insert_geom
		x_round = builder.font_units_to_int(x_center)
		y_round = builder.font_units_to_int(y_center)
		x_center = iterate_scaledown(x_round, group.sc) * builder.resolution
		y_center = iterate_scaledown(y_round, group.sc) * builder.resolution
		x_pl = x_center_group + x_center - int(g.w_full / 2) * builder.resolution
		y_pl = y_center_group + y_center + int(g.h_full / 2) * builder.resolution
		group_position(g, builder, x_pl, y_pl)

def overlay_position(group, builder, x, y):
	x_accum = x
	for g in group.lits1:
		group_position(g, builder, x_accum, y)
		x_accum += g.w_full * builder.resolution
	y_accum = y
	for g in group.lits2:
		group_position(g, builder, x, y_accum)
		y_accum -= g.h_full * builder.resolution

def literal_position(group, builder, x, y):
	pass

def singleton_position(group, builder, x, y):
	pass

def blank_position(group, builder, x, y):
	pass

def lost_position(group, builder, x, y):
	pass

def bracket_open_position(group, builder, x, y, height):
	group.x = x
	group.y = y
	group.sc = 0
	while builder.font_units_to_int(SCALEDOWN ** group.sc * builder.font_units) > height and group.sc+1 < builder.n_scales:
		group.sc += 1

def bracket_close_position(group, builder, x, y, height):
	group.x = x
	group.y = y
	group.sc = 0
	while builder.font_units_to_int(SCALEDOWN ** group.sc * builder.font_units) > height and group.sc+1 < builder.n_scales:
		group.sc += 1

##### to characters

def fragment_tree(frag, builder):
	return [ch for g in frag.groups for ch in top_group_tree(g, builder)]

def top_group_tree(group, builder):
	return [ch for ch in group_tree(group, builder)]

def group_tree(group, builder):
	match group:
		case Vertical():
			return vertical_tree(group, builder)
		case Horizontal():
			return horizontal_tree(group, builder)
		case Enclosure():
			return enclosure_tree(group, builder)
		case Basic():
			return basic_tree(group, builder)
		case Overlay():
			return overlay_tree(group, builder)
		case Literal():
			return literal_tree(group, builder)
		case Singleton():
			return singleton_tree(group, builder)
		case Blank():
			return blank_tree(group, builder)
		case Lost():
			return lost_tree(group, builder)
		case BracketOpen():
			return bracket_open_tree(group, builder)
		case BracketClose():
			return bracket_close_tree(group, builder)

def vertical_tree(group, builder):
	chars = []
	if group.alt:
		chars.extend(ligature_tree(group, builder))
	chars.extend(ch for g in group.groups for ch in group_tree(g, builder))
	return chars

def horizontal_tree(group, builder):
	chars = []
	if group.alt:
		chars.extend(ligature_tree(group, builder))
	chars.extend(ch for g in group.groups for ch in group_tree(g, builder))
	return chars

def enclosure_tree(group, builder):
	level = 'w' if group.typ == 'walled' else 'p'
	direction = 'ver' if group.ver else 'hor'
	factor = SCALEDOWN ** group.sc
	chars = []
	if group.delim_open:
		open_name = group.open_name
		if group.ver:
			open_name = builder.cap_rot_scale_to_cap[(open_name, group.sc)]
			chars.append((open_name, group.delim_open_x, group.delim_open_y, 0, 0))
		else:
			open_name = builder.cap_scale_to_cap[(open_name, group.sc)]
			height = round(factor * builder.em) * builder.resolution
			chars.append((open_name, group.delim_open_x, group.delim_open_y - height, 0, 0))
		if group.damage_open:
			w = builder.font_units_to_int(factor * group.delim_open_unscaled_w)
			h = builder.font_units_to_int(factor * group.delim_open_unscaled_h)
			chars.extend(damage_tree(builder, group.x, group.y, \
					w, h, group.damage_open))
	for g in group.groups:
		if group.ver:
			digits = builder.int_to_octal_reverse(g.h)
			y_accum = g.y
			for p, d in enumerate(digits[:-1]):
				if int(d) > 0:
					outline = builder.outline_(level, group.sc, direction, d, p)
					chars.append((outline, \
							group.x, y_accum - int(d) * 8 ** p * builder.resolution, 0, 0))
					y_accum -= int(d) * 8**p * builder.resolution
			for _ in range(int(digits[-1])):
				outline = builder.outline_(level, group.sc, direction, 1, builder.len_oct-1)
				chars.append((outline, \
						group.x, y_accum - 8**(builder.len_oct-1) * builder.resolution, 0, 0))
				y_accum -= 8**(builder.len_oct-1) * builder.resolution
		else:
			digits = builder.int_to_octal_reverse(g.w)
			x_accum = g.x
			for p, d in enumerate(digits[:-1]):
				if int(d) > 0:
					outline = builder.outline_(level, group.sc, direction, d, p)
					chars.append((outline, \
							x_accum, group.y - round(SCALEDOWN ** group.sc * builder.em) * builder.resolution, 0, 0))
					x_accum += int(d) * 8**p * builder.resolution
			for _ in range(int(digits[-1])):
				outline = builder.outline_(level, group.sc, direction, 1, builder.len_oct-1)
				chars.append((outline, \
						x_accum, group.y - round(SCALEDOWN ** group.sc * builder.em) * builder.resolution, 0, 0))
				x_accum += 8**(builder.len_oct-1) * builder.resolution
		chars.extend(group_tree(g, builder))
	if group.delim_close:
		close_name = group.close_name
		if group.ver:
			_, h = builder.unscaled_cap_rot_to_size[close_name]
			close_name = builder.cap_rot_scale_to_cap[(close_name, group.sc)]
			height = round(factor * h / builder.resolution) * builder.resolution
			chars.append((close_name, group.delim_close_x, group.delim_close_y - height, 0, 0))
		else:
			close_name = builder.cap_scale_to_cap[(close_name, group.sc)]
			height = round(factor * builder.em) * builder.resolution
			chars.append((close_name, group.delim_close_x, group.delim_close_y - height, 0, 0))
		if group.damage_close:
			w = builder.font_units_to_int(factor * group.delim_close_unscaled_w)
			h = builder.font_units_to_int(factor * group.delim_close_unscaled_h)
			chars.extend(damage_tree(builder, group.delim_close_x, group.delim_close_y, \
					w, h, group.damage_close))
	return chars

def basic_tree(group, builder):
	chars = group_tree(group.core, builder)
	for _, g in group.insertions.items():
		chars.extend(group_tree(g, builder))
	return chars

def overlay_tree(group, builder):
	chars = []
	if group.alt:
		chars.extend(ligature_tree(group, builder))
	chars.extend(ch for g in group.lits1 for ch in group_tree(g, builder))
	chars.extend(ch for g in group.lits2 for ch in group_tree(g, builder))
	return chars

def literal_tree(group, builder):
	chars = []
	if not group.is_absent:
		if hasattr(group, 'alt_name'):
			name = group.alt_name
		else:
			name = builder.sym[group.alt]
		if group.vs:
			name = builder.name_rotate_to_name[(name, num_to_rotate(group.vs))]
		if group.mirror and name in builder.name_to_mirrored:
			name = builder.name_to_mirrored[name]
		w, h, dx, dy = builder.unscaled_sign_to_size[name]
		if group.sc > 0:
			name = builder.name_scale_to_name[(name, group.sc)]
		factor = SCALEDOWN ** group.sc
		x_center = round(factor * (w/2+dx))
		y_center = round(factor * (h/2+dy))
		x = group.x + int(group.w_full / 2) * builder.resolution - x_center
		y = group.y - int(group.h_full / 2) * builder.resolution - y_center
		chars.append((name, x, y, 0, 0))
	chars.extend(damage_tree(builder, group.x, group.y, group.w_full, group.h_full, group.damage))
	return chars

def singleton_tree(group, builder):
	chars = []
	name = builder.sym[group.ch]
	if group.ver:
		name = builder.cap_to_rotate[name]
		w, h = builder.unscaled_cap_rot_to_size[name]
		if name in builder.openings_rot:
			x_center = round(w/2)
			y_center = round((h+builder.margin/2)/2)
		else:
			x_center = round(w/2)
			y_center = round((h-builder.margin/2)/2)
	else:
		w, h = builder.unscaled_cap_to_size[name]
		if name in builder.openings:
			x_center = round((w-builder.margin/2)/2)
			y_center = round(h/2)
		else:
			x_center = round((w+builder.margin/2)/2)
			y_center = round(h/2)
	x = group.x + int(group.w_full / 2) * builder.resolution - x_center
	y = group.y - int(group.h_full / 2) * builder.resolution - y_center
	chars.append((name, x, y, 0, 0))
	chars.extend(damage_tree(builder, group.x, group.y, group.w_full, group.h_full, group.damage))
	return chars

def blank_tree(group, builder):
	return []

def lost_tree(group, builder):
	chars = []
	if group.expand:
		chars.extend(damage_tree(builder, group.x, group.y, group.w_full, group.h_full, 15))
	else:
		name = group.name
		w, h = builder.unscaled_lost_to_size[name]
		if group.sc > 0:
			name = builder.lost_scale_to_lost[(name, group.sc)]
		factor = SCALEDOWN ** group.sc
		x_center = round(factor * builder.em * w / 2) * builder.resolution
		y_center = round(factor * builder.em * h / 2) * builder.resolution
		x = group.x + int(group.w_full / 2) * builder.resolution - x_center
		y = group.y - int(group.h_full / 2) * builder.resolution - y_center
		chars.append((name, x, y, 0, 0))
	return chars

def bracket_open_tree(group, builder):
	bracket = builder.sym[group.ch]
	bracket = builder.bracket_scale_to_bracket[(bracket, group.sc)]
	w = builder.bracket_width[bracket]
	w_font = builder.bracket_width[bracket]
	h_font = round(SCALEDOWN ** group.sc * builder.font_units)
	x = group.x - w_font
	y = group.y - h_font
	return [(bracket, x, y, 0, 0)]

def bracket_close_tree(group, builder):
	bracket = builder.sym[group.ch]
	bracket = builder.bracket_scale_to_bracket[(bracket, group.sc)]
	w = builder.bracket_width[bracket]
	w_font = builder.bracket_width[bracket]
	h_font = round(SCALEDOWN ** group.sc * builder.font_units)
	x = group.x
	y = group.y - h_font
	return [(bracket, x, y, 0, 0)]

def ligature_tree(group, builder):
	name = builder.sym[group.alt.ch]
	w, h, dx, dy = builder.unscaled_sign_to_size[name]
	if group.sc > 0:
		name = builder.name_scale_to_name[(name, group.sc)]
	factor = SCALEDOWN ** group.sc
	x_center = round(factor * (w/2+dx))
	y_center = round(factor * (h/2+dx))
	x = group.x + int(group.w_full / 2) * builder.resolution - x_center
	y = group.y - int(group.h_full / 2) * builder.resolution - y_center
	return [(name, x, y, 0, 0)]

def damage_tree(builder, x, y, w, h, damage):
	chars = []
	w2 = math.ceil(w / 2)
	h2 = math.ceil(h / 2)
	match damage:
		case 1:
			chars.extend(damage_rect(builder, x, y, w2, h2))
		case 2:
			chars.extend(damage_rect(builder, x, y - h2 * builder.resolution, w2, h2))
		case 3:
			chars.extend(damage_rect(builder, x, y, w2, h))
		case 4:
			chars.extend(damage_rect(builder, x + w2 * builder.resolution, y, w2, h2))
		case 5:
			chars.extend(damage_rect(builder, x, y, w, h2))
		case 6:
			chars.extend(damage_rect(builder, x + w2 * builder.resolution, y, w2, h2))
			chars.extend(damage_rect(builder, x, y - h2 * builder.resolution, w2, h2))
		case 7:
			chars.extend(damage_rect(builder, x, y, w, h2))
			chars.extend(damage_rect(builder, x, y - h2 * builder.resolution, w2, h2))
		case 8:
			chars.extend(damage_rect(builder, x + w2 * builder.resolution, y - h2 * builder.resolution, w2, h2))
		case 9:
			chars.extend(damage_rect(builder, x, y, w2, h2))
			chars.extend(damage_rect(builder, x + w2 * builder.resolution, y - h2 * builder.resolution, w2, h2))
		case 10:
			chars.extend(damage_rect(builder, x, y - h2 * builder.resolution, w, h2))
		case 11:
			chars.extend(damage_rect(builder, x, y, w2, h2))
			chars.extend(damage_rect(builder, x, y - h2 * builder.resolution, w, h2))
		case 12:
			chars.extend(damage_rect(builder, x + w2 * builder.resolution, y, w2, h))
		case 13:
			chars.extend(damage_rect(builder, x, y, w, h2))
			chars.extend(damage_rect(builder, x + w2 * builder.resolution, y - h2 * builder.resolution, w2, h2))
		case 14:
			chars.extend(damage_rect(builder, x + w2 * builder.resolution, y, w2, h2))
			chars.extend(damage_rect(builder, x, y - h2 * builder.resolution, w, h2))
		case 15:
			chars.extend(damage_rect(builder, x, y, w, h))
	return chars

def damage_rect(builder, x, y, w, h):
	chars = []
	w_digits = builder.int_to_octal_reverse(w)
	h_digits = builder.int_to_octal_reverse(h)
	y_accum = y
	for j, dy in enumerate(h_digits):
		height = int(dy) * 8 ** j * builder.resolution
		x_accum = x
		for i, dx in enumerate(w_digits):
			if int(dx) > 0 and int(dy) > 0:
				if f'shade_{dx}_{dy}_{i}_{j}' not in builder.sym:
					raise Exception(f'shade_{dx}_{dy}_{i}_{j} not in builder.sym')
				ch = builder.shade_(dx, dy, i, j)
				chars.append((ch, x_accum, y_accum - height, 0, 0))
			x_accum += int(dx) * 8 ** i * builder.resolution
		y_accum -= height
	return chars
