import csv
import json
import importlib.resources as resources
from collections import defaultdict

TRANSLIT_POINTS_FILE = 'translitpoints.csv'
KEYWORD_POINTS_FILE = 'keywordpoints.csv'
POINT_INFO_FILE = 'pointinfo.csv'
POINT_ROTATIONS_FILE = 'pointrotations.csv'
INSERTIONS_FILE = 'insertions.json'
LIGATURES_FILE = 'ligatures.json'
CIRCULAR_FILE = 'circular.csv'
LR_SYMMETRIC_FILE = 'lrsymmetric.csv'
TB_SYMMETRIC_FILE = 'tbsymmetric.csv'

_translit_to_chars = None
_keyword_to_chars = None
_char_to_info = None
_char_to_rotations = None
_char_to_insertions = None
_char_to_overlay_ligature = None
_char_to_overlay_ligatures = None
_circular = None
_lr_symmetric = None
_tb_symmetric = None

def translit_to_chars(t):
	if _translit_to_chars is None:
		cache_translit()
	if t in _translit_to_chars:
		return _translit_to_chars[t]
	else:
		return []

def keyword_to_chars(t):
	if _keyword_to_chars is None:
		cache_keywords()
	if t in _keyword_to_chars:
		return _keyword_to_chars[t]
	else:
		return []

def cache_translit():
	global _translit_to_chars
	_translit_to_chars = defaultdict(list)
	with resources.files('hieropy.resources').joinpath(TRANSLIT_POINTS_FILE).open('r') as f:
		reader = csv.reader(f)
		for row in reader:
			translit = row[0]
			points = row[1].split()
			_translit_to_chars[translit] = [chr(int(p,16)) for p in points]

def cache_keywords():
	global _keyword_to_chars
	_keyword_to_chars = defaultdict(list)
	with resources.files('hieropy.resources').joinpath(KEYWORD_POINTS_FILE).open('r') as f:
		reader = csv.reader(f)
		for row in reader:
			keyword = row[0]
			points = row[1].split()
			_keyword_to_chars[keyword] = [chr(int(p,16)) for p in points]

def char_to_info(ch):
	if _char_to_info is None:
		cache_info()
	if ch in _char_to_info:
		return _char_to_info[ch]
	else:
		return None

def cache_info():
	global _char_to_info
	_char_to_info = {}
	with resources.files('hieropy.resources').joinpath(POINT_INFO_FILE).open('r') as f:
		reader = csv.reader(f, delimiter='$')
		for row in reader:
			point = row[0]
			info = row[1]
			_char_to_info[chr(int(point,16))] = info

def char_to_rotations(ch):
	if _char_to_rotations is None:
		cache_rotations()
	if ch in _char_to_rotations:
		return _char_to_rotations[ch]
	else:
		return []

def allowed_rotations(ch):
	return [rot[0] for rot in char_to_rotations(ch)]

def rotation_adjustment(ch, coarse):
	i = allowed_rotations(ch).index(coarse)
	return char_to_rotations(ch)[i][1]

def cache_rotations():
	global _char_to_rotations
	_char_to_rotations = {}
	with resources.files('hieropy.resources').joinpath(POINT_ROTATIONS_FILE).open('r') as f:
		reader = csv.reader(f, delimiter=' ')
		for row in reader:
			point = row[0]
			rotations = []
			for pair in row[1].split(','):
				[coarse,diff] = pair.split('+')
				rotations.append((int(coarse), int(diff)))
			_char_to_rotations[chr(int(point,16))] = rotations

def mirrored_insertion_places(places):
	places_mir = {}
	for place, adjustment in places.items():
		x = 1 - adjustment.x if adjustment.x is not None else None
		adjustment_mir = InsertionAdjust(x, adjustment.y)
		match place:
			case 'ts': places_mir['te'] = adjustment_mir
			case 'bs': places_mir['be'] = adjustment_mir
			case 'te': places_mir['ts'] = adjustment_mir
			case 'be': places_mir['bs'] = adjustment_mir
			case 'm': places_mir['m'] = adjustment_mir
			case 't': places_mir['t'] = adjustment_mir
			case 'b': places_mir['b'] = adjustment_mir
	return places_mir

class Insertion:
	def __init__(self, ch, rot, places):
		self.ch = ch
		self.rot = rot
		self.places = places

	def rotation(self):
		return 0 if self.rot is None else self.rot

	def place_names(self):
		return self.places.keys()

	def mirrored(self):
		return Insertion(self.ch, self.rot, mirrored_insertion_places(self.places))

	def __str__(self):
		return 'Insertion ' + str(self.ch) + ' ' + str(self.rot) + ' ' + str(self.places)

class InsertionAdjust:
	def __init__(self, x=None, y=None):
		self.x = x
		self.y = y

	def get_x(self, default):
		return self.x if self.x is not None else default

	def get_y(self, default):
		return self.y if self.y is not None else default

def char_to_insertions(ch, mirror=False):
	if _char_to_insertions is None:
		cache_insertions()
	if ch in _char_to_insertions:
		insertions = _char_to_insertions[ch]
		if mirror:
			return [insertion.mirrored() for insertion in insertions]
		else:
			return insertions
	else:
		return []

def char_to_places(ch, rotation, mirror):
	places = []
	for ins in char_to_insertions(ch, mirror):
		if ins.rotation() == rotation:
			for name in ins.place_names():
				if name not in places:
					places.append(name)
	return places
	
def cache_insertions():
	global _char_to_insertions
	_char_to_insertions = {}
	with resources.files('hieropy.resources').joinpath(INSERTIONS_FILE).open('r') as f:
		map_json = json.load(f)
	for point_json, insertion_jsons in map_json.items():
		ch = chr(int(point_json,16))
		insertions = []
		for insertion_json in insertion_jsons:
			alt = None
			rot = None
			places = {}
			for key, value in insertion_json.items():
				if key == 'ch':
					alt = chr(int(value,16))
				elif key == 'rot':
					rot = value
				else:
					x = insertion_json[key].get('x', None)
					y = insertion_json[key].get('y', None)
					places[key] = InsertionAdjust(x, y)
			insertions.append(Insertion(alt, rot, places))
		_char_to_insertions[ch] = insertions

class OverlayLigature:
	def __init__(self, ch, alt, horizontal, vertical):
		self.ch = ch
		self.alt = alt
		self.horizontal = horizontal
		self.vertical = vertical

class FlatElem:
	def __init__(self, ch, vs, mirror, x, y, w, h):
		self.ch = ch
		self.vs = vs
		self.mirror = mirror
		self.x = x
		self.y = y
		self.w = w
		self.h = h

def flat_group(group_json):
	group = []
	for elem in group_json:
		ch = chr(int(elem['ch'],16))
		vs = elem.get('vs', 0)
		mirror = elem.get('mirror', False)
		x = elem['x']
		y = elem['y']
		w = elem['w']
		h = elem['h']
		group.append(FlatElem(ch, vs, mirror, x, y, w, h))
	return group

def char_to_overlay_ligature(ch):
	if _char_to_overlay_ligature is None:
		cache_ligatures()
	if ch in _char_to_overlay_ligature:
		return _char_to_overlay_ligature[ch]
	else:
		return ch
	
def overlay_to_ligature(hor, ver):
	if _char_to_overlay_ligatures is None:
		cache_ligatures()
	ligs = []
	if hor[0].ch in _char_to_overlay_ligatures:
		ligs = _char_to_overlay_ligatures[hor[0].ch]
		for lig in ligs:
			if len(lig.horizontal) == len(hor) and \
					len(lig.vertical) == len(ver) and \
					all(g1.ch == g2.ch and g1.vs == g2.vs and g1.mirror == g2.mirror \
						for g1, g2 in zip(lig.horizontal, hor)) and \
					all(g1.ch == g2.ch and g1.vs == g2.vs and g1.mirror == g2.mirror \
						for g1, g2 in zip(lig.vertical, ver)):
				return lig, False
	if len(hor) == 1 and len(ver) == 1 and ver[0].ch in _char_to_overlay_ligatures:
		ligs = _char_to_overlay_ligatures[ver[0].ch]
		for lig in ligs:
			if len(lig.horizontal) == 1 and len(lig.vertical) == 1 and \
					lig.horizontal[0].ch == ver[0].ch and lig.vertical[0].ch == hor[0].ch:
				return lig, True
	return None, False

def cache_ligatures():
	global _char_to_overlay_ligature
	global _char_to_overlay_ligatures
	_char_to_overlay_ligature = {}
	_char_to_overlay_ligatures = defaultdict(list)
	with resources.files('hieropy.resources').joinpath(LIGATURES_FILE).open('r') as f:
		map_json = json.load(f)
	for point_json in map_json:
		parts_json = map_json[point_json]
		ch = chr(int(point_json,16))
		if parts_json['type'] == 'overlay':
			alt = 'alt' in parts_json
			hor = flat_group(parts_json['horizontal'])
			ver = flat_group(parts_json['vertical'])
			ligature = OverlayLigature(ch, alt, hor, ver)
			_char_to_overlay_ligature[ch] = ligature
			if not alt:
				_char_to_overlay_ligatures[hor[0].ch].append(ligature)
				_char_to_overlay_ligatures[ver[0].ch].append(ligature)

def circular_chars():
	global _circular
	if _circular is None:
		_circular = char_set_from(CIRCULAR_FILE)
	return _circular

def lr_symmetric_chars():
	global _lr_symmetric
	if _lr_symmetric is None:
		_lr_symmetric = char_set_from(LR_SYMMETRIC_FILE)
	return _lr_symmetric

def tb_symmetric_chars():
	global _tb_symmetric
	if _tb_symmetric is None:
		_tb_symmetric = char_set_from(TB_SYMMETRIC_FILE)
	return _tb_symmetric

def char_set_from(filename):
	charset = set() 
	with resources.files('hieropy.resources').joinpath(filename).open('r') as f:
		reader = csv.reader(f, delimiter=' ')
		for row in reader:
			charset.add(chr(int(row[0],16)))
	return charset
