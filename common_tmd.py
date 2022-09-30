from math import radians, atan2
import mathutils

global errors
errors = []
correction_local = mathutils.Euler((radians(90), 0, radians(90))).to_matrix().to_4x4()
correction_global = mathutils.Euler((radians(-90), radians(-90), 0)).to_matrix().to_4x4()

def vec_roll_to_mat3(vec, roll):
	#port of the updated C function from armature.c
	#https://developer.blender.org/T39470
	#note that C accesses columns first, so all matrix indices are swapped compared to the C version
	
	nor = vec.normalized()
	THETA_THRESHOLD_NEGY = 1.0e-9
	THETA_THRESHOLD_NEGY_CLOSE = 1.0e-5
	
	#create a 3x3 matrix
	bMatrix = mathutils.Matrix().to_3x3()

	theta = 1.0 + nor[1]

	if (theta > THETA_THRESHOLD_NEGY_CLOSE) or ((nor[0] or nor[2]) and theta > THETA_THRESHOLD_NEGY):

		bMatrix[1][0] = -nor[0]
		bMatrix[0][1] = nor[0]
		bMatrix[1][1] = nor[1]
		bMatrix[2][1] = nor[2]
		bMatrix[1][2] = -nor[2]
		if theta > THETA_THRESHOLD_NEGY_CLOSE:
			#If nor is far enough from -Y, apply the general case.
			bMatrix[0][0] = 1 - nor[0] * nor[0] / theta
			bMatrix[2][2] = 1 - nor[2] * nor[2] / theta
			bMatrix[0][2] = bMatrix[2][0] = -nor[0] * nor[2] / theta
		
		else:
			#If nor is too close to -Y, apply the special case.
			theta = nor[0] * nor[0] + nor[2] * nor[2]
			bMatrix[0][0] = (nor[0] + nor[2]) * (nor[0] - nor[2]) / -theta
			bMatrix[2][2] = -bMatrix[0][0]
			bMatrix[0][2] = bMatrix[2][0] = 2.0 * nor[0] * nor[2] / theta

	else:
		#If nor is -Y, simple symmetry by Z axis.
		bMatrix = mathutils.Matrix().to_3x3()
		bMatrix[0][0] = bMatrix[1][1] = -1.0

	#Make Roll matrix
	rMatrix = mathutils.Matrix.Rotation(roll, 3, nor)
	
	#Combine and output result
	mat = rMatrix * bMatrix
	return mat

def mat3_to_vec_roll(mat):
	#this hasn't changed
	vec = mat.col[1]
	vecmat = vec_roll_to_mat3(mat.col[1], 0)
	vecmatinv = vecmat.invert()
	rollmat = vecmatinv * mat
	roll = atan2(rollmat[0][2], rollmat[2][2])
	return vec, roll
	
def name_to_blender(s):
	s = s.rstrip(b"\x00").decode("utf-8")
	if "_l_" in s:
		s+= ".l"
	elif "_L_" in s:
		s+= ".L"
	if "_r_" in s:
		s+= ".r"
	elif "_R_" in s:
		s+= ".R"
	return s.replace("_R_","_").replace("_L_","_").replace("_r_","_").replace("_l_","_")
	
def name_to_tmd(s):
	if '.L' in s:
		s = s[:2]+"L_"+s[2:-2]
	elif '.R' in s:
		s = s[:2]+"R_"+s[2:-2]
	elif '.l' in s:
		s = s[:2]+"l_"+s[2:-2]
	elif '.r' in s:
		s = s[:2]+"r_"+s[2:-2]
	return s
	
def log_error(error):
	print(error)
	global errors
	errors.append(error)