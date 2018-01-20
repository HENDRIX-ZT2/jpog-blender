bl_info = {	"name": "Toshi TMD format (JPOG)",
			"author": "Equinox & HENDRIX",
			"blender": (2, 79, 0),
			"location": "File > Import-Export",
			"description": "Import-Export models, skeletons and animations.",
			"warning": "",
			"support": 'COMMUNITY',
			"category": "Import-Export"}
			
# #need this?
if "bpy" in locals():
	import importlib
	if "import_tmd" in locals():
		importlib.reload(import_tmd)
	if "export_tmd" in locals():
		importlib.reload(export_tmd)

import bpy
from bpy.props import StringProperty, FloatProperty, BoolProperty, IntProperty, CollectionProperty
from bpy_extras.io_utils import (ImportHelper, ExportHelper)
from bpy_extras.object_utils import AddObjectHelper, object_data_add
import bpy.utils.previews
preview_collection = bpy.utils.previews.new()

class ApplyScaleToObAndAnims(bpy.types.Operator):
	"""Apply Scale to Objects and Animations."""
	bl_idname = "object.apply_scale_ob_anims"
	bl_label = "Apply Scale to Objects and Animations"
	bl_options = {'REGISTER', 'UNDO'}
			
	def execute(self, context):
		from . import apply_scale_ob_anims
		apply_scale_ob_anims.run()
		return {'FINISHED'}
	
class ImportTMD(bpy.types.Operator, ImportHelper):
	"""Import from TMD file format (.TMD)"""
	bl_idname = "import_scene.toshi_tmd"
	bl_label = 'Import TMD'
	bl_options = {'UNDO'}
	filename_ext = ".TMD"
	filter_glob = StringProperty(default="*.tmd", options={'HIDDEN'})
	use_custom_normals = BoolProperty(name="Use TMD Normals", description="Preserves the original shading of a TMD.", default=False)
	use_anims = BoolProperty(name="Import Anims", description="If checked, all animations will be imported.", default=True)
	extract_textures = BoolProperty(name="Extract TMLs", description="Unpack textures from TML files.", default=True)
	#mirror_mesh = BoolProperty(name="Mirror Rigged Meshes", description="Mirrors models with a skeleton. Careful, sometimes bones don't match!", default=True)
	def execute(self, context):
		from . import import_tmd
		keywords = self.as_keywords(ignore=("axis_forward", "axis_up", "filter_glob"))
		errors = import_tmd.load(self, context, **keywords)
		for error in errors:
			self.report({"ERROR"}, error)
		return {'FINISHED'}

class ExportTMD(bpy.types.Operator, ExportHelper):
	"""Export to TMD file format (.TMD)"""
	bl_idname = "export_scene.toshi_tmd"
	bl_label = 'Export TMD'
	filename_ext = ".TMD"
	filter_glob = StringProperty(default="*.tmd", options={'HIDDEN'})
	export_anims = BoolProperty(name="Export Anims", description="If checked, animations are exported from blender. If not, keyframes are copied from the imported TMD and no TKL is created.", default=False)
	append_anims = BoolProperty(name="Append Anims", description="If checked, the original keyframes are included in the exported TKL file. If not, only the keyframes from blender are written.", default=False)
	pad_anims = BoolProperty(name="Pad Anims", description="If checked, only keyframes from blender will be exported and then padded to the original length of the TKL.", default=False)
	# author_name = StringProperty(name="Author", description="A signature included in the TMD file.", default=author)
	# create_lods = BoolProperty(name="Create LODs", description="Adds Levels of Detail - overwrites existing LODs!", default=True)
	# numlods = IntProperty(	name="Number of LODs",
							# description="Number of Levels Of Detail, including the original",
							# min=1, max=5,
							# default=2,)
	# rate = IntProperty(	name="Detail Decrease Rate",
							# description="The higher, the faster the detail will decrease: ratio = 1 /(LODX + Rate)",
							# min=1, max=5,
							# default=2,)
	def execute(self, context):
		from . import export_tmd
		keywords = self.as_keywords(ignore=("axis_forward", "axis_up", "filter_glob", "check_existing"))
		errors = export_tmd.save(self, context, **keywords)
		for error in errors:
			self.report({"ERROR"}, error)
		return {'FINISHED'}
		
#Add to a menu
def menu_func_export(self, context):
	self.layout.operator(ExportTMD.bl_idname, text="Toshi Model (.tmd)", icon_value=preview_collection["jpog.png"].icon_id)

def menu_func_import(self, context):
	self.layout.operator(ImportTMD.bl_idname, text="Toshi Model (.tmd)", icon_value=preview_collection["jpog.png"].icon_id)

def menu_func_obj(self, context):
	self.layout.operator(ApplyScaleToObAndAnims.bl_idname, icon_value=preview_collection["jpog.png"].icon_id)
	
def register():
	import os
	icons_dir = os.path.join(os.path.dirname(__file__), "icons")
	for icon_name_ext in os.listdir(icons_dir):
		icon_name = os.path.basename(icon_name_ext)
		preview_collection.load(icon_name, os.path.join(os.path.join(os.path.dirname(__file__), "icons"), icon_name_ext), 'IMAGE')
	bpy.utils.register_module(__name__)
	
	bpy.types.INFO_MT_file_import.append(menu_func_import)
	bpy.types.INFO_MT_file_export.append(menu_func_export)
	bpy.types.VIEW3D_PT_tools_object.append(menu_func_obj)
	
def unregister():
	bpy.utils.previews.remove(preview_collection)
	
	bpy.utils.unregister_module(__name__)

	bpy.types.INFO_MT_file_import.remove(menu_func_import)
	bpy.types.INFO_MT_file_export.remove(menu_func_export)
	bpy.types.VIEW3D_PT_tools_object.remove(menu_func_obj)

if __name__ == "__main__":
	register()
