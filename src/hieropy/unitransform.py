from .unistructure import *
from .uniconstants import mirror_place, mirror_bracket, mirror_damage, \
		rotate_place, num_to_rotate, rotate_to_num, rotate_damage, num_to_corners, corners_to_num

def mirror_group(group):
	match group:
		case Vertical(): return mirror_vertical(group)
		case Horizontal(): return mirror_horizontal(group)
		case Enclosure(): return mirror_enclosure(group)
		case Basic(): return mirror_basic(group)
		case Overlay(): return mirror_overlay(group)
		case Literal(): return mirror_literal(group)
		case Singleton(): return mirror_singleton(group)
		case Blank(): return mirror_blank(group)
		case Lost(): return mirror_lost(group)
		case BracketOpen(): return mirror_bracket_open(group)
		case BracketClose(): return mirror_bracket_close(group)

def mirror_vertical(group):
	return Vertical([mirror_group(g) for g in group.groups])

def mirror_horizontal(group):
	return Horizontal(reversed([mirror_group(g) for g in group.groups]))

def mirror_enclosure(group):
	return Enclosure(group.typ, reversed([mirror_group(g) for g in group.groups]), \
		group.delim_open, group.damage_open, group.delim_close, group.damage_close)

def mirror_basic(group):
	core = mirror_group(group.core)
	insertions = {mirror_place(pl): mirror_group(g) for (pl,g) in group.insertions.items()}
	return Basic(core, insertions)

def mirror_overlay(group):
	lits1 = reversed([mirror_group(g) for g in group.lits1])
	lits2 = [mirror_group(g) for g in group.lits2]
	return Overlay(lits1, lits2)

def mirror_literal(group):
	mirror = not group.mirror
	damage = mirror_damage(group.damage)
	return Literal(group.ch, group.vs, mirror, damage)

def mirror_singleton(group):
	return group

def mirror_blank(group):
	return group

def mirror_lost(group):
	return group

def mirror_bracket_open(group):
	return BracketClose(mirror_bracket(group.ch))

def mirror_bracket_close(group):
	return BracketOpen(mirror_bracket(group.ch))

def rotate_group(group, rot):
	match group:
		case Vertical(): return rotate_vertical(group, rot)
		case Horizontal(): return rotate_horizontal(group, rot)
		case Enclosure(): return rotate_enclosure(group, rot)
		case Basic(): return rotate_basic(group, rot)
		case Overlay(): return rotate_overlay(group, rot)
		case Literal(): return rotate_literal(group, rot)
		case Singleton(): return rotate_singleton(group, rot)
		case Blank(): return rotate_blank(group, rot)
		case Lost(): return rotate_lost(group, rot)
		case BracketOpen(): return rotate_bracket_open(group, rot)
		case BracketClose(): return rotate_bracket_close(group, rot)

def rotate_vertical(group, rot):
	groups = [rotate_group(g, rot) for g in group.groups]
	match rot:
		case 90:
			return make_horizontal(reversed(groups))
		case 270:
			return make_horizontal(groups)
		case _:
			return make_vertical(reversed(groups))

def rotate_horizontal(group, rot):
	groups = [rotate_group(g, rot) for g in group.groups if rot == 180 or is_group(g)]
	match rot:
		case 90:
			return make_vertical(groups)
		case 270:
			return make_vertical(reversed(groups))
		case _:
			return make_horizontal(reversed(groups))

def rotate_enclosure(group, rot):
	return Enclosure(group.typ, reversed([rotate_group(g, rot) for g in group.groups]), \
		group.delim_open, group.damage_open, group.delim_close, group.damage_close)

def rotate_basic(group, rot):
	core = rotate_group(group.core, rot)
	insertions = {rotate_place(pl, rot): rotate_group(g, rot) for (pl,g) in group.insertions.items()}
	return Basic(core, insertions)

def rotate_overlay(group, rot):
	match rot:
		case 90:
			lits1 = reversed([rotate_group(g, rot) for g in group.lits2])
			lits2 = [rotate_group(g, rot) for g in group.lits1]
		case 270:
			lits1 = [rotate_group(g, rot) for g in group.lits2]
			lits2 = reversed([rotate_group(g, rot) for g in group.lits1])
		case _:
			lits1 = reversed([rotate_group(g, rot) for g in group.lits1])
			lits2 = reversed([rotate_group(g, rot) for g in group.lits2])
	return Overlay(lits1, lits2)

def rotate_literal(group, rot):
	vs = rotate_to_num(num_to_rotate(group.vs) + (-rot if group.mirror else rot))
	damage = rotate_damage(group.damage, rot)
	return Literal(group.ch, vs, group.mirror, damage)

def rotate_singleton(group, rot):
	return group

def rotate_blank(group, rot):
	return group

def rotate_lost(group, rot):
	match rot:
		case 90 | 270:
			return Lost(group.height, group.width, group.expand)
		case _:
			return group

def rotate_bracket_open(group, rot):
	match rot:
		case 180:
			return BracketClose(rotate_bracket(group.ch))

def rotate_bracket_close(group, rot):
	match rot:
		case 180:
			return BracketOpen(rotate_bracket(group.ch))

def damage_group(group, corners):
	match group:
		case Vertical(): return damage_vertical(group, corners)
		case Horizontal(): return damage_horizontal(group, corners)
		case Enclosure(): return damage_enclosure(group, corners)
		case Basic(): return damage_basic(group, corners)
		case Overlay(): return damage_overlay(group, corners)
		case Literal(): return damage_literal(group, corners)
		case Singleton(): return damage_singleton(group, corners)
		case Blank(): return damage_blank(group, corners)
		case Lost(): return damage_lost(group, corners)
		case BracketOpen(): return damage_bracket_open(group, corners)
		case BracketClose(): return damage_bracket_close(group, corners)

def damage_vertical(group, corners):
	corners_t = top_corners(corners)
	corners_b = bottom_corners(corners)
	mid = len(group.groups) // 2
	groups_t = [damage_group(g, corners_t) for g in group.groups[:mid]]
	groups_b = [damage_group(g, corners_b) for g in group.groups[-mid:]]
	groups_mid = [damage_group(group.groups[mid], corners)] if len(group.groups) % 2 else []
	return Vertical(groups_t + groups_mid + groups_b)

def damage_horizontal(group, corners):
	corners_s = start_corners(corners)
	corners_e = end_corners(corners)
	mid = len(group.groups) // 2
	groups_s = [damage_group(g, corners_s) for g in group.groups[:mid]]
	groups_e = [damage_group(g, corners_e) for g in group.groups[-mid:]]
	groups_mid = [damage_group(group.groups[mid], corners)] if len(group.groups) % 2 else []
	return Horizontal(groups_s + groups_mid + groups_e)

def damage_enclosure(group, corners):
	corners_t = top_corners(corners)
	corners_b = bottom_corners(corners)
	if len(group.groups) < 2:
		groups = [damage_group(g, corners) for g in group.groups]
	else:
		mid = len(group.groups) // 2
		groups_t = [damage_group(g, corners_t) for g in group.groups[:mid]]
		groups_b = [damage_group(g, corners_b) for g in group.groups[-mid:]]
		groups_mid = [damage_group(group.groups[mid], corners)] if len(group.groups) % 2 else []
		groups = groups_t + groups_mid + groups_b
	return Enclosure(group.typ, groups, \
		group.delim_open, group.damage_open, group.delim_close, group.damage_close)

def damage_basic(group, corners):
	core = damage_group(group.core, corners)
	return Basic(core, group.insertions)

def damage_overlay(group, corners):
	corners_s = start_corners(corners)
	corners_e = end_corners(corners)
	if len(group.lits1) == 1:
		return Overlay([damage_group(group.lits1[0], corners)], group.lits2)
	else:
		mid = len(group.lits1) // 2
		lits_s = [damage_group(g, corners_s) for g in group.lits1[:mid]]
		lits_e = [damage_group(g, corners_e) for g in group.lits1[-mid:]]
		lits_mid = [damage_group(group.lits1[mid], corners)] if len(group.lits1) % 2 else []
		return Overlay(lits_s + lits_mid + lits_e, group.lits2)

def damage_literal(group, corners):
	damage = corners_to_num(add_corners(num_to_corners(group.damage), corners))
	return Literal(group.ch, group.vs, group.mirror, damage)

def damage_singleton(group, corners):
	damage = corners_to_num(add_corners(num_to_corners(group.damage), corners))
	return Singleton(group.ch, damage)

def damage_blank(group, corners):
	if corners_empty(corners):
		return group
	else:
		return Lost(group.dim, group.dim, True)

def damage_lost(group, corners):
	return group

def damage_bracket_open(group, corners):
	return group

def damage_bracket_close(group, corners):
	return group

def start_corners(corners):
	return { 'ts': corners['ts'], 'te': corners['ts'], 'bs': corners['bs'], 'be': corners['bs'] }
def end_corners(corners):
	return { 'ts': corners['te'], 'te': corners['te'], 'bs': corners['be'], 'be': corners['be'] }
def top_corners(corners):
	return { 'ts': corners['ts'], 'bs': corners['ts'], 'te': corners['te'], 'be': corners['te'] }
def bottom_corners(corners):
	return { 'ts': corners['bs'], 'bs': corners['bs'], 'te': corners['be'], 'be': corners['be'] }
def corners_empty(corners):
	return not (corners['ts'] or corners['te'] or corners['bs'] or corners['be'])

def add_corners(corners1, corners2):
	return { corner: (corners1[corner] or corners2[corner]) for corner in ['ts', 'bs', 'te', 'be'] }
