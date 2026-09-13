import bpy
import os

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
SOURCE = os.path.join(ROOT, 'output', 'test_walk_se')
DESTINATION = os.path.join(ROOT, 'output', 'runtime_size_calibration')

# This is one shared source rectangle, deliberately not a per-frame alpha crop.
# It keeps the ground anchor and canvas stable while testing visible character
# heights of 24, 28 and 32 pixels in the SDL runtime.
CROP_X = 64
CROP_Y = 32
CROP_WIDTH = 128
CROP_HEIGHT = 192
SOURCE_CHARACTER_HEIGHT = 162.0


def common_crop(image, name):
    cropped = bpy.data.images.new(name, width=CROP_WIDTH, height=CROP_HEIGHT, alpha=True)
    source = list(image.pixels)
    pixels = [0.0] * (CROP_WIDTH * CROP_HEIGHT * 4)
    for row in range(CROP_HEIGHT):
        source_offset = ((CROP_Y + row) * image.size[0] + CROP_X) * 4
        target_offset = row * CROP_WIDTH * 4
        pixels[target_offset:target_offset + CROP_WIDTH * 4] = source[source_offset:source_offset + CROP_WIDTH * 4]
    cropped.pixels = pixels
    return cropped


for size in (24, 28, 32):
    folder = os.path.join(DESTINATION, str(size))
    os.makedirs(folder, exist_ok=True)
    scale = size / SOURCE_CHARACTER_HEIGHT
    target_width = max(1, round(CROP_WIDTH * scale))
    target_height = max(1, round(CROP_HEIGHT * scale))
    for index in range(4):
        image = bpy.data.images.load(os.path.join(SOURCE, 'frame_{:02d}.png'.format(index)), check_existing=False)
        cropped = common_crop(image, 'runtime_crop_{}_{}'.format(size, index))
        cropped.scale(target_width, target_height)
        cropped.filepath_raw = os.path.join(folder, 'frame_{:02d}.png'.format(index))
        cropped.file_format = 'PNG'
        cropped.save()
        bpy.data.images.remove(cropped)
        bpy.data.images.remove(image)
print('RUNTIME_SIZE_CALIBRATION=24,28,32 SHARED_CROP=128x192')
