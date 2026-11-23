class Wiki:
	def __init__(self, lines):
		self.lines = lines

class WikiLine:
	def __init__(self, groups):
		self.groups = groups

class WikiVertical:
	def __init__(self, groups):
		self.groups = [g for g in groups if not isinstance(g, str)]
		if len(groups) > 1 and all(g.surface_form for g in self.groups):
			self.surface_form = ''
			for g in groups:
				if isinstance(g, str):
					self.surface_form += g
				else:
					self.surface_form += g.surface_form
		else:
			self.surface_form = None

class WikiHorizontal:
	def __init__(self, groups):
		self.groups = groups
		self.surface_form = groups[0].surface_form if len(groups) == 1 else None

class WikiSign:
	def __init__(self, name, mirror):
		self.name = name
		self.mirror = mirror
		self.surface_form = name if not self.mirror else None

class WikiBlank:
	def __init__(self, size):
		self.size = size
		self.surface_form = None

class WikiEnclosure:
	def __init__(self, begin, groups, end):
		self.begin = begin
		self.groups = groups
		self.end = end
		self.surface_form = None

class WikiBracketOpen:
	def __init__(self, ch):
		self.ch = ch
		self.surface_form = None

class WikiBracketClose:
	def __init__(self, ch):
		self.ch = ch
		self.surface_form = None

class WikiText:
	def __init__(self, text):
		self.text = text
		self.surface_form = None
