import os
import sys
import re
import pickle
import math
import numpy as np
from itertools import chain, permutations, combinations
import importlib.resources as resources
from collections import defaultdict
from scipy.spatial import KDTree
from PIL import Image, ImageFont, ImageDraw, ImageOps, ImageChops

from .uniconstants import HIERO_FONT_FILENAME
from .uninames import all_chars
from .unistructure import Literal
from .ocrdata import ocr_omit
from .spatialparsing import SpatialParser, GroupAndToken

class ImageUniConverter:
	# There are arrays of equal length, an index representing one component belonging to one character:
	# chars: the Unicode character to which the component belongs
	# char_variants: indexes 0, 1, 2, ... to distinguish different variants of the same character
	# char_parts: indexes 0, 1, 2, ... to distinguish the respective components of one (variant) character
	#	(the value is -1 for the character as a whole)
	# vectors: a vector representation of the shape of a component
	# widths: the width of a component in terms of 1 EM
	# heights: the height of a component in terms of 1 EM
	# ratios: width / height
	#
	# char_records: maps a pair consisting of character and variant index to a list of components
	# (relative coordinates and dimensions)
	#
	# char_wholes: maps a pair consisting of character and variant index to an
	# index in the "vector" array. Used only for characters with more than one
	# component.
	#
	# tree: maps vectors to an index for the above
	fields = ['normal_size', 'threshold', \
			'chars', 'char_variants', 'char_parts', 'vectors', 'widths', 'heights', 'ratios', \
			'char_records', 'char_wholes', 'tree']

	def __init__(self, normal_size, threshold, \
				chars, char_variants, char_parts, vectors, widths, heights, ratios, \
				char_records, char_wholes, tree):
		self.normal_size = normal_size
		self.threshold = threshold

		self.chars = chars
		self.char_variants = char_variants
		self.char_parts = char_parts
		self.vectors = vectors
		self.widths = widths
		self.heights = heights
		self.ratios = ratios

		self.char_records = char_records
		self.char_wholes = char_wholes
		self.tree = tree

		self.normal_dim =  normal_size, normal_size
		self.size_factor = 0.15 # width/height (in EM) below which a component is ignored
		self.distance_factor = 0.10 # distance (in EM) of small components from main components
		self.k = 20 # k best for classification
		self.vector_diff = 2 # how much worse vectors within best k still considered,
				# as factor of distance of best vector
		self.ratio_diff = 0.1 # what difference in angle between aspect ratios still considered, 
				# must be value between 0 and 1
		self.size_diff = 0.5 # what difference in height considered, 
				# must be value between 0 and 1
		self.composite_diff = 0.2 # difference between coordinates in components still considered,
				# must be value between 0 and 1

	def _compress(self):
		if not isinstance(self.chars, np.ndarray):
			self.chars = np.array(self.chars, dtype='U1')
		if not isinstance(self.char_variants, np.ndarray):
			self.char_variants = np.array(self.char_variants, dtype='int8')
		if not isinstance(self.char_parts, np.ndarray):
			self.char_parts = np.array(self.char_parts, dtype='int8')
		if not isinstance(self.vectors, np.ndarray):
			self.vectors = np.stack(self.vectors, axis=0)
		if not isinstance(self.widths, np.ndarray):
			self.widths = np.array(self.widths, dtype='float16')
		if not isinstance(self.heights, np.ndarray):
			self.heights = np.array(self.heights, dtype='float16')
		if not isinstance(self.ratios, np.ndarray):
			self.ratios = np.array(self.ratios, dtype='float16')

	def add_vector(self, ch, variant, part_index, vector, segment, font_size):
		w = segment.w / font_size
		h = segment.h / font_size
		r = segment.w / segment.h
		self.chars.append(ch)
		self.char_variants.append(variant)
		self.char_parts.append(part_index)
		self.vectors.append(vector)
		self.widths.append(w)
		self.heights.append(h)
		self.ratios.append(r)

	def add_vectors(self, ch, variant, whole_vector, parts, font_size):
		if whole_vector is None:
			return
		biggest_vector, biggest_segment = parts[0]
		if len(parts) > 1:
			for i, (vector, segment) in enumerate(parts):
				self.add_vector(ch, variant, i, vector, segment, font_size)
			self.char_wholes[(ch,variant)] = len(self.chars)
			self.add_vector(ch, variant, -1, whole_vector, biggest_segment, font_size)
			if not all(biggest_segment.includes(segment) for _,segment in parts[1:]): 
				self.char_records[(ch,variant)] = [(s.x, s.y, s.w, s.h) for (_, s) in parts]
		else:
			self.add_vector(ch, variant, -1, biggest_vector, biggest_segment, font_size)
		
	@staticmethod
	def from_font(font_path=None, font_size=96, normal_size=20, threshold=160):
		if font_path:
			font = ImageFont.truetype(font_path, font_size)
		else:
			with resources.files('hieropy.resources').joinpath(HIERO_FONT_FILENAME).open('rb') as f:
				font = ImageFont.truetype(f, font_size)
		converter = ImageUniConverter(normal_size, threshold, [], [], [], [], [], [], [], {}, {}, None)
		for ch in all_chars():
			if ch in ocr_omit():
				continue
			whole_vector, parts = converter.char_to_vectors(font, ch, font_size)
			converter.add_vectors(ch, 0, whole_vector, parts, font_size)
		converter.tree = KDTree(converter.vectors)
		return converter

	@staticmethod
	def from_exemplars(path, normal_size=20, threshold=160):
		converter = ImageUniConverter(normal_size, threshold, [], [], [], [], [], [], [], {}, {}, None)
		for filename in os.listdir(path):
			namematch = re.fullmatch(r'(\d+)-(\d+)-(\d+)\.(png|PNG)', filename)
			if not namematch:
				continue
			codepoint = namematch.group(1)
			ch = chr(int(codepoint, 16))
			if ch in ocr_omit():
				continue
			variant = int(namematch.group(2))
			height = int(namematch.group(3))
			image_path = os.path.join(path, filename)
			image = Image.open(image_path)
			_, h = image.size
			font_size = h * 100 / height
			whole_vector, parts = converter.image_to_vectors(image, font_size)
			converter.add_vectors(ch, variant, whole_vector, parts, font_size)
		converter.tree = KDTree(converter.vectors)
		return converter

	def dump(self, path):
		self._compress()
		with open(path, 'wb') as f:
			pickle.dump({field: getattr(self, field) for field in ImageUniConverter.fields}, f)

	@staticmethod
	def load(path):
		with open(path, 'rb') as f:
			obj = pickle.load(f)
		if not isinstance(obj, dict) or not set(ImageUniConverter.fields).issubset(obj.keys()):
			raise ValueError('Invalid ImageUniConverter file')
		return ImageUniConverter(*[obj[field] for field in ImageUniConverter.fields])

	def char_to_vectors(self, font, ch, font_size):
		image = self.char_to_image(font, ch, font_size)
		if image:
			return self.image_to_vectors(image, font_size)
		else:
			return None, []

	def image_to_vectors(self, image, font_size):
		w, h = image.size
		components = image_to_components(image, self.threshold)
		components = merge_components_from_small(w, h, components, \
				self.size_factor, self.distance_factor, font_size)
		segments = [Segment.from_component(c) for c in components] 
		vectors = [(self.image_to_vector(s.image), s) for s in segments]
		vectors = sorted(vectors, key=lambda v: v[1].area(), reverse=True)
		return self.image_to_vector(image), vectors

	def char_to_image(self, font, ch, font_size):
		padding = round(font_size // 3)
		canvas_dim = font_size + 2 * padding, font_size + 2 * padding
		canvas = Image.new('L', canvas_dim, color='white')
		draw = ImageDraw.Draw(canvas)
		draw.text((padding, padding), ch, font=font, fill='black')
		inverted = ImageOps.invert(canvas)
		bbox = inverted.getbbox()
		if not bbox:
			return None
		return canvas.crop(bbox)

	def image_to_vector(self, image):
		resized = image.resize(self.normal_dim, resample=Image.Resampling.LANCZOS)
		return np.asarray(resized).flatten()

	def convert_line(self, image, direction=None, threshold=None, em=None):
		image = image.convert('L')
		w, h = image.size
		if direction == None:
			direction = 'vlr' if w < h else 'hlr'
		if threshold == None:
			threshold = self.threshold
		if direction[0] == 'h':
			componentss = image_to_components_chunked_hor(image, threshold)
		else:
			componentss = image_to_components_chunked_ver(image, threshold)
		if em is None:
			em = components_to_em([p for c in componentss for p in c])
		componentss = [merge_components_from_small(w, h, c, \
				self.size_factor, self.distance_factor, em) for c in componentss]
		componentss = [self.merge_components_by_proximity(w, h, c, em) for c in componentss]
		segments = [Segment.from_component(c) for components in componentss for c in components]
		classifications = [self.classify_segment(s, em) for s in segments]
		segments, classifications = self.join_segments_by_inclusion(segments, classifications)
		segments, classifications = self.join_segments_by_common_character(segments, classifications)
		tokens = []
		for j, (s, (_, indexes)) in enumerate(zip(segments, classifications)):
			next_token = None
			for i in indexes:
				ch = self.chars[i]
				part = self.char_parts[i]
				if part < 0:
					lit = Literal(ch, 0, False, 0)
					next_token = GroupAndToken(lit, s.x, s.y, s.w, s.h)
					break
			if next_token:
				tokens.append(next_token)
			else:
				dists = []
				for i in indexes:
					ch = self.chars[i]
					variant = self.char_variants[i]
					part_height = self.heights[i]
					whole = self.char_wholes[(ch,variant)]
					vec1 = self.vectors[whole]
					whole_height = self.heights[whole]
					vec2 = self.image_to_vector(s.image)
					if part_height == whole_height:
						dists.append(vector_diff(vec1, vec2))
					else:
						dists.append(sys.maxsize)
				best_index, best_dist = min(zip(indexes, dists), key=lambda pair: pair[1])
				if best_dist != sys.maxsize:
					lit = Literal(self.chars[best_index], 0, False, 0)
					tokens.append(GroupAndToken(lit, s.x, s.y, s.w, s.h))
		parser = SpatialParser(direction=direction)
		return parser.best_fragment(tokens)

	def classify_segment(self, segment, em):
		segment_ratio = segment.w / segment.h
		dists, indexes = self.classify(segment.image, k=self.k)
		dists_prefix = [dist for dist in dists if dist <= dists[0] * self.vector_diff]
		indexes_prefix = indexes[:len(dists_prefix)]
		indexes_prefix = self.filter_by_ratio(indexes_prefix, segment_ratio)
		indexes_prefix = self.filter_by_size(indexes_prefix, segment.h / em)
		return dists_prefix, indexes_prefix

	def classify(self, image, k=1):
		vector = self.image_to_vector(image)
		return self.tree.query(vector, k=k)

	def filter_by_ratio(self, indexes, ratio):
		filtered = []
		for i in indexes:
			if normal_angle_diff(self.ratios[i], ratio) < self.ratio_diff:
				filtered.append(i)
		return filtered if len(filtered) > 0 else indexes[:1]

	def filter_by_size(self, indexes, height):
		filtered = []
		for i in indexes:
			if min(self.heights[i] / height, height / self.heights[i]) >= self.size_diff:
				filtered.append(i)
		return filtered if len(filtered) > 0 else indexes[:1]

	def join_segments_by_inclusion(self, segments, classifications):
		while True:
			joinings = []
			for i in range(len(segments)):
				dists, indexes = classifications[i]
				best_dist = [dists[cl] for cl in range(len(indexes)) if self.char_parts[indexes[cl]] < 0]
				for index in indexes:
					ch, ch_variant = self.chars[index], self.char_variants[index]
					whole = self.char_wholes.get((ch,ch_variant))
					if whole is not None:
						char_vec = self.vectors[whole]
						joining = self.make_joining_by_inclusion(segments, classifications, char_vec, i, whole)
						if len(joining.indexes) > 1:
							joinings.append(joining)
			if len(joinings) > 0:
				best_joining = max(joinings, key=lambda j: len(j.indexes))
				segments, classifications = joinings[0].apply(segments, classifications)
			else:
				break
		return segments, classifications

	def make_joining_by_inclusion(self, segments, classifications, char_vec, i, whole):
		joined_segment = segments[i]
		joined_vec = self.image_to_vector(joined_segment.image)
		joined_dist = vector_diff(joined_vec, char_vec)
		joined_indexes = []
		for j, segment in enumerate(segments):
			if j != i and joined_segment.includes(segment):
				joined_segment_new = Segment.merge(joined_segment, segment)
				joined_vec = self.image_to_vector(joined_segment_new.image)
				joined_dist_new = vector_diff(joined_vec, char_vec)
				if joined_dist_new <= joined_dist:
					joined_segment = joined_segment_new 
					joined_dist = joined_dist_new
					joined_indexes.append(j)
		return Joining([i] + joined_indexes, joined_dist, whole)

	def join_segments_by_common_character(self, segments, classifications):
		while True:
			chars = defaultdict(list)
			for segment_num, (_, indexes) in enumerate(classifications):
				for index in indexes:
					ch = self.chars[index]
					variant = self.char_variants[index]
					part_num = self.char_parts[index]
					if part_num >= 0:
						chars[(ch,variant)].append((segment_num, part_num))
			joinings = []
			for pair, parts in chars.items():
				char_parts = self.char_records.get(pair)
				if char_parts:
					whole = self.char_wholes.get(pair)
					if len(set(p for _, p in parts)) == len(char_parts):
						for part_indexes in list(permutations(range(len(parts)), len(char_parts))):
							part_nums = [parts[i][1] for i in part_indexes]
							segment_nums = [parts[i][0] for i in part_indexes]
							if part_nums == list(range(len(char_parts))) and \
										len(set(segment_nums)) == len(segment_nums):
								segment_nums = [parts[i][0] for i in part_indexes]
								segments_joined = [segments[i].rectangle() for i in segment_nums]
								if self.consistent_segments(segments_joined, char_parts):
									joining = Joining(segment_nums, 0, whole)
									joinings.append(joining)
			if len(joinings) > 0:
				best_joining = max(joinings, key=lambda j: len(j.indexes))
				segments, classifications = joinings[0].apply(segments, classifications)
			else:
				break
		return segments, classifications

	def consistent_segments(self, segments1, segments2):
		segments1, ratio1 = normalize_rectangles(segments1)
		segments2, ratio2 = normalize_rectangles(segments2)
		if normal_angle_diff(ratio1, ratio2) > self.ratio_diff:
			return False
		for (x1, y1, w1, h1), (x2, y2, w2, h2) in zip(segments1, segments2):
			x_min_diff = abs(x1 - x2)
			y_min_diff = abs(y1 - y2)
			x_max_diff = abs(x1 + w1 - x2 - w2)
			y_max_diff = abs(y1 + h1 - y2 - h2)
			return x_min_diff < self.composite_diff and y_min_diff < self.composite_diff and \
					x_max_diff < self.composite_diff and y_max_diff < self.composite_diff

	def merge_components_by_proximity(self, w, h, components, em):
		if len(components) <= 2:
			return components
		max_extended = math.ceil(em * self.distance_factor)
		classes = find_near_components(w, h, components, max_extended)
		new_components = []
		for cl in classes:
			while len(cl) > 0:
				best_subset = None
				best_dist = sys.maxsize
				for subset in chain.from_iterable(combinations(cl, r) for r in range(1, len(cl)+1)):
					joint = [p for i in subset for p in components[i]]
					image, _, _ = component_to_image(joint)
					dist = self.classify(image)[0]
					if dist < best_dist:
						best_subset = subset
						best_dist = dist
				new_components.append([p for i in best_subset for p in components[i]])
				cl = cl - set(best_subset)
		return new_components

class Segment:
	def __init__(self, image, x, y):
		self.image = image
		self.x = x
		self.y = y
		self.w, self.h = image.size

	def rectangle(self):
			return (self.x, self.y, self.w, self.h)

	def area(self):
		return self.w * self.h

	def includes(self, other):
		return self.x <= other.x and other.x + other.w <= self.x + self.w and \
				self.y <= other.y and other.y + other.h <= self.y + self.h

	@staticmethod
	def from_component(component):
		image, x_offset, y_offset = component_to_image(component)
		return Segment(image, x_offset, y_offset)

	@staticmethod																	
	def merge(segment1, segment2):													 
		x_min = min(segment1.x, segment2.x)											
		x_max = max(segment1.x + segment1.w, segment2.x + segment2.w)				
		y_min = min(segment1.y, segment2.y)											
		y_max = max(segment1.y + segment1.h, segment2.y + segment2.h)				
		w = x_max - x_min															
		h = y_max - y_min															
		image1 = Image.new(mode='L', size=(w,h), color='white')
		image2 = Image.new(mode='L', size=(w,h), color='white')
		image1.paste(segment1.image, (segment1.x-x_min, segment1.y-y_min))				
		image2.paste(segment2.image, (segment2.x-x_min, segment2.y-y_min))				
		image = ImageChops.darker(image1, image2)											
		return Segment(image, x_min, y_min) 

def component_to_image(component):
	x_offset = min([x for x,_,_ in component])
	x_max = max([x for x,_,_ in component])
	y_offset = min([y for _,y,_ in component])
	y_max = max([y for _,y,_ in component])
	w = x_max - x_offset + 1
	h = y_max - y_offset + 1
	image = Image.new('L', (w, h), color='white')
	for x, y, p in component:
		image.putpixel((x-x_offset,y-y_offset), p)
	return image, x_offset, y_offset

def component_from(image, visited, x, y, threshold):
	component = []
	w, h = image.size
	to_visit = [(x,y)]
	while len(to_visit) > 0:
		(x1,y1) = to_visit.pop()
		if 0 <= x1 and x1 < w and 0 <= y1 and y1 < h and \
				image.getpixel((x1,y1)) < threshold and not visited[x1,y1]:
			visited[x1,y1] = True
			component.append((x1, y1, image.getpixel((x1,y1))))
			for x_diff in [-1,0,1]:
				for y_diff in [-1,0,1]:
					if (x_diff, y_diff) != (0, 0):
						to_visit.append((x1+x_diff, y1+y_diff))
	return component
			
def image_to_components(image, threshold):
	w, h = image.size
	visited = np.zeros((w, h), dtype=bool)
	components = []
	for x in range(w):
		for y in range(h):
			component = component_from(image, visited, x, y, threshold)
			if len(component) > 0:
				components.append(component)
	return components

def image_to_components_chunked_hor(image, threshold):
	w, h = image.size
	visited = np.zeros((w, h), dtype=bool)
	componentss = []
	components = []
	for x in range(w):
		if empty_column(image, threshold, x):
			if len(components) > 0:
				componentss.append(components)
				components = []
		for y in range(h):
			component = component_from(image, visited, x, y, threshold)
			if len(component) > 0:
				components.append(component)
	if len(components) > 0:
		componentss.append(components)
	return componentss

def image_to_components_chunked_ver(image, threshold):
	w, h = image.size
	visited = np.zeros((w, h), dtype=bool)
	componentss = []
	components = []
	for y in range(h):
		if empty_row(image, threshold, y):
			if len(components) > 0:
				componentss.append(components)
				components = []
		for x in range(w):
			component = component_from(image, visited, x, y, threshold)
			if len(component) > 0:
				components.append(component)
	if len(components) > 0:
		componentss.append(components)
	return componentss

def empty_column(image, threshold, x):
	for y in range(0, image.size[1]):
		if image.getpixel((x,y)) < threshold:
			return False
	return True

def empty_row(image, threshold, y):
	for x in range(0, image.size[0]):
		if image.getpixel((x,y)) < threshold:
			return False
	return True

def merge_components_from_small(w, h, components, size_factor, extend_factor, em):
	numbers_large = np.full((w, h), -1)
	numbers_small = np.full((w, h), -1)
	min_size, max_extend = em * size_factor, em * extend_factor
	components_large = []
	components_small = []
	for component in components:
		if max(*component_size(component)) >= min_size:
			for p in component:
				numbers_large[p[0], p[1]] = len(components_large)
			components_large.append(component)
		else:
			for p in component:
				numbers_small[p[0], p[1]] = len(components_small)
			components_small.append(component)
	extend = 1
	smalls = set(range(len(components_small)))
	while len(smalls) > 0 and extend <= max_extend:
		small, merge_large, merge_small = \
				find_common_point2(w, h, numbers_large, numbers_small, smalls, components_small, extend)
		if small is None:
			extend += 1
		elif merge_large is not None:
			for p in components_small[small]:
				numbers_small[p[0], p[1]] = -1
				numbers_large[p[0], p[1]] = merge_large
			components_large[merge_large].extend(components_small[small])
			smalls.remove(small)
		elif merge_small is not None:
			for p in components_small[small]:
				numbers_small[p[0], p[1]] = merge_small
			components_small[merge_small].extend(components_small[small])
			smalls.remove(small)
	components_small = [components_small[i] for i in smalls]
	return components_large + [c for c in components_small if max(*component_size(c)) >= min_size]

def component_size(component):
	return max(p[0] for p in component) - min(p[0] for p in component), \
			max(p[1] for p in component) - min(p[1] for p in component)

def components_to_em(components):
	return max([component_size(c)[0] for c in components] + \
					[component_size(c)[1] for c in components], default=0)

def find_common_point1(w, h, numbers, components, extend):
	pairs = set()
	for i in range(len(components)):
		points = square_around_each_point(w, h, components[i], extend)
		for p in points:
			if numbers[p] >= 0 and numbers[p] != i:
				pairs.add((i, numbers[p].item()))
	return pairs

def find_common_point2(w, h, numbers_large, numbers_small, smalls, components_small, extend):
	for small in smalls:
		points = square_around_each_point(w, h, components_small[small], extend)
		for p in points:
			if numbers_large[p] >= 0:
				return small, numbers_large[p], None
			elif numbers_small[p] >= 0 and numbers_small[p] != small:
				return small, None, numbers_small[p],
	return None, None, None

def square_around_each_point(w, h, component, extend):
	return [p2 for p1 in component for p2 in square_around_point(w, h, p1[0], p1[1], extend)]

def square_around_point(w, h, x, y, extend):
	points = []
	for diff in range(-extend, extend):
		if in_area(x + diff, y - extend, w, h):
			points.append((x + diff, y - extend))
		if in_area(x + extend, y + diff, w, h):
			points.append((x + extend, y + diff))
		if in_area(x - diff, y + extend, w, h):
			points.append((x - diff, y + extend))
		if in_area(x - extend, y - diff, w, h):
			points.append((x - extend, y - diff))
	return points

def in_area(x, y, w, h):
	return 0 <= x and x < w and 0 <= y and y < h 

def vector_diff(vec1, vec2):
	return np.linalg.norm(vec1.astype(np.float64) - vec2.astype(np.float64))

# Candidate of segments to be joined from the classification of components on one line.
class Joining:
	def __init__(self, indexes, distance, whole):
		"""
		indexes: indexes in components which may be joined together
		distance: between joined segment and whole character
		whole: index of whole character in vector array
		"""
		self.indexes = indexes
		self.distance = distance
		self.whole = whole

	def apply(self, segments, classifications):
		segment = segments[self.indexes[0]]
		for i in self.indexes[1:]:
			segment = Segment.merge(segment, segments[i])
		zipped = list(zip(segments, classifications))
		new_segments = [s for i, s in enumerate(segments) if i not in self.indexes] + [segment]
		new_classifications = [c for i, c in enumerate(classifications) if i not in self.indexes] + \
				[([self.distance], [self.whole])]
		return new_segments, new_classifications

def normal_angle_diff(ratio1, ratio2):
	angle1 = math.atan2(ratio1, 1) / math.pi / 0.5
	angle2 = math.atan2(ratio2, 1) / math.pi / 0.5
	return abs(angle1 - angle2)

def normalize_rectangles(rectangles):
	if len(rectangles) == 0:
		return rectangles
	else:
		x, y, w, h = rectangles[0]
		x_min, y_min, x_max, y_max = x, y, x+w, y+h
		for x, y, w, h in rectangles[1:]:
			x_min, y_min = min(x_min, x), min(y_min, y)
			x_max, y_max = max(x_max, x+w), max(y_max, y+h)
		w_total, h_total = x_max - x_min, y_max - y_min 
		return [((x-x_min)/w_total, (y-y_min)/h_total, w/w_total, h/h_total) for (x, y, w, h) in rectangles], \
				w_total / h_total

def find_near_components(w, h, components, max_extend):
	numbers = np.full((w, h), -1)
	for i, component in enumerate(components):
		for p in component:
			numbers[p[0], p[1]] = i
	equiv_classes = {i:i for i in range(len(components))}
	extend = 1
	for extend in range(1, max_extend+1):
		if len(set(equiv_classes.values())) <= 1:
			break
		pairs = find_common_point1(w, h, numbers, components, extend)
		for i, j in pairs:
			cl1 = equiv_classes[i]
			cl2 = equiv_classes[j]
			equiv_classes = {k: (cl1 if cl0 in [cl1, cl2] else cl0) for k,cl0 in equiv_classes.items()}
	return [{i for i in equiv_classes.keys() if equiv_classes[i] == cl} for cl in set(equiv_classes.values())]
