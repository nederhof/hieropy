class History():
	def __init__(self, editor):
		self.editor = editor
		self.states = []
		self.size = 0
		self.set_buttons()

	def remember(self):
		tree = self.editor.tree
		s = str(tree)
		if not s:
			return
		self.states = self.states[:self.size]
		self.states.append({ 'string': s, 'address': tree.get_focus_address() })
		self.size += 1
		self.set_buttons()

	def undo(self):
		if self.size > 0:
			tree = self.editor.tree
			if self.size == len(self.states):
				self.states.append({ 'string': str(tree), 'address': tree.get_focus_address() })
			self.size -= 1
			prev = self.states[self.size]
			self.editor.make(prev['string'], prev['address'])
			self.set_buttons()

	def redo(self):
		if self.size < len(self.states) - 1:
			self.size += 1
			nex = self.states[self.size]
			self.editor.make(nex['string'], nex['address'])
			self.set_buttons()

	def set_buttons(self):
		self.editor.disable_undo(self.size <= 0)
		self.editor.disable_redo(self.size >= len(self.states) - 1)
