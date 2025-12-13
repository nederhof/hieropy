import csv
import importlib.resources as resources

from .uniconstants import num_to_rotate, rotate_to_num, mirror_place, mirror_rotate, quarter_mirror_rotate
from .uniprops import circular_chars, lr_symmetric_chars, tb_symmetric_chars
from .unistructure import *
from .hieroparsing import UniParser

LEGACY_FILE = 'legacy.csv'
LEGACY_TYPES = ['aspect', 'repetition', 'transform', 'variant', 'overlay', 'insertion', 'tabular']

def mirrored_group(group):
	if isinstance(group, Literal):
		return Literal(group.ch, group.vs, not group.mirror, group.damage)
	elif isinstance(group, Vertical):
		return Vertical([mirrored_group(g) for g in group.groups])
	elif isinstance(group, Horizontal):
		return Horizontal([mirrored_group(g) for g in reversed(group.groups)])
	else:
		return Overlay([mirrored_group(l) for l in group.lits1], 
			[mirrored_group(l) for l in group.lits2])

def damaged_group(group, damage):
	if isinstance(group, Literal):
		return Literal(group.ch, group.vs, group.mirror, damage)
	elif isinstance(group, Vertical):
		return Vertical([damaged_group(g, 15) for g in group.groups])
	elif isinstance(group, Horizontal):
		return Horizontal([damaged_group(g, 15) for g in group.groups])
	else:
		return Overlay([damaged_group(group.lits1[0], damage)] + group.lits1[1:], group.lits2)

def make_vertical(groups):
	subgroups = []
	for group in groups:
		if isinstance(group, Vertical):
			subgroups.extend(group.groups)
		else:
			subgroups.append(group)
	if len(subgroups) == 0:
		return None
	elif len(subgroups) == 1:
		return subgroups[0]
	else:
		return Vertical(subgroups)

def make_horizontal(groups):
	subgroups = []
	for group in groups:
		if isinstance(group, Horizontal):
			subgroups.extend(group.groups)
		else:
			subgroups.append(group)
	if len(subgroups) == 0:
		return None
	elif len(subgroups) == 1:
		return subgroups[0]
	else:
		return Horizontal(subgroups)

class UniNormalizer:
	def __init__(self, types=None, excepts=None):
		self.types = [] if types is None else types
		self.excepts = [] if excepts is None else excepts
		self.parser = UniParser()
		self.read_legacy()

	def read_legacy(self):
		self.type_to_char_to_alt = {typ: {} for typ in LEGACY_TYPES}
		with resources.files('hieropy.resources').joinpath(LEGACY_FILE).open('r') as f:
			reader = csv.reader(f)
			for point, typ, alt in reader:
				ch =  chr(int(point,16))
				self.type_to_char_to_alt[typ][ch] = self.parser.parse(alt)

	def normalize(self, fragment):
		self.errors = []
		for typ in self.types:
			if typ == 'legacy':
				for typ in LEGACY_TYPES:
					fragment = self.apply_legacy_type(typ, fragment)
			elif typ in LEGACY_TYPES:
				fragment = self.apply_legacy_type(typ, fragment)
			elif typ == 'order':
				fragment = self.apply_overlay_reorder(fragment)
			elif typ == 'damage':
				fragment = self.remove_damage(fragment)
			elif typ == 'bracket':
				fragment = self.remove_bracket(fragment)
			elif typ == 'expand':
				fragment = self.expand(fragment)
			elif typ == 'rotation':
				fragment = self.normalize_rotation(fragment)
			else:
				self.errors.append('Unrecognized normalization ' + typ)
		return fragment
 
	def legacy_literal(self, ch, vs, mirror, damage, typ):
		legacy_map = self.type_to_char_to_alt[typ]
		if ch in legacy_map and ch not in self.excepts:
			alt = legacy_map[ch].groups[0]
			if isinstance(alt, Literal):
				alt_ch = alt.ch
				alt_vs = rotate_to_num(num_to_rotate(alt.vs) + num_to_rotate(vs))
				alt_mirror = alt.mirror != mirror
				return Literal(alt_ch, alt_vs, alt_mirror, damage)
			if vs:
				self.errors.append('Cannot normalize rotated sign ' + ch)
			if isinstance(alt, Basic):
				core = alt.core
				place = list(alt.insertions.keys())[0]
				inserted = alt.insertions[place]
				if mirror:
					core = mirrored_group(core)
					inserted = mirrored_group(inserted)
					place = mirror_place(place)
				if damage:
					core = damaged_group(core, damage)
				return Basic(core, {place: inserted})
			elif isinstance(alt, Overlay):
				if mirror:
					alt = mirrored_group(alt)
				if damage:
					alt = damaged_group(alt, damage)
				return alt
			elif isinstance(alt, (Vertical, Horizontal)):
				if mirror:
					alt = mirrored_group(alt)
				if damage:
					if damage == 15:
						alt = damaged_group(alt, 15)
					else:
						self.errors.append('Cannot normalize partially damaged tabular group ' + ch)
				return alt
		return Literal(ch, vs, mirror, damage)

	def legacy_basic(self, core, insertions):
		if isinstance(core, (Literal, Overlay)):
			return Basic(core, insertions)
		elif isinstance(core, Basic):
			joint_insertions = {}
			for place, group in core.insertions.items():
				if place in joint_insertions:
					self.errors.append('Cannot use clashing insertions for ' + str(core))
					return Literal(PLACEHOLDER, 0, False, 0)
				else:
					joint_insertions[place] = group
			for place, group in insertions.items():
				if place in joint_insertions:
					self.errors.append('Cannot use clashing insertions for ' + str(core))
					return Literal(PLACEHOLDER, 0, False, 0)
				else:
					joint_insertions[place] = group
			return Basic(core.core, joint_insertions)
		else:
			self.errors.append('Cannot use complex group as core ' + str(core))
			return Literal(PLACEHOLDER, 0, False, 0)

	def legacy_overlay(self, lits1, lits2):
		flat_lits1 = []
		for group in lits1:
			if isinstance(group, Literal):
				flat_lits1.append(group)
			elif isinstance(group, Horizontal):
				for g in group.groups:
					if isinstance(g, Literal):
						flat_lits1.append(g)
					else:
						self.errors.append('Cannot use complex group in overlay ' + str(g))
						return Literal(PLACEHOLDER, 0, False, 0)
			else:
				self.errors.append('Cannot use complex group in overlay ' + str(group))
				return Literal(PLACEHOLDER, 0, False, 0)
		flat_lits2 = []
		for group in lits2:
			if isinstance(group, Literal):
				flat_lits2.append(group)
			elif isinstance(group, Vertical):
				for g in group.groups:
					if isinstance(g, Literal):
						flat_lits2.append(g)
					else:
						self.errors.append('Cannot use complex group in overlay ' + str(g))
						return Literal(PLACEHOLDER, 0, False, 0)
			else:
				self.errors.append('Cannot use complex group in overlay ' + str(group))
				return Literal(PLACEHOLDER, 0, False, 0)
		return Overlay(flat_lits1, flat_lits2)

	def apply_legacy_type(self, typ, fragment):
		transformation = { \
			Literal: lambda *args: self.legacy_literal(*args, typ), \
			Vertical: lambda groups: make_vertical(groups),
			Horizontal: lambda groups: make_horizontal(groups),
			Basic: lambda *args: self.legacy_basic(*args),
			Overlay: lambda *args: self.legacy_overlay(*args),
		}
		return fragment.map(transformation)

	def overlay_reorder(self, lits1, lits2):
		if len(lits1) == 1 and len(lits2) == 1 and ord(lits2[0].ch) < ord(lits1[0].ch):
			lits1, lits2 = lits2, lits1
		return Overlay(lits1, lits2)

	def apply_overlay_reorder(self, fragment):
		transformation = { \
			Overlay: lambda *args: self.overlay_reorder(*args),
		}
		return fragment.map(transformation)

	def remove_damage_enclosure(self, typ, groups, delim_open, damage_open, delim_close, damage_close):
		return Enclosure(typ, groups, delim_open, 0, delim_close, 0)

	def remove_damage_literal(self, ch, vs, mirror, damage):
		return Literal(ch, vs, mirror, 0)

	def remove_damage_singleton(self, ch, damage):
		return Singleton(ch, 0)

	def remove_damage(self, fragment):
		transformation = { \
			Enclosure: lambda *args: self.remove_damage_enclosure(*args), \
			Literal: lambda *args: self.remove_damage_literal(*args), \
			Singleton: lambda *args: self.remove_damage_singleton(*args), \
		}
		return fragment.map(transformation)

	def remove_bracket_horizontal(self, groups):
		proper_groups = [g for g in groups if not isinstance(g, (BracketOpen, BracketClose))]
		if len(proper_groups) >= 2:
			return Horizontal(proper_groups)
		return proper_groups[0]

	def remove_bracket(self, fragment):
		transformation = { \
			Vertical: lambda groups: make_vertical(groups), \
			Horizontal: lambda groups: self.remove_bracket_horizontal(groups), \
		}
		return fragment.map(transformation)

	def expand_lost(self, width, height, expand):
		return Lost(width, height, True)

	def expand(self, fragment):
		transformation = { \
			Lost: lambda *args: self.expand_lost(*args),
		}
		return fragment.map(transformation)

	def normalize_rotation_literal(self, ch, vs, mirror, damage):
		if ch in circular_chars():
			return Literal(ch, 0, False, damage)
		rotation = num_to_rotate(vs)
		allowed = allowed_rotations(ch)
		if ch in lr_symmetric_chars():
			mirrored_rotation = mirror_rotate(rotation)
			if rotation == 0 or rotation == 180:
				mirror = False
			elif rotation not in allowed and mirrored_rotation in allowed:
				vs = rotate_to_num(mirrored_rotation)
				mirror = not mirror
		if ch in tb_symmetric_chars():
			mirrored_rotation = quarter_mirror_rotate(rotation)
			if rotation == 90 or rotation == 270:
				mirror = False
			elif rotation not in allowed and mirrored_rotation in allowed:
				vs = rotate_to_num(mirrored_rotation)
				mirror = not mirror
		rotation = num_to_rotate(vs)
		if rotation != 0 and rotation not in allowed:
			self.errors.append(f'Unregistered rotation {rotation} for {ch}')
		return Literal(ch, vs, mirror, damage)

	def normalize_rotation(self, fragment):
		transformation = { \
			Literal: lambda *args: self.normalize_rotation_literal(*args),
		}
		return fragment.map(transformation)
