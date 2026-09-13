import bpy
import os

TOOLS_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
PROJECT_ROOT = os.path.abspath(os.path.join(TOOLS_ROOT, '..', '..'))
SOURCE_ROOT = os.path.join(TOOLS_ROOT, 'output', 'worker_cleaner_female')
DESTINATION_ROOT = os.path.join(PROJECT_ROOT, 'assets', 'pedestrians', 'worker_cleaner_female')

# Shared with CANONICAL_WALK: one constant crop/canvas for all 16 frames.
CROP_X = 64
CROP_Y = 32
CROP_WIDTH = 128
CROP_HEIGHT = 192
SOURCE_CHARACTER_HEIGHT = 162.0
TARGET_CHARACTER_HEIGHT = 32
TARGET_WIDTH = max(1, round(CROP_WIDTH * TARGET_CHARACTER_HEIGHT / SOURCE_CHARACTER_HEIGHT))
TARGET_HEIGHT = max(1, round(CROP_HEIGHT * TARGET_CHARACTER_HEIGHT / SOURCE_CHARACTER_HEIGHT))


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


for direction in ('se', 'sw', 'nw', 'ne'):
    source_folder = os.path.join(SOURCE_ROOT, direction)
    destination_folder = os.path.join(DESTINATION_ROOT, direction)
    os.makedirs(destination_folder, exist_ok=True)
    for index in range(4):
        image = bpy.data.images.load(os.path.join(source_folder, 'frame_{:02d}.png'.format(index)), check_existing=False)
        cropped = common_crop(image, 'worker_cleaner_female_{}_{}'.format(direction, index))
        cropped.scale(TARGET_WIDTH, TARGET_HEIGHT)
        cropped.filepath_raw = os.path.join(destination_folder, 'frame_{:02d}.png'.format(index))
        cropped.file_format = 'PNG'
        cropped.save()
        bpy.data.images.remove(cropped)
        bpy.data.images.remove(image)

print('WORKER_CLEANER_FEMALE_RUNTIME directions=4 frame_size={}x{} character_height={}'.format(TARGET_WIDTH, TARGET_HEIGHT, TARGET_CHARACTER_HEIGHT))
