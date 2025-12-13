from collections import Counter
from itertools import groupby

from .unistructure import Fragment, Vertical, Horizontal, Enclosure, Basic, \
	Overlay, Literal, Singleton, Blank, Lost, BracketOpen, BracketClose, \
	is_group
from .resstructure import VerGroup, VerSubgroup, HorGroup, HorSubgroup, \
	Namedglyph, Emptyglyph, Box, Stack, Insert, Modify
from .uniconstants import *
from .uninames import name_to_char, name_to_char_cap, mnemonic_to_name
from .uniprops import InsertionAdjust
from .uninormalize import make_vertical, make_horizontal

class ResUniConverter:
	def __init__(self):
		self.errors = []

	def report(self, message):
		self.errors.append(message)

	def convert_fragment(self, fragment):
		if fragment.hiero is None:
			return Fragment([])
		else:
			return Fragment(self.convert_groups(fragment.hiero.groups, True))

	def convert_fragment_by_predominant_color(self, fragment):
		return [(Fragment(self.convert_groups(groups, True)), color) for
				(groups, color) in self.partition_by_predominant_color(fragment)]

	def convert_groups(self, groups, outer):
		converteds = []
		for g in groups:
			converted = self.convert_group(g)
			if converted is not None:
				if is_group(converted, outer=outer):
					converteds.append(converted)
				else:
					self.report('Ignored top group ' + str(g))
		return converteds

	def convert_group(self, group):
		match group:
			case VerGroup():
				return self.convert_ver_group(group)
			case VerSubgroup():
				return self.convert_group(group.group)
			case HorGroup():
				return self.convert_hor_group(group)
			case HorSubgroup():
				return self.convert_group(group.group)
			case Namedglyph():
				return self.convert_namedglyph(group)
			case Emptyglyph():
				return self.convert_emptyglyph(group)
			case Box():
				return self.convert_box(group)
			case Stack():
				return self.convert_stack(group)
			case Insert():
				return self.convert_insert(group)
			case Modify():
				return self.convert_modify(group)

	def convert_ver_group(self, group):
		groups = []
		for g in group.groups:
			converted = self.convert_group(g)
			if converted is not None:
				groups.append(converted)
		if len(groups) == 0:
			return None
		elif len(groups) == 1:
			return groups[0]
		subgroups = []
		for g in groups:
			if is_group(g):
				subgroups.append(g)
			else:
				self.report('Ignored subgroup in ' + str(group))
		return make_vertical(subgroups)

	def convert_hor_group(self, group):
		groups = []
		for g in group.groups:
			converted = self.convert_group(g)
			if converted is not None:
				groups.append(converted)
		if len(groups) == 0:
			return None
		elif len(groups) == 1:
			return groups[0]
		subgroups = []
		for g in groups:
			if is_group(g, hor=True):
				subgroups.append(g)
			else:
				self.report('Ignored subgroup in ' + str(group))
		i = len(subgroups) - 1
		while i >= 0:
			if isinstance(subgroups[i], BracketOpen):
				if i == len(subgroups)-1 or isinstance(subgroups[i+1], BracketOpen):
					self.report('Excess bracket open in ' + str(group))
					subgroups.pop(i)
			elif isinstance(subgroups[i], BracketClose):
				if i == 0 or isinstance(subgroups[i-1], BracketClose):
					self.report('Excess bracket close in ' + str(group))
					subgroups.pop(i)
			i = i-1
		return make_horizontal(subgroups)

	def convert_namedglyph(self, group):
		if len(group.notes) > 0:
			self.report('Cannot convert notes in ' + str(group))
		name = group.name
		vs = namedglyph_to_vs(group)
		mir = group.mirrored()
		sh = shading_res_to_uni(group)
		if name == 'open':
			name = 'V11a'
		elif name == 'close':
			name = 'V11b'
		elif mnemonic_to_name(name):
			name = mnemonic_to_name(name)
		elif name[0] == '"':
			if vs:
				self.report('Cannot rotate ' + str(group))
			if mir:
				self.report('Cannot mirror ' + str(group))
			if sh:
				self.report('Cannot shade ' + str(group))
			match name[1]:
				case '[' | '(' | '{': return BracketOpen(name[1])
				case '<': return BracketOpen('\u2329')
				case ']' | ')' | '}': return BracketClose(name[1])
				case '>': return BracketClose('\u232A')
				case _:
					self.report('Cannot convert short string ' + str(group))
					return Literal(PLACEHOLDER, 0, False, 0)
		if name_to_char(name):
			return Literal(name_to_char(name), vs, mir, sh)
		elif name_to_char_cap(name):
			if vs:
				self.report('Cannot rotate singleton in ' + str(group))
			if mir:
				self.report('Cannot mirror singleton in ' + str(group))
			return Singleton(name_to_char_cap(name), sh)
		else:
			self.report('Cannot convert named glyph ' + str(group))
			return Literal(PLACEHOLDER, vs, mir, sh)

	def convert_emptyglyph(self, group):
		if group.note is not None:
			self.report('Cannot convert note in ' + str(group))
		if group.width == 0 or group.height == 0:
			return None
		sh = shading_res_to_uni(group)
		if sh:
			width = 0.5 if group.width <= 0.5 else 1
			height = 0.5 if group.height <= 0.5 else 1
			return Lost(width, height, True)
		else:
			size = 0.5 if group.width <= 0.5 and group.height <= 0.5 else 1
			return Blank(size)

	def convert_box(self, group):
		groups = [] if group.hiero is None else self.convert_groups(group.hiero.groups, False)
		if len(group.notes) > 0:
			self.report('Cannot convert notes in ' + str(group))
		typ = 'plain'
		delim_open = '\U00013379'
		delim_close = '\U0001337A'
		match group.name:
			case 'cartouche':
				if group.mirrored():
					delim_open = '\U0001342F'
					delim_close = '\U0001337B'
			case 'oval':
				delim_close = '\U0001337B'
			case 'serekh':
				if group.mirrored():
					self.report('Cannot mirror ' + str(group))
				delim_open = '\U00013258'
				delim_close = '\U00013282'
			case 'inb':
				typ = 'walled'
				delim_open = '\U00013288'
				delim_close = '\U00013289'
			case 'rectangle':
				delim_open = '\U00013258'
				delim_close = '\U0001325D'
			case 'Hwtopenover':
				if group.mirrored():
					delim_open = '\U00013258'
					delim_close = '\U0001325B'
				else:
					delim_open = '\U0001325A'
					delim_close = '\U0001325D'
			case 'Hwtopenunder':
				if group.mirrored():
					delim_open = '\U00013258'
					delim_close = '\U0001325C'
				else:
					delim_open = '\U00013259'
					delim_close = '\U0001325D'
			case 'Hwtcloseover':
				if group.mirrored():
					delim_open = '\U0001325A'
					delim_close = '\U0001325D'
				else:
					delim_open = '\U00013258'
					delim_close = '\U0001325B'
			case 'Hwtcloseunder':
				if group.mirrored():
					delim_open = '\U00013259'
					delim_close = '\U0001325D'
				else:
					delim_open = '\U00013258'
					delim_close = '\U0001325C'
		ts, bs, te, be = res_group_shading_to_corners(group)
		shade_open = corners_to_uni_shade(ts, bs, ts, bs)
		shade_close = corners_to_uni_shade(te, be, te, be)
		return Enclosure(typ, groups, delim_open, shade_open, delim_close, shade_close)

	def convert_stack(self, group):
		group1 = self.convert_group(group.group1)
		group2 = self.convert_group(group.group2)
		if group1 is None:
			return group2
		elif group2 is None:
			return group1
		elif is_flat_horizontal(group1) and is_flat_vertical(group2):
			lits1 = [group1] if isinstance(group1, Literal) else group1.groups
			lits2 = [group2] if isinstance(group2, Literal) else group2.groups
			return Overlay(lits1, lits2)
		elif is_flat_vertical(group1) and is_flat_horizontal(group2):
			lits2 = [group1] if isinstance(group1, Literal) else group1.groups
			lits1 = [group2] if isinstance(group2, Literal) else group2.groups
			return Overlay(lits1, lits2)
		else:
			self.report('Cannot convert ' + str(group))
			return None

	def convert_insert(self, group):
		group1 = self.convert_group(group.group1)
		group2 = self.convert_group(group.group2)
		if group1 is None:
			return group2
		elif group2 is None:
			return group1
		elif not is_group(group2):
			self.report('Cannot convert inserted group in ' + str(group))
			return group1
		places = allowed_insertions(group1)
		x, y = group.position()
		place = closest_insertion_place(x, y, places, group1)
		if place is None:
			self.report('Cannot convert inserted group in ' + str(group))
			return group1
		elif isinstance(group1, (Literal, Overlay)):
			insertions = {place: group2}
			return Basic(group1, insertions)
		else:
			group1.insertions[place] = group2
			return group1

	def convert_modify(self, group):
		ts, bs, te, be = res_group_shading_to_corners(group)
		if ts or bs or te or be:
			self.report('Cannot convert shading in ' + str(group))
		return self.convert_group(group.group)

	def partition_by_predominant_color(self, fragment):
		if fragment.hiero is None:
			return []
		colored_groups = [(g, self.predominant_color(g)) for g in fragment.hiero.groups]
		colored_chunks = [list(pairs) for _, pairs in groupby(colored_groups, key=lambda x: x[1])]
		return [([group for group,_ in pairs], pairs[0][1]) for pairs in colored_chunks]
		
	def predominant_color(self, group):
		freqs = self.color_to_freq_group(group)
		if freqs:
			if len(freqs) > 1:
				self.report('Multiple colors in ' + str(group))
			epsilon = 1e-6
			freqs += Counter({'black': epsilon}) # favour black in case of tie breaking
			return freqs.most_common(1)[0][0]
		else:
			return 'black'

	def color_to_freq_hiero(self, hiero):
		return sum([self.color_to_freq_group(g) for g in hiero.groups], Counter())

	def color_to_freq_group(self, group):
		match group:
			case VerGroup():
				return self.color_to_freq_ver_group(group)
			case VerSubgroup():
				return self.color_to_freq_group(group.group)
			case HorGroup():
				return self.color_to_freq_hor_group(group)
			case HorSubgroup():
				return self.color_to_freq_group(group.group)
			case Namedglyph():
				return self.color_to_freq_namedglyph(group)
			case Emptyglyph():
				return self.color_to_freq_emptyglyph(group)
			case Box():
				return self.color_to_freq_box(group)
			case Stack():
				return self.color_to_freq_stack(group)
			case Insert():
				return self.color_to_freq_insert(group)
			case Modify():
				return self.color_to_freq_modify(group)

	def color_to_freq_ver_group(self, group):
		return sum([self.color_to_freq_group(g) for g in group.groups], Counter())
		
	def color_to_freq_hor_group(self, group):
		return sum([self.color_to_freq_group(g) for g in group.groups], Counter())

	def color_to_freq_namedglyph(self, group):
		return Counter([group.colored()])

	def color_to_freq_emptyglyph(self, group):
		return Counter()

	def color_to_freq_box(self, group):
		return Counter([group.colored()]) + \
			(0 if group.hiero is None else self.color_to_freq_hiero(group.hiero))

	def color_to_freq_stack(self, group):
		return self.color_to_freq_group(group.group1) + self.color_to_freq_group(group.group2)

	def color_to_freq_insert(self, group):
		return self.color_to_freq_group(group.group1) + self.color_to_freq_group(group.group2)

	def color_to_freq_modify(self, group):
		return self.color_to_freq_group(group.group)

def is_flat_horizontal(group):
	return isinstance(group, Literal) or \
			isinstance(group, Horizontal) and all(isinstance(g, Literal) for g in group.groups)

def is_flat_vertical(group):
	return isinstance(group, Literal) or \
			isinstance(group, Vertical) and all(isinstance(g, Literal) for g in group.groups)

def namedglyph_to_vs(glyph):
	rounded = round(glyph.rotate % 360 / 45) * 45
	return rotate_to_num(360 - rounded) if glyph.mirrored() else rotate_to_num(rounded)

def shading_res_to_uni(group):
	ts, bs, te, be = res_group_shading_to_corners(group)
	return corners_to_uni_shade(ts, bs, te, be)

def res_group_shading_to_corners(group):
	ts = False
	bs = False
	te = False
	be = False
	if group.shade is not None or len(group.shades) > 0:
		if group.shade == True:
			ts = True
			bs = True
			te = True
			be = True
		else:
			for patt in group.shades:
				x_low, x_high, y_low, y_high = res_pattern_to_square(patt)
				if x_low < 0.5 and y_low < 0.5:
					ts = True
				if x_low < 0.5 and y_high > 0.5:
					bs = True
				if x_high > 0.5 and y_low < 0.5:
					te = True
				if x_high > 0.5 and y_high > 0.5:
					be = True
	elif group.globs.shade:
		ts = True
		bs = True
		te = True
		be = True
	return ts, bs, te, be

def res_pattern_to_square(patt):
	x_low = 0
	x_high = 1
	y_low = 0
	y_high = 1
	for ch in patt:
		match ch:
			case 's':
				x_high = x_low + (x_high - x_low) / 2
			case 'e':
				x_low = x_low + (x_high - x_low) / 2
			case 't':
				y_high = y_low + (y_high - y_low) / 2
			case 'b':
				y_low = y_low + (y_high - y_low) / 2
	return x_low, x_high, y_low, y_high

def corners_to_uni_shade(ts, bs, te, be):
	return (1 if ts else 0) | (2 if bs else 0) | (4 if te else 0) | (8 if be else 0)

def allowed_insertions(group):
	if isinstance(group, Literal):
		places = group.allowed_places()
		return places if len(places) > 0 else INSERTION_PLACES
	elif isinstance(group, Overlay):
		places = group.allowed_places()
		return places if len(places) > 0 else OVERLAY_INSERTION_PLACES
	elif isinstance(group, Basic):
		return [place for place in allowed_insertions(group.core) if place not in group.insertions]
	else:
		return []

def closest_insertion_place(x0, y0, places, group):
	best_place = None
	best_dist = float('inf')
	core = group.core if isinstance(group, Basic) else group
	for place in places:
		x1, y1 = insertion_position(place, InsertionAdjust())
		dist = (x0-x1)*(x0-x1) + (y0-y1)*(y0-y1)
		if dist < best_dist:
			best_place = place
			best_dist = dist
	return best_place
