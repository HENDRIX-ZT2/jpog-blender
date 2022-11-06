from math import radians, atan2
import mathutils
import bpy

global errors
errors = []
correction_local = mathutils.Euler((radians(90), 0, radians(90))).to_matrix().to_4x4()
correction_global = mathutils.Euler((radians(-90), radians(-90), 0)).to_matrix().to_4x4()
	
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

# source: https://github.com/HENDRIX-ZT2/bfb-blender/blob/blender2.80/common_bfb.py
# by Hendrix

def LOD(ob, level):
    """Adds a newly created object to a lod collection, creates one if neeed, and sets their visibility"""
    lod_name = "LOD"+str(level)
    if lod_name not in bpy.data.collections:
        coll = bpy.data.collections.new(lod_name)
        bpy.context.scene.collection.children.link(coll)
    else:
        coll = bpy.data.collections[lod_name]
	# Link active object to the new collection
    coll.objects.link(ob)
	# show lod 0, hide the others
    should_hide = level != 0
	# hide object in view layer
    hide_collection(lod_name, should_hide)
	# hide object in view layer
    ob.hide_set(should_hide, view_layer=bpy.context.view_layer)



def hide_collection(lod_name, should_hide):
	# get view layer, hide collection there
	# print(list(x for x in bpy.context.view_layer.layer_collection.children))
	bpy.context.view_layer.layer_collection.children[lod_name].hide_viewport = should_hide


def ensure_active_object():
	# ensure that we have objects in the scene
	if bpy.context.scene.objects:
		# operator needs an active object, set one if missing (eg. user had deleted the active object)
		if not bpy.context.view_layer.objects.active:
			bpy.context.view_layer.objects.active = bpy.context.scene.objects[0]
		# now enter object mode on the active object, if we aren't already in it
		bpy.ops.object.mode_set(mode="OBJECT")
	else:
		print("No objects in scene, nothing to export!")