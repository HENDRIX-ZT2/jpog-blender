import os
import time
import math
import bpy
import mathutils
from struct import iter_unpack, unpack_from
from subprocess import check_call
from .utils.tristrip import triangulate

def get_text():
	text_name = "JPOG.txt"
	if text_name not in bpy.data.texts:
		text_ob = bpy.data.texts.new(text_name)
	else:
		text_ob = bpy.data.texts[text_name]
	return text_ob

def export_matrix(mat):
	bytes = b''
	for row in mat: bytes += pack('=4f',*row)
	return bytes
	
def get_matrix(x): return mathutils.Matrix(list(iter_unpack('4f',datastream[x:x+64])))

def select_layer(layer_nr): return tuple(i == layer_nr for i in range(0, 20))

def log_error(error):
	print(error)
	global errors
	errors.append(error)
	
def vec_roll_to_mat3(vec, roll):
	#port of the updated C function from armature.c
	#https://developer.blender.org/T39470
	#note that C accesses columns first, so all matrix indices are swapped compared to the C version
	
	nor = vec.normalized()
	THETA_THRESHOLD_NEGY = 1.0e-9
	THETA_THRESHOLD_NEGY_CLOSE = 1.0e-5
	
	#create a 3x3 matrix
	bMatrix = mathutils.Matrix().to_3x3()

	theta = 1.0 + nor[1];

	if (theta > THETA_THRESHOLD_NEGY_CLOSE) or ((nor[0] or nor[2]) and theta > THETA_THRESHOLD_NEGY):

		bMatrix[1][0] = -nor[0];
		bMatrix[0][1] = nor[0];
		bMatrix[1][1] = nor[1];
		bMatrix[2][1] = nor[2];
		bMatrix[1][2] = -nor[2];
		if theta > THETA_THRESHOLD_NEGY_CLOSE:
			#If nor is far enough from -Y, apply the general case.
			bMatrix[0][0] = 1 - nor[0] * nor[0] / theta;
			bMatrix[2][2] = 1 - nor[2] * nor[2] / theta;
			bMatrix[0][2] = bMatrix[2][0] = -nor[0] * nor[2] / theta;
		
		else:
			#If nor is too close to -Y, apply the special case.
			theta = nor[0] * nor[0] + nor[2] * nor[2];
			bMatrix[0][0] = (nor[0] + nor[2]) * (nor[0] - nor[2]) / -theta;
			bMatrix[2][2] = -bMatrix[0][0];
			bMatrix[0][2] = bMatrix[2][0] = 2.0 * nor[0] * nor[2] / theta;

	else:
		#If nor is -Y, simple symmetry by Z axis.
		bMatrix = mathutils.Matrix().to_3x3()
		bMatrix[0][0] = bMatrix[1][1] = -1.0;

	#Make Roll matrix
	rMatrix = mathutils.Matrix.Rotation(roll, 3, nor)
	
	#Combine and output result
	mat = rMatrix * bMatrix
	return mat

def mat3_to_vec_roll(mat):
	#this hasn't changed
	vec = mat.col[1]
	vecmat = vec_roll_to_mat3(mat.col[1], 0)
	vecmatinv = vecmat.inverted()
	rollmat = vecmatinv * mat
	roll = math.atan2(rollmat[0][2], rollmat[2][2])
	return vec, roll
			
def load(operator, context, filepath = "", use_custom_normals = False, use_anims=False, extract_textures=False):

	correction_local = mathutils.Euler((math.radians(90), 0, math.radians(90))).to_matrix().to_4x4()
	correction_global = mathutils.Euler((math.radians(-90), math.radians(-90), 0)).to_matrix().to_4x4()
	
	#store unknown variables to retrieve them on export
	vars = {}
	
	#set the visible layers for this scene
	bools = []
	for i in range(20):	 
		if i < 6: bools.append(True)
		else: bools.append(False)
	bpy.context.scene.layers = bools
	
	starttime = time.clock()
	global errors
	errors = []
	
	mat_2_obj = {}
	global datastream
	#when no object exists, or when we are in edit mode when script is run
	try: bpy.ops.object.mode_set(mode='OBJECT')
	except: pass
	print("\nImporting",os.path.basename(filepath))
	f = open(filepath, 'rb')
	datastream = f.read()
	f.close()
	
	#header
	remaining_bytes, tkl_ref, magic_value1, magic_value2, lod_data_offset, salt, u1, u2	 = unpack_from("I 8s 2L 4I", datastream, 8)
	scene_block_bytes, num_nodes, u3, num_anims, u4 = unpack_from("I 4H", datastream, 60)
	aux_node_data, node_data, anim_pointer = unpack_from("3I", datastream, 60+56)
	
	vars["tmd_path"] = filepath
	vars["salt"] = salt
	vars["u1"] = u1
	vars["u2"] = u2
	vars["u3"] = u3
	vars["u4"] = u4
	vars["magic_value1"] = magic_value1
	vars["magic_value2"] = magic_value2
	
	#print(aux_node_data, node_data, anim_pointer)
	#decrypt the addresses
	aux_node_data += 60 - salt
	node_data += 60 - salt
	anim_pointer += 60 - salt
	if aux_node_data == 124:
		anim_pointer = node_data
		node_data = aux_node_data
	#else:
		#what does the aux node data do?
		#node_aux = unpack_from(str(num_nodes)+"i", datastream, aux_node_data)
		#print("node_aux",node_aux)
	#print(aux_node_data, node_data, anim_pointer)

	#create the armature
	armData = bpy.data.armatures.new("DUMMY Scene Root Armature")
	armData.show_axes = True
	armData.draw_type = 'STICK'
	armature = bpy.data.objects.new("DUMMY Scene Root", armData)
	armature.show_x_ray = True
	bpy.context.scene.objects.link(armature)
	bpy.context.scene.objects.active = armature
	bpy.ops.object.mode_set(mode = 'EDIT')
	
	#read the bones
	fallback_matrix = {}
	pos = node_data
	#note that these are not necessarily sorted, so we must build a list manually and can't just take the bones from the armature in the end!
	bone_names = []
	for i in range(0, num_nodes):
		x, y, z, w = unpack_from("4f", datastream, pos)
		fallback_quat = mathutils.Quaternion((w,x,y,z))
		#this is the finished matrix in armature ie. world space
		bind = get_matrix(pos+16).transposed()
		inv_bind = get_matrix(pos+80).transposed()
		name_len =  unpack_from("B", datastream, pos+144)[0]
		bone_name = unpack_from(str(name_len)+"s", datastream, pos+145)[0].rstrip(b"\x00").decode("utf-8")
		bone_names.append(bone_name)
		parent_id, updates, x, y, z = unpack_from("hH 3f", datastream, pos+160)
		fallback_trans = mathutils.Vector((x,y,z))
		
		#create a matrix from the fallback values
		#technically, storing the translations would be enough
		#but this is convenient
		fallback_matrix[bone_name] = fallback_quat.to_matrix().to_4x4()
		fallback_matrix[bone_name].translation = fallback_trans
		pos+=176

		#create a bone
		bone = armData.edit_bones.new(bone_name)
		#parent it and get the armature space matrix
		if parent_id > -1:
			bone.parent = armData.edit_bones[bone_names[parent_id]]
		
		#create and pose the bone
		#correct the bind pose matrix axis
		#blender bones are Y forward, while bind is X forward - correction_local takes care of that
		#this will result in a good looking skeleton, just globally rotated - correction_global fixes that
		bind = correction_global * correction_local * bind * correction_local.inverted()
		tail, roll = mat3_to_vec_roll(bind.to_3x3())
		bone.head = bind.to_translation()
		bone.tail = tail + bone.head
		bone.roll = roll
	
	# #fix the bone length
	for bone in armData.edit_bones:
		if bone.parent:
			if bone.children:
				childheads = mathutils.Vector()
				for child in bone.children:
					childheads += child.head
				#do it like this to avoid deleting zero-length bones inbetween!
				bone_length = (bone.head - childheads/len(bone.children)).length
				if bone_length < 0.01:
					bone_length = 0.25
				bone.length = bone_length
			# end of a chain
			else:
				bone.length = bone.parent.length
	bpy.ops.object.mode_set(mode = 'OBJECT')
	armature.layers = select_layer(5)

	pos = lod_data_offset + 60
	#124 124 5756
	# = 206568 + 60
	#print(lod_data_offset)
	#max_lod_distance just a guess but sound, and 
	num_lods, max_lod_distance = unpack_from("I f", datastream, pos)
	print("max_lod_distance", max_lod_distance)
	print("Number of LODs:",num_lods)
	pos+=8
	
	#max_lod_distance 34.92011260986328
	#0.0 2.0976476669311523 -1.001983642578125 3.7165191173553467 30.53643798828125
	#max_lod_distance 6.398754596710205
	#0.0 0.26798370480537415 -0.06812041997909546 -0.0847543329000473 6.109550476074219
	#0 5% -2% 10% 90%
	for level in range(0,num_lods):
		#possibly LOD extents, ie. near far distance and bias?
		#note that these values are the same for all lods
		num_meshes_in_lod, u6, s_x, s_y, s_z, d = unpack_from("I f 4f ", datastream, pos)
		
		print("Meshes in LOD:",num_meshes_in_lod)
		print(u6, s_x, s_y, s_z, d)
		pos+=24
		for mesh in range(0,num_meshes_in_lod):
			num_pieces, num_all_strip_indices, num_all_verts, matname = unpack_from("3I 32s ", datastream, pos)
			#print(num_pieces, num_all_strip_indices, num_all_verts, matname)
			pos+=44
			#these lists are extended by every piece
			mesh_verts = []
			mesh_tris = []
			#we must store them for each piece, so we can do the rigging correctly
			mesh_piece_node_indices = []
			mesh_tristrips = []
			#i = (b, b, b, b), (w,w,w,w)
			mesh_weights = {}
			
			for meshpiece in range(0,num_pieces):
				print("Piece:",meshpiece)
				num_strip_indices, num_verts, num_piece_nodes, num_highest_index, bbc_x, bbc_y, bbc_z, bbe_x, bbe_y, bbe_z = unpack_from("4I 3f 3f", datastream, pos)
				print("Verts:",num_verts)
				print("Nodes:",num_piece_nodes)
				print("num_strip_indices:",num_strip_indices)
				print("Highest vert index:",num_highest_index)
				pos += 40

				#the nodes used by this mesh - used in the lookup for the bone weights
				mesh_piece_node_indices.append(unpack_from(str(num_piece_nodes)+"I ", datastream, pos))
				pos += 4*num_piece_nodes
				#read the verts of this piece
				#store verts and tristrip
				mesh_verts.extend(list(iter_unpack("3f 3f 4B 4B 2f", datastream[pos : pos+40*num_verts])))
				pos += 40*num_verts
				#verts can be referred to from another piece!
				print("stripstart",pos)
				mesh_tristrips.append(unpack_from(str(num_strip_indices)+"h ", datastream, pos))
				
				pos += 2*num_strip_indices
			#print(mesh_verts)
			#print(mesh_tristrips)
			for tristrip, piece_node_indices in zip(mesh_tristrips, mesh_piece_node_indices):
				#to resolve the rigging correctly, the weights must be resolved in the piece where they are used in the tristrip
				for i in tristrip:
					#we could do
					if i not in mesh_weights:
						bones = []
						weights = []
						for b, w in zip([int(x/3) for x in mesh_verts[i][10:14]], [ x/255 for x in mesh_verts[i][6:10]]):
							if w > 0:
								bones.append(bone_names[piece_node_indices[b]])
								weights.append(w)
						mesh_weights[i] = (bones, weights)
			matname = matname.split(b"\x00")[0].decode("utf-8")
			
			if matname not in mat_2_obj.keys():
				mat_2_obj[matname] = []
			name = matname+"_LOD"+str(level)+"_MESH"+str(mesh)
			
			#build the mesh
			me = bpy.data.meshes.new(name)
			me.from_pydata([v[0:3] for v in mesh_verts], [], triangulate(mesh_tristrips))
			me.update()
			ob = bpy.data.objects.new(name, me)
			mat_2_obj[matname].append(ob)
			bpy.context.scene.objects.link(ob)
			bpy.context.scene.objects.active = ob
			ob.layers = select_layer(level)
			
			#weight painting
			ob.parent = armature
			mod = ob.modifiers.new('SkinDeform', 'ARMATURE')
			mod.object = armature
			for i, weights in mesh_weights.items():
				for bone_name, weight in zip(weights[0], weights[1]):
					#could also do this in a preceding loop via used indices - faster!
					if bone_name not in ob.vertex_groups: ob.vertex_groups.new(bone_name)
					ob.vertex_groups[bone_name].add([i], weight, 'REPLACE')
					
			#UV: flip V coordinate
			me.uv_textures.new("UV")
			me.uv_layers[-1].data.foreach_set("uv", [uv for pair in [mesh_verts[l.vertex_index][14:16] for l in me.loops] for uv in (pair[0], -pair[1])])
			
			#build a correctly sorted normals array, sorted by the order of faces - loops does not work!!
			no_array = []
			for face in me.polygons:
				for vertex_index in face.vertices:
					no_array.append(mesh_verts[vertex_index][3:6])	
				face.use_smooth = True
			if use_custom_normals:
				me.use_auto_smooth = True
				#doesn't seem to need either in current blender, but the normals are not exactly as intended
				#bpy.ops.mesh.customdata_custom_splitnormals_add()
				#me.calc_normals_split()
				me.normals_split_custom_set(no_array)
				
			#so ugly, working with context and operators - perhaps there is a better solution
			bpy.context.scene.objects.active = ob
			bpy.ops.object.mode_set(mode = 'EDIT')
			bpy.ops.mesh.remove_doubles(threshold = 0.0001, use_unselected = False)
			bpy.ops.uv.seams_from_islands()
			bpy.ops.object.mode_set(mode = 'OBJECT')
	
	tkl_path = os.path.join(os.path.dirname(filepath), tkl_ref.split(b"\x00")[0].decode("utf-8")+".tkl")
	vars["tkl_path"] = tkl_path
	if use_anims:
		#read the tkl
		print("\nReading",tkl_path)
		f = open(tkl_path, 'rb')
		tklstream = f.read()
		f.close()
		
		loc_lut = {}
		rot_lut = {}
		tkl_b00, tkl_b01, tkl_b02, tkl_b03, tkl_remaining_bytes, tkl_name, tkl_b04, tkl_b05, tkl_b06, tkl_b07, tkl_b08, tkl_b09, tkl_b10, tkl_b11, tkl_b12, tkl_b13, num_loc, num_rot, tkl_i00, tkl_i01, tkl_i02, tkl_i03, tkl_i04	=  unpack_from("4B I 6s 10B 2I 5I", tklstream, 4)
		#tkl_i04 probably another size value, close to tkl_remaining_bytes
		pos = 56
		for i in range(0, num_loc):
			loc_lut[i] = mathutils.Vector((unpack_from("3f", tklstream, pos)))
			pos+=12
		for i in range(0, num_rot):
			x,y,z,w = unpack_from("4f", tklstream, pos)
			rot_lut[i] = mathutils.Quaternion((w,x,y,z))
			pos+=16
		
		#anims
		fps = bpy.context.scene.render.fps
		armature.animation_data_create()
		pos = anim_pointer
		anim_offsets = unpack_from(str(num_anims)+"I", datastream, pos)
		#read all anims
		for anim_offset in anim_offsets:
			pos = anim_offset + 60 - salt
			name_len =  unpack_from("B", datastream, pos)[0]
			anim_name = unpack_from(str(name_len)+"s", datastream, pos+1)[0].rstrip(b"\x00").decode("utf-8")
			ub1, ub2, num_groups, duration =  unpack_from("3I f", datastream, pos+16)
			channel_offsets = unpack_from(str(num_nodes)+"I", datastream, pos+32)
			#create the action
			action = bpy.data.actions.new(name = anim_name)
			action.use_fake_user = True
			armature.animation_data.action = action
			#read all bone channels
			for i, channel_offset in enumerate(channel_offsets):
				bone_name = bone_names[i]
				channel_offset += 60 - salt
				pos = channel_offset
				channel_mode, num_frames =  unpack_from("2H", datastream, pos)
				pos += 4
				if channel_mode != 2:
					# 0 = fallback trans, quat key
					# 1 = trans + rot keys
					# 2 = skip
					# 3 = fallback quat, trans key
					#initialize all fcurves
					loc_fcurves = [action.fcurves.new(data_path = 'pose.bones["'+bone_name+'"].location', index = i, action_group = bone_name) for i in (0,1,2)]
					rot_fcurves = [action.fcurves.new(data_path = 'pose.bones["'+bone_name+'"].rotation_quaternion', index = i, action_group = bone_name) for i in (0,1,2,3)]
					for i in range(0,num_frames):
						key_time, loc_index, rot_index = unpack_from("f H H", datastream, pos)
						#build a matrix from this key and save it
						key_matrix = rot_lut[rot_index].to_matrix().to_4x4()
						#use the fallback if we should
						if channel_mode == 0:
							key_matrix.translation = fallback_matrix[bone_name].translation
						if channel_mode == 1:
							key_matrix.translation = loc_lut[loc_index]
						if channel_mode == 3:
							key_matrix = fallback_matrix[bone_name]
							key_matrix.translation = loc_lut[loc_index]
						
						#and do local space correction only (as keyframes do not act in global space)
						#we must make this matrix relative to the rest pose to conform with how blender bones work
						key_matrix = fallback_matrix[bone_name].inverted() * key_matrix
						key_matrix =  correction_local * key_matrix *correction_local.inverted()
						for fcurve, key in zip(loc_fcurves, key_matrix.to_translation()):
							fcurve.keyframe_points.insert(key_time*fps, key).interpolation = "LINEAR"
						for fcurve, key in zip(rot_fcurves, key_matrix.to_quaternion()):
							fcurve.keyframe_points.insert(key_time*fps, key).interpolation = "LINEAR"
						pos+=8
			
			#loop looped anims
			if anim_name.lower().endswith("_lp"):
				for fcurve in action.fcurves:
					mod = fcurve.modifiers.new('CYCLES')
			
	#find the right material
	#create material and texture if they don't already exist
	matlibs = os.path.join(os.path.dirname(os.path.dirname(filepath)), "matlibs")
	if not os.path.isdir(matlibs):
		log_error('/matlibs folder missing. Models should be imported from JPOG-like folder structure.')
		matlibs = os.path.dirname(filepath)
	if extract_textures:
		try:
			tmls = [file for file in os.listdir(matlibs) if file.lower().endswith(".tml")]
			for tml in tmls:
				tml_path = os.path.join(matlibs, tml)
				with open(tml_path, 'rb') as f:
					#read the last 2048 bytes
					try:
						f.seek(-2048,2)
					#select few seem to be shorter, maybe we can skip the exception
					except:
						print("TOO SHORT",tml_path)
						f.seek(0)
					datastream = f.read()
					# see if the matname is in it
					for matname in mat_2_obj.keys():
						#print((matname,))
						if any((b"\x00"+matname.encode('utf-8')+b"\x00" in datastream, b"\x00"+matname.title().encode('utf-8')+b"\x00" in datastream, b"\x00"+matname.lower().encode('utf-8')+b"\x00" in datastream)):
							#print(matname,os.path.basename(tml_path))
						
							# #now read it properly
							# f.seek(0)
							# #header
							# u6, num_textures = unpack_from("2I", datastream, 4)
							# pos = 12
							# print("Number of Textures:",num_textures)
							# for texture in range(0, num_textures):
								# tex_id, data_size, b00, b01, b02, b03, b04, b05, b06, b07, tex_format, width, height, b8, b9, b10, b11, b12, b13 = unpack_from("2I 8B 3H 6B", datastream, pos)
								# #print(data_size, tex_format)
								# pos+=data_size+28
							# num_materials = unpack_from("I", datastream, pos)[0]
							# mat_lut = list(iter_unpack("32s", datastream[pos+4 : pos+4+32*num_materials]))
							# pos += 4+32*num_materials
							# print("mat_lut:",mat_lut)
							# for material in range(0, num_materials):
								# lut_index, u7, num_mat_textures = unpack_from("I 2H", datastream, pos)
								# #unknown tends to be 2 or 3
								# print(lut_index, u7, num_mat_textures)
								# #matname = mat_lut[lut_index]
								# #indices into the list of textures, which should probably be built or stored in a dict
								# used_textures =  unpack_from(str(num_mat_textures)+"I", datastream, pos+8)
								# pos += 8 + 4* num_mat_textures
								
							#extract all to bmp
							check_call(os.path.join(os.path.dirname(__file__), 'ConvertTML.exe "'+tml_path+'"'))
							#we only have to unpack this once
							break
		except:
			log_error('TML reading failed! Could not extract textures.')
		
	try:
		for matname in mat_2_obj.keys():
					
			print("Material:",matname)
			#create or retrieve a material
			if matname not in bpy.data.materials:
				mat = bpy.data.materials.new(matname)
				mat.specular_intensity = 0.0
				mat.ambient = 1
				mat.use_transparency = True
			else:
				mat = bpy.data.materials[matname]
				
			#even if no TMLs were found, we still get a dummy material (for re-export!)
			for ob in mat_2_obj[matname]:
				me = ob.data
				#needed?
				if not me.materials:
					me.materials.append(mat)
				else:
					me.materials[0] = mat
			
			#find the image file candidates
			textures = [file for file in os.listdir(matlibs) if file.lower() == matname.lower()+".tga"]
			#print(textures)
			#do something better?
			if textures:
				texture = textures[-1]
				
				if texture not in bpy.data.textures:
					tex = bpy.data.textures.new(texture, type = 'IMAGE')
					try:
						img = bpy.data.images.load(os.path.join(matlibs, texture))
					except:
						print("Could not find image "+texture+", generating blank image!")
						img = bpy.data.images.new(texture,1,1)
					tex.image = img
				else: tex = bpy.data.textures[texture]
				#now create the slot in the material for the texture
				mtex = mat.texture_slots.add()
				mtex.texture = tex
				mtex.texture_coords = 'UV'
				mtex.use_map_color_diffuse = True 
				mtex.use_map_color_emission = True 
				mtex.emission_color_factor = 0.5
				mtex.uv_layer = "UV"
				
				#assign textures to mesh
				for ob in mat_2_obj[matname]:
					me = ob.data
					
					#reversed so the last is shown
					for mtex in reversed(mat.texture_slots):
						if mtex:
							for texface in me.uv_textures["UV"].data:
								texface.image = mtex.texture.image
					#and for rendering, make sure each poly is assigned to the material
					for f in me.polygons:
						f.material_index = 0
	except:
		log_error('Material creation failed!')
	
	#store the vars
	text_ob = get_text()
	text_ob.clear()
	text_ob.write(str(vars))
	
	success = '\nFinished TMD Import in %.2f seconds\n' %(time.clock()-starttime)
	print(success)
	return errors