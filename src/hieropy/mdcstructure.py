from collections import Counter
from itertools import groupby

from .uniconstants import corners_to_num, rotate_to_num
from .unitransform import start_corners, end_corners

class Line:
	def __init__(self, items):
		self.parts = []
		groups = []
		text = ''
		def flush_fragment():
			nonlocal groups
			if len(groups) > 0:
				self.parts.append(Fragment(groups))
				groups = []
		def flush_text():
			nonlocal text
			if text != '':
				self.parts.append(Text(text))
				text = ''
		for item in items:
			if item:
				match item:
					case Break():
						flush_fragment()
					case Text():
						flush_fragment()
						text += item.text if text == '' else '\n' + item.text
					case LineNumber():
						flush_fragment()
						flush_text()
						self.parts.append(item)
					case Toggle():
						if not item.is_empty():
							flush_text()
							groups.append(item)
					case Quadrat():
						flush_text()
						groups.append(item)
		flush_text()
		flush_fragment()
		self.propagate_toggles()

	def propagate_toggles(self):
		state = State()
		pruned = []
		for part in self.parts:
			if isinstance(part, Fragment):
				state = part.propagate_toggles(state)
				if len(part.groups) > 0:
					pruned.append(part)
			else:
				pruned.append(part)
		self.parts = pruned

class Fragment:
	def __init__(self, groups):
		self.groups = groups

	def propagate_toggles(self, state):
		pruned = []
		for group in self.groups:
			state = group.propagate_toggles(state)
			if not isinstance(group, Toggle):
				pruned.append(group)
		self.groups = pruned
		return state

	def color_freq(self):
		return sum([g.color_freq() for g in self.groups], Counter())

	def colors(self):
		return sum([g.color_freq() for g in self.groups], Counter()).keys()

	def cut_by_color(self):
		if len(self.groups) == 0:
			return []
		else:
			colored_groups = [(g, g.predominant_color()) for g in self.groups]
			colored_chunks = [list(pairs) for _, pairs in groupby(colored_groups, key=lambda x: x[1])]
			return [Fragment([group for group,_ in pairs]) for pairs in colored_chunks]

class Part:
	def __init__(self):
		pass

	def chained_leaf(self):
		return None

	def propagate_toggles(self, state):
		self.state = state
		return state

	def shading_corners(self):
		if isinstance(self, Hieroglyph) and 'shade' in self.modifiers:
			corners = self.modifiers['shade']
		else:
			corners = empty_corners()
		return complete_corners(corners, self.state.shade)

	def shading_num(self):
		return corners_to_num(self.shading_corners())

	def color_freq(self):
		return Counter()

	def predominant_color(self):
		freqs = self.color_freq() + Counter({'black': 1e-6})
		return freqs.most_common(1)[0][0]

class Break(Part):
	def __init__(self, text):
		self.text = text

class Text(Part):
	def __init__(self, text):
		self.text = text

	def __str__(self):
		return self.text

class LineNumber(Part):
	def __init__(self, text):
		self.text = text

	def __str__(self):
		return self.text

class Quadrat(Part):
	def __init__(self, group, shading):
		self.group = group
		self.shading = shading

	def chained_leaf(self):
		return self.group.chained_leaf()

	def propagate_toggles(self, state):
		return self.group.propagate_toggles(state)

	def color_freq(self):
		return self.group.color_freq()

class Vertical(Part):
	def __init__(self, groups):
		self.groups = groups

	def chained_leaf(self):
		return self.groups[0].chained_leaf() if len(self.groups) == 1 else None

	def propagate_toggles(self, state):
		pruned = []
		for group in self.groups:
			state = group.propagate_toggles(state)
			if not isinstance(group, Toggle):
				pruned.append(group)
		self.groups = pruned
		return state

	def color_freq(self):
		return sum([g.color_freq() for g in self.groups], Counter())

class Horizontal(Part):
	def __init__(self, groups):
		self.groups = groups

	def chained_leaf(self):
		return self.groups[0].chained_leaf() if len(self.groups) == 1 else None

	def propagate_toggles(self, state):
		pruned = []
		for group in self.groups:
			state = group.propagate_toggles(state)
			if not isinstance(group, Toggle):
				pruned.append(group)
		self.groups = pruned
		return state

	def color_freq(self):
		return sum([g.color_freq() for g in self.groups], Counter())

class Complex(Part):
	def __init__(self, group1, hieroglyph, group2):
		self.group1 = group1
		self.hieroglyph = hieroglyph
		self.group2 = group2

	def propagate_toggles(self, state):
		state = super().propagate_toggles(state)
		if self.group1:
			state = self.group1.propagate_toggles(state)
		state = self.hieroglyph.propagate_toggles(state)
		if self.group2:
			state = self.group2.propagate_toggles(state)
		return state

	def color_freq(self):
		freq = self.hieroglyph.color_freq()
		if self.group1:
			freq += self.group1.color_freq()
		if self.group2:
			freq += self.group2.color_freq()
		return freq

class Overlay(Part):
	def __init__(self, hieroglyph1, hieroglyph2):
		self.hieroglyph1 = hieroglyph1
		self.hieroglyph2 = hieroglyph2

	def propagate_toggles(self, state):
		state = super().propagate_toggles(state)
		for hieroglyph in [self.hieroglyph1, self.hieroglyph2]:
			state = hieroglyph.propagate_toggles(state)
		return state

	def color_freq(self):
		return self.hieroglyph1.color_freq() + self.hieroglyph2.color_freq()

class Ligature(Part):
	def __init__(self, hieroglyphs):
		self.hieroglyphs = hieroglyphs

	def propagate_toggles(self, state):
		state = super().propagate_toggles(state)
		for hieroglyph in self.hieroglyphs:
			state = hieroglyph.propagate_toggles(state)
		return state

	def color_freq(self):
		return sum([h.color_freq() for h in self.hieroglyphs], Counter())

class Absolute(Part):
	def __init__(self, hieroglyphs):
		self.hieroglyphs = hieroglyphs

	def propagate_toggles(self, state):
		state = super().propagate_toggles(state)
		for hieroglyph in self.hieroglyphs:
			state = hieroglyph.propagate_toggles(state)
		return state

	def color_freq(self):
		return sum([h.color_freq() for h in self.hieroglyphs], Counter())

class Hieroglyph(Part):
	def __init__(self):
		pass

	def chained_leaf(self):
		return self

	def rotate_num(self):
		return rotate_to_num(self.modifiers['rotate']) if 'rotate' in self.modifiers else 0

	def rotate_coarse(self):
		rot = self.modifiers['rotate'] if 'rotate' in self.modifiers else 0
		return round(rot / 90) * 90

	def safe_placement(self):
		if self.placement:
			return self.placement['x'], self.placement['y'], self.placement['s']
		else:
			scale = self.modifiers['scale'] if 'scale' in self.modifiers else 100
			return 0, 0, scale

class Sign(Hieroglyph):
	def __init__(self, name, modifiers, placement):
		self.name = name
		self.modifiers = modifiers
		self.placement = placement

	def set_modifiers_and_placement(self, modifiers, placement):
		return Sign(self.name, modifiers, placement)

	def effective_color(self):
		if 'color' in self.modifiers and self.modifiers['color'] == 'red' or self.state.color == 'red':
			return 'red'
		else:
			return 'black'

	def color_freq(self):
		return Counter([self.effective_color()])

class Blank(Hieroglyph):
	def __init__(self, size, modifiers, placement):
		self.size = size
		self.modifiers = modifiers
		self.placement = placement

	def set_modifiers_and_placement(self, modifiers, placement):
		return Blank(self.size, modifiers, placement)

class Lost(Hieroglyph):
	def __init__(self, w, h, modifiers, placement):
		self.w = w
		self.h = h
		self.modifiers = modifiers
		self.placement = placement

	def set_modifiers_and_placement(self, modifiers, placement):
		return Lost(self.w, self.h, modifiers, placement)

class BracketOpen(Hieroglyph):
	def __init__(self, ch, modifiers, placement):
		self.ch = ch
		self.modifiers = modifiers
		self.placement = placement

	def set_modifiers_and_placement(self, modifiers, placement):
		return BracketOpen(self.ch, modifiers, placement)

class BracketClose(Hieroglyph):
	def __init__(self, ch, modifiers, placement):
		self.ch = ch
		self.modifiers = modifiers
		self.placement = placement

	def set_modifiers_and_placement(self, modifiers, placement):
		return BracketClose(self.ch, modifiers, placement)

class Enclosure(Hieroglyph):
	def __init__(self, begin, groups, end, modifiers, placement):
		self.begin = begin
		self.groups = groups
		self.end = end
		self.modifiers = modifiers
		self.placement = placement

	def set_modifiers_and_placement(self, modifiers, placement):
		return Enclosure(self.begin, self.groups, self.end, modifiers, placement)

	def propagate_toggles(self, state):
		state = super().propagate_toggles(state)
		pruned = []
		for group in self.groups:
			state = group.propagate_toggles(state)
			if not isinstance(group, Toggle):
				pruned.append(group)
		self.groups = pruned
		return state

	def effective_color(self):
		if 'color' in self.modifiers and self.modifiers['color'] == 'red' or self.state.color == 'red':
			return 'red'
		else:
			return 'black'

	def color_freq(self):
		return Counter([self.effective_color()]) + sum([g.color_freq() for g in self.groups], Counter())

	def open_shading_corners(self):
		corners = self.modifiers['shade'] if 'shade' in self.modifiers else empty_corners()
		return complete_corners(start_corners(corners), self.state.shade)

	def close_shading_corners(self):
		corners = self.modifiers['shade'] if 'shade' in self.modifiers else empty_corners()
		return complete_corners(end_corners(corners), self.state.shade)

	def open_shading_num(self):
		return corners_to_num(self.open_shading_corners())

	def close_shading_num(self):
		return corners_to_num(self.close_shading_corners())

class State:
	def __init__(self, color='black', shade=False):
		self.color = color
		self.shade = shade

	def update(self, toggle):
		match toggle.properties.get('color'):
			case 'toggle':
				color = 'red' if self.color == 'black' else 'black'
			case 'red':
				color = 'red'
			case 'black':
				color = 'black'
			case _:
				color = self.color
		match toggle.properties.get('shade'):
			case 'toggle':
				shade = not self.shade
			case 'on':
				shade = True
			case 'off':
				shade = False
			case _:
				shade = self.shade
		return State(color, shade)

class Toggle:
	def __init__(self, properties):
		self.properties = properties

	def propagate_toggles(self, state):
		return state.update(self)

	def update(self, properties):
		properties_new = self.properties.copy()
		properties_new.update(properties)
		return Toggle(properties_new)

	def is_empty(self):
		return len(self.properties) == 0

def empty_corners():
	return { 'ts': False, 'te': False, 'bs': False, 'be': False }

def complete_corners(corners, glob):
	return { corner: (corners[corner] or glob) for corner in ['ts', 'bs', 'te', 'be'] }
