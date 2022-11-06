bl_info = {	"name": "Toshi TMD format (JPOG)",
			"author": "Equinox, HENDRIX & AdventureT",
			"blender": (2, 80, 0),
			"location": "File > Import-Export",
			"description": "Import-Export models, skeletons and animations.",
			"warning": "",
			"wiki_url": "https://github.com/HENDRIX-ZT2/jpog-blender",
			"support": 'COMMUNITY',
			"tracker_url": "https://github.com/HENDRIX-ZT2/jpog-blender/issues/new",
			"category": "Import-Export"}


import bpy
from bpy.props import StringProperty, BoolProperty
from bpy_extras.io_utils import ImportHelper, ExportHelper
from bpy_extras.object_utils import AddObjectHelper, object_data_add
import bpy.utils.previews
preview_collection = bpy.utils.previews.new()


class Toshi_OT_ApplyScaleToObAndAnims(bpy.types.Operator):
	"""Apply Scale to Objects and Animations."""
	bl_idname = "object.apply_scale_ob_anims"
	bl_label = "Apply Scale to Objects and Animations"
	bl_options = {'REGISTER', 'UNDO'}
	change_speed : BoolProperty(name="Adjust Speed", description="Counter the scale with a speed adjustment to prevent slithering.", default=False)
			
	def execute(self, context):
		from . import apply_scale_ob_anims
		keywords = self.as_keywords(ignore=("axis_forward", "axis_up", "filter_glob"))
		apply_scale_ob_anims.run(self, context, **keywords)
		return {'FINISHED'}
	
class Toshi_OT_ImportTMD(bpy.types.Operator, ImportHelper):
	"""Import from TMD file format (.TMD)"""
	bl_idname = "import_scene.toshi_tmd"
	bl_label = 'Import TMD'
	bl_options = {'UNDO'}
	filename_ext = ".tmd"
	filter_glob : StringProperty(default="*.tmd", options={'HIDDEN'})
	use_custom_normals : BoolProperty(name="Use TMD Normals", description="Preserves the original shading of a TMD.", default=False)
	use_anims : BoolProperty(name="Import Anims", description="If checked, all animations will be imported.", default=True)
	extract_textures : BoolProperty(name="Extract TMLs", description="Unpack textures from TML files.", default=True)
	set_fps : BoolProperty(name="Adjust FPS", description="Set the scene to 30 frames per second to conform with the TMDs.", default=True)
	def execute(self, context):
		from . import import_tmd
		keywords = self.as_keywords(ignore=("axis_forward", "axis_up", "filter_glob"))
		errors = import_tmd.load(self, context, **keywords)
		for error in errors:
			self.report({"ERROR"}, error)
		return {'FINISHED'}

class Toshi_OT_ExportTMD(bpy.types.Operator, ExportHelper):
	"""Export to TMD file format (.TMD)"""
	bl_idname = "export_scene.toshi_tmd"
	bl_label = 'Export TMD'
	filename_ext = ".tmd"
	filter_glob : StringProperty(default="*.tmd", options={'HIDDEN'})
	export_anims : BoolProperty(name="Export Anims", description="If checked, animations are exported from blender. If not, keyframes are copied from the imported TMD and no TKL is created.", default=False)
	pad_anims : BoolProperty(name="Pad Anims", description="If checked, only keyframes from blender will be exported and then padded to the original length of the TKL. Good for quick tests. Warning - this can overwrite original TKLs. Use the tkl-merger for proper versions and turn this off. If it is off, the exported TKL file has the same name as your exported model.", default=False)
	def execute(self, context):
		from . import export_tmd
		keywords = self.as_keywords(ignore=("axis_forward", "axis_up", "filter_glob", "check_existing"))
		errors = export_tmd.save(self, context, **keywords)
		for error in errors:
			self.report({"ERROR"}, error)
		return {'FINISHED'}


classes = (
	Toshi_OT_ImportTMD,
	Toshi_OT_ExportTMD,
	Toshi_OT_ApplyScaleToObAndAnims
)

#Add to a menu
def menu_func_export(self, context):
	self.layout.operator(Toshi_OT_ExportTMD.bl_idname, text="Toshi Model (.tmd)", icon_value=preview_collection["jpog.png"].icon_id)

def menu_func_import(self, context):
	self.layout.operator(Toshi_OT_ImportTMD.bl_idname, text="Toshi Model (.tmd)", icon_value=preview_collection["jpog.png"].icon_id)

def menu_func_obj(self, context):
	self.layout.operator(Toshi_OT_ApplyScaleToObAndAnims.bl_idname, icon_value=preview_collection["jpog.png"].icon_id)
	
def register():
	import os
	icons_dir = os.path.join(os.path.dirname(__file__), "icons")
	for icon_name_ext in os.listdir(icons_dir):
		icon_name = os.path.basename(icon_name_ext)
		preview_collection.load(icon_name, os.path.join(os.path.join(os.path.dirname(__file__), "icons"), icon_name_ext), 'IMAGE')
	
	for c in classes: bpy.utils.register_class(c)
    		
	bpy.types.TOPBAR_MT_file_import.append(menu_func_import)
	bpy.types.TOPBAR_MT_file_export.append(menu_func_export)
	bpy.types.VIEW3D_PT_active_tool.append(menu_func_obj)
	
def unregister():
	bpy.utils.previews.remove(preview_collection)

	for c in classes: bpy.utils.unregister_class(c)

	bpy.types.TOPBAR_MT_file_import.remove(menu_func_import)
	bpy.types.TOPBAR_MT_file_export.remove(menu_func_export)
	bpy.types.VIEW3D_PT_active_tool.remove(menu_func_obj)

if __name__ == "__main__":
	register()
