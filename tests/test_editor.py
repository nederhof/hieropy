import unittest
import time
from unittest.mock import patch
from random import randint

from hieropy import UniEditor, CustomSignList, UniParser, Options

class TestEditor(unittest.TestCase):
	@unittest.skip("Skipping test that opens GUI")
	def test_editor(self):
		UniEditor()

	@unittest.skip("Skipping test that opens GUI")
	def test_editor_with_callback(self):
		UniEditor(save=lambda x: print(x), cancel=lambda x: print(x))

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

	# @unittest.skip("Skipping test that opens GUI")
	def test_custom(self):
		mnemonics = [('jjj', 'A1z')]
		info = [('\uF000', '<ul><li><b>Det.</b> description</li></ul>')]
		fontname = 'CustomFont'
		fontpath = 'tests/resources/NewGardinerNonCore.ttf'
		signs = [('\uF000', 'A800', '\U00013000'), \
			('\U00013460', 'A801', '\U00013050'), \
			('\U0001346E', 'B801')]
		custom = CustomSignList(fontname, fontpath, signs, mnemonics=mnemonics, info=info)
		encoding = ''
		def save(e):
			nonlocal encoding
			encoding = e
		UniEditor(custom=custom, save=save)
		options1 = Options(custom=custom)
		options2 = Options(custom=custom, imagetype='pdf')
		options3 = Options(custom=custom, imagetype='svg')
		parser = UniParser()
		fragment = parser.parse(encoding)
		printed1 = fragment.print(options1)
		printed2 = fragment.print(options2)
		printed3 = fragment.print(options3)
		printed1.get_pil().save('tests/tmp/testimage1.png')
		printed2.get_pil().save('tests/tmp/testimage2a.png')
		with open('tests/tmp/testimage2b.pdf', 'wb') as f:
			f.write(printed2.get_pdf())
		with open('tests/tmp/testimage3.svg', 'w', encoding='utf-8') as f:
			f.write(printed3.get_svg())

if __name__ == '__main__':
	unittest.main()
