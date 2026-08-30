# coding: utf-8
# vim: set syntax=python 
import unittest
import re

from hieropy import UniParser
from hieropy.uniconstants import *
from hieropy.unistructure import *
from hieropy.unirandom import UniGenerator
from hieropy.uniomnifont import UniOmniFontBuilder

from tests.fontemulation import FontEmulator
from tests.omniaux import make_page, first_difference

DIR = 'tests/tmp/'
FONTFILE = 'omnifont'

class TestOmni(unittest.TestCase):

	@classmethod
	def setUpClass(cls):
		cls.builder = UniOmniFontBuilder(debug=True, maxdepth=5)
		cls.builder.make_font_initial()
		cls.builder.syntax_analysis()
		cls.builder.make_font_final(f'{DIR}/{FONTFILE}.ttf')
		cls.fontname = cls.builder.fontname
		cls.info = cls.builder.builder.all_text()
		cls.features = cls.builder.builder.features()
		cls.emulator = FontEmulator(f'{DIR}/{FONTFILE}.ttf')
		cls.parser = UniParser()

	def various_encodings(self):
		with open('tests/resources/omni.txt', 'r') as f:
			return f.readlines()

	def no_test_single(self):
		encodings = self.various_encodings()
		make_page(FONTFILE, f'{DIR}/omnitest1.html', self.fontname, encodings, 'hlr', self.info)

	def no_test_encodings(self):
		encodings = self.various_encodings()
		for encoding in encodings:
			self.compare(encoding)

	def test_generation(self):
		generator = UniGenerator(depth_limit=7, chars=[chr(0x13000), chr(0x13001), chr(0x13002)])
		# generator = UniGenerator(depth_limit=3, chars=[chr(0x13000), chr(0x13001), chr(0x13002)])
		fragments = [generator.generate_fragment() for _ in range(100000)]
		for fragment in fragments:
			self.compare(str(fragment))

	def compare(self, encoding):
		fragment = self.parser.parse(encoding)
		encoding = str(fragment)
		names_tree = fragment_tree(fragment, self.builder)
		raw_names, _ = self.emulator.run(encoding, 'hlr')
		names_emulator = [re.sub(r'_base$', '', s) for s in raw_names]
		i = first_difference(names_tree, names_emulator)
		if i is not None:
			print(fragment)
			print(names_tree[i])
			print(names_emulator[i])
			print(names_tree)
			print(names_emulator)
			with open(f'{DIR}/omni.txt', 'a', encoding='utf-8') as f:
				f.write(str(fragment) + '\n')

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
	inner = [ch for g in group.groups for ch in group_tree(g, builder, level+1)]
	return [builder.open_('v'), builder.depth_(level), builder.record] + inner + \
			[builder.depth_(level), builder.close_('v')]

def horizontal_tree(group, builder, level):
	inner = [ch for g in group.groups for ch in group_tree(g, builder, level+1)]
	return [builder.open_('h'), builder.depth_(level), builder.record] + inner + \
			[builder.depth_(level), builder.close_('h')]

def enclosure_tree(group, builder, level):
	open_chars = []
	if group.delim_open:
		open_chars.append(builder.sym[group.delim_open])
		if group.damage_open:
			open_chars.append(builder.damaged[group.damage_open-1])
	close_chars = []
	if group.delim_close:
		close_chars.append(builder.sym[group.delim_close])
		if group.damage_close:
			close_chars.append(builder.damaged[group.damage_close-1])
	inner = [ch for g in group.groups for ch in group_tree(g, builder, level+1)]
	letter = 'w' if group.typ == 'walled' else 'p'
	return [builder.open_(letter), builder.depth_(level), builder.record] + open_chars + inner + close_chars + \
			[builder.depth_(level), builder.close_(letter)]

def basic_tree(group, builder, level):
	insertions = []
	for place, g in group.insertions.items():
		place_ch = builder.sym[INSERTION_CHARS[INSERTION_PLACES.index(place)]]
		insertions.append(place_ch)
		insertions += group_tree(g, builder, level+1)
	return [builder.open_('i'), builder.depth_(level), builder.record] + \
			group_tree(group.core, builder, level+1) + insertions + \
			[builder.depth_(level), builder.close_('i')]

def overlay_tree(group, builder, level):
	if len(group.lits1) > 1:
		hor = [builder.open_('h'), builder.depth_(level+1), builder.record] + \
			[ch for g in group.lits1 for ch in group_tree(g, builder, level+2)] + \
			[builder.depth_(level+1), builder.close_('h')]
	else:
		hor = group_tree(group.lits1[0], builder, level+1)
	if len(group.lits2) > 1:
		ver = [builder.open_('v'), builder.depth_(level+1), builder.record] + \
			[ch for g in group.lits2 for ch in group_tree(g, builder, level+2)] + \
			[builder.depth_(level+1), builder.close_('v')]
	else:
		ver = group_tree(group.lits2[0], builder, level+1)
	return [builder.open_('o'), builder.depth_(level), builder.record] + hor + ver + \
			[builder.depth_(level), builder.close_('o')]

def literal_tree(group, builder, level):
	name = builder.sym[group.ch]
	if group.vs:
		name = builder.name_rotate_to_name[(name, num_to_rotate(group.vs))]
	mir = [builder.mirror] if group.mirror else []
	dam = [builder.damaged[group.damage-1]] if group.damage else []
	return [builder.open_('b'), builder.depth_(level), builder.record, name] + mir + dam + \
			[builder.depth_(level), builder.close_('b')]

def singleton_tree(group, builder, level):
	name = builder.sym[group.ch]
	dam = [builder.damaged[group.damage-1]] if group.damage else []
	return [builder.open_('b'), builder.depth_(level), builder.record, name] + dam + \
			[builder.depth_(level), builder.close_('b')]

def blank_tree(group, builder, level):
	name = builder.full_blank if group.dim == 1 else builder.half_blank
	return [builder.open_('b'), builder.depth_(level), builder.record, name, builder.depth_(level), builder.close_('b')]

def lost_tree(group, builder, level):
	if group.width == 0.5 and group.height == 0.5:
		ch = builder.half_lost_exp if group.expand else builder.half_lost
	elif group.width == 0.5 and group.height == 1:
		ch = builder.tall_lost_exp if group.expand else builder.tall_lost
	elif group.width == 1 and group.height == 0.5:
		ch = builder.wide_lost_exp if group.expand else builder.wide_lost
	else:
		ch = builder.full_lost_exp if group.expand else builder.full_lost
	return [builder.open_('b'), builder.depth_(level), builder.record, ch, builder.depth_(level), builder.close_('b')]

def bracket_open_tree(group, builder, level):
	return [builder.sym[group.ch]]

def bracket_close_tree(group, builder, level):
	return [builder.sym[group.ch]]

