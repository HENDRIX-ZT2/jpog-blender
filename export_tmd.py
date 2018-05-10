import os
import time
import math
import bpy
import mathutils
from struct import pack, unpack_from
from .utils.tristrip import stripify

def export_matrix(mat):
	bytes = b''
	for row in mat: bytes += pack('=4f',*row)
	return bytes
	
def log_error(error):
	print(error)
	global errors
	errors.append(error)
			
def save(operator, context, filepath = '', export_anims = False, create_lods = False, pad_anims = False, numlods = 1, rate = 1):

	MAX_BONES_PER_PIECE = 27

	print("\nStarting export to",filepath)
	starttime = time.clock()
	global errors
	errors = []

	text_name = "JPOG.txt"
	if text_name not in bpy.data.texts:
		log_error("You must import a TMD file before you can export one!")
		return errors
	
	#get the vars
	text_ob = bpy.data.texts[text_name]
	#yes bad but I am lazy
	vars = eval(text_ob.as_string())
	
	correction_local = mathutils.Euler((math.radians(90), 0, math.radians(90))).to_matrix().to_4x4()
	correction_global = mathutils.Euler((math.radians(-90), math.radians(-90), 0)).to_matrix().to_4x4()
	
	for armature in bpy.data.objects:
		if type(armature.data) == bpy.types.Armature:
			break
	# implement ZT2 like filtering at some point, so only baked anims are exported
	animations = bpy.data.actions
	
	#probably version number
	#uncommon:
	#magic_value1 2316361
	#magic_value2 136
	#more common
	#magic_value1 = 3299401
	#magic_value2 = 1960
	magic_value1 = vars["magic_value1"]
	magic_value2 = vars["magic_value2"]
	salt = vars["salt"]
	u1 = vars["u1"]
	u2 = vars["u2"]
	u3 = vars["u3"]
	num_anims = len(animations)
	u4 = vars["u4"]
	node_data = 124
	anim_pointer = node_data + 176 * len(armature.data.bones)
	#lod_data_offset = anim_pointer
	print("node_data",node_data)
	#let's not support that for now
	#anim_pointer = 0
	#pack("3I", aux_node_data, node_data, anim_pointer) ]

	bones_bytes = []
	fallback_matrix = {}
	
	#read the original TMD: do two things at max
	#set the bone names list into the original order
	#just copy the anim_bytes block from the imported file
	if not export_anims:
		tmd_path = vars["tmd_path"]
		print("Copying anims from",tmd_path)
		with open(tmd_path, 'rb') as f:
			header = f.read(130)
			remaining_bytes, tkl_ref, magic_value1, magic_value2, lod_data_offset, salt, u1, u2 = unpack_from("I 8s 2L 4I", header, 8)
			tkl_ref = tkl_ref.split(b"\x00")[0].decode("utf-8")
			scene_block_bytes, num_nodes, u3, num_anims, u4 = unpack_from("I 4H", header, 60)
			aux_node_data, node_data, anim_pointer = unpack_from("3I", header, 60+56)
			#decrypt the addresses
			aux_node_data += 60 - salt
			node_data += 60 - salt
			anim_pointer += 60 - salt
			if aux_node_data == 124:
				anim_pointer = node_data
				node_data = aux_node_data
			
			f.seek(anim_pointer)	
			anim_bytes = f.read(lod_data_offset + 60 - anim_pointer)
		
			f.seek(node_data)
			node_bytes = f.read(176 * num_nodes)
			pos = 0
			#note that these are not necessarily sorted, so we must build a list manually and can't just take the bones from the armature in the end!
			bone_names = []
			for i in range(0, num_nodes):
				name_len =  unpack_from("B", node_bytes, pos+144)[0]
				bone_name = unpack_from(str(name_len)+"s", node_bytes, pos+145)[0].rstrip(b"\x00").decode("utf-8")
				bone_names.append(bone_name)
				pos+=176

	else:
		# create a new sorting from blender bones, updated bones before non-updated bones.
		b_bones = armature.data.bones.keys()
		bone_names = [b for b in b_bones if armature.data.bones[b].use_deform] + [b for b in b_bones if not armature.data.bones[b].use_deform]

	#export all bones in the correct order
	for bone_name in bone_names:
		try:
			bone = armature.data.bones[bone_name]
		except:
			#skip this bone
			log_error("Bone "+bone_name+" is missing from the armature, but was expected to be there as the original model contained it.")
			continue
		#for the export, we get the original bind like this
		bind = correction_global.inverted() *  correction_local.inverted() * bone.matrix_local *  correction_local
		mat_local = bind
		#only non-skeletal nodes can ignore updates
		updates = 0 if bone.use_deform else 1
		parent_id = -1
		if bone.parent:
			parent_id = bone_names.index(bone.parent.name)
			p_bind_restored = correction_global.inverted() *  correction_local.inverted() * bone.parent.matrix_local *  correction_local
			mat_local = p_bind_restored.inverted() * mat_local
		fallback_matrix[bone_name] = mat_local
		#mind the order of quat keys when packing!
		q = mat_local.to_quaternion()
		l = mat_local.to_translation()
		#note that on import, the bind is transposed right after reading, so here we do it in the very end 
		bones_bytes.append( b"".join((pack('4f', q.x, q.y, q.z, q.w), export_matrix(bind.transposed()), export_matrix(bind.inverted().transposed()), pack('B 15s hH 3f', len(bone.name), bone_name.encode("utf-8"), parent_id, updates, *l) )))
	
	bones_bytes = b"".join(bones_bytes)
	
	if export_anims:
		#just set overwrite the original for quick testing
		if pad_anims:
			tkl_ref = os.path.basename(vars["tkl_path"][:-4])[:6]
		#just a dummy file which has to be merged
		else:
			tkl_ref = os.path.basename(filepath[:-4])[:6]
			
		print("Going to create",tkl_ref+".tkl")
		
		anim_bytes = []
		channels_bytes = []
		all_quats = []
		all_locs = []
		#just get all vars
		#TODO: only read the header block, or store the vars
		tkl_path = vars["tkl_path"]
		with open(tkl_path, 'rb') as f:
			tklstream = f.read()
		tkl_b00, tkl_b01, tkl_b02, tkl_b03, tkl_remaining_bytes, tkl_name, tkl_b04, tkl_b05, tkl_b06, tkl_b07, tkl_b08, tkl_b09, tkl_b10, tkl_b11, tkl_b12, tkl_b13, num_loc, num_rot, tkl_i00, tkl_i01, tkl_i02, tkl_i03, tkl_i04	=  unpack_from("4B I 6s 10B 2I 5I", tklstream, 4)
		
		fps = bpy.context.scene.render.fps
		#note this var is not encrypted here
		offset = anim_pointer + len(animations) * 4
		for action in animations:
			print(action.name)
			#Animation Pointer Block
			#offsets are encrypted
			anim_bytes.append(pack('I', offset - 60 + salt))
			#every bone, and only every bone, is written
			offset += 32 + len(bone_names) * 4
			
			channel_pointer_bytes = []
			channel_bytes = []
			
			#by definition, a secondary anim will have some bones unkeyframed
			# ub1 = 0
			# for bone_name in bone_names:
				# if bone_name not in action.groups:
					# ub1 = 1
					# break
			# #not sure
			# ub2 = 0
			action_name = action.name[:-2]
			ub1 = int(action.name[-2])
			ub2 = int(action.name[-1])
			
			channel_pointer_bytes.append(pack('B 15s 3I f', len(action_name), action_name.encode("utf-8"), ub1, ub2, len(bone_names), action.frame_range[1]/fps))
			
			for bone_name in bone_names:
				channel_pointer_bytes.append(pack('I', offset - 60 + salt))
				if bone_name in action.groups:
					group = action.groups[bone_name]
					rotations = [fcurve for fcurve in group.channels if fcurve.data_path.endswith("quaternion")]
					translations = [fcurve for fcurve in group.channels if fcurve.data_path.endswith("location")]
				else:
					rotations = []
					translations = []
					
				#prepare the fcurves for export -> make sure they are properly sampled, with no keys missing
				fcurves = rotations+translations
				times = []
				same_amount_of_keys = all(len(fcu.keyframe_points) == len(fcurves[0].keyframe_points) for fcu in fcurves)
				if not same_amount_of_keys:
					print(bone_name+" has differing keyframe numbers for each fcurve")
					#get all times
					for fcu in fcurves:
						for key in fcu.keyframe_points:
							key_time = key.co[0]
							if key_time not in times: times.append(key_time)
					times.sort()
					#sample and recreate all fcurves according to the full times
					for fcu in fcurves:
						samples = [fcu.evaluate(key_time) for key_time in times]
						fcu_dp, fcu_i = fcu.data_path, fcu.array_index
						action.fcurves.remove(fcu)
						fcu = action.fcurves.new(fcu_dp, index=fcu_i, action_group=bone_name)
						fcu.keyframe_points.add(count=len(times))
						fcu.keyframe_points.foreach_set("co", [x for co in zip(times, samples) for x in co])
						fcu.update()
					#get the new curves because we deleted the original ones
					rotations = [fcurve for fcurve in group.channels if fcurve.data_path.endswith("quaternion")]
					translations = [fcurve for fcurve in group.channels if fcurve.data_path.endswith("location")]
					
				elif same_amount_of_keys:
					#ok, but the keys could still be moved to different times
					pass
				
				#first, create define how to get the timestamp and key matrix for this bone
				if (not rotations) and (not translations):
					channel_mode = 2
					num_keys = 0
				elif not translations:
					channel_mode = 0
					num_keys = len(rotations[0].keyframe_points)
					def get_key(rotations, translations, i):
						key_matrix = mathutils.Quaternion([fcurve.keyframe_points[i].co[1] for fcurve in rotations]).to_matrix().to_4x4()
						return rotations[0].keyframe_points[i].co[0]/fps, key_matrix
				elif not rotations:
					channel_mode = 3
					num_keys = len(translations[0].keyframe_points)
					def get_key(rotations, translations, i):
						key_matrix = mathutils.Matrix()
						key_matrix.translation = [fcurve.keyframe_points[i].co[1] for fcurve in translations]
						return translations[0].keyframe_points[i].co[0]/fps, key_matrix
				else:
					channel_mode = 1
					num_keys = len(rotations[0].keyframe_points)
					def get_key(rotations, translations, i):
						key_matrix = mathutils.Quaternion([fcurve.keyframe_points[i].co[1] for fcurve in rotations]).to_matrix().to_4x4()
						key_matrix.translation = [fcurve.keyframe_points[i].co[1] for fcurve in translations]
						return rotations[0].keyframe_points[i].co[0]/fps, key_matrix
				
				#now, we assume that all curves are the same length and the keys are in columns
				channel_bytes.append(pack('2H', channel_mode, num_keys ))
				for i in range(0, num_keys):
					#space conversion, simply inverse of import
					try:
						timestamp, key_matrix = get_key(rotations, translations, i)
					except:
						log_error("Bone "+bone_name+" in "+action_name+" has incomplete / faulty keyframes.")
					
					key_matrix = correction_local.inverted() * key_matrix * correction_local
					key_matrix = fallback_matrix[group.name] * key_matrix
					
					q = key_matrix.to_quaternion()
					l = key_matrix.to_translation()
				
					#even if use_channel says no, things still have to be written!
					if l not in all_locs: all_locs.append(l)
					if q not in all_quats: all_quats.append(q)
					
					#super primitive indexing, it should be using a KD-Tree for closest neighbour search.
					l_index = all_locs.index(l)
					q_index = all_quats.index(q)
					
					channel_bytes.append(pack('f2H', timestamp, l_index, q_index ))
				# size of this channel: channelinfo (4b) + num_keys * key (8b)
				offset += 4 + num_keys * 8
			channels_bytes += channel_pointer_bytes + channel_bytes
			
		anim_bytes += channels_bytes
		anim_bytes = b"".join(anim_bytes)
	
		print("Final Loc keys:",len(all_locs))
		print("Final Rot keys:",len(all_quats))	
		
		#create the TKL file
		tkl_path = os.path.join(os.path.dirname(filepath), tkl_ref+".tkl")
		print("\nWriting",tkl_path)
		
		#new test
		if pad_anims:
			all_locs.extend([all_locs[0] for x in range(num_loc-len(all_locs))])
			all_quats.extend([all_quats[0] for x in range(num_rot-len(all_quats))])
		
		tkl_locs = [pack("3f", *l) for l in all_locs]
		tkl_quats = [pack("4f", q.x, q.y, q.z, q.w) for q in all_quats]
		tkl_len_data = len(tkl_locs)*16 + len(tkl_quats)*12
		#54 or 39- both exist?
		#x = 54
		#tkl_header = pack("4s I I 6s 10B 2I 5I", b"TPKL", 0, tkl_len_data+44, tkl_ref.encode("utf-8"), x, 0, 160, 152, x, 0, 212, 254, 18, 0, len(all_locs), len(all_quats), 0, 12, 16, 4, tkl_len_data)
		tkl_header = pack("4s 4B I 6s 10B 2I 5I", b"TPKL", tkl_b00, tkl_b01, tkl_b02, tkl_b03, tkl_len_data+44, tkl_ref.encode("utf-8"), tkl_b04, tkl_b05, tkl_b06, tkl_b07, tkl_b08, tkl_b09, tkl_b10, tkl_b11, tkl_b12, tkl_b13, len(all_locs), len(all_quats), tkl_i00, tkl_i01, tkl_i02, tkl_i03, tkl_len_data)
		with open(tkl_path, 'wb') as f:
			f.write(b"".join( (tkl_header, b"".join(tkl_locs), b"".join(tkl_quats) ) ))
		
	#find all models
	lod_bytes = []
	lods = []

	#ideally
	#ob.layers = (1 0 0 0 0 0 ...)
	#ob.layers = (0 1 0 0 0 0 ...)
	#bad data
	#ob.layers = (1 1 1 1 1 0 ...)
	for i in range(0,10):
		lod = [ob for ob in bpy.data.objects if "_LOD"+str(i) in ob.name]
		if lod: lods.append(lod)
		else: break
	if not lods:
		log_error("Could not find any LODs! Follow the naming convention of imported TMDs!")
		return errors
	
	max_lod_distance = 2 * max(max(ob.dimensions) for ob in bpy.data.objects)
	lod_bytes.append(pack('I f', len(lods), max_lod_distance))
	for lod in lods:
		#possibly LOD extents, ie. near far distance and bias?
		#note that these values are the same for all lods
		#might also be some bounding volume, sphere maybe (f3 = diameter)
		f0 = 0.05 * max_lod_distance
		f1 = -0.02 * max_lod_distance
		f2 = 0.1 * max_lod_distance
		f3 = 0.9 * max_lod_distance
		lod_bytes.append(pack('I f 4f ',len(lod), 0, f0, f1, f2, f3))
		for ob in lod:
			print("\nProcessing mesh of",ob.name)
			
			#remove unneeded modifiers
			for mod in ob.modifiers:
				if mod.type in ('ARMATURE','TRIANGULATE'):
					ob.modifiers.remove(mod)
			ob.modifiers.new('Triangulate', 'TRIANGULATE')
			#make a copy with all modifiers applied - I think there was another way to do it too
			me = ob.to_mesh(bpy.context.scene, True, "PREVIEW", calc_tessface=True, calc_undeformed=False)
			me.calc_normals_split()
			#and restore the armature modifier
			ob.modifiers.new('SkinDeform', 'ARMATURE').object = armature
			
			#initialize the piece lists
			max_pieces = 4
			bones_pieces = []
			tris_pieces = []
			for i in range(0, max_pieces):
				bones_pieces.append([])
				tris_pieces.append([])
				
			print("Splitting into pieces of <= 28 bones")
			#first step:
			#go over all triangles, see which bones their verts use, see which tri goes into which piece
			for polygon in me.polygons:
				tri_bones = set()
				for loop_index in polygon.loop_indices:
					vertex = me.vertices[me.loops[loop_index].vertex_index]
					#we can only look up the name here, and index it per piece
					for vertex_group in vertex.groups:
						bone_name = ob.vertex_groups[vertex_group.group].name
						bone_weight = vertex_group.weight
						#should this vertex group be used?
						if bone_weight > 0 and bone_name in bone_names:
							#add it to the set
							tri_bones.add(bone_name)
					
				#go over all pieces and see where we can add this tri
				for i in range(0, max_pieces):
					#see how many bones this triangle would add to the piece
					bones_to_add = sum([1 for bone_name in tri_bones if bone_name not in bones_pieces[i]])
					
					#so can we add it to this piece? if not go to the next loop/piece
					if len(bones_pieces[i]) + bones_to_add > MAX_BONES_PER_PIECE:
						continue
						
					#ok we can add it, so add it to the bones
					#add only unique - don't use a set here because it must be sorted. then we can do the bone lookup in the same step
					#all second order pieces will use the same bone list!
					for bone_name in tri_bones:
						if bone_name not in bones_pieces[i]:
							bones_pieces[i].append(bone_name)
					
					#also add the tri
					tris_pieces[i].append(polygon.loop_indices)
					
					#ok, done, skip the other pieces because the tri is already added
					break
			
			uv_layer = me.uv_layers[0].data
			piece_data = []
			mesh_vertices = []
			dummy_vertices = []
			#do the second splitting
			for temp_piece_i in range(0, max_pieces):
				if bones_pieces[temp_piece_i]:
					print("\nProcessing temp piece", temp_piece_i)
					print("temp tris:", len(tris_pieces[temp_piece_i]))
					print("temp bones:", len(bones_pieces[temp_piece_i]))
					
					#at this point we have the tris in the right pieces, so all verts that are used in piece 0 will exist for piece 1 (incase we want to reuse them)
					tmd_piece_tris = []
					for tri in tris_pieces[temp_piece_i]:
						tmd_tri=[]
						for loop_index in tri:
							vertex = me.vertices[me.loops[loop_index].vertex_index]
							co = vertex.co
							no = me.loops[loop_index].normal
							#no = vertex.normal
							w = []
							#we can only look up the name here, and index it per piece
							for vertex_group in vertex.groups:
								bone_name = ob.vertex_groups[vertex_group.group].name
								bone_weight = vertex_group.weight
								#should this vertex group be used?
								if bone_weight > 0 and bone_name in bone_names:
									w.append((int(bones_pieces[temp_piece_i].index(bone_name) * 3), bone_weight))

							#could also check len(w_s)
							if not w:
								log_error("Weight painting error, at least one vertex is not weighted!")
								return errors
								
							#only use the 4 biggest keys
							w_s = sorted(w, key = lambda x:x[1], reverse = True)[0:4]
							
							#for normalization
							w_sum = sum([weight for id, weight in w_s])
							
							#pad the weight list to 4 bones, ie. add empty bones if missing
							for i in range(0, 4-len(w_s)): w_s.append((0,0))
							
							#index the bone names, and build the list of bones used in this piece's strip
							b = [id for id, weight in w_s]
							w = [int(weight / w_sum * 255) for id, weight in w_s]
							
							#the final vert
							vert = pack('3f 3f 4B 4B 2f', co.x, co.y, co.z, no.x, no.y, no.z, *w, *b, uv_layer[loop_index].uv.x, -uv_layer[loop_index].uv.y )
							dummy = pack('3f 2f', co.x, co.y, co.z, uv_layer[loop_index].uv.x, -uv_layer[loop_index].uv.y )
							#we could probably spread them out by pieces, but it doesn't seem to be required
							if dummy not in dummy_vertices:
								dummy_vertices.append(dummy)
								mesh_vertices.append(vert)
							
							# #get the corrected index for this tri
							tmd_tri.append(dummy_vertices.index(dummy))
						tmd_piece_tris.append(tmd_tri)
					#there is just one input strip created from the triangles
					in_strip = stripify(tmd_piece_tris, stitchstrips = True)[0]
					
					#then we must split
					piece_len = 7500
					overlap = 2
					for n in range(0, len(in_strip), piece_len):
						piece_data.append((in_strip[n : piece_len+n+overlap], bones_pieces[temp_piece_i]))
						
			num_pieces = len(piece_data)
			num_all_strip_indices = sum([len(strip) for strip, piece_bone_names in piece_data])
			num_all_verts = len(mesh_vertices)
			
			print("\nWriting mesh",ob.name)
			print("pieces:",num_pieces)
			print("all_strip_entries:",num_all_strip_indices)
			print("all_verts:",num_all_verts)
			lod_bytes.append(pack("3I 32s ", num_pieces, num_all_strip_indices, num_all_verts, me.materials[0].name.encode("utf-8")))
			for piece_i in range(0, len(piece_data)):
				
				print("\nWriting piece",piece_i)
				strip, piece_bone_names = piece_data[piece_i]
				# apparently, this does not fix the issue for acro
				# for bone_name in piece_bone_names:
					# bone = armature.data.bones[bone_name]
					# if bone.parent:
						# parent_name = bone.parent.name
						# if parent_name not in piece_bone_names:
							# if len(piece_bone_names) < MAX_BONES_PER_PIECE:
								# print("Extending bone parent chain by",parent_name)
								# piece_bone_names.append(parent_name)
				#print(piece_bone_names)
				print("piece_bones:", len(piece_bone_names))
				
				#note that these are for the whole object and not the piece - might have to be adjusted
				bbc_x, bbc_y, bbc_z = 0.125 * sum((mathutils.Vector(b) for b in ob.bound_box), mathutils.Vector())
				bbe_x, bbe_y, bbe_z = ob.dimensions
			
				#just dump all verts into the last piece
				piece_verts = []
				#if piece_i == len(piece_data)-1:
				if piece_i == 0:
					piece_verts = mesh_vertices
				
				print("strip_entries:", len(strip))
				print("piece_verts:", len(piece_verts))
				
				#write the mesh_piece header
				lod_bytes.append(pack("4I 3f 3f", len(strip), len(piece_verts), len(piece_bone_names), max(strip), bbc_x, bbc_y, bbc_z, bbe_x, bbe_y, bbe_z))
				
				#write the piece_bones
				lod_bytes.append(pack(str(len(piece_bone_names))+"I", *[bone_names.index(bone_name) for bone_name in piece_bone_names]))
				
				#write the verts
				lod_bytes.append(b"".join(piece_verts))
				
				#write the whole tristrip
				lod_bytes.append(pack(str(len(strip))+"h", *strip))
		
	lod_bytes = b"".join(lod_bytes)

	with open(filepath, 'wb') as f:
		remaining_bytes = 112 + len(bones_bytes) + len(anim_bytes) + len(lod_bytes)
		
		lod_offset = anim_pointer-60+len(anim_bytes)
		print("node_data",node_data)
		print("anim_pointer",anim_pointer)
		print("lod_offset",lod_offset)
		header_bytes = pack('8s I 8s 2L 4I 4I', b"TMDL", remaining_bytes, tkl_ref.encode("utf-8"), magic_value1, magic_value2, lod_offset, salt, u1, u2, 0,0,0,0 )+ pack("I 4H 11I", lod_offset, len(bone_names), u3, num_anims, u4, 0,0,0,0,0,0,0,0,0,0,0)+ pack("2I", node_data-60+salt, anim_pointer-60+salt)
		f.write(b"".join((header_bytes, bones_bytes, anim_bytes, lod_bytes)))

	success = '\nFinished TMD Export in %.2f seconds\n' %(time.clock()-starttime)
	print(success)
	return errors