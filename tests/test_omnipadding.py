# coding: utf-8
# vim: set syntax=python 
import unittest
import re

from hieropy import UniParser
from hieropy.uniconstants import *
from hieropy.unistructure import *
from hieropy.unirandom import UniGenerator
from hieropy.uniomnifont import *

from tests.fontemulation import FontEmulator
from tests.omniaux import make_page, first_difference
from tests.test_omniscaling import fragment_sizing, fragment_max_depth, direction_strings, to_insert_x, to_insert_y

DIR = 'tests/tmp/'
FONTFILE = 'omnifont'

class TestOmni(unittest.TestCase):

	@classmethod
	def setUpClass(cls):
		cls.builder = UniOmniFontBuilder(debug=True, ndigits=2)
		cls.builder.make_font_initial()
		cls.builder.syntax_analysis()
		cls.builder.local_analysis()
		cls.builder.scale_analysis()
		cls.builder.padding_analysis()
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
		make_page(FONTFILE, f'{DIR}/omnitest3.html', self.fontname, encodings, 'hlr', self.info)

	def test_encodings(self):
		encodings = sorted(self.various_encodings(), key=len)
		for encoding in encodings:
			print(encoding)
			if not self.compare(encoding, 'hlr'):
				return

	def test_generation(self):
		generator = UniGenerator(depth_limit=5, chars=[chr(0x13000), chr(0x13001), chr(0x13002)])
		generator.weights['fragment'] = [0, 1]
		fragments = [generator.generate_fragment() for _ in range(30000)]
		encodings = [str(f) for f in fragments]
		encodings = sorted(set(encodings), key=len)
		for i, encoding in enumerate(encodings):
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
		depth = fragment_max_depth(fragment)
		if depth > self.builder.max_depth:
			print(f'Depth {depth} exceeds {self.builder.max_depth}') 
			return True
		fragment_sizing(fragment, self.builder, direction)
		fragment_pad(fragment, self.builder, direction)
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

##### add padding

def quotients(n, divisor):
	q = n // divisor
	r = n - q * divisor
	return q, q + r

def recalculate_padding(group, builder, w_limit, h_limit, w_pad, h_pad, w_alt=False, h_alt=False):
	if w_limit is not None:
		group.w_full = w_limit
	else:
		group.w_full = (group.w + w_pad) % (builder.max_octal_int+1)
	if h_limit is not None:
		group.h_full = h_limit
	else:
		group.h_full = (group.h + h_pad) % (builder.max_octal_int+1)
	if w_alt:
		group.w_pad = group.w_full
	else:
		group.w_pad = max(group.w_full - group.w, 0)
	if h_alt:
		group.h_pad = group.h_full
	else:
		group.h_pad = max(group.h_full - group.h, 0)

def fragment_pad(frag, builder, direction):
	w_limit = builder.em if direction == 'vlr' else None
	h_limit = None if direction == 'vlr' else builder.em
	for g in frag.groups:
		top_group_pad(g, builder, w_limit, h_limit, 0, 0)

def top_group_pad(group, builder, w_limit, h_limit, w_pad, h_pad):
	group_pad(group, builder, w_limit, h_limit, w_pad, h_pad)

def group_pad(group, builder, w_limit, h_limit, w_pad, h_pad):
	match group:
		case Vertical():
			return vertical_pad(group, builder, w_limit, h_limit, w_pad, h_pad)
		case Horizontal():
			return horizontal_pad(group, builder, w_limit, h_limit, w_pad, h_pad)
		case Enclosure():
			return enclosure_pad(group, builder, w_limit, h_limit, w_pad, h_pad)
		case Basic():
			return basic_pad(group, builder, w_limit, h_limit, w_pad, h_pad)
		case Overlay():
			return overlay_pad(group, builder, w_limit, h_limit, w_pad, h_pad)
		case Literal():
			return literal_pad(group, builder, w_limit, h_limit, w_pad, h_pad)
		case Singleton():
			return singleton_pad(group, builder, w_limit, h_limit, w_pad, h_pad)
		case Blank():
			return blank_pad(group, builder, w_limit, h_limit, w_pad, h_pad)
		case Lost():
			return lost_pad(group, builder, w_limit, h_limit, w_pad, h_pad)

def vertical_pad(group, builder, w_limit, h_limit, w_pad, h_pad):
	recalculate_padding(group, builder, w_limit, h_limit, w_pad, h_pad, h_alt=group.alt)
	h_q0, h_q1 = quotients(group.h_pad, group.length)
	for i, g in enumerate(group.groups):
		if i+1 < len(group.groups):
			group_pad(g, builder, group.w_full, None, 0, h_q0)
		else:
			group_pad(g, builder, group.w_full, None, 0, h_q1)

def horizontal_pad(group, builder, w_limit, h_limit, w_pad, h_pad):
	recalculate_padding(group, builder, w_limit, h_limit, w_pad, h_pad, w_alt=group.alt)
	w_q0, w_q1 = quotients(group.w_pad, group.length)
	proper_subgroups = [g for g in group.groups if not isinstance(g, (BracketOpen, BracketClose))]
	for i, g in enumerate(proper_subgroups):
		if i+1 < len(proper_subgroups):
			group_pad(g, builder, None, group.h_full, w_q0, 0)
		else:
			group_pad(g, builder, None, group.h_full, w_q1, 0)

def enclosure_pad(group, builder, w_limit, h_limit, w_pad, h_pad):
	recalculate_padding(group, builder, w_limit, h_limit, w_pad, h_pad)
	if group.ver:
		w_limit_sub = round(SCALEDOWN ** (group.sc+1) * builder.em)
	else:
		w_limit_sub = None
	if group.ver:
		h_limit_sub = None
	else:
		h_limit_sub = round(SCALEDOWN ** (group.sc+1) * builder.em)
	for g in group.groups:
		group_pad(g, builder, w_limit_sub, h_limit_sub, 0, 0)

def basic_pad(group, builder, w_limit, h_limit, w_pad, h_pad):
	recalculate_padding(group, builder, w_limit, h_limit, w_pad, h_pad)
	size = builder.em
	for _ in range(group.sc):
		size = math.floor(SCALEDOWN * size)
	group_pad(group.core, builder, group.w_full, group.h_full, 0, 0)
	for _, g in group.insertions.items():
		group_pad(g, builder, None, None, 0, 0)

def overlay_pad(group, builder, w_limit, h_limit, w_pad, h_pad):
	recalculate_padding(group, builder, w_limit, h_limit, w_pad, h_pad)
	group.w1_full = group.w_full
	group.h1_full = group.h_full
	group.w1_pad = max(group.w_full - group.w1, 0)
	group.h1_pad = max(group.h_full - group.h1, 0)
	group.w2_full = group.w_full
	group.h2_full = group.h_full
	group.w2_pad = max(group.w_full - group.w2, 0)
	group.h2_pad = max(group.h_full - group.h2, 0)
	if len(group.lits1) == 1:
		group_pad(group.lits1[0], builder, group.w_full, group.h_full, 0, 0)
	else:
		w1_q0, w1_q1 = quotients(group.w1_pad, len(group.lits1))
		for i, g in enumerate(group.lits1):
			if i+1 < len(group.lits1):
				group_pad(g, builder, None, group.h_full, w1_q0, 0)
			else:
				group_pad(g, builder, None, group.h_full, w1_q1, 0)
	if len(group.lits2) == 1:
		group_pad(group.lits2[0], builder, group.w_full, group.h_full, 0, 0)
	else:
		h2_q0, h2_q1 = quotients(group.h2_pad, len(group.lits2))
		for i, g in enumerate(group.lits2):
			if i+1 < len(group.lits2):
				group_pad(g, builder, group.w_full, None, 0, h2_q0)
			else:
				group_pad(g, builder, group.w_full, None, 0, h2_q1)

def literal_pad(group, builder, w_limit, h_limit, w_pad, h_pad):
	recalculate_padding(group, builder, w_limit, h_limit, w_pad, h_pad)

def singleton_pad(group, builder, w_limit, h_limit, w_pad, h_pad):
	recalculate_padding(group, builder, w_limit, h_limit, w_pad, h_pad)

def blank_pad(group, builder, w_limit, h_limit, w_pad, h_pad):
	recalculate_padding(group, builder, w_limit, h_limit, w_pad, h_pad)

def lost_pad(group, builder, w_limit, h_limit, w_pad, h_pad):
	recalculate_padding(group, builder, w_limit, h_limit, w_pad, h_pad)

def bracket_open_pad(group, builder, height):
	pass

def bracket_close_pad(group, builder, height):
	pass

##### to characters

def to_width(builder, n):
	oc = reversed(list(f'{n:0{builder.len_oct}o}'))
	return [builder.width_(d) for d in oc]

def to_height(builder, n):
	oc = reversed(list(f'{n:0{builder.len_oct}o}'))
	return [builder.height_(d) for d in oc]

def to_width_full(builder, n):
	oc = reversed(list(f'{n:0{builder.len_oct}o}'))
	return [builder.width_full_(d) for d in oc]

def to_height_full(builder, n):
	oc = reversed(list(f'{n:0{builder.len_oct}o}'))
	return [builder.height_full_(d) for d in oc]

def to_width_full_scaled(builder, n):
	oc = reversed(list(f'{n:0{builder.len_oct}o}'))
	return [builder.width_full_scaled_(d) for d in oc]

def to_height_full_scaled(builder, n):
	oc = reversed(list(f'{n:0{builder.len_oct}o}'))
	return [builder.height_full_scaled_(d) for d in oc]

def full_dimensions(builder, group):
	return to_insert_x(builder, group.insert_x, group.parent_sc) + \
			to_insert_y(builder, group.insert_y, group.parent_sc) + \
			([builder.anchor_end_insert] if group.insert_x is not None else []) + \
			[builder.scale_group_active_(group.sc)] + \
			to_width(builder, group.w) + to_height(builder, group.h) + \
			to_width_full(builder, group.w_full) + to_height_full(builder, group.h_full)

def full_dimensions_overlay(builder, sc, w, h, w_full, h_full):
	return [builder.scale_group_active_(sc)] + \
			to_width(builder, w) + to_height(builder, h) + \
			to_width_full(builder, w_full) + to_height_full(builder, h_full)

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
			full_dimensions(builder, group) + \
			[builder.record] + alt_chars + inner + \
			[builder.depth_(level)] + \
			[builder.close_('v')]

def horizontal_tree(group, builder, level):
	alt_chars = [builder.sym[group.alt.ch]] if group.alt else []
	inner = [ch for g in group.groups for ch in group_tree(g, builder, level+1)]
	return [builder.open_('h')] + \
			direction_strings(group, builder, level) + \
			[builder.length_(group.length), builder.depth_(level)] + \
			full_dimensions(builder, group) + \
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
			full_dimensions(builder, group) + \
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
			full_dimensions(builder, group) + \
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
			full_dimensions_overlay(builder, group.sc1, group.w1, group.h1, group.w1_full, group.h1_full) + \
			[builder.record] + \
			[ch for g in group.lits1 for ch in group_tree(g, builder, level+2)] + \
			[builder.depth_(level+1), builder.close_('h')]
	else:
		hor = group_tree(group.lits1[0], builder, level+1)
	if len(group.lits2) > 1:
		capped_len = min(len(group.lits2), MAX_COUNT)
		ver = [builder.open_('v')] + \
			[builder.length_(capped_len), builder.flat, builder.depth_(level+1)] + \
			full_dimensions_overlay(builder, group.sc2, group.w2, group.h2, group.w2_full, group.h2_full) + \
			[builder.record] + \
			[ch for g in group.lits2 for ch in group_tree(g, builder, level+2)] + \
			[builder.depth_(level+1), builder.close_('v')]
	else:
		ver = group_tree(group.lits2[0], builder, level+1)
	return [builder.open_('o')] + \
			direction_strings(group, builder, level) + \
			[builder.depth_(level)] + \
			full_dimensions(builder, group) + \
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
			full_dimensions(builder, group) + \
			[builder.record, name] + mir + dam + \
			[builder.depth_(level), builder.close_('b')]

def singleton_tree(group, builder, level):
	dam = [builder.damaged[group.damage-1]] if group.damage else []
	return [builder.open_('b')] + \
			direction_strings(group, builder, level) + \
			[builder.depth_(level)] + \
			full_dimensions(builder, group) + \
			[builder.record, group.name] + dam + \
			[builder.depth_(level), builder.close_('b')]

def blank_tree(group, builder, level):
	return [builder.open_('b')] + \
			direction_strings(group, builder, level) + \
			[builder.depth_(level)] + \
			full_dimensions(builder, group) + \
			[builder.record, group.name, builder.depth_(level)] + \
			[builder.close_('b')]

def lost_tree(group, builder, level):
	return [builder.open_('b')] + \
			direction_strings(group, builder, level) + \
			[builder.depth_(level)] + \
			full_dimensions(builder, group) + \
			[builder.record, group.name, builder.depth_(level)] + \
			[builder.close_('b')]

def bracket_open_tree(group, builder, level):
	return [builder.sym[group.ch]]

def bracket_close_tree(group, builder, level):
	return [builder.sym[group.ch]]
