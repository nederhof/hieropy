import tkinter as tk
from rtree import index

HORSEP_DEFAULT = 7
VERSEP_DEFAULT = 10
BORDER_DEFAULT = 6
PLAIN_THICKNESS_DEFAULT = 2
FOCUS_THICKNESS_DEFAULT = 5

PLAIN_COLOR = 'gray40'
FOCUS_COLOR = 'blue'

class DrawnTreeNode():
	def __init__(self, tree, calculator, drawer, text, click_handler):
		self.tree = tree
		self.calculator = calculator
		self.drawer = drawer
		self.set_text(text)
		self.children = []
		self.click_handler = click_handler
		self.focus = False

	def set_text(self, text):
		self.text = text
		self.dir = ''
		self.hiero_size = 0
		self.w_in, self.h_in = self.calculator(text)
		self.w = self.w_in + 2 * self.tree.border
		self.h = self.h_in + 2 * self.tree.border

	def append_child(self, node):
		self.children.append(node)

	def remove_child(self, node):
		self.children.remove(node)

	def used_nodes(self):
		nodes = {self}
		for child in self.children:
			nodes.update(child.used_nodes())
		return nodes

	def position(self, x, y):
		self.x = x
		self.y = y

	def tree_size(self):
		if not self.children:
			return self.w, self.h
		elif len(self.children) == 1:
			return max(self.w, self.subtrees_size()[0]), self.h + self.subtrees_size()[1] + self.tree.versep
		else:
			return max(self.w, self.subtrees_size()[0]), self.h + self.subtrees_size()[1] + 2 * self.tree.versep

	def subtrees_size(self):
		return sum(child.tree_size()[0] for child in self.children) + (len(self.children)-1) * self.tree.horsep, \
				max(child.tree_size()[1] for child in self.children)

	def reposition(self, x, y, mirror):
		if not self.children:
			self.position(x, y)
		else:
			w_tree, h_tree = self.tree_size()
			w_subtrees, h_subtrees = self.subtrees_size()
			node_margin = (w_tree - self.w) // 2
			subtrees_margin = (w_tree - w_subtrees) // 2
			self.position(x + node_margin, y)
			x += subtrees_margin
			y += self.h + self.tree.versep if len(self.children) == 1 else self.h + 2 * self.tree.versep
			for child in (reversed(self.children) if mirror else self.children):
				child.reposition(x, y, mirror)
				x += child.tree_size()[0] + self.tree.horsep

	def top_anchor(self):
		return self.x + self.w // 2, self.y

	def bottom_anchor(self):
		return self.x + self.w // 2, self.y + self.h

	def draw(self, draw_line, draw_node):
		if self.children:
			x_bot, y_bot = self.bottom_anchor()
			draw_line(x_bot, y_bot, x_bot, y_bot + self.tree.versep)
			if len(self.children) == 1:
				self.children[0].draw(draw_line, draw_node)
				draw_node(self.children[0])
			else:
				x_min, y_sub = self.children[0].top_anchor()
				x_max, _ = self.children[-1].top_anchor()
				draw_line(x_min, y_sub - self.tree.versep, x_max, y_sub - self.tree.versep)
				for child in self.children:
					x_top, y_top = child.top_anchor()
					draw_line(x_top, y_top - self.tree.versep, x_top, y_top)
					child.draw(draw_line, draw_node)
					draw_node(child)

class DrawnTrees():
	def __init__(self, horsep=HORSEP_DEFAULT, versep=VERSEP_DEFAULT, \
			plain_thickness=PLAIN_THICKNESS_DEFAULT, focus_thickness=FOCUS_THICKNESS_DEFAULT, border=BORDER_DEFAULT):
		self.horsep = horsep
		self.versep = versep
		self.border = border
		self.plain_thickness = plain_thickness
		self.focus_thickness = focus_thickness
		self.trees = []
		self.nodes = set()
		self.dir = 'hlr'

	def rl(self):
		return self.dir in ['hrl', 'vrl']

	def append_child(self, tree):
		self.trees.append(tree)

	def insert_child(self, index, node):
		self.trees.insert(index, node)

	def remove_child(self, node):
		self.trees.remove(node)

	def remove_all(self):
		self.trees = []

	def replace_child(self, node_new, node_old):
		i = self.trees.index(node_old)
		if i >= 0:
			self.trees[i] = node_new

	# subclass overrides
	def destroy_node(self, node):
		self.nodes.remove(node)

	def used_nodes(self):
		nodes = set()
		for tree in self.trees:
			nodes.update(tree.used_nodes())
		return nodes

	def cleanup(self):
		leftover = self.nodes - self.used_nodes()
		for node in leftover:
			self.destroy_node(node)

	def size(self):
		if not self.trees:
			return 2 * self.horsep, 2 * self.versep
		else:
			return sum(tree.tree_size()[0] for tree in self.trees) + (len(self.trees)+1) * self.horsep, \
					max(tree.tree_size()[1] for tree in self.trees) + 2 * self.versep

	def reposition(self):
		x = self.horsep
		y = self.versep
		for tree in (reversed(self.trees) if self.rl() else self.trees):
			tree.reposition(x, y, self.rl())
			x += tree.tree_size()[0] + self.horsep

	# subclass overrides
	def draw(self):
		self.clear_all()
		trees = list(reversed(self.trees)) if self.rl() else self.trees
		h = min([tree.h // 2 for tree in trees], default=0)
		for tree in self.trees:
			tree.draw(self.draw_line, self.draw_node)
		for i in range(len(trees)):
			tree = trees[i]
			if i+1 < len(trees):
				tree_next = trees[i+1]
				self.draw_line(tree.x + tree.w, self.versep+h, tree_next.x, self.versep+h)
			self.draw_node(tree)

	# subclass overrides
	def draw_node(self, node):
		pass

	# subclass overrides
	def draw_line(self, x0, y0, x1, y1):
		pass

	# subclass overrides
	def clear_all(self):
		pass

	def refresh(self):
		self.cleanup()
		self.reposition()
		self.draw()
			
class TkTreeNode(DrawnTreeNode):
	def __init__(self, tree, calculator, drawer, text, click_handler):
		super().__init__(tree, calculator, drawer, text, click_handler)

	def scroll_into_view(self):
		w = self.tree.canvas.winfo_width()
		h = self.tree.canvas.winfo_height()
		left = self.tree.canvas.canvasx(0)
		right = self.tree.canvas.canvasx(w)
		top = self.tree.canvas.canvasy(0)
		bottom = self.tree.canvas.canvasy(h)
		if self.x < left or self.x + self.w > right:
			x = self.x + 0.5 * self.w                                                                   
			frac = (x - w/2) / self.tree.canvas.winfo_reqwidth()                                        
			frac = max(0, min(frac, 1))                                                           
			self.tree.canvas.xview_moveto(frac)
		if self.y < top or self.y + self.h > bottom:                                                       
			y = self.y + 0.5 * self.h                                                                   
			frac = (y - h/2) / self.tree.canvas.winfo_reqheight()                                      
			frac = max(0, min(frac, 1))                                                           
			self.tree.canvas.yview_moveto(frac)

class TkTrees(DrawnTrees):
	def __init__(self, frame, canvas):
		super().__init__()
		self.frame = frame
		self.canvas = canvas
		self.canvas.bind("<Button-1>", self.click_handler)
		self.canvas.bind("<Motion>", self.move_handler)
		self.canvas.bind("<Leave>", self.leave_handler)

	def create_node(self, calculator, drawer, text, click_handler):
		node = TkTreeNode(self, calculator, drawer, text, click_handler)
		self.nodes.add(node)
		return node

	def draw(self):
		w, h = self.size()
		self.canvas.config(width=w, height=h, scrollregion=(0,0,w,h))
		super().draw()

	def draw_line(self, x0, y0, x1, y1):
		self.canvas.create_line(x0, y0, x1, y1, width=self.plain_thickness, capstyle=tk.ROUND, fill=PLAIN_COLOR, tags='line')

	def draw_node(self, node):
		color = FOCUS_COLOR if node.focus else PLAIN_COLOR
		thickness = self.focus_thickness if node.focus else self.plain_thickness
		self.canvas.create_rectangle(node.x, node.y, node.x + node.w, node.y + node.h, outline=color, \
			width=thickness, tags='node')
		node.drawer(self.canvas, node)
		if index:
			self.index.insert(self.node_num, (node.x, node.y, node.x + node.w, node.y + node.h))
			self.num_to_node[self.node_num] = node
			self.node_num += 1

	def clear_all(self):
		self.canvas.delete('all')
		self.index = index.Index()
		self.node_num = 0
		self.num_to_node = {}

	def click_handler(self, event):
		if index:
			x = self.canvas.canvasx(event.x)
			y = self.canvas.canvasy(event.y)
			candidates = self.index.intersection((x, y, x, y))
			num = next(candidates, None)
			if num is not None and num in self.num_to_node:
				self.num_to_node[num].click_handler()

	def move_handler(self, event):
		self.canvas.delete('hover')
		if index:
			x = self.canvas.canvasx(event.x)
			y = self.canvas.canvasy(event.y)
			candidates = self.index.intersection((x, y, x, y))
			num = next(candidates, None)
			if num is not None and num in self.num_to_node:
				node = self.num_to_node[num]
				if not node.focus:
					self.canvas.create_rectangle(node.x, node.y, node.x + node.w, node.y + node.h, \
						fill='gray', stipple='gray50', outline='', tags='hover')

	def leave_handler(self, event):
		self.canvas.delete('hover')
