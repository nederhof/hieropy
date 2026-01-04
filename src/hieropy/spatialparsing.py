import sys
import math
from collections import defaultdict
from itertools import product, combinations

from .options import Options
from .uniconstants import insertion_position, INSERTION_PLACES
from .uniproperties import InsertionAdjust
from .unistructure import Fragment, Vertical, Horizontal, Enclosure, Basic, Overlay, \
		Literal, BracketOpen, BracketClose
from .uninormalization import is_group, is_horizontal, make_horizontal, make_vertical

options = Options()

class ParseParams:
	def __init__(self, slack=0, exhaustive=False):
		self.slack = slack
		self.exhaustive = exhaustive

def group_format(group):
	group.init_scale()
	group.fit(options, 1, 1)
	w_font, h_font = group.size(options)
	group.format(options, 0, 0, w_font, w_font, 0, 0, h_font, h_font)

class GroupAndTokens:
	def __init__(self, group, tokens):
		self.group = group
		self.tokens = tokens

	@staticmethod
	def vertical(groups):
		group = make_vertical([g.group for g in groups])
		tokens = [token for g in groups for token in g.tokens]
		return GroupAndTokens(group, tokens)
		
	@staticmethod
	def horizontal_safe(groups):
		group = make_horizontal([g.group for g in groups])
		if is_horizontal(group.groups):
			tokens = [token for g in groups for token in g.tokens]
			return [GroupAndTokens(group, tokens)]
		else:
			return []

	@staticmethod
	def enclosure(enclosure, enclosed):
		empty = enclosure.group
		group = Enclosure(empty.typ, [enclosed.group], empty.delim_open, empty.damage_open, \
				empty.delim_close, empty.damage_close)
		tokens = enclosure.tokens + enclosed.tokens
		return GroupAndTokens(group, tokens)

	@staticmethod
	def basic(core, place_to_group):
		insertions = {}
		tokens = [t for t in core.tokens]
		for place in INSERTION_PLACES:
			if place in place_to_group:
				inserted = place_to_group[place]
				insertions[place] = inserted.group
				tokens.extend(inserted.tokens)
		group = Basic(core.group, insertions)
		return GroupAndTokens(group, tokens)

	@staticmethod
	def overlay(lits1, lits2):
		group = Overlay([lit.group for lit in lits1], [lit.group for lit in lits2])
		tokens = [token for lits in [lits1, lits2] for lit in lits for token in lit.tokens]
		return GroupAndTokens(group, tokens)

class GroupAndToken(GroupAndTokens):
	def __init__(self, group, x, y, w, h):
		self.group = group
		self.x = x
		self.y = y
		self.w = w
		self.h = h
		self.tokens = [self]

	@staticmethod
	def from_group_on_surface(group, x_corner, y_corner, w_scale, h_scale):
		if isinstance(group, (BracketOpen, BracketClose)):
			return GroupAndToken(group, x_corner, y_corner, 0.1 * w_scale, h_scale)
		elif isinstance(group, (Literal, Overlay, Enclosure)):
			group_format(group)
			return GroupAndToken(group, x_corner, y_corner, group.w * w_scale, group.h * h_scale)
		else:
			return None

	@staticmethod
	def normalize(tokens):
		if len(tokens) == 0:
			return tokens
		box = BoundingBox(tokens)
		normal_tokens = []
		for token in tokens:
			x = (token.x - box.x) / box.h
			w = token.w / box.h
			y = (token.y - box.y) / box.h
			h = token.h / box.h
			normal_tokens.append(GroupAndToken(token.group, x, y, w, h))
		return normal_tokens

	@staticmethod
	def dist_tokens(tokens1, tokens2):
		return sum(GroupAndToken.dist_token(t1, t2) for (t1,t2) in zip(tokens1, tokens2))

	@staticmethod
	def dist_token(token1, token2):
		x1_min, x1_max = token1.x, token1.x + token1.w
		x2_min, x2_max = token2.x, token2.x + token2.w
		y1_min, y1_max = token1.y, token1.y + token1.h
		y2_min, y2_max = token2.y, token2.y + token2.h
		points1 = [(x,y) for x in [x1_min, x1_max] for y in [y1_min, y1_max]]
		points2 = [(x,y) for x in [x2_min, x2_max] for y in [y2_min, y2_max]]
		return sum(math.dist(p1, p2) for (p1, p2) in zip(points1, points2))

	@staticmethod
	def extract_group(group):
		match group:
			case Vertical(): return GroupAndToken.extract_vertical(group)
			case Horizontal(): return GroupAndToken.extract_horizontal(group)
			case Enclosure(): return GroupAndToken.extract_enclosure(group)
			case Basic(): return GroupAndToken.extract_basic(group)
			case Overlay(): return GroupAndToken.extract_overlay(group)
			case _: return GroupAndToken.extract_atomic(group)

	@staticmethod
	def extract_vertical(group):
		return [t for g in group.groups for t in GroupAndToken.extract_group(g)]

	@staticmethod
	def extract_horizontal(group):
		return [t for g in group.groups for t in GroupAndToken.extract_group(g)]

	@staticmethod
	def extract_enclosure(group):
		empty = Enclosure(group.typ, [], group.delim_open, group.damage_open, group.delim_close, group.damage_close)
		return [GroupAndToken(group, group.delim_open_rect.x, group.delim_open_rect.y, \
				group.delim_close_rect.x + group.delim_close_rect.w, group.delim_open_rect.h)] + \
			[t for g in group.groups for t in GroupAndToken.extract_group(g)]

	@staticmethod
	def extract_basic(group):
		if isinstance(group.core, Literal):
			tokens = GroupAndToken.extract_atomic(group.core)
		else:
			tokens = GroupAndToken.extract_overlay(group.core)
		for place in INSERTION_PLACES:
			if place in group.insertions:
				tokens.extend(GroupAndToken.extract_group(group.insertions[place]))
		return tokens

	@staticmethod
	def extract_overlay(group):
		return [t for dimension in [group.lits1, group.lits2] for lit in dimension \
				for t in GroupAndToken.extract_group(lit)]

	@staticmethod
	def extract_atomic(group): # Literal, BracketOpen, BracketClose
		return [GroupAndToken(group, group.x, group.y, group.w, group.h)]

class BoundingBox:
	def __init__(self, tokens):
		self.x, x_max = tokens[0].x, tokens[0].x + tokens[0].w
		self.y, y_max = tokens[0].y, tokens[0].y + tokens[0].h
		x_center, y_center = tokens[0].x + tokens[0].w / 2, tokens[0].y + tokens[0].h / 2
		x_center_min, x_center_max = x_center, x_center
		y_center_min, y_center_max = y_center, y_center
		for token in tokens[1:]:
			self.x, x_max = min(self.x, token.x), max(x_max, token.x + token.w)
			self.y, y_max = min(self.y, token.y), max(y_max, token.y + token.h)
			x_center, y_center = token.x + token.w / 2, token.y + token.h / 2
			x_center_min, x_center_max = min(x_center_min, x_center), max(x_center_max, x_center)
			y_center_min, y_center_max = min(y_center_min, y_center), max(y_center_max, y_center)
		self.w = x_max - self.x
		self.h = y_max - self.y
		self.margin_l = x_center_min - self.x
		self.margin_r = x_max - x_center_max
		self.margin_t = y_center_min - self.y
		self.margin_b = y_max - y_center_max

	@staticmethod
	def overlap(box1, box2):
		return box2.x < box1.x + box1.w and box1.x < box2.x + box2.w and \
			box2.y < box1.y + box1.h and box1.y < box2.y + box2.h

class SpatialParser:
	def __init__(self, direction='hlr'):
		self.direction = direction

	def h(self):
		return self.direction in ['hlr', 'hrl']

	def lr(self):
		return self.direction in ['hlr', 'vlr']

	def best_fragment(self, tokens):
		chunks = self.split(tokens, ParseParams())
		groups = []
		for chunk in chunks:
			group = self.best_top_group_exhaustive(chunk)
			if group:
				groups.append(group)
		return Fragment(groups)

	def best_top_group_exhaustive(self, tokens):
		parse = None
		for slack in [0.1, 0.2, 0.3, 0.4, 0.5]:
			parse = self.best_top_group(tokens, ParseParams(slack=slack))
			if parse:
				break
		if not parse:
			parse = self.best_top_group(tokens, ParseParams(exhaustive=True))
		return parse

	def best_top_group(self, tokens, params=None):
		if params is None:
			params = ParseParams()
		tokens = GroupAndToken.normalize(tokens)
		parses = self.parse_group(tokens, params)
		best_parse = None
		min_dist = sys.maxsize
		for parse in parses:
			group_format(parse.group)
			formatted_tokens = GroupAndToken.normalize(GroupAndToken.extract_group(parse.group))
			dist = GroupAndToken.dist_tokens(parse.tokens, formatted_tokens)
			if dist < min_dist:
				best_parse = parse.group
				min_dist = dist
		return best_parse

	def parse_group(self, tokens, params):
		if len(tokens) == 0:
			return []
		elif len(tokens) == 1:
			return [tokens[0]]
		else:
			return self.parse_vertical(tokens, params) + \
					self.parse_horizontal(tokens, params) + \
					self.parse_enclosure(tokens, params) + \
					self.parse_basic(tokens, params) + \
					self.parse_overlay(tokens, params)

	def parse_vertical(self, tokens, params):
		parses = []
		for (prefix, suffix) in split_from_top(tokens, params):
			parses1 = self.parse_group(prefix, params)
			parses2 = self.parse_group(suffix, params)
			for parse1 in parses1:
				for parse2 in parses2:
					if all(is_group(p.group) for p in [parse1, parse2]):
						parses.append(GroupAndTokens.vertical([parse1, parse2]))
		return parses

	def parse_horizontal(self, tokens, params):
		parses = []
		for (prefix, suffix) in split_from_left(tokens, params):
			parses1 = self.parse_group(prefix, params)
			parses2 = self.parse_group(suffix, params)
			for parse1 in parses1:
				for parse2 in parses2:
					parses.extend(GroupAndTokens.horizontal_safe([parse1, parse2]))
		return parses

	def parse_enclosure(self, tokens, params):
		parses = []
		for i in range(len(tokens)):
			enclosure = tokens[i]
			if isinstance(enclosure.group, Enclosure):
				rest = tokens[:i] + tokens[i+1:]
				if all(contained_token(enclosure, t, params) for t in rest):
					enclosed_parses = self.parse_group(rest, params)
					for enclosed_parse in enclosed_parses:
						parses.append(GroupAndTokens.enclosure(enclosure, enclosed_parse))
		return parses

	def parse_basic(self, tokens, params):
		parses = []
		for i in range(len(tokens)):
			core = tokens[i]
			if isinstance(core.group, (Literal, Overlay)):
				rest = tokens[:i] + tokens[i+1:]
				parses.extend(self.parse_insertions(core, rest, params))
		return parses

	def parse_overlay(self, tokens, params):
		if params.exhaustive and False:
			return self.parse_overlay_exhaustive(tokens, params)
		parses = []
		for i, j in list(combinations(range(len(tokens)), 2)):
			if not isinstance(tokens[i].group, Literal) or not isinstance(tokens[j].group, Literal):
				continue
			elif crossing_tokens(tokens[i], tokens[j], params):
				lits1 = [tokens[i]]
				lits2 = [tokens[j]]
				rest = tokens[:i] + tokens[i+1:j] + tokens[j+1:]
			elif crossing_tokens(tokens[j], tokens[i], params):
				lits1 = [tokens[j]]
				lits2 = [tokens[i]]
				rest = tokens[:i] + tokens[i+1:j] + tokens[j+1:]
			else:
				continue
			k = len(rest)-1
			while k >= 0:
				if not isinstance(rest[k].group, Literal):
					pass
				elif crossing_tokens(lits1[0], rest[k], params):
					lits2.append(rest.pop(k))
				elif crossing_tokens(rest[k], lits2[0], params):
					lits1.append(rest.pop(k))
				k -= 1
			lits1 = sorted(lits1, key=lambda t: t.x + t.w / 2)
			lits2 = sorted(lits2, key=lambda t: t.y + t.h / 2)
			core = GroupAndTokens.overlay(lits1, lits2)
			if len(rest) == 0:
				parses.append(core)
			else:
				parses.extend(self.parse_insertions(core, rest, params))
		return parses

	def parse_overlay_exhaustive(self, tokens, params):
		parses = []
		for k in range(1, len(tokens)):
			for indexes1 in combinations(range(len(tokens)), k):
				lits1 = [tokens[i] for i in indexes1]
				if not all(isinstance(lit.group, Literal) for lit in lits1):
					continue
				lits1 = sorted(lits1, key=lambda t: t.x + t.w / 2)
				rest1 = [tokens[i] for i in range(len(tokens)) if i not in indexes1]
				for m in range(1, len(rest1)+1):
					for indexes2 in combinations(range(len(rest1)), m):
						lits2 = [tokens[i] for i in indexes2]
						if not all(isinstance(lit.group, Literal) for lit in lits2):
							continue
						lits2 = sorted(lits2, key=lambda t: t.y + t.h / 2)
						rest = [rest1[i] for i in range(len(rest1)) if i not in indexes2]
						core = GroupAndTokens.overlay(lits1, lits2)
						if len(rest) == 0:
							parses.append(core)
						else:
							parses.extend(self.parse_insertions(core, rest, params))
		return parses

	def parse_insertions(self, core, rest, params):
		parses = []
		core_box = BoundingBox(core.tokens)
		if not any(BoundingBox.overlap(core_box, BoundingBox(token.tokens)) for token in rest):
			return parses
		places = core.group.allowed_places()
		if len(places) > 0:
			insertion_tokens = split_around_core(core, rest)
			subparsess = []
			place_list = list(insertion_tokens.keys())
			for place in place_list:
				subparses = self.parse_group(insertion_tokens[place], params)
				subparses = list(filter(lambda s: is_group(s.group), subparses))
				subparsess.append(subparses)
			for subparse_list in product(*subparsess):
				insertions = {}
				for place, subparse in zip(place_list, subparse_list):
					insertions[place] = subparse
				parses.append(GroupAndTokens.basic(core, insertions))
		return parses

	def split(self, tokens, params):
		if self.h():
			return self.split_horizontal(tokens, params)
		else:
			return self.split_vertical(tokens, params)

	def split_vertical(self, tokens, params):
		tokens = sorted(tokens, key=lambda t: t.y + t.h / 2)
		chunks = []
		while len(tokens) > 0:
			top_tokens = [tokens[0]]
			bottom_tokens = tokens[1:]
			while len(bottom_tokens) > 0:
				t_box = BoundingBox(top_tokens)
				b_box = BoundingBox(bottom_tokens)
				overlap = params.slack * max(t_box.margin_b, b_box.margin_t)
				if t_box.y + t_box.h - overlap < b_box.y:
					break
				top_tokens.append(bottom_tokens.pop(0))
			chunks.append(top_tokens)
			tokens = bottom_tokens
		return chunks

	def split_horizontal(self, tokens, params):
		tokens = sorted(tokens, key=lambda t: t.x + t.w / 2)
		chunks = []
		while len(tokens) > 0:
			left_tokens = [tokens[0]]
			right_tokens = tokens[1:]
			while len(right_tokens) > 0:
				l_box = BoundingBox(left_tokens)
				r_box = BoundingBox(right_tokens)
				overlap = params.slack * max(l_box.margin_r, r_box.margin_l)
				if l_box.x + l_box.w - overlap < r_box.x:
					break
				left_tokens.append(right_tokens.pop(0))
			chunks.append(left_tokens)
			tokens = right_tokens
		return chunks if self.lr() else reversed(chunks)

def split_from_top(tokens, params):
	tokens = sorted(tokens, key=lambda t: t.y + t.h / 2)
	if params.exhaustive:
		splits = []
		for i in range(1,len(tokens)):
			top_tokens = tokens[:i]
			bottom_tokens = tokens[i:]
			t_box = BoundingBox(top_tokens)
			b_box = BoundingBox(bottom_tokens)
			t_center = t_box.x + t_box.w / 2
			b_center = b_box.x + b_box.w / 2
			dist = abs(t_center - b_center)
			if dist < max(t_box.w / 2, b_box.w / 2):
				splits.append((top_tokens, bottom_tokens))
		return splits
	else:
		top_tokens = [tokens[0]]
		bottom_tokens = tokens[1:]
		while len(bottom_tokens) > 0:
			t_box = BoundingBox(top_tokens)
			b_box = BoundingBox(bottom_tokens)
			overlap = params.slack * max(t_box.margin_b, b_box.margin_t)
			if t_box.y + t_box.h - overlap < b_box.y:
				return [(top_tokens, bottom_tokens)]
			top_tokens.append(bottom_tokens.pop(0))
		return []

def split_from_left(tokens, params):
	tokens = sorted(tokens, key=lambda t: t.x + t.w / 2)
	if params.exhaustive:
		splits = []
		for i in range(1,len(tokens)):
			left_tokens = tokens[:i]
			right_tokens = tokens[i:]
			t_box = BoundingBox(left_tokens)
			b_box = BoundingBox(right_tokens)
			t_center = t_box.y + t_box.h / 2
			b_center = b_box.y + b_box.h / 2
			dist = abs(t_center - b_center)
			if dist < max(t_box.h / 2, b_box.h / 2):
				splits.append((left_tokens, right_tokens))
		return splits
	else:
		left_tokens = [tokens[0]]
		right_tokens = tokens[1:]
		while len(right_tokens) > 0:
			l_box = BoundingBox(left_tokens)
			r_box = BoundingBox(right_tokens)
			overlap = params.slack * max(l_box.margin_r, r_box.margin_l)
			if l_box.x + l_box.w - overlap < r_box.x:
				return [(left_tokens, right_tokens)]
			left_tokens.append(right_tokens.pop(0))
		return []

def split_around_core(core, tokens):
	group = core.group
	box = BoundingBox(core.tokens)
	place_to_pos = {}
	place_to_tokens = defaultdict(list)
	for place in group.allowed_places():
		pos_x, pos_y = insertion_position(place, InsertionAdjust())
		place_to_pos[place] = (box.x + pos_x * box.w, box.y + pos_y * box.h)
	for token in tokens:
		x_center, y_center = token.x + token.w / 2, token.y + token.h / 2
		best_place = None
		min_dist = sys.maxsize
		for place in group.allowed_places():
			dist = math.dist(place_to_pos[place], (x_center, y_center))
			if dist < min_dist:
				best_place = place
				min_dist = dist
		place_to_tokens[best_place].append(token)
	return place_to_tokens

def crossing_tokens(token1, token2, params):
	x1_min, x1_max = token1.x, token1.x + token1.w
	x2_min, x2_max = token2.x, token2.x + token2.w
	y1_min, y1_max = token1.y, token1.y + token1.h
	y2_min, y2_max = token2.y, token2.y + token2.h
	x_overlap = params.slack * min(token1.w, token2.w)
	y_overlap = params.slack * min(token1.h, token2.h)
	return x2_min - x_overlap < x1_min and x1_max < x2_max + x_overlap and \
		y1_min - y_overlap < y2_min and y2_max < y1_max + y_overlap

def contained_token(token1, token2, params):
	x1_min, x1_max = token1.x, token1.x + token1.w
	x2_min, x2_max = token2.x, token2.x + token2.w
	y1_min, y1_max = token1.y, token1.y + token1.h
	y2_min, y2_max = token2.y, token2.y + token2.h
	x_overlap = params.slack * min(token1.w, token2.w)
	y_overlap = params.slack * min(token1.h, token2.h)
	return x2_min > x1_min - x_overlap and x2_max < x1_max + x_overlap and \
		y2_min > y1_min - y_overlap and y2_max < y1_max + y_overlap
