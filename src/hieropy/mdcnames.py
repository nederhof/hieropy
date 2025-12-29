import csv
import importlib.resources as resources

from .uniconstants import INSERTION_PLACES

NAME_POINT_FILE = 'namepointmdc.csv'
NAME_COMPOSITE_FILE = 'namecompositemdc.csv'
MNEMONIC_NAME_FILE = 'mnemonicnamemdc.csv'
NAME_ZONE_FILE = 'namezonemdc.csv'
LIGATURE_FILE = 'ligaturemdc.csv'
LIGATURE_SCHEMA = 'ligatureschemamdc.txt'
FLAT_TALL_FILE = 'flattallnamesmdc.txt'
FLAT_WIDE_FILE = 'flatwidenamesmdc.txt'

_name_to_char = None
_name_to_chars = None
_mnemonic_to_name = None
_name_to_zones = None
_ligature_to_chars = None
_name_len_index_to_ligature_schema = None
_flat_tall = None
_flat_wide = None

def name_to_char(name):
	if _name_to_char is None:
		cache_name_and_char()
	return _name_to_char.get(name)

def name_to_chars(name):
	if _name_to_chars is None:
		cache_name_and_chars()
	return _name_to_chars.get(name)

def mnemonic_to_name(mnemonic):
	if _mnemonic_to_name is None:
		cache_mnemonic()
	return _mnemonic_to_name.get(mnemonic)

def name_to_zones(name):
	if _name_to_zones is None:
		cache_zones()
	return _name_to_zones[name] if name in _name_to_zones else (None, None)

def ligature_to_chars(name):
	if _ligature_to_chars is None:
		cache_ligature()
	return _ligature_to_chars.get(name)

def ligature_schema(name, length, index):
	if _name_len_index_to_ligature_schema is None:
		cache_ligature()
	return _name_len_index_to_ligature_schema.get((name, length, index))

def is_flat_tall(name):
	if _flat_tall is None:
		cache_ligature()
	return name in _flat_tall

def is_flat_wide(name):
	if _flat_wide is None:
		cache_ligature()
	return name in _flat_wide

def is_flat(name):
	return is_flat_tall(name) or is_flat_wide(name)

def cache_name_and_char():
	global _name_to_char
	_name_to_char = {}
	with resources.files('hieropy.resources').joinpath(NAME_POINT_FILE).open('r') as f:
		reader = csv.reader(f)
		for row in reader:
			n = row[0]
			p = chr(int(row[1],16))
			_name_to_char[n] = p

def cache_name_and_chars():
	global _name_to_chars
	_name_to_chars = {}
	with resources.files('hieropy.resources').joinpath(NAME_COMPOSITE_FILE).open('r', encoding='utf-8') as f:
		reader = csv.reader(f)
		for row in reader:
			n = row[0]
			p = row[1]
			_name_to_chars[n] = p

def cache_mnemonic():
	global _mnemonic_to_name
	_mnemonic_to_name = {}
	with resources.files('hieropy.resources').joinpath(MNEMONIC_NAME_FILE).open('r') as f:
		reader = csv.reader(f)
		for row in reader:
			if row[0][0] == '#':
				continue
			mnem = row[0]
			name = row[1]
			_mnemonic_to_name[mnem] = name

def cache_zones():
	global _name_to_zones
	_name_to_zones = {}
	with resources.files('hieropy.resources').joinpath(NAME_ZONE_FILE).open('r') as f:
		reader = csv.reader(f, delimiter=' ')
		for row in reader:
			name = row[0]
			zone1 = None if row[1] == '-' else row[1]
			zone2 = None if row[2] == '-' else row[2]
			_name_to_zones[name] = (zone1, zone2)

def cache_ligature():
	global _ligature_to_chars, _name_len_index_to_ligature_schema, _flat_tall, _flat_wide
	_ligature_to_chars = {}
	with resources.files('hieropy.resources').joinpath(LIGATURE_FILE).open('r', encoding='utf-8') as f:
		reader = csv.reader(f, delimiter=' ')
		for row in reader:
			lig = row[0]
			chars = row[1]
			_ligature_to_chars[lig] = chars
	_name_len_index_to_ligature_schema = {}
	with resources.files('hieropy.resources').joinpath(LIGATURE_SCHEMA).open('r') as f:
		for line in f:
			parts = line.split()
			length = len(parts)
			for i, part in enumerate(parts):
				if part not in INSERTION_PLACES:
					name = part
					index = i
			_name_len_index_to_ligature_schema[(name, length, index)] = parts
	with resources.files('hieropy.resources').joinpath(FLAT_TALL_FILE).open('r') as f:
		_flat_tall = [name for line in f for name in line.split()]
	with resources.files('hieropy.resources').joinpath(FLAT_WIDE_FILE).open('r') as f:
		_flat_wide = [name for line in f for name in line.split()]
