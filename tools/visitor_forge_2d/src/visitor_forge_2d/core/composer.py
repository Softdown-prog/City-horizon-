from __future__ import annotations

import math
from pathlib import Path
from typing import Iterable

from PIL import Image, ImageChops

from .model import CharacterDefinition, JointSpec, JointTransform, LayerSpec, PoseSpec

# Affine matrix layout:
# x' = a*x + b*y + c
# y' = d*x + e*y + f
Matrix = tuple[float, float, float, float, float, float]
IDENTITY: Matrix = (1.0, 0.0, 0.0, 0.0, 1.0, 0.0)


def _mul(left: Matrix, right: Matrix) -> Matrix:
    a1, b1, c1, d1, e1, f1 = left
    a2, b2, c2, d2, e2, f2 = right
    return (
        a1 * a2 + b1 * d2,
        a1 * b2 + b1 * e2,
        a1 * c2 + b1 * f2 + c1,
        d1 * a2 + e1 * d2,
        d1 * b2 + e1 * e2,
        d1 * c2 + e1 * f2 + f1,
    )


def _translate(x: float, y: float) -> Matrix:
    return (1.0, 0.0, x, 0.0, 1.0, y)


def _rotate_scale(rotation_degrees: float, sx: float, sy: float) -> Matrix:
    angle = math.radians(rotation_degrees)
    cosine = math.cos(angle)
    sine = math.sin(angle)
    return (cosine * sx, -sine * sy, 0.0, sine * sx, cosine * sy, 0.0)


def _inverse(matrix: Matrix) -> Matrix:
    a, b, c, d, e, f = matrix
    determinant = a * e - b * d
    if abs(determinant) < 1e-8:
        raise ValueError("Non-invertible 2D transform")
    inv = 1.0 / determinant
    ia = e * inv
    ib = -b * inv
    id_ = -d * inv
    ie = a * inv
    ic = -(ia * c + ib * f)
    iff = -(id_ * c + ie * f)
    return (ia, ib, ic, id_, ie, iff)


def _hex_rgba(value: str) -> tuple[int, int, int, int]:
    text = value.strip().lstrip("#")
    if len(text) == 6:
        text += "FF"
    if len(text) != 8:
        raise ValueError(f"Expected #RRGGBB or #RRGGBBAA, got {value!r}")
    return tuple(int(text[index : index + 2], 16) for index in (0, 2, 4, 6))  # type: ignore[return-value]


def _apply_tint(image: Image.Image, color: tuple[int, int, int, int]) -> Image.Image:
    """Multiply RGB by a palette color while preserving painted luminance/alpha.

    White source pixels become the palette color. Existing darker pixels keep
    their shading. This lets the art library use simple grayscale masks without
    forcing the compositor to understand clothes, skin, hair, etc.
    """
    source = image.convert("RGBA")
    rgb = source.convert("RGB")
    tint = Image.new("RGB", source.size, color[:3])
    tinted = ImageChops.multiply(rgb, tint)
    alpha = source.getchannel("A")
    if color[3] != 255:
        alpha = alpha.point(lambda value: int(value * color[3] / 255.0))
    tinted.putalpha(alpha)
    return tinted


def _apply_opacity(image: Image.Image, opacity: float) -> Image.Image:
    if opacity >= 0.999:
        return image
    result = image.copy()
    alpha = result.getchannel("A").point(lambda value: int(value * opacity))
    result.putalpha(alpha)
    return result


class LayerComposer:
    """Compose articulated RGBA parts on a high-resolution working canvas.

    The core deliberately knows nothing about humans. A character module merely
    supplies a skeleton, layers and poses. The same compositor can later drive
    mascots, animals, animated signs or other layered 2D assets.
    """

    def __init__(self, asset_root: str | Path) -> None:
        self.asset_root = Path(asset_root)

    def _load_layer(self, layer: LayerSpec, definition: CharacterDefinition) -> Image.Image:
        source = (self.asset_root / layer.source).resolve()
        root = self.asset_root.resolve()
        if root != source and root not in source.parents:
            raise ValueError(f"Layer path escapes asset root: {layer.source}")
        if not source.is_file():
            raise FileNotFoundError(f"Layer source not found: {source}")

        image = Image.open(source).convert("RGBA")
        if layer.palette_slot:
            color_value = definition.palette.get(layer.palette_slot)
            if color_value is None:
                raise ValueError(
                    f"Layer {layer.layer_id} requests missing palette slot {layer.palette_slot}"
                )
            image = _apply_tint(image, _hex_rgba(color_value))
        return _apply_opacity(image, layer.opacity)

    @staticmethod
    def _joint_frames(definition: CharacterDefinition, pose: PoseSpec) -> dict[str, Matrix]:
        frames: dict[str, Matrix] = {}

        def resolve(joint_id: str) -> Matrix:
            if joint_id in frames:
                return frames[joint_id]

            joint: JointSpec = definition.joints[joint_id]
            transform: JointTransform = pose.joints.get(joint_id, JointTransform())
            local_rs = _rotate_scale(
                transform.rotation_degrees,
                transform.scale.x,
                transform.scale.y,
            )

            if joint.parent is None:
                frame = _mul(
                    _translate(
                        joint.position.x + transform.translation.x,
                        joint.position.y + transform.translation.y,
                    ),
                    local_rs,
                )
            else:
                parent = definition.joints[joint.parent]
                parent_frame = resolve(joint.parent)
                offset_x = joint.position.x - parent.position.x + transform.translation.x
                offset_y = joint.position.y - parent.position.y + transform.translation.y
                frame = _mul(_mul(parent_frame, _translate(offset_x, offset_y)), local_rs)

            frames[joint_id] = frame
            return frame

        for joint_id in definition.joints:
            resolve(joint_id)
        return frames

    @staticmethod
    def _layer_to_canvas(layer_image: Image.Image, layer: LayerSpec, size: tuple[int, int]) -> Image.Image:
        canvas = Image.new("RGBA", size, (0, 0, 0, 0))
        left = int(round(layer.position.x - layer.pivot.x))
        top = int(round(layer.position.y - layer.pivot.y))
        canvas.alpha_composite(layer_image, (left, top))
        return canvas

    @staticmethod
    def _transform_canvas(image: Image.Image, matrix: Matrix) -> Image.Image:
        inverse = _inverse(matrix)
        return image.transform(
            image.size,
            Image.Transform.AFFINE,
            inverse,
            resample=Image.Resampling.BICUBIC,
        )

    def compose(self, definition: CharacterDefinition, pose: PoseSpec) -> Image.Image:
        if pose.direction != definition.direction:
            raise ValueError(
                f"Pose direction {pose.direction!r} does not match character direction "
                f"{definition.direction!r}"
            )

        size = definition.canvas.working_size
        result = Image.new("RGBA", size, (0, 0, 0, 0))
        joint_frames = self._joint_frames(definition, pose)
        part_by_layer = {part.layer_id: part for part in definition.parts}

        layers: Iterable[LayerSpec] = sorted(
            (layer for layer in definition.layers.values() if layer.visible),
            key=lambda layer: (layer.z_index, layer.layer_id),
        )

        for layer in layers:
            source = self._load_layer(layer, definition)
            layer_canvas = self._layer_to_canvas(source, layer, size)
            part = part_by_layer.get(layer.layer_id)
            if part and part.joint_id:
                joint = definition.joints[part.joint_id]
                # joint_frames maps joint-local coordinates to posed canvas.
                # Convert base canvas coordinates to joint-local first.
                matrix = _mul(joint_frames[part.joint_id], _translate(-joint.position.x, -joint.position.y))
                layer_canvas = self._transform_canvas(layer_canvas, matrix)
            result = Image.alpha_composite(result, layer_canvas)

        return result
