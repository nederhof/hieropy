import re
import math

from .resconstants import *

class Globals:
	def __init__(self, direction, size):
		self.direction = 'hlr'
		self.size = 1
		self.color = 'black'
		self.shade = False
		self.sep = 1
		self.fit = False
		self.mirror = False
		if direction is not None:
			self.direction = direction
		if size is not None:
			self.size = size
	def clone(self):
		copy = Globals(self.direction, self.size)
		copy.color = self.color
		copy.shade = self.shade
		copy.sep = self.sep
		copy.fit = self.fit
		copy.mirror = self.mirror
		return copy
	def update(self, size):
		if size == self.size:
			return self
		else:
			copy = self.clone()
			copy.size = size
			return copy
	def header_args(self):
		arg_list = []
		if self.direction != 'hlr':
			arg_list.append(Arg(self.direction))
		if self.size != 1:
			arg_list.append(Arg('size', self.size))
		return arg_list
	def switch_args(self):
		arg_list = []
		if self.color != 'black':
			arg_list.append(Arg(self.color))
		if self.shade:
			arg_list.append(Arg('shade'))
		if self.sep != 1:
			arg_list.append(Arg('sep', self.sep))
		if self.fit:
			arg_list.append(Arg('fit'))
		if self.mirror:
			arg_list.append(Arg('mirror'))
		return arg_list

class Group:
	def args_str(self):
		args = self.args()
		return '[' + ','.join(str(a) for a in args) + ']' if len(args) > 0 else ''
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

class Fragment(Group):
	def __init__(self, arg_list, sw, hiero):
		self.direction = None
		self.size = None
		for arg in arg_list:
			if arg.is_direction():
				self.direction = arg.lhs
			elif arg.is_real_non_zero('size'):
				self.size = arg.rhs
		self.sw = sw
		self.hiero = hiero
		self.propagate()
	def args(self):
		arg_list = []
		if self.direction is not None:
			arg_list.append(self.direction)
		if self.size is not None:
			arg_list.append(Arg('size', self.size))
		return arg_list
	def __str__(self):
		return self.args_str() + str(self.sw) + (str(self.hiero) if self.hiero is not None else '')
	def propagate(self):
		self.globs = self.sw.update(Globals(self.direction, self.size))
		if self.hiero:
			self.final_globs = self.hiero.propagate(self.globs)
		else:
			self.final_globs = self.globs

class Hiero(Group):
	def __init__(self, group):
		self.groups = [group]
		self.ops = []
		self.sws = []
	def add_group(self, arg_list, sw, group):
		self.ops.append(Op(arg_list, False))
		self.sws.append(sw)
		self.groups.append(group)
		return self
	def __str__(self):
		s = str(self.groups[0])
		for i in range(len(self.ops)):
			s += '-' + str(self.ops[i]) + str(self.sws[i]) + str(self.groups[i+1])
		return s
	def propagate(self, globs):
		self.globs = globs
		globs = self.groups[0].propagate(globs)
		for op, sw, group in zip(self.ops, self.sws, self.groups[1:]):
			globs = op.propagate(globs)
			globs = sw.update(globs)
			globs = group.propagate(globs)
		return globs
	
class VerGroup(Group):
	def __init__(self, group1, arg_list, sw, group2):
		self.groups = [group1, group2]
		self.ops = [Op(arg_list, True)]
		self.sws = [sw]
	def add_group(self, arg_list, sw, group):
		self.ops.append(Op(arg_list, False))
		self.sws.append(sw)
		self.groups.append(group)
		return self
	def __str__(self):
		s = str(self.groups[0])
		for i in range(len(self.ops)):
			s += ':' + str(self.ops[i]) + str(self.sws[i]) + str(self.groups[i+1])
		return s
	def propagate(self, globs):
		self.globs = globs
		globs = self.groups[0].propagate(globs)
		for op, sw, group in zip(self.ops, self.sws, self.groups[1:]):
			globs = op.propagate(globs)
			globs = sw.update(globs)
			globs = group.propagate(globs)
		return globs

class VerSubgroup(Group):
	def __init__(self, sw1, group, sw2):
		self.sw1 = sw1
		self.group = group
		self.sw2 = sw2
	def __str__(self):
		return str(self.sw1) + str(self.group) + str(self.sw2)
	def propagate(self, globs):
		self.globs = globs
		globs = self.sw1.update(globs)
		globs = self.group.propagate(globs)
		return self.sw2.update(globs)

class HorGroup(Group):
	def __init__(self, group1, arg_list, sw, group2):
		self.groups = [group1, group2]
		self.ops = [Op(arg_list, True)]
		self.sws = [sw]
	def add_group(self, arg_list, sw, group):
		self.ops.append(Op(arg_list, False))
		self.sws.append(sw)
		self.groups.append(group)
		return self
	def __str__(self):
		s = str(self.groups[0])
		for i in range(len(self.ops)):
			s += '*' + str(self.ops[i]) + str(self.sws[i]) + str(self.groups[i+1])
		return s
	def propagate(self, globs):
		self.globs = globs
		globs = self.groups[0].propagate(globs)
		for op, sw, group in zip(self.ops, self.sws, self.groups[1:]):
			globs = op.propagate(globs)
			globs = sw.update(globs)
			globs = group.propagate(globs)
		return globs

class HorSubgroup(Group):
	def __init__(self, sw1, group, sw2):
		self.sw1 = sw1
		self.group = group
		self.sw2 = sw2
	def __str__(self):
		if isinstance(self.group, VerGroup):
			return '(' + str(self.sw1) + str(self.group) + ')' + str(self.sw2)
		else:
			return str(self.sw1) + str(self.group) + str(self.sw2)
	def propagate(self, globs):
		self.globs = globs
		globs = self.sw1.update(globs)
		globs = self.group.propagate(globs)
		return self.sw2.update(globs)

class Op(Group):
	def __init__(self, arg_list, is_first=False):
		self.sep = None
		self.fit = None
		self.fix = False
		self.shade = None
		self.shades = []
		self.size = None
		for arg in arg_list:
			if arg.is_real('sep'):
				self.sep = arg.rhs
			elif arg.is_lhs_only('fit'):
				self.fit = True
			elif arg.is_lhs_only('nofit'):
				self.fit = False
			elif arg.is_lhs_only('fix'):
				self.fix = True
			elif arg.is_lhs_only('shade'):
				self.shade = True
			elif arg.is_lhs_only('noshade'):
				self.shade = False
			elif arg.is_pattern():
				self.shades.append(arg.lhs)
			elif is_first and arg.is_size_unit():
				self.size = arg.rhs
		self.is_first = is_first
	def args(self):
		arg_list = []
		if self.sep is not None:
			arg_list.append(Arg('sep', self.sep))
		if self.fit == True:
			arg_list.append('fit')
		elif self.fit == False:
			arg_list.append('nofit')
		if self.fix:
			arg_list.append('fix')
		if self.shade == True:
			arg_list.append('shade')
		elif self.shade == False:
			arg_list.append('noshade')
		arg_list.extend(self.shades)
		if self.size == 'inf':
			if self.is_first:
				arg_list.append(Arg('size', 'inf'))
		elif self.size is not None:
			arg_list.append(Arg('size', self.size))
		return arg_list
	def __str__(self):
		return self.args_str()
	def propagate(self, globs):
		self.globs = globs
		return globs

class Namedglyph(Group):
	def __init__(self, name, arg_list, notes, sw):
		self.name = name
		self.mirror = None
		self.rotate = 0
		self.scale = 1
		self.xscale = 1
		self.yscale = 1
		self.color = None
		self.shade = None
		self.shades = []
		for arg in arg_list:
			if arg.is_lhs_only('mirror'):
				self.mirror = True
			elif arg.is_lhs_only('nomirror'):
				self.mirror = False
			elif arg.is_nat('rotate'):
				self.rotate = arg.rhs % 360
			elif arg.is_real_non_zero('scale'):
				self.scale = arg.rhs
			elif arg.is_real_non_zero('xscale'):
				self.xscale = arg.rhs
			elif arg.is_real_non_zero('yscale'):
				self.yscale = arg.rhs
			elif arg.is_color():
				self.color = arg.lhs
			elif arg.is_lhs_only('shade'):
				self.shade = True
			elif arg.is_lhs_only('noshade'):
				self.shade = False
			elif arg.is_pattern():
				self.shades.append(arg.lhs)
		self.notes = notes
		self.sw = sw
	def args(self):
		arg_list = []
		if self.mirror == True:
			arg_list.append('mirror')
		elif self.mirror == False:
			arg_list.append('nomirror')
		if self.rotate != 0:
			arg_list.append(Arg('rotate', self.rotate))
		if self.scale != 1:
			arg_list.append(Arg('scale', self.scale))
		if self.xscale != 1:
			arg_list.append(Arg('xscale', self.xscale))
		if self.yscale != 1:
			arg_list.append(Arg('yscale', self.yscale))
		if self.color is not None:
			arg_list.append(self.color)
		if self.shade == True:
			arg_list.append('shade')
		elif self.shade == False:
			arg_list.append('noshade')
		arg_list.extend(self.shades)
		return arg_list
	def __str__(self):
		return self.name + self.args_str() + ''.join(str(n) for n in self.notes) + str(self.sw)
	def propagate(self, globs):
		self.globs = globs
		for note in self.notes:
			globs = note.propagate(globs)
		return self.sw.update(globs)
	def mirrored(self):
		return self.mirror if self.mirror is not None else self.globs.mirror
	def colored(self):
		return self.color if self.color is not None else self.globs.color

class Emptyglyph(Group):
	def __init__(self, arg_list, note, sw):
		self.width = 1
		self.height = 1
		self.shade = None
		self.shades = []
		self.firm = False
		for arg in arg_list:
			if arg.is_real('width'):
				self.width = arg.rhs
			elif arg.is_real('height'):
				self.height = arg.rhs
			elif arg.is_lhs_only('shade'):
				self.shade = True
			elif arg.is_lhs_only('noshade'):
				self.shade = False
			elif arg.is_pattern():
				self.shades.append(arg.lhs)
			elif arg.is_lhs_only('firm'):
				self.firm = True
		self.note = note
		self.sw = sw
	def args(self):
		arg_list = []
		if self.width != 1:
			arg_list.append(Arg('width', self.width))
		if self.height != 1:
			arg_list.append(Arg('height', self.height))
		if self.shade == True:
			arg_list.append('shade')
		elif self.shade == False:
			arg_list.append('noshade')
		arg_list.extend(self.shades)
		if self.firm:
			arg_list.append('firm')
		return arg_list
	@staticmethod
	def point_args():
		return [Arg('width', 0), Arg('height', 0)]
	def __str__(self):
		if self.width == 0 and self.height == 0 and self.shade is None and len(self.shades) == 0 and not self.firm:
			main = '.' 
		else:
			main = 'empty' + self.args_str()
		return main + (str(self.note) if self.note is not None else '') + str(self.sw)
	def propagate(self, globs):
		self.globs = globs
		if self.note is not None:
			globs = self.note.propagate(globs)
		return self.sw.update(globs)

class Box(Group):
	def __init__(self, name, arg_list, sw1, hiero, notes, sw2):
		self.name = name
		self.direction = None
		self.mirror = None
		self.scale = 1
		self.color = None
		self.shade = None
		self.shades = []
		self.size = 1
		self.opensep = None
		self.closesep = None
		self.undersep = None
		self.oversep = None
		for arg in arg_list:
			if arg.is_lhs_only('h') or arg.is_lhs_only('v'):
				self.direction = arg.lhs
			elif arg.is_lhs_only('mirror'):
				self.mirror = True
			elif arg.is_lhs_only('nomirror'):
				self.mirror = False
			elif arg.is_real_non_zero('scale'):
				self.scale = arg.rhs
			elif arg.is_color():
				self.color = arg.lhs
			elif arg.is_lhs_only('shade'):
				self.shade = True
			elif arg.is_lhs_only('noshade'):
				self.shade = False
			elif arg.is_pattern():
				self.shades.append(arg.lhs)
			elif arg.is_real_non_zero('size'):
				self.size = arg.rhs
			elif arg.is_real('opensep'):
				self.opensep = arg.rhs
			elif arg.is_real('closesep'):
				self.closesep = arg.rhs
			elif arg.is_real('undersep'):
				self.undersep = arg.rhs
			elif arg.is_real('oversep'):
				self.oversep = arg.rhs
		self.sw1 = sw1
		self.hiero = hiero
		self.notes = notes
		self.sw2 = sw2
	def args(self):
		arg_list = []
		if self.direction is not None:
			arg_list.append(self.direction)
		if self.mirror == True:
			arg_list.append('mirror')
		elif self.mirror == False:
			arg_list.append('nomirror')
		if self.scale != 1:
			arg_list.append(Arg('scale', self.scale))
		if self.color is not None:
			arg_list.append(self.color)
		if self.shade == True:
			arg_list.append('shade')
		elif self.shade == False:
			arg_list.append('noshade')
		arg_list.extend(self.shades)
		if self.size != 1:
			arg_list.append(Arg('size', self.size))
		if self.opensep is not None:
			arg_list.append(Arg('opensep', self.opensep))
		if self.closesep is not None:
			arg_list.append(Arg('closesep', self.closesep))
		if self.undersep is not None:
			arg_list.append(Arg('undersep', self.undersep))
		if self.oversep is not None:
			arg_list.append(Arg('oversep', self.oversep))
		return arg_list
	def __str__(self):
		return self.name + self.args_str() + '(' + str(self.sw1) + \
			(str(self.hiero) if self.hiero is not None else '') + ')' + \
			''.join(str(n) for n in self.notes) + str(self.sw2)
	def propagate(self, globs):
		self.globs = globs
		globs = self.sw1.update(globs)
		if self.hiero is not None:
			saved_size = globs.size
			globs = globs.update(self.size)
			globs = self.hiero.propagate(globs)
			globs = globs.update(saved_size)
		for note in self.notes:
			globs = note.propagate(globs)
		return self.sw2.update(globs)
	def mirrored(self):
		return self.mirror if self.mirror is not None else self.globs.mirror
	def colored(self):
		return self.color if self.color is not None else self.globs.color

class Stack(Group):
	def __init__(self, arg_list, sw1, group1, sw2, group2, sw3):
		self.x = 0.5
		self.y = 0.5
		self.onunder = None
		for arg in arg_list:
			if arg.is_real_low('x'):
				self.x = arg.rhs
			elif arg.is_real_low('y'):
				self.y = arg.rhs
			elif arg.is_lhs_only('on') or arg.is_lhs_only('under'):
				self.onunder = arg.lhs
		self.sw1 = sw1
		self.group1 = group1
		self.sw2 = sw2
		self.group2 = group2
		self.sw3 = sw3
	def args(self):
		arg_list = []
		if self.x != 0.5:
			arg_list.append(Arg('x', self.x))
		if self.y != 0.5:
			arg_list.append(Arg('y', self.y))
		if self.onunder is not None:
			arg_list.append(self.onunder)
		return arg_list
	def __str__(self):
		return 'stack' + self.args_str() + '(' + str(self.sw1) + \
				str(self.group1) + ',' + str(self.sw2) + \
				str(self.group2) + ')' + str(self.sw3)
	def propagate(self, globs):
		self.globs = globs
		globs = self.sw1.update(globs)													   
		globs = self.group1.propagate(globs)												 
		globs = self.sw2.update(globs)													   
		globs = self.group2.propagate(globs)												 
		return self.sw3.update(globs)

class Insert(Group):
	def __init__(self, arg_list, sw1, group1, sw2, group2, sw3):
		self.place = ''
		self.x = 0.5
		self.y = 0.5
		self.fix = False
		self.sep = None
		for arg in arg_list:
			if arg.is_place():
				self.place = arg.lhs
			elif arg.is_real_low('x'):
				self.x = arg.rhs
			elif arg.is_real_low('y'):
				self.y = arg.rhs
			elif arg.is_lhs_only('fix'):
				self.fix = True
			elif arg.is_real('sep'):
				self.sep = arg.rhs
		self.sw1 = sw1
		self.group1 = group1
		self.sw2 = sw2
		self.group2 = group2
		self.sw3 = sw3
	def args(self):
		arg_list = []
		if self.place != '':
			arg_list.append(self.place)
		if self.x != 0.5:
			arg_list.append(Arg('x', self.x))
		if self.y != 0.5:
			arg_list.append(Arg('y', self.y))
		if self.fix:
			arg_list.append('fix')
		if self.sep is not None:
			arg_list.append(Arg('sep', self.sep))
		return arg_list
	def __str__(self):
		return 'insert' + self.args_str() + '(' + str(self.sw1) + \
			str(self.group1) + ',' + str(self.sw2) + \
			str(self.group2) + ')' + str(self.sw3)
	def propagate(self, globs):
		self.globs = globs
		globs = self.sw1.update(globs)													   
		globs = self.group1.propagate(globs)												 
		globs = self.sw2.update(globs)													   
		globs = self.group2.propagate(globs)												 
		return self.sw3.update(globs)
	def position(self):
		return ( 0 if self.place.endswith('s') else 1 if self.place.endswith('e') else self.x,
				0 if self.place.startswith('t') else 1 if self.place.startswith('b') else self.y)

class Modify(Group):
	def __init__(self, arg_list, sw1, group, sw2):
		self.width = None
		self.height = None
		self.above = 0
		self.below = 0
		self.before = 0
		self.after = 0
		self.omit = False
		self.shade = None
		self.shades = []
		for arg in arg_list:
			if arg.is_real_non_zero('width'):
				self.width = arg.rhs
			elif arg.is_real_non_zero('height'):
				self.height = arg.rhs
			elif arg.is_real('above'):
				self.above = arg.rhs
			elif arg.is_real('below'):
				self.below = arg.rhs
			elif arg.is_real('before'):
				self.before = arg.rhs
			elif arg.is_real('after'):
				self.after = arg.rhs
			elif arg.is_lhs_only('omit'):
				self.omit = True
			elif arg.is_lhs_only('shade'):
				self.shade = True
			elif arg.is_lhs_only('noshade'):
				self.shade = False
			elif arg.is_pattern():
				self.shades.append(arg.lhs)
		self.sw1 = sw1
		self.group = group
		self.sw2 = sw2
	def args(self):
		arg_list = []
		if self.width is not None:
			arg_list.append(Arg('width', self.width))
		if self.height is not None:
			arg_list.append(Arg('height', self.height))
		if self.above != 0:
			arg_list.append(Arg('above', self.above))
		if self.below != 0:
			arg_list.append(Arg('below', self.below))
		if self.before != 0:
			arg_list.append(Arg('before', self.before))
		if self.after != 0:
			arg_list.append(Arg('after', self.after))
		if self.omit:
			arg_list.append('omit')
		if self.shade == True:
			arg_list.append('shade')
		elif self.shade == False:
			arg_list.append('noshade')
		arg_list.extend(self.shades)
		return arg_list
	def __str__(self):
		return 'modify' + self.args_str() + '(' + str(self.sw1) + \
			str(self.group) + ')' + str(self.sw2)
	def propagate(self, globs):
		self.globs = globs
		globs = self.sw1.update(globs)													   
		globs = self.group.propagate(globs)												 
		return self.sw2.update(globs)

class Note(Group):
	def __init__(self, s, arg_list):
		self.color = None
		for arg in arg_list:
			if arg.is_color():
				self.color = arg.lhs
		self.str = s
	def args(self):
		arg_list = []
		if self.color is not None:
			arg_list.append(self.color)
		return arg_list
	def __str__(self):
		return '^' + self.str + self.args_str()
	def propagate(self, globs):
		self.globs = globs
		return globs																		   

class Switch(Group):
	def __init__(self, arg_list):
		self.color = None
		self.shade = None
		self.sep = None
		self.fit = None
		self.mirror = None
		for arg in arg_list:
			if arg.is_color():
				self.color = arg.lhs
			elif arg.is_lhs_only('shade'):
				self.shade = True
			elif arg.is_lhs_only('noshade'):
				self.shade = False
			elif arg.is_real('sep'):
				self.sep = arg.rhs
			elif arg.is_lhs_only('fit'):
				self.fit = True
			elif arg.is_lhs_only('nofit'):
				self.fit = False
			elif arg.is_lhs_only('mirror'):
				self.mirror = True
			elif arg.is_lhs_only('nomirror'):
				self.mirror = False
	def args(self):
		arg_list = []
		if self.color is not None:
			arg_list.append(self.color)
		if self.shade == True:
			arg_list.append('shade')
		elif self.shade == False:
			arg_list.append('noshade')
		if self.sep is not None:
			arg_list.append(Arg('sep', self.sep))
		if self.fit == True:
			arg_list.append('fit')
		elif self.fit == False:
			arg_list.append('nofit')
		if self.mirror == True:
			arg_list.append('mirror')
		elif self.mirror == False:
			arg_list.append('nomirror')
		return arg_list
	def __str__(self):
		a = self.args_str()
		return '!' + a if a != '' else ''
	def is_empty(self):
		return self.color is None and self.shade is None and self.sep is None and \
				self.fit is None and self.mirror is None
	def join(self, sw):
		copy = Switch([])
		copy.color = self.color
		copy.shade = self.shade
		copy.sep = self.sep
		copy.fit = self.fit
		copy.mirror = self.mirror
		if sw.color is not None:
			copy.color = sw.color
		if sw.shade is not None:
			copy.shade = sw.shade
		if sw.sep is not None:
			copy.sep = sw.sep
		if sw.fit is not None:
			copy.fit = sw.fit
		if sw.mirror is not None:
			copy.mirror = sw.mirror
		return copy
	def update(self, globs):
		if self.is_empty():
			return globs
		copy = globs.clone()
		if self.color is not None:
			copy.color = self.color
		if self.shade is not None:
			copy.shade = self.shade
		if self.sep is not None:
			copy.sep = self.sep
		if self.fit is not None:
			copy.fit = self.fit
		if self.mirror is not None:
			copy.mirror = self.mirror
		return copy

class Arg:
	def __init__(self, lhs, rhs=None):
		self.lhs = lhs
		self.rhs = rhs
	def is_lhs_only(self, lhs):
		return self.lhs == lhs and self.rhs is None
	def is_direction(self):
		return self.lhs in DIRECTIONS and self.rhs is None
	def is_color(self):
		return self.lhs in COLORS and self.rhs is None
	def is_place(self):
		return self.lhs in PLACES and self.rhs is None
	def is_pattern(self):
		return re.fullmatch(r'[tbse]+', self.lhs) and self.rhs is None
	def is_real(self, lhs):
		return self.lhs == lhs and isinstance(self.rhs, (int, float))
	def is_real_non_zero(self, lhs):
		return self.is_real(lhs) and self.rhs > 0
	def is_real_low(self, lhs):
		return self.is_real(lhs) and self.rhs <= 1
	def is_nat(self, lhs):
		return self.is_real(lhs) and self.rhs.is_integer()
	def is_size_unit(self):
		return self.is_real_non_zero('size') or self.lhs == 'size' and self.rhs == 'inf'
	def __str__(self):
		if self.rhs is None:
			return self.lhs
		elif isinstance(self.rhs, float):
			return self.lhs + '=' + '{:g}'.format(self.rhs)
		else:
			return self.lhs + '=' + str(self.rhs)
