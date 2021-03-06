""" Generate DTM in Blender

Using the Displace and Decimate modifiers to generate a terrain 3D model from
(geo)images (png, tif, geotif, etc)
"""
import os
import sys
import subprocess
import bpy # Blender Python API

def new_texture():
    bpy.ops.texture.new()
    return bpy.data.textures[-1]

def new_material():
    bpy.ops.material.new()
    return bpy.data.materials[-1]

def open_image(filepath):
    bpy.ops.image.open(filepath=filepath)
    return bpy.data.images[-1]

def new_image_texture(material, image, name='img'):
    """ Create a new texture from an image (which we open)

    we need a material here, to set the texture active
    otherwise we can't change its type (to image in this case)
    """
    material.active_texture = new_texture()
    material.active_texture.name = name
    material.active_texture.type = 'IMAGE'
    material.active_texture.image = image
    return material.active_texture

def new_plane(name='Plane', scale=(1,1,1)):
    bpy.ops.object.select_all(action='DESELECT')
    bpy.ops.mesh.primitive_plane_add()
    bpy.context.object.scale = scale
    bpy.context.object.name = name
    return bpy.context.object

def select_only(obj):
    bpy.ops.object.select_all(action='DESELECT')
    obj.select = True
    bpy.context.scene.objects.active = obj

def subdivide(obj, number_cuts=1):
    select_only(obj)
    bpy.ops.object.mode_set(mode='EDIT')
    bpy.ops.mesh.subdivide(number_cuts=number_cuts)
    bpy.ops.object.mode_set(mode='OBJECT')
    return obj

def new_cube(name='Cube', scale=(1,1,1)):
    bpy.ops.object.select_all(action='DESELECT')
    bpy.ops.mesh.primitive_cube_add()
    bpy.context.object.scale = scale
    bpy.context.object.name = name
    return bpy.context.object

def set_viewport(viewport_shade='WIREFRAME', clip_end=1000):
    """ Set the default view mode

    :param viewport_shade: enum in ['BOUNDBOX', 'WIREFRAME', 'SOLID', 'TEXTURED'], default 'WIREFRAME'
    """
    for area in bpy.context.window.screen.areas:
        if area.type == 'VIEW_3D':
            for space in area.spaces:
                if space.type == 'VIEW_3D':
                    space.viewport_shade = viewport_shade
                    space.clip_end = clip_end

def save(filepath=None, check_existing=False, compress=True):
    """ Save .blend file

    :param filepath: File Path
    :type  filepath: string, (optional, default: current file)
    :param check_existing: Check and warn on overwriting existing files
    :type  check_existing: boolean, (optional, default: False)
    :param compress: Compress, Write compressed .blend file
    :type  compress: boolean, (optional, default: True)
    """
    if not filepath:
        filepath = bpy.data.filepath
    bpy.ops.wm.save_mainfile(filepath=filepath, check_existing=check_existing,
            compress=compress)

def setup():
    """ Setup the scene """
    # Delete the default objects
    bpy.ops.object.select_all(action='SELECT')
    bpy.ops.object.delete()
    # Add light (sun)
    bpy.ops.object.lamp_add(type='SUN', location=(0, 0, 300))
    # Set Game mode
    bpy.context.scene.render.engine = 'BLENDER_GAME'
    # make sure OpenGL shading language shaders (GLSL) is the
    # material mode to use for rendering
    bpy.context.scene.game_settings.material_mode = 'GLSL'
    # Set the unit system to use for button display (in edit mode) to metric
    bpy.context.scene.unit_settings.system = 'METRIC'
    # Select the type of Framing to Extend,
    # Show the entire viewport in the display window,
    # viewing more horizontally or vertically.
    bpy.context.scene.game_settings.frame_type = 'EXTEND'
    # see the texture in realtime (in the 3D viewport)
    set_viewport('TEXTURED', 10000)
    # Set the color at the horizon to dark azure
    bpy.context.scene.world.horizon_color = (0.05, 0.22, 0.4)
    # Display framerate and profile information of the simulation
    bpy.context.scene.game_settings.show_framerate_profile = True

def usage():
    sys.stderr.write('usage: blender -P blend_dtm.py -- file_dem.tiff file_img.tiff\n')

def ext_exec(cmd, python=None):
    if not python:
        python = 'python%i.%i'%(sys.version_info.major, sys.version_info.minor)

    return subprocess.getoutput('%s -c"%s"' % (python, cmd) )

def fix_python_path(python=None):
    pythonpath = ext_exec("import os,sys;print(os.pathsep.join(sys.path))")
    sys.path.extend(pythonpath.split(os.pathsep))

def geotransform(filepath):
    """ Get the GeoTransform from the :param:filepath DEM using gdal

    In a north up image, padfTransform[1] is the pixel width,
    and padfTransform[5] is the pixel height. The upper left corner of the
    upper left pixel is at position (padfTransform[0],padfTransform[3]).

    The default transform is (0,1,0,0,0,1)
    """
    try:
        # Run externally since `gdal.Open` crashes Blender :-/
        geot = ext_exec("import gdal,gdalconst;print(gdal.Open('%s', gdalconst.GA_ReadOnly).GetGeoTransform())"%filepath)
        if geot:
            print('[DEBUG] GetGeoTransform: %s'%geot)
            return [float(value) for value in geot[1:-1].split(', ')]
    except Exception:
        print('[WARNING] GDAL error GetGeoTransform')
    return (0,1,0,0,0,1)

def main(argv=[]):
    args = []
    if '--' in argv:
        args = argv[argv.index('--')+1:]

    if len(args) < 2:
        usage()
        return 1

    image_dem = open_image(args[0])
    image_img = open_image(args[1])
    if image_dem.size[:] != image_img.size[:]:
        print('[WARN] The size of the 2 image differ')

    fix_python_path()
    geot = geotransform(args[0])
    xsize = image_dem.size[0] * abs(geot[1]) / 2
    ysize = image_dem.size[1] * abs(geot[5]) / 2

    setup()

    #########################################################################
    # Add our ground object
    ground = new_plane('Ground', (xsize, ysize, 1))
    subdivide(ground, max(xsize, ysize))

    #########################################################################
    # Add material
    ground.active_material = new_material()
    ground.active_material.specular_intensity = 0
    ground.active_material.name = 'Ground'
    material = ground.active_material

    #########################################################################
    # Add texture
    image_dem.colorspace_settings.name = 'Linear'
    texture_dem = new_image_texture(material, image_dem, 'dem')
    # do not show on the material (use only later for the terrain modifier)
    material.use_textures[material.active_texture_index] = False

    material.active_texture_index += 1
    texture_img = new_image_texture(material, image_img, 'img')

    #bpy.ops.object.shade_smooth()
    # TODO get depth resolution from image_dem (w/gdal)
    add_displace_modifier(ground, texture_dem)
    #add_decimate_modifier(ground)
    #add_water_cube((xsize+1, ysize+1, max(image_dem.pixels)/2))

    bpy.ops.file.pack_all() # bpy.ops.image.pack(as_png=True)
    save('/tmp/dtm.blend')
    # bpy.ops.view3d.view_selected(use_all_regions=True) # XXX no poll()
    return 0

def add_water_cube(scale=(1,1,1)):
    """ Add cube 'water' to hide the bottom

    (save memory, don't render many vertices)
    """
    cube = new_cube('Water', scale)
    cube.active_material = new_material()
    cube.active_material.name = 'Water'
    cube.active_material.use_shadeless = True
    cube.active_material.diffuse_color = (0.3, 0.4, 0.8)
    return cube

def add_displace_modifier(obj, texture, strength=1, direction='Z', apply=False):
    """ Add displace modifier

    http://wiki.blender.org/index.php/Doc:2.6/Manual/Modifiers/Deform/Displace
    """
    select_only(obj)
    bpy.ops.object.modifier_add(type='DISPLACE')
    modifier = bpy.context.object.modifiers[-1]
    modifier.texture = texture
    modifier.strength = strength
    modifier.direction = direction
    if apply:
        bpy.ops.object.modifier_apply(modifier=modifier.name)
    return modifier

def add_decimate_modifier(obj, ratio=0.5, apply=False, show_viewport=False):
    """ Add displace modifier

    http://wiki.blender.org/index.php/Doc:2.6/Manual/Modifiers/Generate/Decimate
    """
    select_only(obj)
    bpy.ops.object.modifier_add(type='DECIMATE')
    modifier = bpy.context.object.modifiers[-1]
    modifier.show_viewport = show_viewport # no preview : faster
    modifier.ratio = ratio
    if apply:
        bpy.ops.object.modifier_apply(modifier=modifier.name)
    return modifier

def add_hillshade(demfile, material):
    """ Add hillshade """
    hillshade_png = '%s.hillshade.png'%demfile
    if not os.path.isfile(hillshade_png):
        subprocess.getstatusoutput("gdaldem hillshade %s %s -of png"%(demfile, hillshade_png))
    image_hsh = open_image(hillshade_png)
    material.active_texture_index += 1
    texture_hsh = new_image_texture(material, image_hsh, 'hsh')
    texture_hsh.use_normal_map = True
    texture_slot_hsh = material.texture_slots[material.active_texture_index]
    texture_slot_hsh.use_map_color_diffuse = False
    texture_slot_hsh.use_map_normal = True
    texture_slot_hsh.normal_factor = -0.5

if __name__ == '__main__':
    main(sys.argv)
