from .unistructure import *

def chars_from_literals(group):
	chars = []
	def add_literal_char(ch, vs, mirror, damage):
		chars.append(ch)
		return Literal(ch, vs, mirror, damage)
	transformation = { Literal: add_literal_char }
	group.map(transformation)
	return chars

def chars_from(group):
	chars = []
	def add_literal_char(ch, vs, mirror, damage):
		chars.append(ch)
		return Literal(ch, vs, mirror, damage)
	def add_enclosure_chars(typ, groups, delim_open, damage_open, delim_close, damage_close):
		if delim_open is not None:
			chars.append(delim_open)
		if delim_close is not None:
			chars.append(delim_close)
		return Enclosure(typ, groups, delim_open, damage_open, delim_close, damage_close)
	def add_singleton_char(ch, damage):
		chars.append(ch)
		return Singleton(ch, damage)
	transformation = { Literal: add_literal_char, Enclosure: add_enclosure_chars, Singleton: add_singleton_char }
	group.map(transformation)
	return chars
