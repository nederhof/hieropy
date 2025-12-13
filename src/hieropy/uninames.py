import csv
import re
import importlib.resources as resources
from collections import defaultdict

from .uniconstants import CAP_CHARS, PLACEHOLDER

NAME_POINT_FILE = 'namepoint.csv'
NAME_POINT_EXT_FILE = 'namepointext.csv'
MNEMONIC_NAME_FILE = 'mnemonicname.csv'
TALL_FILE = 'tallnames.txt'
BROAD_FILE = 'broadnames.txt'
NARROW_FILE = 'narrownames.txt'

UNI_CATEGORIES = ['A','B','C','D','E','F','G','H','I', \
	'K','L','M','N','NL','NU','O','P','Q','R','S','T','U','V','W','X','Y','Z','Aa']

_name_to_char = None
_char_to_name = None
_name_to_char_cap = None
_char_to_name_cap = None
_cat_to_chars = None
_cat_to_chars_ext = None
_mnemonic_to_name = None
_name_to_mnemonics = None
_tall_names = None
_broad_names = None
_narrow_names = None

def name_to_char(name):
	if _name_to_char is None:
		cache_name_and_char()
	return _name_to_char.get(name)

def char_to_name(ch):
	if _char_to_name is None:
		cache_name_and_char()
	return _char_to_name.get(ch, '')

def name_to_char_cap(name):
	if _name_to_char_cap is None:
		cache_name_and_char()
	return _name_to_char_cap.get(name)

def char_to_name_cap(ch):
	if _char_to_name_cap is None:
		cache_name_and_char()
	return _char_to_name_cap[ch]

def is_extended_char(ch):
	if _extended_chars is None:
		cache_name_and_char()
	return ch in _extended_chars

def cat_to_chars(cat):
	if _cat_to_chars is None:
		cache_name_and_char()
	return _cat_to_chars[cat]

def cat_to_chars_ext(cat):
	if _cat_to_chars_ext is None:
		cache_name_and_char()
	return _cat_to_chars_ext[cat]

def mnemonic_to_name(mnemonic):
	if _mnemonic_to_name is None:
		cache_mnemonic()
	return _mnemonic_to_name.get(mnemonic)

def name_to_mnemonics(name):
	if _name_to_mnemonics is None:
		cache_mnemonic()
	return _name_to_mnemonics.get(name, [])

def tall_names():
	if _tall_names is None:
		cache_size_names()
	return _tall_names

def broad_names():
	if _broad_names is None:
		cache_size_names()
	return _broad_names

def narrow_names():
	if _narrow_names is None:
		cache_size_names()
	return _narrow_names

def tall_chars():
	return [name_to_char(name) for name in tall_names()]

def broad_chars():
	return [name_to_char(name) for name in broad_names()]

def narrow_chars():
	return [name_to_char(name) for name in narrow_names()]

def dissect_name(name):
	match = re.match('^([A-IK-Z]?|NL|NU|Aa)([0-9]{1,3})([a-z]{0,2})$', name)
	if match:
		return match.group(1), int(match.group(2)), match.group(3)
	else:
		return None, None, None

def name_to_cat(name):
	cat, _, _ = dissect_name(name)
	return cat

def cache_name_and_char():
	global _name_to_char
	global _char_to_name
	global _name_to_char_cap
	global _char_to_name_cap
	global _extended_chars
	global _cat_to_chars
	global _cat_to_chars_ext
	_name_to_char = {}
	_extended_chars = set()
	_cat_to_chars = defaultdict(list)
	_cat_to_chars_ext = defaultdict(list)
	for i, file in enumerate([NAME_POINT_FILE, NAME_POINT_EXT_FILE]):
		with resources.files('hieropy.resources').joinpath(file).open('r') as f:
			reader = csv.reader(f)
			for row in reader:
				n = row[0]
				p = chr(int(row[1],16))
				_name_to_char[n] = p
				cat = name_to_cat(n)
				if i == 0:
					_cat_to_chars[cat].append(p)
				else:
					_cat_to_chars_ext[cat].append(p)
					_extended_chars.add(p)
	_name_to_char_cap = {}
	_char_to_name = {p: n for (n, p) in _name_to_char.items()}
	_char_to_name_cap = {}
	for p in CAP_CHARS:
		n = _char_to_name[p]
		c = name_to_cat(n)
		_cat_to_chars[c].remove(p)
		del _name_to_char[n]
		del _char_to_name[p]
		_name_to_char_cap[n] = p
		_char_to_name_cap[p] = n

def cache_mnemonic():
	global _mnemonic_to_name
	global _name_to_mnemonics
	_mnemonic_to_name = {}
	_name_to_mnemonics = defaultdict(list)
	with resources.files('hieropy.resources').joinpath(MNEMONIC_NAME_FILE).open('r') as f:
		reader = csv.reader(f)
		for row in reader:
			mnem = row[0]
			name = row[1]
			_mnemonic_to_name[mnem] = name
			_name_to_mnemonics[name].append(mnem)

def cache_size_names():
	global _tall_names, _broad_names, _narrow_names
	with resources.files('hieropy.resources').joinpath(TALL_FILE).open('r') as f:
		_tall_names = [name for line in f for name in line.split()]
	with resources.files('hieropy.resources').joinpath(BROAD_FILE).open('r') as f:
		_broad_names = [name for line in f for name in line.split()]
	with resources.files('hieropy.resources').joinpath(NARROW_FILE).open('r') as f:
		_narrow_names = [name for line in f for name in line.split()]
