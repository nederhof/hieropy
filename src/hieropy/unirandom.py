import random

from .uniconstants import OPEN_BRACKETS, CLOSE_BRACKETS, INSERTION_PLACES, OVERLAY_INSERTION_PLACES, \
	OPENING_PLAIN_CHARS, OPENING_WALLED_CHARS, CLOSING_PLAIN_CHARS, CLOSING_WALLED_CHARS
from .uninames import basic_chars
from .uniconstants import rotate_to_num
from .uniproperties import allowed_rotations
from .unistructure import Fragment, Vertical, Horizontal, Enclosure, Basic, \
    Overlay, Literal, Singleton, Blank, Lost, BracketOpen, BracketClose

class UniGenerator:
	def __init__(self, depth_limit=None, chars=None):
		self.depth_limit = depth_limit
		self.chars = chars or basic_chars()
		self.weights = { \
			'fragment': [0, 1, 0.1, 0.1, 0.1],
			'top_group': [1, 0.05],
			'group': [0.5, 0.5, 1],
			'ver_group': [1, 0.5, 0.1, 0.1, 0.05],
			'ver_subgroup': [1, 0.05],
			'hor_group': [0.2, 0.2, 1, 0.5, 0.1, 0.1],
			'hor_group_bracket_open': [0.2, 1],
			'hor_group_bracket_close': [0.2, 1],
			'hor_subgroup': [0.2, 1],
			'open_bracket': 5 * [1],
			'close_bracket': 5 * [1],
			'basic_group': [1, 1, 1, 0.1],
			'insertion_literal': [1, 0.5, 0.25, 0.1, 0.05, 0.04, 0.03],
			'insertion_overlay': [1, 0.5, 0.25, 0.1],
			'in_group': [0.5, 0.5, 0.5, 1, 1, 0.5],
			'core_group': [0.1, 1],
			'flat_hor_group': [1, 0.2, 0.1, 0.1],
			'flat_ver_group': [1, 0.2, 0.1, 0.1],
			'literal_rotation': [1, 0.05],
			'literal_mirror': [1, 0.1],
			'placeholder': 6 * [1],
			'placeholder_expand': [1, 1],
			'enclosure_type': [1, 1],
			'enclosure_groups': [1, 1, 1, 0.1, 0.1, 0.1, 0.1, 0.1],
			'enclosure_opening': [1, 0.1],
			'enclosure_closing': [1, 0.1],
			'singleton': [1, 1, 1, 1],
			'plain_opening_delimiter': 5 * [1],
			'plain_closing_delimiter': 6 * [1],
			'walled_opening_delimiter': 2 * [1],
			'walled_closing_delimiter': 2 * [1],
			'damaged': [1] + 15 * [0.1],
		}
	
	def pick_index(self, element):
		weights = self.weights[element]
		return random.choices(range(len(weights)), weights=weights, k=1)[0]

	def generate_fragment(self, depth=0):
		i = self.pick_index('fragment')
		groups = []
		for _ in range(i):
			group = self.generate_top_group(depth+1)
			if len(groups) > 0: 
				prev = groups[-1]
				if isinstance(prev, Enclosure) and prev.delim_close is None and isinstance(group, Singleton) or \
						isinstance(prev, Singleton) and isinstance(group, Enclosure) and group.delim_open is None:
					continue
			groups.append(group)
		return Fragment(groups)

	def generate_top_group(self, depth=0):
		i = self.pick_index('top_group')
		match i:
			case 0:
				return self.generate_group(depth+1)
			case _:
				return self.generate_singleton()

	def generate_group(self, depth=0):
		if depth > self.depth_limit:
			i = 2
		else:
			i = self.pick_index('group')
		match i:
			case 0:
				return self.generate_ver_group(depth+1)
			case 1:
				return self.generate_hor_group(depth+1)
			case _:
				return self.generate_basic_group(depth+1)

	def generate_ver_group(self, depth=0):
		i = self.pick_index('ver_group')
		groups = []
		for _ in range(i+2):
			groups.append(self.generate_ver_subgroup(depth+1))
		return Vertical(groups)

	def generate_ver_subgroup(self, depth=0):
		if depth > self.depth_limit:
			i = 1
		else:
			i = self.pick_index('ver_subgroup')
		match i:
			case 0:
				return self.generate_hor_group(depth+1)
			case _:
				return self.generate_basic_group(depth+1)
		
	def generate_hor_group(self, depth=0):
		i = self.pick_index('hor_group')
		groups = []
		match i:
			case 0:
				groups.append(self.generate_open_bracket())
				groups.append(self.generate_hor_subgroup(depth+1))
			case 1:
				groups.append(self.generate_hor_subgroup(depth+1))
				groups.append(self.generate_close_bracket())
			case _:
				for _ in range(i):
					i_open = self.pick_index('hor_group_bracket_open')
					i_close = self.pick_index('hor_group_bracket_close')
					if i_open == 0:
						groups.append(self.generate_open_bracket())
					groups.append(self.generate_hor_subgroup(depth+1))
					if i_close == 0:
						groups.append(self.generate_close_bracket())
		return Horizontal(groups)

	def generate_hor_subgroup(self, depth=0):
		if depth > self.depth_limit:
			i = 1
		else:
			i = self.pick_index('hor_subgroup')
		match i:
			case 0:
				return self.generate_ver_group(depth+1)
			case _:
				return self.generate_basic_group(depth+1)
		
	def generate_open_bracket(self):
		i = self.pick_index('open_bracket')
		return BracketOpen(OPEN_BRACKETS[i])

	def generate_close_bracket(self):
		i = self.pick_index('close_bracket')
		return BracketClose(CLOSE_BRACKETS[i])
		
	def generate_basic_group(self, depth=0):
		if depth > self.depth_limit:
			i = 0
		else:
			i = self.pick_index('basic_group')
		match i:
			case 0:
				return self.generate_core_group(depth+1)
			case 1:
				return self.generate_insert_group(depth+1)
			case 2:
				return self.generate_placeholder()
			case _:
				return self.generate_enclosure(depth+1)
		
	def generate_insert_group(self, depth=0):
		core = self.generate_core_group(depth+1)
		if isinstance(core, Overlay):
			i = self.pick_index('insertion_overlay') + 1
			places = sorted(random.sample(range(len(OVERLAY_INSERTION_PLACES)), i))
		else:
			i = self.pick_index('insertion_literal') + 1
			places = sorted(random.sample(range(len(INSERTION_PLACES)), i))
		insertions = {}
		for place in places:
			insertions[INSERTION_PLACES[place]] = self.generate_in_group(depth+1)
		return Basic(core, insertions)

	def generate_in_group(self, depth=0):
		if depth > self.depth_limit:
			i = 3
		else:
			i = self.pick_index('in_group')
		match i:
			case 0:
				return self.generate_ver_group(depth+1)
			case 1:
				return self.generate_hor_group(depth+1)
			case 2:
				return self.generate_insert_group(depth+1)
			case 3:
				return self.generate_core_group(depth+1)
			case 4:
				return self.generate_placeholder()
			case _:
				return self.generate_enclosure(depth+1)

	def generate_core_group(self, depth=0):
		if depth > self.depth_limit:
			i = 1
		else:
			i = self.pick_index('core_group')
		match i:
			case 0:
				return Overlay(self.generate_flat_hor_group(depth+1), self.generate_flat_ver_group(depth+1))
			case _:
				return self.generate_literal()
		
	def generate_flat_hor_group(self, depth=0):
		if depth > self.depth_limit:
			i = 0
		else:
			i = self.pick_index('flat_hor_group')
		lits = []
		for _ in range(i+1):
			lits.append(self.generate_literal())
		return lits
			
	def generate_flat_ver_group(self, depth=0):
		if depth > self.depth_limit:
			i = 0
		else:
			i = self.pick_index('flat_ver_group')
		lits = []
		for _ in range(i+1):
			lits.append(self.generate_literal())
		return lits
		
	def generate_literal(self):
		ch = self.generate_sign()
		rots = allowed_rotations(ch)
		if len(rots) > 0 and self.pick_index('literal_rotation'):
			vs = rotate_to_num(random.choice(rots))
		else:
			vs = 0
		mirror = self.pick_index('literal_mirror') == 1
		damage = self.generate_damaged()
		return Literal(ch, vs, mirror, damage)
		
	def generate_sign(self):
		return random.choice(self.chars)

	def generate_placeholder(self):
		i = self.pick_index('placeholder')
		i_exp = self.pick_index('placeholder_expand')
		match i:
			case 0:
				return Blank(1)
			case 1:
				return Blank(0.5)
			case 2:
				return Lost(0.5, 0.5, i_exp == 0)
			case 3:
				return Lost(1, 0.5, i_exp == 0)
			case 4:
				return Lost(0.5, 1, i_exp == 0)
			case _:
				return Lost(1, 1, i_exp == 0)

	def generate_enclosure(self, depth=0):
		i_type = self.pick_index('enclosure_type')
		i_groups = self.pick_index('enclosure_groups')
		i_opening = self.pick_index('enclosure_opening')
		i_closing = self.pick_index('enclosure_closing')
		typ = 'plain' if i_type == 0 else 'walled'
		groups = []
		for _ in range(i_groups):
			groups.append(self.generate_group(depth+1))
		if i_opening == 0:
			if typ == 'plain':
				delim_open, damage_open = self.generate_plain_opening()
			else:
				delim_open, damage_open = self.generate_walled_opening()
		else:
			delim_open, damage_open = None, 0
		if i_closing == 0:
			if typ == 'plain':
				delim_close, damage_close = self.generate_plain_closing()
			else:
				delim_close, damage_close = self.generate_walled_closing()
		else:
			delim_close, damage_close = None, 0
		return Enclosure(typ, groups, delim_open, damage_open, delim_close, damage_close)

	def generate_singleton(self):
		i = self.pick_index('singleton')
		match i:
			case 0:
				ch, damage = self.generate_plain_opening()
			case 1:
				ch, damage = self.generate_plain_closing()
			case 2:
				ch, damage = self.generate_walled_opening()
			case _:
				ch, damage = self.generate_walled_closing()
		return Singleton(ch, damage)

	def generate_plain_opening(self):
		return self.generate_plain_opening_delimiter(), self.generate_damaged()

	def generate_plain_closing(self):
		return self.generate_plain_closing_delimiter(), self.generate_damaged()

	def generate_walled_opening(self):
		return self.generate_walled_opening_delimiter(), self.generate_damaged()

	def generate_walled_closing(self):
		return self.generate_walled_closing_delimiter(), self.generate_damaged()

	def generate_plain_opening_delimiter(self):
		i = self.pick_index('plain_opening_delimiter')
		return OPENING_PLAIN_CHARS[i]

	def generate_plain_closing_delimiter(self):
		i = self.pick_index('plain_closing_delimiter')
		return CLOSING_PLAIN_CHARS[i]

	def generate_walled_opening_delimiter(self):
		i = self.pick_index('walled_opening_delimiter')
		return OPENING_WALLED_CHARS[i]

	def generate_walled_closing_delimiter(self):
		i = self.pick_index('walled_closing_delimiter')
		return CLOSING_WALLED_CHARS[i]

	def generate_damaged(self):
		return self.pick_index('damaged')
