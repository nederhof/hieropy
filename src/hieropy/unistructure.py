import sys
import math

from .options import *
from .uniconstants import *
from .uninames import char_to_name, char_to_name_cap
from .uniprops import allowed_rotations, rotation_adjustment, \
	char_to_insertions, char_to_places, InsertionAdjust, \
	char_to_overlay_ligature, overlay_to_ligature
from .printables import PlaneRestricted, PlaneExtended, OrthogonalHull, \
	PrintedPdf, PrintedSvg, PrintedPil, PrintedPilWithoutExtras, \
	em_size_of, open_rect

class Group:
	def init_scale(self):
		self.scale = 1
	def resize(self, f):
		self.scale *= f
	def fit(self, options, w, h):
		size = self.size(options)
		f = 1.0
		if w < math.inf and 0 < size[0]:
			f = min(f, w / size[0])
		if h < math.inf and 0 < size[1]:
			f = min(f, h / size[1])
		self.resize(f)
	def copy(self):
		self.map({ })

class Fragment(Group):
	# groups: list of Vertical/Horizontal/Enclosure/Basic/Overlay/Literal/Singleton/Blank/Lost
	def __init__(self, groups):
		super().__init__()
		self.groups = groups
	def __repr__(self):
		return '-'.join([repr(g) for g in self.groups])
	def __str__(self):
		return ''.join([str(g) for g in self.groups])
	def map(self, transformation):
		groups = [g.map(transformation) for g in self.groups]
		return transformation.get(Fragment, Fragment)(groups)
	def size(self, options):
		sizes = [g.size(options) for g in self.groups]
		if options.h():
			w = sum(s[0] for s in sizes) + options.sep * max(len(sizes)-1, 0)
			h = max([s[1] for s in sizes] + [options.linesize])
		else:
			w = max([s[0] for s in sizes] + [options.linesize])
			h = sum(s[1] for s in sizes) + options.sep * max(len(sizes)-1, 0)
		return w, h
	def format(self, options):
		for g in self.groups:
			g.init_scale()
		if options.h():
			for g in self.groups:
				g.fit(options, math.inf, options.linesize)
			x0 = options.hmargin
			x = x0 + options.sep / 2
			y0 = options.vmargin
			y1 = y0 + options.sep / 2
			y2 = y1 + options.linesize
			y3 = y2 + options.sep / 2
			for i, group in enumerate(self.groups):
				x1 = x + group.size(options)[0]
				if i < len(self.groups)-1 or options.separated:
					x2 = x1 + options.sep / 2
				else:
					x2 = options.hmargin + self.size(options)[0] + options.sep
				group.format(options, x0, x, x1, x2, y0, y1, y2, y3)
				if options.separated:
					x0 = 0
					x = options.sep / 2
				else:
					x0 = x2
					x = x1 + options.sep
		else:
			for g in self.groups:
				g.fit(options, options.linesize, math.inf)
			x0 = options.hmargin
			x1 = x0 + options.sep / 2
			x2 = x1 + options.linesize
			x3 = x2 + options.sep / 2
			y0 = options.vmargin
			print(y0)
			y = y0 + options.sep / 2
			for i, group in enumerate(self.groups):
				y1 = y + group.size(options)[1]
				if i < len(self.groups)-1 or options.separated:
					y2 = y1 + options.sep / 2
				else:
					y2 = options.vmargin + self.size(options)[1] + options.sep
				group.format(options, x0, x1, x2, x3, y0, y, y1, y2)
				if options.separated:
					y0 = 0
					y = options.sep / 2
				else:
					y0 = y2
					y = y1 + options.sep
	def print(self, options):
		self.format(options)
		size = self.size(options)
		if options.separated:
			printeds = []
			w_accum = 0
			h_accum = 0
			for i, g in enumerate(self.groups):
				sub_size = g.size(options)
				if options.h():
					width = sub_size[0] + options.sep
					if i == 0:
						width += options.hmargin
					if i == len(self.groups) - 1:
						width += options.hmargin
					height = size[1] + options.sep + 2 * options.vmargin
				if options.v():
					width = size[0] + options.sep + 2 * options.hmargin
					height = sub_size[1] + options.sep
					if i == 0:
						height += options.vmargin
					if i == len(self.groups) - 1:
						height += options.vmargin
				match options.imagetype:
					case 'pdf':
						printed = PrintedPdf(width, height, w_accum, h_accum, options)
					case 'svg':
						printed = PrintedSvg(width, height, w_accum, h_accum, options)
					case _:
						printed = PrintedPil(width, height, w_accum, h_accum, options)
				g.print(options, printed)
				printeds.append(printed)
				if options.h():
					w_accum += printed.width()
				else:
					h_accum += printed.height()
			return printeds
		else:
			width = size[0] + options.sep + 2 * options.hmargin
			height = size[1] + options.sep + 2 * options.vmargin
			match options.imagetype:
				case 'pdf':
					printed = PrintedPdf(width, height, 0, 0, options)
				case 'svg':
					printed = PrintedSvg(width, height, 0, 0, options)
				case _:
					printed = PrintedPil(width, height, 0, 0, options)
			printed.add_text(str(self))
			for g in self.groups:
				g.print(options, printed)
			return printed

class Vertical(Group):
	# groups: list of Horizontal/Enclosure/Basic/Overlay/Literal/Blank/Lost
	def __init__(self, groups):
		super().__init__()
		self.groups = groups
	def __repr__(self):
		return ':'.join([repr(g) for g in self.groups])
	def __str__(self):
		return VER.join([str(g) for g in self.groups])
	def map(self, transformation):
		groups = [g.map(transformation) for g in self.groups]
		return transformation.get(Vertical, Vertical)(groups)
	def init_scale(self):
		super().init_scale()
		for g in self.groups:
			g.init_scale()
	def size(self, options):
		sizes = [g.size(options) for g in self.groups]
		w = max(s[0] for s in sizes)
		h = sum(s[1] for s in sizes) + self.scale * options.sep * (len(sizes)-1)
		return w, h
	def net_height(self, options):
		return sum(Vertical.net_height_of(g, options) for g in self.groups)
	def resize(self, f):
		super().resize(f)
		for g in self.groups:
			g.resize(f)
	def fit(self, options, w, h):
		for g in self.groups:
			Vertical.fit_proper_groups(g, options, 1, math.inf)
		super().fit(options, w, h)
	def format(self, options, x0, x1, x2, x3, y0, y1, y2, y3):
		net_height = self.net_height(options)
		buf = ((y2-y1) - net_height) / (len(self.groups)-1 + self.nested_vertical_spaces())
		for i, group in enumerate(self.groups):
			if i < len(self.groups)-1:
				h = Vertical.net_height_of(group, options)
				y4 = y1 + h + Vertical.nested_vertical_spaces_of(group) * buf
				y5 = y4 + buf / 2
			else:
				y4 = y2
				y5 = y3
			group.format(options, x0, x1, x2, x3, y0, y1, y4, y5)
			y0 = y5
			y1 = y4 + buf
	def nested_vertical_spaces(self):
		return sum(Vertical.nested_vertical_spaces_of(g) for g in self.groups)
	@staticmethod
	def fit_proper_groups(group, options, w, h):
		if isinstance(group, Horizontal):
			proper_groups = group.proper_groups()
			if len(proper_groups) == 1:
				proper_group = proper_groups[0]
				if isinstance(proper_group, Vertical):
					Vertical.fit_proper_groups(proper_group, options, w, h)
					return
		group.fit(options, w, h)
	@staticmethod
	def nested_vertical_spaces_of(group):
		if isinstance(group, Horizontal):
			proper_groups = group.proper_groups()
			if len(proper_groups) == 1:
				proper_group = proper_groups[0]
				if isinstance(proper_group, Vertical):
					return len(proper_group.groups) -1
		return 0
	@staticmethod
	def net_height_of(group, options):
		if isinstance(group, Horizontal):
			proper_groups = group.proper_groups()
			if len(proper_groups) == 1:
				proper_group = proper_groups[0]
				if isinstance(proper_group, Vertical):
					return Vertical.net_height_of(proper_group, options)
		elif isinstance(group, Vertical):
			return sum(Vertical.net_height_of(g, options) for g in group.groups)
		return group.size(options)[1]
	def print(self, options, printed):
		for i, group in enumerate(self.groups):
			if i > 0:
				printed.add_hidden(VER)
			group.print(options, printed)

class Horizontal(Group):
	# groups: list of Vertical/Enclosure/Basic/Overlay/Literal/Blank/Lost/BracketOpen/BracketClose
	def __init__(self, groups):
		super().__init__()
		self.groups = groups
	def __repr__(self):
		s = ''
		for i, group in enumerate(self.groups):
			if i > 0 and not isinstance(self.groups[i-1], BracketOpen) and not isinstance(group, BracketClose):
				s += '*'
			if isinstance(group, Vertical):
				s += '(' + repr(group) + ')'
			else:
				s += repr(group)
		return s
	def __str__(self):
		s = ''
		for i, group in enumerate(self.groups):
			if i > 0 and not isinstance(self.groups[i-1], BracketOpen) and not isinstance(group, BracketClose):
				s += HOR
			if isinstance(group, Vertical):
				s += BEGIN_SEGMENT + str(group) + END_SEGMENT
			else:
				s += str(group)
		return s
	def map(self, transformation):
		groups = [g.map(transformation) for g in self.groups]
		return transformation.get(Horizontal, Horizontal)(groups)
	def init_scale(self):
		super().init_scale()
		for g in self.groups:
			g.init_scale()
	def size(self, options):
		sizes = [g.size(options) for g in self.groups if not isinstance(g, (BracketOpen, BracketClose))]
		w = sum(s[0] for s in sizes) + self.scale * options.sep * (len(sizes)-1)
		h = max(s[1] for s in sizes)
		return w, h
	def net_width(self, options):
		return sum(g.size(options)[0] for g in self.groups \
			if not isinstance(g, (BracketOpen, BracketClose)))
	def resize(self, f):
		super().resize(f)
		for g in self.groups:
			g.resize(f)
	def fit(self, options, w, h):
		for g in self.groups:
			g.fit(options, math.inf, 1)
		super().fit(options, w, h)
	def format(self, options, x0, x1, x2, x3, y0, y1, y2, y3):
		proper_groups = self.proper_groups()
		if len(proper_groups) == 1:
			first = self.groups[0]
			last = self.groups[len(self.groups)-1]
			if isinstance(first, BracketOpen):
				first.format(options, x0, y0, x1-x0, y3-y0)
				x0 = x1
			if isinstance(last, BracketClose):
				last.format(options, x2, y0, x3-x2, y3-y0)
				x3 = x2
			proper_groups[0].format(options, x0, x1, x2, x3, y0, y1, y2, y3)
		else:
			net_width = self.net_width(options)
			buf = ((x2-x1) - net_width) / (len(proper_groups)-1)
			for i, group in enumerate(self.groups):
				if isinstance(group, BracketOpen):
					group.format(options, x0, y0, x1-x0, y3-y0)
					x0 = x1
				elif not isinstance(group, BracketClose):
					if i < len(self.groups)-1:
						x4 = x1 + group.size(options)[0]
						nex = self.groups[i+1]
						if isinstance(nex, BracketClose):
							nex.format(options, x4, y0, buf / 2, y3-y0)
							x5 = x4
							x6 = x5 + buf / 2
						else:
							x5 = x4 + buf / 2
							x6 = x5
					else:
						x4 = x2
						x5 = x3
						x6 = x5
					group.format(options, x0, x1, x4, x5, y0, y1, y2, y3)
					x0 = x6
					x1 = x4 + buf
	def proper_groups(self):
		return [g for g in self.groups if not isinstance(g, (BracketOpen, BracketClose))]
	def print(self, options, printed):
		for i, group in enumerate(self.groups):
			if i > 0 and not isinstance(self.groups[i-1], BracketOpen) and \
					not isinstance(group, BracketClose):
				printed.add_hidden(HOR)
			if isinstance(group, Vertical):
				printed.add_hidden(BEGIN_SEGMENT)
				group.print(options, printed)
				printed.add_hidden(END_SEGMENT)
			else:
				group.print(options, printed)

class Enclosure(Group):
	# typ: 'plain' or 'walled'
	# groups: list of Vertical/Horizontal/Enclosure/Basic/Overlay/Literal/Blank/Lost
	# delim_open: character/None
	# damage_open: 0 -- 15
	# delim_close: character/None
	# damage_close: 0 -- 15
	def __init__(self, typ, groups, delim_open, damage_open, delim_close, damage_close):
		super().__init__()
		self.typ = typ
		self.groups = groups
		self.delim_open = delim_open
		self.damage_open = damage_open
		self.delim_close = delim_close
		self.damage_close = damage_close
	def __repr__(self):
		params = []
		name = 'walled' if self.typ == 'walled' else 'boxed'
		if self.delim_open is not None:
			params.append('open=' + char_to_name_cap(self.delim_open))
		if self.delim_close is not None:
			params.append('close=' + char_to_name_cap(self.delim_close))
		params_str = ('[' + ','.join(params) + ']') if len(params) > 0 else ''
		content = '-'.join([repr(g) for g in self.groups])
		return name + params_str + '(' + content + ')'
	def __str__(self):
		s = ''
		if self.delim_open is not None:
			s += self.delim_open + num_to_damage(self.damage_open)
		s += BEGIN_WALLED_ENCLOSURE if self.typ == 'walled' else BEGIN_ENCLOSURE
		s += ''.join([str(g) for g in self.groups])
		s += END_WALLED_ENCLOSURE if self.typ == 'walled' else END_ENCLOSURE
		if self.delim_close is not None:
			s += self.delim_close + num_to_damage(self.damage_close)
		return s
	def map(self, transformation):
		groups = [g.map(transformation) for g in self.groups]
		return transformation.get(Enclosure, Enclosure)(self.typ, groups, \
			self.delim_open, self.damage_open, self.delim_close, self.damage_close)
	def init_scale(self):
		super().init_scale()
		for g in self.groups:
			g.init_scale()
	def size(self, options):
		if options.h():
			w = self.open_size(options)[0] + self.kern_open_size() + \
					self.inner_size(options)[0] + \
					self.kern_close_size() + self.close_size(options)[0]
			h = self.outline_size(options)[1]
		else:
			w = self.outline_size(options)[0]
			h = self.open_size(options)[1] + self.kern_open_size() + \
					self.inner_size(options)[1] + \
					self.kern_close_size() + self.close_size(options)[1]
		return w, h
	def inner_size(self, options):
		sizes = [g.size(options) for g in self.groups]
		if options.h():
			w = sum(s[0] for s in sizes) + self.scale * options.sep * len(sizes)
			h = max([s[1] for s in sizes] + [0])
		else:
			w = max([s[0] for s in sizes] + [0])
			h = sum(s[1] for s in sizes) + self.scale * options.sep * len(sizes)
		return w, h
	def open_size(self, options):
		ch = self.delim_open_rotated(options)
		size = em_size_of(ch, options, 1, 1, 0, False) if ch else (0, 0)
		w = self.scale * size[0]
		h = self.scale * size[1]
		return w, h
	def close_size(self, options):
		ch = self.delim_close_rotated(options)
		size = em_size_of(ch, options, 1, 1, 0, False) if ch else (0, 0)
		w = self.scale * size[0]
		h = self.scale * size[1]
		return w, h
	def kern_open_size(self):
		return self.scale * self.kern_open
	def kern_close_size(self):
		return self.scale * self.kern_close
	def delim_open_rotated(self, options):
		return self.delim_open if options.h() else rotate_char(self.delim_open)
	def delim_close_rotated(self, options):
		return self.delim_close if options.h() else rotate_char(self.delim_close)
	def outline_ch(self, options):
		ch = WALLED_OUTLINE if self.typ == 'walled' else OUTLINE
		return ch if options.h() else rotate_char(ch)
	def outline_size(self, options):
		size = em_size_of(self.outline_ch(options), options, 1, 1, 0, False)
		w = self.scale * size[0]
		h = self.scale * size[1]
		return w, h
	def resize(self, f):
		super().resize(f)
		for g in self.groups:
			g.resize(f)
	def fit(self, options, w, h):
		inner_space = 1.0 - 2 * self.thickness()
		for g in self.groups:
			if options.h():
				g.fit(options, math.inf, inner_space)
			else:
				g.fit(options, inner_space, math.inf)
		self.fit_open(options)
		self.fit_close(options)
		super().fit(options, w, h)
	def fit_open(self, options):
		if self.delim_open and len(self.groups) > 0:
			meas_options = MeasureOptions(options)
			meas_size = meas_options.fontsize
			w, h = self.open_size(meas_options)
			rect = Rectangle(0, 0, w, h)
			printed = PrintedPilWithoutExtras(meas_options, w, h)
			printed.add_sign(self.delim_open_rotated(meas_options), self.scale, 1, 1, 0, False, rect)
			group = self.groups[0]
			w_group, h_group = group.size(meas_options)
			if options.h():
				group.format(meas_options, 0, 0, w_group, w_group, 0, self.thickness(), h - self.thickness(), h)
				printed_group = PrintedPilWithoutExtras(meas_options, w_group, h)
				group.print(meas_options, printed_group)
				self.kern_open = - Enclosure.h_distance(printed.im, printed_group.im, \
					self.thickness() * meas_size, (h - self.thickness()) * meas_size) / meas_size
			else:
				group.format(meas_options, 0, self.thickness(), w - self.thickness(), w, 0, 0, h_group, h_group)
				printed_group = PrintedPilWithoutExtras(meas_options, w, h_group)
				group.print(meas_options, printed_group)
				self.kern_open = - Enclosure.v_distance(printed.im, printed_group.im, \
					self.thickness() * meas_size, (w - self.thickness()) * meas_size) / meas_size
		else:
			self.kern_open = 0
	def fit_close(self, options):
		if self.delim_close and len(self.groups) > 0:
			meas_options = MeasureOptions(options)
			meas_size = meas_options.fontsize
			w, h = self.close_size(meas_options)
			rect = Rectangle(0, 0, w, h)
			printed = PrintedPilWithoutExtras(meas_options, w, h)
			printed.add_sign(self.delim_close_rotated(meas_options), self.scale, 1, 1, 0, False, rect)
			group = self.groups[-1]
			w_group, h_group = group.size(meas_options)
			if options.h():
				group.format(meas_options, 0, 0, w_group, w_group, 0, self.thickness(), h - self.thickness(), h)
				printed_group = PrintedPilWithoutExtras(meas_options, w_group, h)
				group.print(meas_options, printed_group)
				self.kern_close = - Enclosure.h_distance(printed_group.im, printed.im, \
					self.thickness() * meas_size, (h - self.thickness()) * meas_size) / meas_size
			else:
				group.format(meas_options, 0, self.thickness(), w - self.thickness(), w, 0, 0, h_group, h_group)
				printed_group = PrintedPilWithoutExtras(meas_options, w, h_group)
				group.print(meas_options, printed_group)
				self.kern_close = - Enclosure.v_distance(printed_group.im, printed.im, \
					self.thickness() * meas_size, (w - self.thickness()) * meas_size) / meas_size
		else:
			self.kern_close = 0
	@staticmethod
	def h_distance(im1, im2, y_min, y_max):
		y_min = round(y_min)
		y_max = round(y_max)
		plane1 = PlaneRestricted(im1)
		plane2 = PlaneRestricted(im2)
		dist_min = im1.size[0] + im2.size[0]
		for y in range(y_min, y_max):
			r_most = plane1.rightmost_dark(0, im1.size[0]-1, y)
			l_most = plane2.leftmost_dark(0, im2.size[0]-1, y)
			if r_most and l_most:
				dist_min = min(dist_min, im1.size[0]-1 - r_most + l_most)
		if dist_min < im1.size[0] + im2.size[0]:
			return dist_min
		else:
			return 0
	@staticmethod
	def v_distance(im1, im2, x_min, x_max):
		x_min = round(x_min)
		x_max = round(x_max)
		plane1 = PlaneRestricted(im1)
		plane2 = PlaneRestricted(im2)
		dist_min = im1.size[1] + im2.size[1]
		for x in range(x_min, x_max):
			b_most = plane1.bottommost_dark(x, 0, im1.size[1]-1)
			t_most = plane2.topmost_dark(x, 0, im2.size[1]-1)
			if b_most and t_most:
				dist_min = min(dist_min, im1.size[1]-1 - b_most + t_most)
		if dist_min < im1.size[1] + im2.size[1]:
			return dist_min
		else:
			return 0
	def thickness(self):
		return self.scale * (WALLED_OUTLINE_THICKNESS if self.typ == 'walled' else OUTLINE_THICKNESS)
	def format(self, options, x0_encl, x1_encl, x2_encl, x3_encl, y0_encl, y1_encl, y2_encl, y3_encl):
		w_full, h_full = self.size(options)
		w_buf, h_buf = ((x2_encl-x1_encl) - w_full) / 2, ((y2_encl-y1_encl) - h_full) / 2
		w_open, h_open = self.open_size(options)
		w_close, h_close = self.close_size(options)
		w_outline, h_outline = self.outline_size(options)
		self.areas = []
		self.delim_open_rect = Rectangle(x1_encl + w_buf, y1_encl + h_buf, w_open, h_open)
		if options.h():
			self.delim_close_rect = Rectangle(x2_encl - w_buf - w_close, y1_encl + h_buf, w_close, h_close)
			if self.damage_open:
				shade_open_width = self.delim_open_rect.w + self.kern_open_size()
				self.areas.extend(damage_areas(self.damage_open, x0_encl, \
					self.delim_open_rect.x + shade_open_width / 2, self.delim_open_rect.x + shade_open_width, \
					y0_encl, self.delim_open_rect.y + self.delim_open_rect.h / 2, y3_encl))
			if self.damage_close:
				shade_close_width = self.delim_close_rect.w + self.kern_close_size()
				self.areas.extend(damage_areas(self.damage_close, \
					self.delim_close_rect.x - self.kern_close_size(), \
					self.delim_close_rect.x + self.delim_close_rect.w - shade_close_width / 2, x3_encl, \
					y0_encl, self.delim_close_rect.y + self.delim_close_rect.h / 2, y3_encl))
			x0 = self.delim_open_rect.x + self.delim_open_rect.w + self.kern_open_size()
			x1 = x0 + self.scale * options.sep / 2
			if self.delim_open is None:
				x0 = x0_encl
			for i, group in enumerate(self.groups):
				x2 = x1 + group.size(options)[0]
				x3 = x2 + self.scale * options.sep / 2 if i < len(self.groups)-1 else \
						x3_encl if self.delim_close is None else \
						self.delim_close_rect.x - self.kern_close_size()
				group.format(options, x0, x1, x2, x3, 
					y0_encl, y1_encl + h_buf + self.thickness(), y2_encl - h_buf - self.thickness(), y3_encl)
				x0 = x3
				x1 = x2 + self.scale * options.sep
		else:
			self.delim_close_rect = Rectangle(x1_encl + w_buf, y2_encl - h_buf - h_close, w_close, h_close)
			if self.damage_open:
				shade_open_height = self.delim_open_rect.h + self.kern_open_size()
				self.areas.extend(damage_areas(self.damage_open, \
					x0_encl, self.delim_open_rect.x + self.delim_open_rect.w / 2, x3_encl, y0_encl, \
					self.delim_open_rect.y + shade_open_height / 2, self.delim_open_rect.y + shade_open_height))
			if self.damage_close:
				shade_close_height = self.delim_close_rect.h + self.kern_close_size()
				self.areas.extend(damage_areas(self.damage_close, \
					x0_encl, self.delim_close_rect.x + self.delim_close_rect.w / 2, x3_encl,
					self.delim_close_rect.y - self.kern_close_size(), \
					self.delim_close_rect.y + self.delim_close_rect.h - shade_close_height / 2, y3_encl))
			y0 = self.delim_open_rect.y + self.delim_open_rect.h + self.kern_open_size()
			y1 = y0 + self.scale * options.sep / 2
			if self.delim_open is None:
				y0 = y0_encl
			for i, group in enumerate(self.groups):
				y2 = y1 + group.size(options)[1]
				y3 = y2 + self.scale * options.sep / 2 if i < len(self.groups)-1 else \
						y3_encl if self.delim_close is None else \
						self.delim_close_rect.y - self.kern_close_size()
				group.format(options, \
						x0_encl, x1_encl + w_buf + self.thickness(), x2_encl - w_buf - self.thickness(), x3_encl, \
						y0, y1, y2, y3)
				y0 = y3
				y1 = y2 + self.scale * options.sep
		self.outlines = []
		overlap = 0.02
		if len(self.groups) > 0:
			if options.h():
				w_net = (1 - overlap) * w_outline
				w_inner = self.delim_close_rect.x - \
					(self.delim_open_rect.x + self.delim_open_rect.w - overlap * w_outline)
				if w_inner > 0:
					n = max(1, math.floor(w_inner / w_net))
					scale_x = w_inner / (n * w_net)
					scale_y = 1
					x = self.delim_open_rect.x + self.delim_open_rect.w - overlap * w_outline
					y = self.delim_open_rect.y
					w = scale_x * w_outline
					h = h_outline
					for _ in range(n):
						outline = Rectangle(x, y, w, h)
						outline.scale_x = scale_x
						outline.scale_y = scale_y
						self.outlines.append(outline)
						x += scale_x * w_net
			else:
				h_net = (1 - overlap) * h_outline
				h_inner = self.delim_close_rect.y - \
					(self.delim_open_rect.y + self.delim_open_rect.h - overlap * h_outline)
				if h_inner > 0:
					n = max(1, math.floor(h_inner / h_net))
					scale_x = 1
					scale_y = h_inner / (n * h_net)
					x = self.delim_open_rect.x
					y = self.delim_open_rect.y + self.delim_open_rect.h - overlap * h_outline
					w = w_outline
					h = scale_y * h_outline
					for _ in range(n):
						outline = Rectangle(x, y, w, h)
						outline.scale_x = scale_x
						outline.scale_y = scale_y
						self.outlines.append(outline)
						y += scale_y * h_net
	def print(self, options, printed):
		ch_open = self.delim_open_rotated(options)
		ch_close = self.delim_close_rotated(options)
		x_as = None if options.h() else self.outline_ch(options)
		y_as = None if options.v() else self.outline_ch(options)
		if ch_open:
			printed.add_sign(ch_open, self.scale, 1, 1, 0, False, self.delim_open_rect, \
				unselectable=options.v(), x_as=x_as, y_as=y_as)
			if options.v():
				printed.add_hidden(self.delim_open)
			printed.add_hidden(num_to_damage(self.damage_open))
		printed.add_hidden(BEGIN_WALLED_ENCLOSURE if self.typ == 'walled' else BEGIN_ENCLOSURE)
		for g in self.groups:
			g.print(options, printed)
		printed.add_hidden(END_WALLED_ENCLOSURE if self.typ == 'walled' else END_ENCLOSURE)
		if ch_close:
			printed.add_sign(ch_close, self.scale, 1, 1, 0, False, self.delim_close_rect, \
				unselectable=options.v(), x_as=x_as, y_as=y_as)
			if options.v():
				printed.add_hidden(self.delim_close)
			printed.add_hidden(num_to_damage(self.damage_close))
		for out in self.outlines:
			printed.add_sign(self.outline_ch(options), self.scale, out.scale_x, out.scale_y, \
				0, False, out, unselectable=True)
		for area in self.areas:
			printed.add_shading(area)

class Basic(Group):
	# core: Overlay/Literal
	# ts/bs/te/be/m/t/b: Vertical/Horizontal/Enclosure/Basic/Overlay/Literal/Blank/Lost/None
	def __init__(self, core, insertions):
		super().__init__()
		self.core = core
		self.insertions = {place: insertions[place] for place in insertions if insertions[place] is not None}
		self.core.choose_alt_glyph(self.places())
	def places(self):
		return self.insertions.keys()
	def __repr__(self):
		s = repr(self.core)
		for place, control in zip(INSERTION_PLACES, INSERTION_CHARS):
			if place in self.insertions:
				s = 'insert[' + place + '](' + s + ',' + repr(self.insertions[place]) + ')'
		return s
	def __str__(self):
		s = str(self.core)
		for place, control in zip(INSERTION_PLACES, INSERTION_CHARS):
			if place in self.insertions:
				s += control + Basic.inserted_expression(self.insertions[place])
		return s
	def map(self, transformation):
		core = self.core.map(transformation)
		insertions = {place: self.insertions[place].map(transformation) for place in self.insertions}
		return transformation.get(Basic, Basic)(core, insertions)
	@staticmethod
	def is_bracketed_insert(g):
		return isinstance(g, (Vertical, Horizontal, Basic))
	@staticmethod
	def inserted_expression(g):
		return BEGIN_SEGMENT + str(g) + END_SEGMENT if Basic.is_bracketed_insert(g) else str(g)
	def init_scale(self):
		super().init_scale()
		self.core.init_scale()
		for place in self.insertions:
			self.insertions[place].init_scale()
	def size(self, options):
		size = self.core.size(options)
		w = size[0] * self.extension.w
		h = size[1] * self.extension.h
		return w, h
	def resize(self, f):
		super().resize(f)
		self.core.resize(f)
		for place in self.insertions:
			self.insertions[place].resize(f)
	def fit(self, options, w, h):
		meas_options = MeasureOptions(options)
		core_im = Basic.meas_printed_im(meas_options, self.core)
		core_w, core_h = core_im.size
		for place in self.insertions:
			adjustments = self.core.adjustments.get(place, InsertionAdjust())
			pos_x, pos_y = insertion_position(place, adjustments)
			ins_im = Basic.meas_printed_im(meas_options, self.insertions[place])
			hull, rect_init, ins_w, ins_h = \
					Basic.fit_inserted_hull(meas_options, core_im, core_w, core_h, ins_im, pos_x, pos_y)
			scale = min(1, rect_init.w / ins_w, rect_init.h / ins_h)
			rect, plane_x, plane_y, hull_x, hull_y = \
					Basic.fit_inserted_position(pos_x, pos_y, hull, rect_init, ins_w, ins_h, scale)
			core_plane = PlaneRestricted(core_im) if place == 'm' else PlaneExtended(core_im)
			scale, rect = Basic.fit_grow(hull, scale, rect, plane_x, plane_y, hull_x, hull_y, core_plane)
			ins = self.insertions[place]
			ins.resize(scale)
			ins.rect = (rect.x / core_w, rect.y / core_h, (rect.x + rect.w) / core_w, (rect.y + rect.h) / core_h)
		x0 = min(0, *[ins.rect[0] for ins in self.insertions.values()])
		y0 = min(0, *[ins.rect[1] for ins in self.insertions.values()])
		x1 = max(1, *[ins.rect[2] for ins in self.insertions.values()])
		y1 = max(1, *[ins.rect[3] for ins in self.insertions.values()])
		self.extension = Rectangle(-x0, -y0, x1-x0, y1-y0)
		super().fit(options, w, h)
	@staticmethod
	def meas_printed_im(meas_options, group):
		group.fit(meas_options, math.inf, math.inf)
		w, h = group.size(meas_options)
		group.format(meas_options, 0, 0, w, w, 0, 0, h, h)
		printed = PrintedPilWithoutExtras(meas_options, w, h)
		group.print(meas_options, printed)
		return printed.im
	@staticmethod
	def fit_inserted_hull(meas_options, core_im, core_w, core_h, ins_im, pos_x, pos_y):
		x_init = min(core_w-1, round(pos_x * core_w))
		y_init = min(core_h-1, round(pos_y * core_h))
		rect_init = open_rect(core_im, x_init, y_init)
		margin = round(meas_options.fontsize * meas_options.sep)
		hull = OrthogonalHull(ins_im, margin)
		margin_l = 0 if pos_x == 0 else -hull.x_min
		margin_r = 0 if pos_x == 1 else hull.x_max - (hull.w-1)
		margin_t = 0 if pos_y == 0 else -hull.y_min
		margin_b = 0 if pos_y == 1 else hull.y_max - (hull.h-1)
		ins_w = hull.w + margin_l + margin_r
		ins_h = hull.h + margin_t + margin_b
		return hull, rect_init, ins_w, ins_h
	@staticmethod
	def fit_inserted_position(pos_x, pos_y, hull, rect_init, ins_w, ins_h, scale):
		remainder_w = rect_init.w - scale * ins_w
		remainder_h = rect_init.h - scale * ins_h
		match pos_x:
			case 0: remainder_l, remainder_r = 0, remainder_w
			case 1: remainder_l, remainder_r = remainder_w, 0
			case _: remainder_l, remainder_r = remainder_w / 2, remainder_w / 2
		match pos_y:
			case 0: remainder_t, remainder_b = 0, remainder_h
			case 1: remainder_t, remainder_b = remainder_h, 0
			case _: remainder_t, remainder_b = remainder_h / 2, remainder_h / 2
		rect = Rectangle(rect_init.x + remainder_l, rect_init.y + remainder_t,
			rect_init.w - remainder_w, rect_init.h - remainder_h)
		match pos_x:
			case 0: plane_x, hull_x = rect.x, 0
			case 1: plane_x, hull_x = rect.x + rect.w, hull.w-1
			case _: plane_x, hull_x = rect.x + rect.w/2, hull.w/2
		match pos_y:
			case 0: plane_y, hull_y = rect.y, 0
			case 1: plane_y, hull_y = rect.y + rect.h, hull.h-1
			case _: plane_y, hull_y = rect.y + rect.h/2, hull.h/2
		return rect, plane_x, plane_y, hull_x, hull_y
	@staticmethod
	def fit_grow(hull, scale, rect, plane_x, plane_y, hull_x, hull_y, core_plane):
		incr_factor = 1.1
		min_scale = 0.15
		n_steps = math.ceil(-math.log(scale) / math.log(incr_factor))
		scalings = [scale * (1/scale) ** (i / n_steps) for i in range(1, n_steps+1)]
		for scale_new in scalings:
			disp = Basic.displacement(core_plane, hull, plane_x, plane_y, hull_x, hull_y, scale, scale_new)
			if disp is not None:
				plane_x += disp[0]
				plane_y += disp[1]
			elif scale > min_scale:
				break
			x = plane_x - hull_x * scale_new
			y = plane_y - hull_y * scale_new
			w = hull.w * scale_new
			h = hull.h * scale_new
			if scale >= 0.55 and (x <= -1 or y <= -1 or \
					x+w >= core_plane.im.size[0]+1 or y+h >= core_plane.im.size[1]+1):
				break
			scale = scale_new
			rect = Rectangle(x, y, w, h)
		return scale, rect
	@staticmethod
	def displacement(plane, hull, plane_x, plane_y, hull_x, hull_y, scale_prev, scale):
		boost = max(1, round(max(*plane.im.size) / 30))
		t, b, l, r = Basic.distances(plane, hull, plane_x, plane_y, hull_x, hull_y, scale_prev, scale)
		if l > 0:
			x = l if r >= l else None
		elif r < 0:
			x = r if l <= r else None
		else:
			x = 0
		if t > 0:
			y = t if b >= t else None
		elif b < 0:
			y = b if t <= b else None
		else:
			y = 0
		if x is None:
			if y is None:
				return None
			y_incr = y + boost if y > 0 else y - boost
			plane_x2 = plane_x
			plane_y2 = plane_y + y_incr
			t2, b2, l2, r2 = Basic.distances(plane, hull, plane_x2, plane_y2, hull_x, hull_y, scale_prev, scale)
			if l2 < 0 and r2 > 0 and t2 < 0 and b2 > 0:
				x = 0
				y = y_incr
			else:
				return None
		elif y is None:
			x_incr = x + boost if x > 0 else x - boost
			plane_x2 = plane_x + x_incr
			plane_y2 = plane_y
			t2, b2, l2, r2 = Basic.distances(plane, hull, plane_x2, plane_y2, hull_x, hull_y, scale_prev, scale)
			if l2 < 0 and r2 > 0 and t2 < 0 and b2 > 0:
				x = x_incr
				y = 0
			else:
				return None
		return x, y
	@staticmethod
	def distances(plane, hull, plane_x, plane_y, hull_x, hull_y, scale_prev, scale):
		t = -sys.maxsize
		b = sys.maxsize
		l = -sys.maxsize
		r = sys.maxsize
		for x in range(-hull.dist, hull.w + hull.dist):
			x_plane = round(plane_x + (x - hull_x) * scale)
			y_min = hull.y_mins[x]
			if y_min <= hull_y:
				dist_prev = (hull_y - y_min) * scale_prev
				dist = (hull_y - y_min) * scale
				y_plane = round(plane_y - dist)
				y_plane_min = round(plane_y - dist)
				y_plane_max = round(plane_y - dist_prev)
				bottommost = plane.bottommost_dark(x_plane, y_plane_min, y_plane_max)
				if bottommost is not None:
					t = max(t, bottommost - y_plane + 1)
			y_max = hull.y_maxs[x]
			if y_max >= hull_y:
				dist_prev = (y_max - hull_y) * scale_prev
				dist = (y_max - hull_y) * scale
				y_plane = round(plane_y + dist)
				y_plane_min = round(plane_y + dist_prev)
				y_plane_max = round(plane_y + dist)
				topmost = plane.topmost_dark(x_plane, y_plane_min, y_plane_max)
				if topmost is not None:
					b = min(b, topmost - y_plane - 1)
		for y in range(-hull.dist, hull.h + hull.dist):
			y_plane = round(plane_y + (y - hull_y) * scale)
			x_min = hull.x_mins[y]
			if x_min <= hull_x:
				dist_prev = (hull_x - x_min) * scale_prev
				dist = (hull_x - x_min) * scale
				x_plane = round(plane_x - dist)
				x_plane_min = round(plane_x - dist)
				x_plane_max = round(plane_x - dist_prev)
				rightmost = plane.rightmost_dark(x_plane_min, x_plane_max, y_plane)
				if rightmost is not None:
					l = max(l, rightmost - x_plane + 1)
			x_max = hull.x_maxs[y]
			if x_max >= hull_x:
				dist_prev = (x_max - hull_x) * scale_prev
				dist = (x_max - hull_x) * scale
				x_plane = round(plane_x + dist)
				x_plane_min = round(plane_x + dist_prev)
				x_plane_max = round(plane_x + dist)
				leftmost = plane.leftmost_dark(x_plane_min, x_plane_max, y_plane)
				if leftmost is not None:
					r = min(r, leftmost - x_plane - 1)
		return t, b, l, r
	def format(self, options, x0, x1, x2, x3, y0, y1, y2, y3):
		w_full, h_full = self.size(options)
		w_core, h_core = self.core.size(options)
		buf_x = ((x2-x1) - w_full) / 2
		buf_y = ((y2-y1) - h_full) / 2
		x1_net = x1 + buf_x
		y1_net = y1 + buf_y
		ext = self.extension
		x1_core = x1_net + ext.x * w_core
		x2_core = x1_core + w_core
		y1_core = y1_net + ext.y * h_core
		y2_core = y1_core + h_core
		self.core.format(options, x0, x1_core, x2_core, x3, y0, y1_core, y2_core, y3)
		for place in INSERTION_PLACES:
			if place in self.insertions:
				rect = self.insertions[place].rect
				x1_insert = x1_net + (ext.x + rect[0]) * w_core
				x2_insert = x1_net + (ext.x + rect[2]) * w_core
				x0_insert = x1_insert - self.scale * options.sep / 2
				x3_insert = x2_insert + self.scale * options.sep / 2
				y1_insert = y1_net + (ext.y + rect[1]) * h_core
				y2_insert = y1_net + (ext.y + rect[3]) * h_core
				y0_insert = y1_insert - self.scale * options.sep / 2
				y3_insert = y2_insert + self.scale * options.sep / 2
				self.insertions[place].format(options, x0_insert, x1_insert, x2_insert, x3_insert, \
					y0_insert, y1_insert, y2_insert, y3_insert)
	def print(self, options, printed):
		self.core.print(options, printed)
		for place, ins in self.insertions.items():
			printed.add_hidden(place_to_char(place))
			Basic.print_inserted_expression(options, printed, ins)
	@staticmethod
	def print_inserted_expression(options, printed, g):
		if Basic.is_bracketed_insert(g):
			printed.add_hidden(BEGIN_SEGMENT)
			g.print(options, printed)
			printed.add_hidden(END_SEGMENT)
		else:
			g.print(options, printed)

class Overlay(Group):
	# lits1/lits2: list of Literal
	def __init__(self, lits1, lits2):
		super().__init__()
		self.lits1 = lits1
		self.lits2 = lits2
		self.lig, self.swap = overlay_to_ligature(self.lits1, self.lits2)
		self.alt = self.lig
		self.adjustments = {}
	def __repr__(self):
		return 'overlay(' + '*'.join([repr(lit) for lit in self.lits1]) + ',' + \
						':'.join([repr(lit) for lit in self.lits2]) + ')'
	def __str__(self):
		if len(self.lits1) > 1:
			arg1 = BEGIN_SEGMENT + HOR.join([str(g) for g in self.lits1]) + END_SEGMENT
		else:
			arg1 = str(self.lits1[0])
		if len(self.lits2) > 1:
			arg2 = BEGIN_SEGMENT + VER.join([str(g) for g in self.lits2]) + END_SEGMENT
		else:
			arg2 = str(self.lits2[0])
		return arg1 + OVERLAY + arg2
	def map(self, transformation):
		lits1 = [lit.map(transformation) for lit in self.lits1]
		lits2 = [lit.map(transformation) for lit in self.lits2]
		return transformation.get(Overlay, Overlay)(lits1, lits2)
	def allowed_places(self):
		lig, _ = overlay_to_ligature(self.lits1, self.lits2)
		return char_to_places(lig.ch, 0, False) if lig else OVERLAY_INSERTION_PLACES
	def choose_alt_glyph(self, places):
		if self.lig:
			for ins in char_to_insertions(self.lig.ch):
				ins_places = ins.place_names()
				if all(place in ins_places for place in places):
					if ins.ch:
						self.alt = char_to_overlay_ligature(ins.ch)
					self.adjustments = ins.places
					return
		self.adjustments = {}
	def init_scale(self):
		super().init_scale()
		for g in self.lits1:
			g.init_scale()
		for g in self.lits2:
			g.init_scale()
	def size(self, options):
		if self.alt:
			return self.size_ligature(options)
		sizes1 = [g.size(options) for g in self.lits1]
		widths1 = [s[0] for s in sizes1]
		heights1 = [s[1] for s in sizes1]
		sizes2 = [g.size(options) for g in self.lits2]
		widths2 = [s[0] for s in sizes2]
		heights2 = [s[1] for s in sizes2]
		w = max(sum(widths1), max(widths2))
		h = max(max(heights1), sum(heights2))
		return w, h
	def size_ligature(self, options):
		size = em_size_of(self.alt.ch, options, 1, 1, 0, False)
		w = self.scale * size[0]
		h = self.scale * size[1]
		return w, h
	def resize(self, f):
		super().resize(f)
		for lit in self.lits1:
			lit.resize(f)
		for lit in self.lits2:
			lit.resize(f)
	def format(self, options, x0, x1, x2, x3, y0, y1, y2, y3):
		if self.alt:
			self.format_ligature(options, x0, x1, x2, x3, y0, y1, y2, y3)
			return
		width1 = sum(g.size(options)[0] for g in self.lits1)
		height2 = sum(g.size(options)[1] for g in self.lits2)
		buf_x = ((x2-x1) - width1) / 2
		buf_y = ((y2-y1) - height2) / 2
		x4 = x0
		x = x1 + buf_x
		for i, group in enumerate(self.lits1):
			if i < len(self.lits1)-1:
				x5 = x + group.size(options)[0]
				x6 = x5
			else:
				x5 = x2 - buf_x
				x6 = x3
			group.format(options, x4, x, x5, x6, y0, y1, y2, y3)
			x = x5
			x4 = x6
		y4 = y0
		y = y1 + buf_y
		for i, group in enumerate(self.lits2):
			if i < len(self.lits2)-1:
				y5 = y + group.size(options)[1]
				y6 = y5
			else:
				y5 = y2 - buf_y
				y6 = y3
			group.format(options, x0, x1, x2, x3, y4, y, y5, y6)
			y = y5
			y4 = y6
	def format_ligature(self, options, x0, x1, x2, x3, y0, y1, y2, y3):
		size = self.size(options)
		buf_x = ((x2-x1) - size[0]) / 2
		buf_y = ((y2-y1) - size[1]) / 2
		self.x = x1 + buf_x
		self.y = y1 + (((y2-y1) - size[1]) if options.align == 'bottom' else buf_y)
		self.w = size[0]
		self.h = size[1]
		self.areas = []
		for i, s in enumerate(self.alt.horizontal):
			damage = self.lits2[i].damage if self.swap else self.lits1[i].damage 
			x_min = x0 if i == 0 else self.x + s.x * self.w
			x_mid = self.x + (s.x + s.w / 2) * self.w
			x_max = x3 if i == len(self.alt.horizontal)-1 else self.x + (s.x + s.w) * self.w
			y_mid = self.y + (s.y + s.h / 2) * self.h
			self.areas.extend(damage_areas(damage, x_min, x_mid, x_max, y0, y_mid, y3))
		for i, s in enumerate(self.alt.vertical):
			damage = self.lits1[i].damage if self.swap else self.lits2[i].damage
			x_mid = self.x + (s.x + s.w / 2) * self.w
			y_min = y0 if i == 0 else self.y + s.y * self.h
			y_mid = self.y + (s.y + s.h / 2) * self.h
			y_max = y3 if i == len(self.alt.vertical)-1 else self.y + (s.y + s.h) * self.h
			self.areas.extend(damage_areas(damage, x0, x_mid, x3, y_min, y_mid, y_max))
	def print(self, options, printed):
		if self.alt:
			self.print_ligature(options, printed)
			return
		if len(self.lits1) > 1:
			printed.add_hidden(BEGIN_SEGMENT)
		for g in self.lits1:
			g.print(options, printed)
		if len(self.lits1) > 1:
			printed.add_hidden(END_SEGMENT)
		printed.add_hidden(OVERLAY)
		if len(self.lits2) > 1:
			printed.add_hidden(BEGIN_SEGMENT)
		for g in self.lits2:
			g.print(options, printed)
		if len(self.lits2) > 1:
			printed.add_hidden(END_SEGMENT)
	def print_ligature(self, options, printed):
		printed.add_hidden(str(self))
		printed.add_sign(self.alt.ch, self.scale, 1, 1, 0, False, self, unselectable=True)
		for area in self.areas:
			printed.add_shading(area)

class Literal(Group):
	# ch: character
	# vs: 0 -- 7
	# mirror: Boolean
	# damage: 0 -- 15
	def __init__(self, ch, vs, mirror, damage):
		super().__init__()
		self.ch = ch
		self.alt = ch
		self.adjustments = {}
		self.vs = vs
		self.mirror = mirror
		self.damage = damage
	def __repr__(self):
		params = []
		if self.mirror:
			params.append('mirror')
		if self.damage > 0:
			params.append(str(self.damage))
		params_str = ('[' + ','.join(params) + ']') if len(params) > 0 else ''
		return char_to_name(self.ch) + params_str
	def __str__(self):
		return self.ch + num_to_variation(self.vs) + (MIRROR if self.mirror else '') + num_to_damage(self.damage)
	def map(self, transformation):
		return transformation.get(Literal, Literal)(self.ch, self.vs, self.mirror, self.damage)
	def allowed_places(self):
		return char_to_places(self.ch, self.rotation_coarse(), self.mirror)
	def choose_alt_glyph(self, places):
		insertions = char_to_insertions(self.ch, self.mirror)
		rot = self.rotation_coarse()
		for ins in insertions:
			ins_places = ins.place_names()
			if all(place in ins_places for place in places) and rot == ins.rotation():
				if ins.ch:
					self.alt = ins.ch
				self.adjustments = ins.places
				return
		self.adjustments = {}
	def size(self, options):
		size = em_size_of(self.alt, options, 1, 1, self.rotation(), self.mirror)
		w = self.scale * size[0]
		h = self.scale * size[1]
		return w, h
	def rotation_coarse(self):
		return num_to_rotate(self.vs)
	def rotation(self):
		rot = self.rotation_coarse()
		if rot in allowed_rotations(self.ch):
			return rot + rotation_adjustment(self.ch, rot)
		return rot
	def format(self, options, x0, x1, x2, x3, y0, y1, y2, y3):
		size = self.size(options)
		buf_x = ((x2-x1) - size[0]) / 2
		buf_y = ((y2-y1) - size[1]) / 2
		self.x = x1 + buf_x
		self.y = y1 + (((y2-y1) - size[1]) if options.align == 'bottom' else buf_y)
		self.w = size[0]
		self.h = size[1]
		x_shade = self.x + self.w / 2
		y_shade = self.y + self.h / 2
		self.areas = damage_areas(self.damage, x0, x_shade, x3, y0, y_shade, y3)
	def print(self, options, printed):
		if self.alt == self.ch:
			printed.add_sign(self.ch, self.scale, 1, 1, self.rotation(), self.mirror, self)
		else:
			printed.add_sign(self.alt, self.scale, 1, 1, self.rotation(), self.mirror, self, unselectable=True)
			printed.add_hidden(self.ch)
		for area in self.areas:
			printed.add_shading(area)
		if self.vs:
			printed.add_hidden(num_to_variation(self.vs))
		if self.mirror:
			printed.add_hidden(MIRROR)
		if self.damage:
			printed.add_hidden(num_to_damage(self.damage))

class Singleton(Group):
	# ch: character
	# damage: 0 -- 15
	def __init__(self, ch, damage):
		super().__init__()
		self.ch = ch
		self.damage = damage
	def __repr__(self):
		params = []
		if self.damage > 0:
			params.append(str(self.damage))
		params_str = ('[' + ','.join(params) + ']') if len(params) > 0 else ''
		return char_to_name_cap(self.ch) + params_str
	def __str__(self):
		return self.ch + num_to_damage(self.damage)
	def map(self, transformation):
		return transformation.get(Singleton, Singleton)(self.ch, self.damage)
	def size(self, options):
		size = em_size_of(self.ch_rotated(options), options, 1, 1, 0, False)
		w = self.scale * size[0]
		h = self.scale * size[1]
		return w, h
	def ch_rotated(self, options):
		return self.ch if options.h() else rotate_char(self.ch)
	def format(self, options, x0, x1, x2, x3, y0, y1, y2, y3):
		size = self.size(options)
		buf_x = ((x2-x1) - size[0]) / 2
		buf_y = ((y2-y1) - size[1]) / 2
		self.x = x1 + buf_x
		self.y = y1 + buf_y
		self.w = size[0]
		self.h = size[1]
		x_shade = self.x + self.w / 2
		y_shade = self.y + self.h / 2
		self.areas = damage_areas(self.damage, x0, x_shade, x3, y0, y_shade, y3)
	def print(self, options, printed):
		printed.add_sign(self.ch_rotated(options), self.scale, 1, 1, 0, False, self)
		for area in self.areas:
			printed.add_shading(area)
		if self.damage:
			printed.add_hidden(num_to_damage(self.damage))

class Blank(Group):
	def __init__(self, dim):
		super().__init__()
		self.dim = dim
	def __repr__(self):
		params = []
		if self.dim == 0.5:
			params.append('width=0.5,height=0.5')
		params_str = ('[' + ','.join(params) + ']') if len(params) > 0 else ''
		return 'empty' + params_str
	def __str__(self):
		return FULL_BLANK if self.dim == 1 else HALF_BLANK
	def map(self, transformation):
		return transformation.get(Blank, Blank)(self.dim)
	def size(self, options):
		w = self.scale * self.dim 
		h = self.scale * self.dim 
		return w, h
	def format(self, options, x0, x1, x2, x3, y0, y1, y2, y3):
		pass
	def print(self, options, printed):
		printed.add_hidden(str(self))

class Lost(Group):
	def __init__(self, width, height, expand):
		super().__init__()
		self.width = width
		self.height = height
		self.expand = expand
	def __repr__(self):
		params = ['shade']
		if self.width == 0.5 and self.height == 0.5: 
			params.append('width=0.5,height=0.5')
		elif self.width == 0.5 and self.height == 1:
			params.append('width=0.5,height=1')
		elif self.width == 1 and self.height == 0.5:
			params.append('width=1,height=0.5')
		params_str = ('[' + ','.join(params) + ']') if len(params) > 0 else ''
		return 'empty' + params_str
	def __str__(self):
		if self.width == 0.5 and self.height == 0.5: 
			s = HALF_LOST
		elif self.width == 0.5 and self.height == 1:
			s = TALL_LOST
		elif self.width == 1 and self.height == 0.5:
			s = WIDE_LOST
		else:
			s = FULL_LOST
		s += num_to_variation(1 if self.expand else 0)
		return s
	def map(self, transformation):
		return transformation.get(Lost, Lost)(self.width, self.height, self.expand)
	def size(self, options):
		w = self.scale * self.width
		h = self.scale * self.height
		return w, h
	def format(self, options, x0, x1, x2, x3, y0, y1, y2, y3):
		if self.expand:
			self.areas = [Rectangle(x0, y0, x3-x0, y3-y0)]
		else:
			size = self.size(options)
			buf_x = ((x2-x1) - size[0]) / 2
			buf_y = ((y2-y1) - size[1]) / 2
			self.areas = [Rectangle(x1 + buf_x, y1 + buf_y, size[0], size[1])]
	def print(self, options, printed):
		printed.add_hidden(str(self))
		for area in self.areas:
			printed.add_shading(area)

class BracketOpen(Group):
	def __init__(self, ch):
		super().__init__()
		self.ch = ch
	def __repr__(self):
		return self.ch
	def __str__(self):
		return self.ch
	def map(self, transformation):
		return transformation.get(BracketOpen, BracketOpen)(self.ch)
	def size(self, options):
		return 0, 0
	def format(self, options, x, y, w, h):
		size = em_size_of(self.ch, options, 1, 1, 0, False)
		natural_ratio = size[0]
		available_ratio = w / h
		if available_ratio < natural_ratio:
			self.x_scale = max(0.5, available_ratio / natural_ratio)
		else:
			self.x_scale = 1
		w_adjusted = natural_ratio * h * self.x_scale
		self.x = max(x, x+w - w_adjusted)
		self.y = y
		self.w = w_adjusted
		self.h = h
	def print(self, options, printed):
		printed.add_sign(self.ch, self.h, self.x_scale, 1, 0, False, self, extra=True, bracket=True)

class BracketClose(Group):
	def __init__(self, ch):
		super().__init__()
		self.ch = ch
	def __repr__(self):
		return self.ch
	def __str__(self):
		return self.ch
	def map(self, transformation):
		return transformation.get(BracketClose, BracketClose)(self.ch)
	def size(self, options):
		return 0, 0
	def format(self, options, x, y, w, h):
		size = em_size_of(self.ch, options, 1, 1, 0, False)
		natural_ratio = size[0]
		available_ratio = w / h
		if available_ratio < natural_ratio:
			self.x_scale = max(0.5, available_ratio / natural_ratio)
		else:
			self.x_scale = 1
		w_adjusted = natural_ratio * h * self.x_scale
		self.x = min(x, x+w - w_adjusted)
		self.y = y
		self.w = w_adjusted
		self.h = h
	def print(self, options, printed):
		printed.add_sign(self.ch, self.h, self.x_scale, 1, 0, False, self, extra=True, bracket=True)

def is_group(group, outer=False, hor=False):
	match group:
		case Vertical() | Horizontal() | Enclosure() | Basic() | Overlay() | Literal() | Blank() | Lost():
			return True
		case Singleton():
			return outer
		case BracketOpen() | BracketClose():
			return hor
		case _:
			return False
