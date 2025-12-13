# imagetype: 'pil', 'pdf', 'svg'
# shadealpha: number between 0 and 255
# shadepattern: 'diagonal' or 'uniform'
class Options:
	def __init__(self, direction='hlr', linesize=1.0, fontsize=22, sep=0.08, hmargin=0.04, vmargin=0.04, \
				imagetype='pil', transparent=False, signcolor='black', bracketcolor='red', \
				shadecolor='gray', shadealpha=128, shadepattern='uniform', shadedist=5, shadethickness=1, \
				align='middle', separated=False):
		self.direction = direction
		self.linesize = linesize
		self.fontsize = fontsize
		self.sep = sep
		self.hmargin = hmargin
		self.vmargin = vmargin
		self.imagetype = imagetype
		self.transparent = transparent
		self.signcolor = signcolor
		self.bracketcolor = bracketcolor
		self.shadecolor = shadecolor
		self.shadealpha = shadealpha
		self.shadepattern = shadepattern
		self.shadedist = shadedist
		self.shadethickness = shadethickness
		self.align = align
		self.separated = separated

	def h(self):
		return self.direction in ['hlr', 'hrl']

	def v(self):
		return self.direction in ['vlr', 'vrl']

	def rl(self):
		return self.direction in ['hrl', 'vrl']

class MeasureOptions(Options):
	def __init__(self, options):
		self.direction = 'hlr' if options.h() else 'vlr'
		self.fontsize = 150
		self.signcolor = 'black'
		self.sep = options.sep
		self.transparent = False
		self.align = options.align
