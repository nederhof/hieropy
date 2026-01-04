import re
from collections import Counter

from .hieroparsing import UniParser, MdcParser
import hieropy.mdcstructure as mdc
import hieropy.unistructure as uni
from .uniconstants import num_to_corners
from .unitransform import mirror_group, rotate_group, damage_group
from .uninormalization import is_group, is_horizontal, make_horizontal, make_vertical
from .mdcnames import name_to_char, name_to_chars, mnemonic_to_name, name_to_zones, \
	ligature_to_chars, ligature_schema, is_flat_tall, is_flat_wide, is_flat
from .spatialparsing import GroupAndToken, SpatialParser, ParseParams

def can_add_open_bracket(group):
	if isinstance(group, uni.Horizontal):
		return not isinstance(group.groups[0], uni.BracketOpen)
	else:
		return not isinstance(group, uni.Singleton)
def can_add_close_bracket(group):
	if isinstance(group, uni.Horizontal):
		return not isinstance(group.groups[-1], uni.BracketClose)
	else:
		return not isinstance(group, uni.Singleton)
def add_open_bracket(bracket, group):
	if isinstance(group, uni.Horizontal):
		return uni.Horizontal([bracket] + group.groups)
	else:
		return uni.Horizontal([bracket, group])
def add_close_bracket(group, bracket):
	if isinstance(group, uni.Horizontal):
		return uni.Horizontal(group.groups + [bracket])
	else:
		return uni.Horizontal([group, bracket])

def make_token_from_mdc(group, x, y, s):
	return GroupAndToken.from_group_on_surface(group, x, y, s * 10, s * 10)

class MdcUniConverter:
	def __init__(self, text=False, numbers=False, colors=False):
		self.text = text
		self.numbers = numbers
		self.colors = colors
		self.uni_parser = UniParser()
		self.mdc_parser = MdcParser()
		self.errors = []

	def report(self, message):
		self.errors.append(f'(Line {self.line_no}): ' + message)

	def convert(self, text):
		lines = text.splitlines()
		parts = []
		for self.line_no, line_str in enumerate(lines, 1):
			line = self.mdc_parser.parse(line_str)
			if self.mdc_parser.last_error:
				self.report(self.mdc_parser.last_error)
			if not line:
				self.report('Cannot parse: ' + line_str)
				continue
			for part in line.parts:
				match part:
					case mdc.Text():
						if self.text:
							parts.append(part)
					case mdc.LineNumber():
						if self.numbers:
							parts.append(part)
					case mdc.Fragment():
						if self.colors:
							fragments = part.cut_by_color()
							for f in fragments:
								if len(f.colors()) > 1:
									self.report(f'Multiple colors ({', '.join(f.colors())}) in one group')
								parts.append(self.convert_fragment(f))
						else:
							parts.append(self.convert_fragment(part))
		return parts

	def convert_fragment(self, fragment):
		groups = list(map(self.convert_group, fragment.groups))
		groups = list(filter(lambda g: g is not None, groups))
		i = len(groups)-1
		while i >= 0:
			if isinstance(groups[i], uni.BracketOpen):
				if i+1 < len(groups) and can_add_open_bracket(groups[i+1]):
					groups[i+1] = add_open_bracket(groups[i], groups[i+1])
				else:
					self.report('Ignored open bracket ' + groups[i].ch)
				groups.pop(i)
			elif isinstance(groups[i], uni.BracketClose):
				if i-1 >= 0 and can_add_close_bracket(groups[i-1]):
					groups[i-1] = add_close_bracket(groups[i-1], groups[i])
				else:
					self.report('Ignored close bracket ' + groups[i].ch)
				groups.pop(i)
			i -= 1
		freqs = fragment.color_freq() + Counter({'black': 1e-6})
		color = freqs.most_common(1)[0][0]
		return uni.Fragment(groups, color=color)

	def convert_group(self, group):
		match group:
			case mdc.Quadrat():
				return self.convert_quadrat(group)
			case mdc.Vertical():
				return self.convert_vertical(group)
			case mdc.Horizontal():
				return self.convert_horizontal(group)
			case mdc.Complex():
				return self.convert_complex(group)
			case mdc.Overlay():
				return self.convert_overlay(group)
			case mdc.Ligature():
				return self.convert_ligature(group)
			case mdc.Absolute():
				return self.convert_absolute(group)
			case mdc.Sign():
				return self.convert_sign(group)
			case mdc.Blank():
				return self.convert_blank(group)
			case mdc.Lost():
				return self.convert_lost(group)
			case mdc.BracketOpen():
				return self.convert_bracket_open(group)
			case mdc.BracketClose():
				return self.convert_bracket_close(group)
			case mdc.Enclosure():
				return self.convert_enclosure(group)
			case _:
				return None

	def convert_groups(self, groups, hor=False):
		converted = map(self.convert_group, groups)
		return [g for g in converted if is_group(g, hor=hor)]

	def convert_quadrat(self, quadrat):
		return damage_group(self.convert_group(quadrat.group), quadrat.shading)

	def convert_vertical(self, ver):
		if len(ver.groups) > 2:
			first = ver.groups[0].chained_leaf()
			last = ver.groups[-1].chained_leaf()
			if isinstance(first, mdc.BracketOpen) and isinstance(last, mdc.BracketClose):
				br_open = self.convert_group(first)
				inner = self.convert_groups(ver.groups[1:-1])
				br_close = self.convert_group(last)
				if len(inner) >= 2:
					return uni.Horizontal([br_open, uni.Vertical(inner), br_close])
				elif len(inner) == 1:
					return uni.Horizontal([br_open, inner[0], br_close])
				else:
					self.report(f'Ignored empty bracket pair {br_open} {br_close}')
					return None
		groups = self.convert_groups(ver.groups, hor=True)
		groups = [g for group in groups for g in (group.groups if isinstance(group, uni.Vertical) else [group])]
		if len(groups) >= 2:
			proper_groups = list(filter(lambda g: is_group(g), groups))
			if len(proper_groups) >= 2:
				return uni.Vertical(proper_groups)
			elif len(proper_groups) == 1:
				return proper_groups[0]
			else:
				self.report('Ignored brackets in vertical group')
				return None
		elif len(groups) == 1:
			return groups[0]
		else:
			return None

	def convert_horizontal(self, hor):
		groups = self.convert_groups(hor.groups, hor=True)
		groups = [g for group in groups for g in (group.groups if isinstance(group, uni.Horizontal) else [group])]
		if len(groups) >= 2:
			if is_horizontal(groups):
				return uni.Horizontal(groups)
			self.report('Ignored dangling brackets')
			groups = list(filter(lambda g: is_group(g, hor=True), groups))
			if len(groups) >= 2:
				return uni.Horizontal(groups)
			elif len(groups) == 1:
				return groups[0]
			else:
				return None
		elif len(groups) == 1:
			return groups[0]
		else:
			return None

	def convert_complex(self, group):
		core = self.convert_group(group.hieroglyph)
		if isinstance(core, (uni.Literal, uni.Overlay)):
			places = core.allowed_places()
			if isinstance(group.hieroglyph, mdc.Sign):
				name = group.hieroglyph.name
				if mnemonic_to_name(name):
					name = mnemonic_to_name(name)
				place1, place2 = name_to_zones(name)
			else:
				place1, place2 = None, None
			if place1 is None:
				place1 = 'ts' if 'ts' in places else 'bs' if 'bs' in places else 'ts'
			if place2 is None:
				place2 = 'te' if 'te' in places else 'be' if 'be' in places else 'te'
			insertions = {}
			if group.group1:
				group1 = self.convert_group(group.group1)
				if not is_group(group1):
					if isinstance(group.group1, mdc.Sign) and group.group1.name != 'sic' and \
							not group.group1.name.startswith('"'):
						self.report('Cannot convert zone 1 of complex group')
				else:
					insertions[place1] = group1
			if group.group2:
				group2 = self.convert_group(group.group2)
				if not is_group(group2):
					if isinstance(group.group2, mdc.Sign) and group.group2.name != 'sic' and \
							not group.group2.name.startswith('"'):
						self.report('Cannot convert zone 2 of complex group')
				else:
					insertions[place2] = group2
			if len(insertions) == 0:
				return core
			else:
				return uni.Basic(core, insertions)
		else:
			self.report('Cannot convert complex group')
			return None

	def convert_overlay(self, group):
		group1 = self.convert_group(group.hieroglyph1)
		group2 = self.convert_group(group.hieroglyph2)
		if isinstance(group1, uni.Lost) and isinstance(group2, uni.Literal):
			return damage_group(group2, num_to_corners(15))
		if isinstance(group2, uni.Lost) and isinstance(group1, uni.Literal):
			return damage_group(group1, num_to_corners(15))
		if not group1 or not isinstance(group1, uni.Literal):
			self.report('Cannot convert first argument of overlay')
			return group2
		if not group2 or not isinstance(group2, uni.Literal):
			self.report('Cannot convert second argument of overlay')
			return group1
		return uni.Overlay([group1], [group2])

	def convert_ligature(self, group):
		hieroglyphs = []
		names = []
		for h in group.hieroglyphs:
			if isinstance(h, mdc.Sign):
				hieroglyphs.append(h)
				name = h.name
				if mnemonic_to_name(name):
					names.append(mnemonic_to_name(name))
				else:
					names.append(name)
		if len(hieroglyphs) == 0:
			return None
		elif len(hieroglyphs) == 1:
			return self.convert_group(hieroglyphs[0])
		name = '&'.join(names)
		if ligature_to_chars(name):
			return self.uni_parser.parse(ligature_to_chars(name)).groups[0]
		if all(is_flat(n) for n in names):
			names_hor = list(filter(is_flat_tall, names))
			names_ver = list(filter(is_flat_wide, names))
			if len(names_hor) > 0 and len(names_ver) > 0:
				lits1 = [uni.Literal(name_to_char(n), 0, False, 0) for n in names_hor]
				lits2 = [uni.Literal(name_to_char(n), 0, False, 0) for n in names_ver]
				return uni.Overlay(lits1, lits2)
		for i in range(len(names)):
			schema = ligature_schema(names[i], len(names), i)
			if schema:
				core = uni.Literal(name_to_char(names[i]), 0, False, 0)
				insertions = {}
				for j in range(len(names)):
					if j != i:
						inserted = self.convert_group(hieroglyphs[j])
						if inserted:
							insertions[schema[j]] = inserted
						else:
							self.report('Ignored inserted group')
				if len(insertions):
					return uni.Basic(core, insertions)
				else:
					return core
		self.report('Applying heuristics to convert ligature ' + name)
		core = self.convert_group(hieroglyphs[0])
		if not core:
			self.report('Ignored ligature')
			return None
		places = core.allowed_places()
		place = places[0] if len(places) > 0 else 'ts'
		groups = []
		for h in hieroglyphs[1:]:
			inserted = self.convert_group(h)
			if inserted:
				groups.append(inserted)
			else:
				self.report('Ignored inserted group')
		if len(groups) == 0:
			return core
		elif place in ['t', 'b', 'm']:
			return uni.Basic(core, { place: make_vertical(groups) })
		else:
			return uni.Basic(core, { place: make_horizontal(groups) })

	def convert_absolute(self, group):
		tokens = []
		for h in group.hieroglyphs:
			hiero = self.convert_group(h)
			x, y, s = h.safe_placement()
			token = make_token_from_mdc(hiero, x, y, s)
			if token is None:
				if isinstance(h, mdc.Sign) and h.name != 'sic' and not h.name.startswith('"'):
					self.report('Ignored token in absolute group')
			else:
				tokens.append(token)
		if len(tokens) == 0:
			return None
		parser = SpatialParser()
		parse = parser.best_top_group_exhaustive(tokens)
		if not parse:
			tokens_pruned = [t for t in tokens if not isinstance(t.group, (uni.BracketOpen, uni.BracketClose))]
			if len(tokens_pruned) > 0 and len(tokens_pruned) < len(tokens):
				parse = parser.best_top_group_exhaustive(tokens_pruned)
				if parse:
					self.report('Ignored brackets in absolute group')
		if not parse:
			self.report('Cannot convert absolute group')
			return None
		else:
			return parse

	def convert_sign(self, group):
		mirror = bool(group.modifiers.get('mirror'))
		damage = group.shading_num()
		if name_to_chars(group.name):
			converted = self.uni_parser.parse(name_to_chars(group.name)).groups[0]
			rot = group.rotate_coarse()
			if rot:
				converted = rotate_group(converted, rot)
			if mirror:
				converted = mirror_group(converted)
			if damage:
				converted = damage_group(converted, num_to_corners(damage))
			return converted
		elif name_to_char(group.name):
			ch = name_to_char(group.name)
			vs = group.rotate_num()
			return uni.Literal(ch, vs, mirror, damage)
		elif mnemonic_to_name(group.name):
			name = mnemonic_to_name(group.name)
			if name_to_char(name):
				vs = group.rotate_num()
				ch = name_to_char(name)
				return uni.Literal(ch, vs, mirror, damage)
			else:
				self.report(f'Name {name} not found')
				return None
		else:
			return None

	def convert_blank(self, group):
		return uni.Lost(group.size, group.size, True) if group.shading_num() else uni.Blank(group.size)

	def convert_lost(self, group):
		return uni.Lost(group.w, group.h, True)

	def convert_bracket_open(self, group):
		match group.ch:
			case '[&': return uni.BracketOpen('\u27E8')
			case '[{': return uni.BracketOpen('{')
			case '[[': return uni.BracketOpen('[')
			case '["': return uni.BracketOpen('\u27E6')
			case '[?': return uni.BracketOpen('\u2E22')
			case "['":
				self.report("Approximating ' with \u2E22")
				return uni.BracketOpen('{')
			case _:
				self.report(f"Approximating {group.ch[1]} with [")
				return uni.BracketOpen('[')

	def convert_bracket_close(self, group):
		match group.ch:
			case '&]': return uni.BracketClose('\u27E9')
			case '}]': return uni.BracketClose('}')
			case ']]': return uni.BracketClose(']')
			case '"]': return uni.BracketClose('\u27E7')
			case '?]': return uni.BracketClose('\u2E23')
			case "']":
				self.report("Approximating ' with \u2E23")
				return uni.BracketClose('\u2E23')
			case _:
				self.report(f"Approximating {group.ch[0]} with [")
				return uni.BracketClose(']')

	def convert_enclosure(self, group):
		groups = self.convert_groups(group.groups)
		typ = 'plain'
		delim_open = '\U00013379'
		delim_close = '\U0001337A'
		if group.begin == '' and group.end == '':
			pass
		elif re.fullmatch(r'[Ss].?', group.begin) and group.end == '':
			delim_open = '\U00013258'
			delim_close = '\U00013282'
		elif re.fullmatch(r'[Hh].?', group.begin) and group.end == '':
			delim_open = '\U00013258'
			delim_close = '\U0001325C'
		elif re.fullmatch(r'[Ff].?', group.begin) and group.end == '':
			typ = 'walled'
			delim_open = '\U00013288'
			delim_close = '\U00013289'
		else:
			match group.begin:
				case '0': delim_open = None
				case '1': pass
				case '2': delim_open = '\U0001342F'
				case 'h0': delim_open = None
				case 'h1': delim_open = '\U00013258'
				case 'h2': delim_open = '\U00013259'
				case 'h3': delim_open = '\U0001325A'
				case 's0': delim_open = None
				case 's1': delim_open = '\U00013258'
				case 's2': delim_open = '\U00013258'
				case 's3': delim_open = '\U00013258'
				case 'f0':
					typ = 'walled'
					delim_open = None
				case 'f1':
					typ = 'walled'
					delim_open = '\U00013288'
				case 'b': delim_close = None
				case 'm':
					delim_open = None
					delim_close = None
				case 'e': delim_open = None
			match group.end:
				case '0': delim_close = None
				case '1': delim_close = '\U0001337B'
				case '2': pass
				case 'h0': delim_close = None
				case 'h1': delim_close = '\U0001325D'
				case 'h2': delim_close = '\U0001325C'
				case 'h3': delim_close = '\U0001325B'
				case 's0': delim_close = None
				case 's1': delim_close = '\U0001325D'
				case 's2': delim_close = '\U00013282'
				case 's3': delim_close = '\U0001325D'
				case 'f0': delim_close = None
				case 'f1': delim_close = '\U00013289'
		if re.fullmatch(r'[SsHhFf]b', group.begin) and group.end == '':
			delim_close = None
		elif re.fullmatch(r'[SsHhFf]m', group.begin) and group.end == '':
			delim_open = None
			delim_close = None
		elif re.fullmatch(r'[SsHhFf]e', group.begin) and group.end == '':
			delim_open = None
		damage_open = group.open_shading_num()
		damage_close = group.close_shading_num()
		return uni.Enclosure(typ, groups, delim_open, damage_open, delim_close, damage_close)

def match_ligature_schema(names, schema):
	if len(names) == len(schema):
		for i in range(len(names)):
			if names[i] == schema[i]:
				core = uni.Literal(name_to_char(names[i]), 0, False, 0)
				insertions = {}
				for j in range(len(names)):
					if j != i:
						insertions[schema[j]] = uni.Literal(name_to_char(names[j]), 0, False, 0)
				return uni.Basic(core, insertions)
	else:
		return None
