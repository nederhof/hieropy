import unittest
import time
from unittest.mock import patch
from random import randint

from hieropy import UniEditor

class TestEditor(unittest.TestCase):
	@unittest.skip("Skipping test that opens GUI")
	def test_editor(self):
		myeditor = UniEditor()

	@unittest.skip("Skipping test that opens GUI")
	def test_editor_with_callback(self):
		myeditor = UniEditor(save=lambda x: print(x), cancel=lambda x: print(x))

	@unittest.skip("Skipping test that opens GUI")
	@patch('tkinter.Tk.mainloop') 
	def test_random_edits(self, mock_mainloop):
		for j in range(2):
			print("pass", j)
			myeditor = UniEditor()
			for i in range(500):
				print("step", i)
				r = randint(1, 31)
				match r:
					case 1: myeditor.tree.do_literal()
					case 2: myeditor.tree.do_blank()
					case 3: myeditor.tree.do_prepend()
					case 4: myeditor.tree.do_plus()
					case 5: myeditor.tree.do_semicolon()
					case 6: myeditor.tree.do_bracket_open()
					case 7: myeditor.tree.do_singleton()
					case 8: myeditor.tree.do_lost()
					case 9: myeditor.tree.do_append()
					case 10: myeditor.tree.do_star()
					case 11: myeditor.tree.do_colon()
					case 12: myeditor.tree.do_bracket_close()
					case 13: myeditor.tree.do_overlay()
					case 14: myeditor.tree.do_enclosure()
					case 15: myeditor.tree.do_delete()
					case 16: myeditor.tree.do_insert()
					case 17: myeditor.tree.do_swap()
					case 18: myeditor.tree.move_end()
					case 19: myeditor.tree.move_start()
					case 20: myeditor.tree.move_left()
					case 21: myeditor.tree.move_up()
					case 22: myeditor.tree.move_right()
					case 23: myeditor.tree.move_down()
					case 24: myeditor.tree.do_delete()
					case 25: myeditor.do_name_focus()
					case 26: myeditor.adjust_damage_toggle()
					case 27: myeditor.adjust_mirror_toggle()
					case 28: myeditor.adjust_rotate_next()
					case 29: myeditor.adjust_place_next()
					case 30: myeditor.adjust_expand_toggle()
					case 31: myeditor.adjust_size_toggle()
					case _: print("not applicable")
				myeditor.root.update_idletasks()
				myeditor.root.update()
				time.sleep(0.1)
			myeditor.root.destroy()

if __name__ == '__main__':
	unittest.main()
