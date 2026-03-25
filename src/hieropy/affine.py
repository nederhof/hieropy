import math

def rotate_affine(angle_deg):
	rad = math.radians(angle_deg)
	return math.cos(rad), math.sin(rad), -math.sin(rad), math.cos(rad), 0, 0

def scale_affine(sx, sy):
	return sx, 0, 0, sy, 0, 0

def mirror_affine():
	return -1, 0, 0, 1, 0, 0

def translate_affine(dx, dy):
	return 1, 0, 0, 1, dx, dy

def id_affine():
	return translate_affine(0, 0)

def multiply_affines(aff1, aff2):
	xx1, xy1, yx1, yy1, dx1, dy1 = aff1
	xx2, xy2, yx2, yy2, dx2, dy2 = aff2
	return xx1*xx2 + xy1*yx2, xx1*xy2 + xy1*yy2, yx1*xx2 + yy1*yx2, yx1*xy2 + yy1*yy2, \
			dx1*xx2 + dy1*yx2 + dx2, dx1*xy2 + dy1*yy2 + dy2

def chain_affines(*affs):
	aff_out = id_affine()
	for aff in affs:
		aff_out = multiply_affines(aff, aff_out)
	return aff_out
