import bpy

def run(operator, context, change_speed = False):
	print("Apply scale to objects & anims")
	
	#get the armature
	arms = [ob for ob in bpy.data.objects if not ob.parent and type(ob.data) == bpy.types.Armature]
	if len(arms) != 1:
		return("Error, none or too many armatures")
	
	#get the scale
	arm = arms[0]
	scale = arm.scale[0]
	print("Scale:",scale)
	
	#scale all objects
	for ob in bpy.data.objects:
		ob.select = True
	bpy.ops.object.transform_apply(location = True, scale = True, rotation = True)
	
	#scale the anims
	for action in bpy.data.actions:
		print(action.name)
		for group in action.groups:
			translations = [fcurve for fcurve in group.channels if fcurve.data_path.endswith("location")]
			for fcu in translations:
				for i in range(0, len(fcu.keyframe_points)):
					fcu.keyframe_points[i].co[1] *= scale
		if change_speed:
			for fcu in action.fcurves:
				for i in range(0, len(fcu.keyframe_points)):
					fcu.keyframe_points[i].co[0] *= scale
	#redraw
	bpy.context.scene.frame_set(bpy.context.scene.frame_current)
	bpy.context.scene.update()