import re 

from .hieroparsing import UniParser, WikiParser
from .uniconstants import OPEN_BRACKETS, CLOSE_BRACKETS
from .unitransform import mirror_group
from .unistructure import Fragment, Vertical, Horizontal, Enclosure, Literal, Blank, \
		BracketOpen, BracketClose
from .uninormalization import is_group, is_horizontal, make_horizontal, make_vertical
from .wikistructure import WikiVertical, WikiHorizontal, WikiSign, WikiBlank, WikiEnclosure, \
		WikiBracketOpen, WikiBracketClose, WikiText
from .wikinames import name_to_chars, mnemonic_to_name, combination_to_chars

class WikiUniConverter:
	def __init__(self):
		self.uni_parser = UniParser()
		self.wiki_parser = WikiParser()
		self.errors = []

	def report(self, message):
		self.errors.append(f'(Line {self.line_no}): ' + message)

	def convert(self, text):
		text = text.removesuffix(":")
		text = text.removesuffix("*")
		text = text.removeprefix(":")
		text = text.removeprefix("*")
		text = re.sub(r'[*:]-', '-', text)
		text = re.sub(r'-[*:]', '-', text)
		text = re.sub(r'[-*:]$', '', text)
		text = re.sub(r'^[-*:]', '', text)
		wiki = self.wiki_parser.parse(text)
		self.line_no = 0
		if self.wiki_parser.last_error:
			self.report(self.wiki_parser.last_error)
		if not wiki:
			self.report('Cannot parse: ' + text)
			return []
		lines = []
		for self.line_no, line in enumerate(wiki.lines):
			lines.append(self.convert_line(line))
		lines = list(filter(lambda l: len(l) > 0, lines))
		return lines

	def convert_line(self, line):
		groups = list(map(self.convert_group, line.groups))
		groups = list(filter(lambda g: g is not None, groups))
		fragments = []
		current = []
		for group in groups:
			if isinstance(group, (BracketOpen, BracketClose)):
				if current:
					fragments.append(Fragment(current))
					current = []
				fragments.append(group.ch)
			elif isinstance(group, WikiText):
				if current:
					fragments.append(Fragment(current))
					current = []
				fragments.append(group.text)
			else:
				current.append(group)
		if current:
			fragments.append(Fragment(current))
		return fragments

	def convert_group(self, group):
		match group:
			case WikiVertical():
				return self.convert_vertical(group)
			case WikiHorizontal():
				return self.convert_horizontal(group)
			case WikiSign():
				return self.convert_sign(group)
			case WikiBlank():
				return self.convert_blank(group)
			case WikiEnclosure():
				return self.convert_enclosure(group)
			case WikiBracketOpen():
				return self.convert_bracket_open(group.ch)
			case WikiBracketClose():
				return self.convert_bracket_close(group.ch)
			case WikiText():
				return group

	def convert_groups(self, groups, hor=False):
		converted = list(map(self.convert_group, groups))
		if len(converted) == 1:
			return converted
		else:
			return [g for g in converted if is_group(g, hor=hor)]

	def convert_vertical(self, ver):
		if ver.surface_form:
			chars = combination_to_chars(ver.surface_form)
			if chars:
				return self.uni_parser.parse(chars).groups[0]
		groups = self.convert_groups(ver.groups, hor=True)
		if len(groups) == 1:
			return groups[0]
		groups = [g for group in groups for g in (group.groups if isinstance(group, Vertical) else [group])]
		if len(groups) >= 2:
			return Vertical(groups)
		elif len(groups) == 1:
			return groups[0]
		else:
			return None

	def convert_horizontal(self, hor):
		groups = self.convert_groups(hor.groups, hor=True)
		if len(groups) == 1:
			return groups[0]
		groups = [g for group in groups for g in (group.groups if isinstance(group, Horizontal) else [group])]
		if len(groups) >= 2:
			return Horizontal(groups)
		elif len(groups) == 1:
			return groups[0]
		else:
			return None

	def convert_sign(self, group):
		name = group.name
		if mnemonic_to_name(name):
			name = mnemonic_to_name(name)
		if name_to_chars(name):
			ch = name_to_chars(name)
			if ch in OPEN_BRACKETS:
				return convert_bracket_open(ch)
			elif ch in CLOSE_BRACKETS:
				return convert_bracket_close(ch)
			converted = self.uni_parser.parse(ch).groups[0]
			if group.mirror:
				return mirror_group(converted)
			else:
				return converted
		else:
			self.report(f'Name {group.name} not found')
			return None
	
	def convert_blank(self, group):
		return Blank(group.size)
	
	def convert_enclosure(self, group):
		groups = self.convert_groups(group.groups)
		typ = 'plain'
		delim_open = '\U00013379'
		delim_close = '\U0001337A'
		if group.begin == '' and group.end == '':
			pass
		else:
			match group.begin:
				case '0': delim_open = None
				case '1': pass
				case '2': delim_open = '\U0001342F'
				case 'h0': delim_open = None
				case 'h1': delim_open = '\U00013258'
				case 'h2': delim_open = '\U00013259'
				case 'h3': delim_open = '\U0001325A'
			match group.end:
				case '0': delim_close = None
				case '1': delim_close = '\U0001337B'
				case '2': pass
				case 'h0': delim_close = None
				case 'h1': delim_close = '\U0001325D'
				case 'h2': delim_close = '\U0001325C'
				case 'h3': delim_close = '\U0001325B'
		return Enclosure(typ, groups, delim_open, 0, delim_close, 0)
	
	def convert_bracket_open(self, ch):
		match ch:
			case '[&': return BracketOpen('\u27E8')
			case '[{': return BracketOpen('{')
			case '[[': return BracketOpen('[')
			case '["': return BracketOpen('\u27E6')
			case "['":
				self.report("Approximating ' with \u2E22")
				return BracketOpen('{')
			case _:
				self.report(f"Approximating {group.ch[1]} with [")
				return BracketOpen('[')

	def convert_bracket_close(self, ch):
		match ch:
			case '&]': return BracketClose('\u27E9')
			case '}]': return BracketClose('}')
			case ']]': return BracketClose(']')
			case '"]': return BracketClose('\u27E7')
			case "']":
				self.report("Approximating ' with \u2E23")
				return BracketClose('\u2E23')
			case _:
				self.report(f"Approximating {group.ch[0]} with ]")
				return BracketClose(']')
