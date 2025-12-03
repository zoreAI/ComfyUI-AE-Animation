from __future__ import annotations

import base64
import io as python_io
import json
import logging
from typing import Any, Dict, List, Optional, Sequence

import cv2
import numpy as np
import torch
from PIL import Image
from comfy_api.latest import ComfyExtension, io
from typing_extensions import override


def _safe_int(value: Any, default: int = 0) -> int:
    try:
        if isinstance(value, str) and value.strip():
            return int(value)
        if value is None:
            return default
        return int(value)
    except (ValueError, TypeError):
        return default


def _parse_layers(layers_json: str) -> List[Dict[str, Any]]:
    if not layers_json:
        return []
    try:
        data = json.loads(layers_json)
        if isinstance(data, list):
            return data
        if isinstance(data, dict) and "layers" in data:
            return data.get("layers") or []
    except Exception:
        logging.warning("[AE] Failed to parse layers_keyframes JSON")
    return []


class AEAnimation(io.ComfyNode):
    """
    Single node that reads timeline data from the AE Timeline UI (layers_keyframes)
    and directly renders frames + masks.
    """

    @classmethod
    def define_schema(cls) -> io.Schema:
        schema = io.Schema(
            node_id="AEAnimation",
            display_name="AE Animation",
            category="AE Animation",
            inputs=[
                io.Int.Input("width", default=1280, min=64, max=8192),
                io.Int.Input("height", default=720, min=64, max=8192),
                io.Int.Input("fps", default=16, min=1, max=120),
                io.Int.Input("total_frames", default=81, min=1, max=9999),
                io.Int.Input("mask_expansion", default=0, min=-255, max=255),
                io.Int.Input("mask_feather", default=0, min=0, max=100),
                io.String.Input("layers_keyframes", default="[]", multiline=True),
                io.Int.Input("start_frame", default=0, min=0),
                io.Int.Input("end_frame", default=-1, min=-1),
            ],
            outputs=[
                io.Image.Output("frames"),
                io.Mask.Output("mask_frames"),
            ],
        )
        schema.output_node = True
        return schema

    # ---- helper methods (from previous AERender) ---- #
    @staticmethod
    def _get_value(keyframes: Dict[str, Any], prop: str, time: float, default: float) -> float:
        if prop not in keyframes:
            return default
        frames_data = keyframes[prop]
        if not isinstance(frames_data, list):
            return default
        frames = []
        for frame in frames_data:
            if isinstance(frame, dict) and "time" in frame and "value" in frame:
                frames.append(frame)
        if not frames:
            return default
        frames.sort(key=lambda k: k["time"])
        if time <= frames[0]["time"]:
            return frames[0]["value"]
        if time >= frames[-1]["time"]:
            return frames[-1]["value"]
        for idx in range(len(frames) - 1):
            k1, k2 = frames[idx], frames[idx + 1]
            if k1["time"] <= time <= k2["time"]:
                duration = k2["time"] - k1["time"]
                t = (time - k1["time"]) / duration if duration > 0 else 0
                return k1["value"] + (k2["value"] - k1["value"]) * t
        return default

    @staticmethod
    def _calculate_bezier_pos(path_points: List[Dict[str, float]], time: float, duration: float) -> Optional[tuple[float, float]]:
        if not path_points or len(path_points) < 2:
            return None
        t_norm = max(0.0, min(1.0, time / duration)) if duration > 0 else 0
        total_segments = len(path_points) - 1
        current_segment = min(int(t_norm * total_segments), total_segments - 1)
        segment_t = (t_norm * total_segments) - current_segment

        p0 = path_points[current_segment]
        p1 = path_points[current_segment + 1]
        p0_x, p0_y = p0.get("x", 0), p0.get("y", 0)
        p1_x, p1_y = p1.get("x", 0), p1.get("y", 0)
        cp1_x = p0.get("cp2x", p0_x + (p1_x - p0_x) / 3.0)
        cp1_y = p0.get("cp2y", p0_y + (p1_y - p0_y) / 3.0)
        cp2_x = p1.get("cp1x", p0_x + (p1_x - p0_x) * 2.0 / 3.0)
        cp2_y = p1.get("cp1y", p0_y + (p1_y - p0_y) * 2.0 / 3.0)

        mt = 1 - segment_t
        mt2 = mt * mt
        mt3 = mt2 * mt
        t2 = segment_t * segment_t
        t3 = t2 * segment_t
        x = mt3 * p0_x + 3 * mt2 * segment_t * cp1_x + 3 * mt * t2 * cp2_x + t3 * p1_x
        y = mt3 * p0_y + 3 * mt2 * segment_t * cp1_y + 3 * mt * t2 * cp2_y + t3 * p1_y
        return x, y

    @classmethod
    def _decode_layers(cls, layers: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        decoded = []
        for layer in layers:
            try:
                img_b64 = layer.get("image_data", "")
                if not img_b64:
                    continue
                img_data = base64.b64decode(img_b64.split(",", 1)[1])
                pil = Image.open(python_io.BytesIO(img_data)).convert("RGBA")
                decoded.append({
                    "data": np.array(pil),
                    "keyframes": layer.get("keyframes", {}),
                    "type": layer.get("type", "foreground"),
                    "bg_mode": layer.get("bg_mode", "fit"),
                    "customMask": layer.get("customMask"),
                    "bezierPath": layer.get("bezierPath"),
                    "x": layer.get("x", 0),
                    "y": layer.get("y", 0),
                    "scale": layer.get("scale", 1.0),
                    "rotation": layer.get("rotation", 0),
                    "opacity": layer.get("opacity", 1.0),
                })
            except Exception:  # pragma: no cover
                continue
        return decoded

    # ---- main execution ---- #
    @classmethod
    def execute(
        cls,
        width: int,
        height: int,
        fps: int,
        total_frames: int,
        mask_expansion: int,
        mask_feather: int,
        layers_keyframes: str,
        start_frame: int = 0,
        end_frame: int = -1,
    ) -> io.NodeOutput:
        layers_data = _parse_layers(layers_keyframes)

        project = {
            "width": width,
            "height": height,
            "fps": fps,
            "duration": total_frames / max(fps, 1),
            "total_frames": total_frames,
            "mask_expansion": mask_expansion,
            "mask_feather": mask_feather,
        }

        if end_frame == -1 or end_frame > total_frames:
            end_frame = total_frames

        layers = cls._decode_layers(layers_data)
        num_layers = len(layers)
        print(f"[AE] Render (single node): {width}x{height}, {start_frame}-{end_frame}/{total_frames}, {num_layers} layers")

        frames: List[torch.Tensor] = []
        masks: List[torch.Tensor] = []

        for frame_idx in range(start_frame, end_frame):
            time = frame_idx / max(fps, 1)
            canvas = np.zeros((height, width, 4), dtype=np.uint8)
            mask_canvas = np.zeros((height, width), dtype=np.uint8)

            for layer in layers:
                img_np = layer["data"].copy()
                kf = layer.get("keyframes", {})
                is_foreground = layer.get("type") == "foreground"

                x = cls._get_value(kf, "x", time, layer.get("x", 0))
                y = cls._get_value(kf, "y", time, layer.get("y", 0))

                # Bezier overrides x/y
                bezier_path = layer.get("bezierPath")
                if bezier_path and len(bezier_path) >= 2:
                    path_pos = cls._calculate_bezier_pos(bezier_path, time, project["duration"])
                    if path_pos:
                        x, y = path_pos

                scale = cls._get_value(kf, "scale", time, layer.get("scale", 1.0))
                rotation = cls._get_value(kf, "rotation", time, layer.get("rotation", 0))
                opacity = cls._get_value(kf, "opacity", time, layer.get("opacity", 1.0))
                bg_mode = layer.get("bg_mode", "fit")

                # Apply custom mask on alpha (foreground only)
                if is_foreground and layer.get("customMask"):
                    try:
                        custom_mask_b64 = layer["customMask"].split(",")[1]
                        custom_mask_data = base64.b64decode(custom_mask_b64)
                        custom_mask_img = Image.open(python_io.BytesIO(custom_mask_data)).convert("RGBA")
                        custom_mask_np = np.array(custom_mask_img)
                        orig_h, orig_w = img_np.shape[:2]
                        if custom_mask_np.shape[:2] != (orig_h, orig_w):
                            custom_mask_np = cv2.resize(custom_mask_np, (orig_w, orig_h), interpolation=cv2.INTER_LINEAR)
                        mask_alpha = custom_mask_np[:, :, 3].astype(np.float32) / 255.0
                        if img_np.shape[2] == 4:
                            img_np[:, :, 3] = (img_np[:, :, 3].astype(np.float32) * mask_alpha).astype(np.uint8)
                        else:
                            alpha_channel = (mask_alpha * 255).astype(np.uint8)
                            img_np = np.dstack((img_np, alpha_channel))
                    except Exception as e:
                        print(f"[AE] Custom mask error: {e}")

                # Scale
                new_w, new_h = img_np.shape[1], img_np.shape[0]
                if not is_foreground:
                    orig_w, orig_h = img_np.shape[1], img_np.shape[0]
                    if bg_mode == "fit":
                        base_scale = min(width / orig_w, height / orig_h)
                    elif bg_mode == "fill":
                        base_scale = max(width / orig_w, height / orig_h)
                    else:
                        base_scale = 1.0
                    final_scale = base_scale * scale
                    if bg_mode == "stretch":
                        new_w = max(1, int(width * scale))
                        new_h = max(1, int(height * scale))
                    else:
                        new_w = max(1, int(orig_w * final_scale))
                        new_h = max(1, int(orig_h * final_scale))
                else:
                    if scale != 1.0 and scale > 0:
                        new_w = max(1, int(img_np.shape[1] * scale))
                        new_h = max(1, int(img_np.shape[0] * scale))

                if new_w != img_np.shape[1] or new_h != img_np.shape[0]:
                    img_np = cv2.resize(img_np, (new_w, new_h), interpolation=cv2.INTER_LINEAR)
                current_w, current_h = img_np.shape[1], img_np.shape[0]

                if abs(rotation) > 0.1:
                    center = (current_w // 2, current_h // 2)
                    matrix = cv2.getRotationMatrix2D(center, rotation, 1.0)
                    img_np = cv2.warpAffine(img_np, matrix, (current_w, current_h), borderMode=cv2.BORDER_CONSTANT, borderValue=(0, 0, 0, 0))

                paste_x = int(width // 2 + x - current_w // 2)
                paste_y = int(height // 2 + y - current_h // 2)

                if is_foreground:
                    if img_np.shape[2] == 4:
                        mask_layer_np = (img_np[:, :, 3].astype(np.float32) * opacity).astype(np.uint8)
                    else:
                        mask_layer_np = np.full((current_h, current_w), int(255 * opacity), dtype=np.uint8)
                    m_y_start = max(0, paste_y)
                    m_x_start = max(0, paste_x)
                    m_y_end = min(paste_y + current_h, height)
                    m_x_end = min(paste_x + current_w, width)
                    if m_y_end > m_y_start and m_x_end > m_x_start:
                        layer_y_offset = max(0, -paste_y)
                        layer_x_offset = max(0, -paste_x)
                        src_mask = mask_layer_np[layer_y_offset:layer_y_offset + (m_y_end - m_y_start), layer_x_offset:layer_x_offset + (m_x_end - m_x_start)]
                        mask_canvas[m_y_start:m_y_end, m_x_start:m_x_end] = np.maximum(mask_canvas[m_y_start:m_y_end, m_x_start:m_x_end], src_mask)

                # Composite image
                y_start = max(0, paste_y)
                x_start = max(0, paste_x)
                y_end = min(paste_y + current_h, height)
                x_end = min(paste_x + current_w, width)
                if y_end > y_start and x_end > x_start:
                    src_y = max(0, -paste_y)
                    src_x = max(0, -paste_x)
                    src_region = img_np[src_y:src_y + (y_end - y_start), src_x:src_x + (x_end - x_start)]
                    dst_region = canvas[y_start:y_end, x_start:x_end]
                    alpha = (src_region[:, :, 3:4].astype(np.float32) / 255.0) * opacity if src_region.shape[2] == 4 else np.full((src_region.shape[0], src_region.shape[1], 1), opacity, dtype=np.float32)
                    for c in range(3):
                        dst_region[:, :, c] = (dst_region[:, :, c].astype(np.float32) * (1 - alpha[:, :, 0]) + src_region[:, :, c].astype(np.float32) * alpha[:, :, 0]).astype(np.uint8)
                    dst_region[:, :, 3] = np.maximum(dst_region[:, :, 3], (alpha[:, :, 0] * 255).astype(np.uint8))
                    canvas[y_start:y_end, x_start:x_end] = dst_region

            if mask_expansion != 0:
                kernel = np.ones((3, 3), np.uint8)
                if mask_expansion > 0:
                    mask_canvas = cv2.dilate(mask_canvas, kernel, iterations=abs(mask_expansion))
                else:
                    mask_canvas = cv2.erode(mask_canvas, kernel, iterations=abs(mask_expansion))
            if mask_feather > 0:
                ksize = max(3, mask_feather * 2 + 1)
                mask_canvas = cv2.GaussianBlur(mask_canvas, (ksize, ksize), 0)

            frame_rgb = canvas[:, :, :3].astype(np.float32) / 255.0
            frames.append(torch.from_numpy(frame_rgb))
            masks.append(torch.from_numpy(mask_canvas.astype(np.float32) / 255.0))

        if not frames:
            return io.NodeOutput(torch.zeros((1, 64, 64, 3)), torch.zeros((1, 64, 64)))

        frames_tensor = torch.stack(frames)
        masks_tensor = torch.stack(masks)
        return io.NodeOutput(frames_tensor, masks_tensor)


class AEAnimationExtension(ComfyExtension):
    @override
    async def get_node_list(self) -> List[type[io.ComfyNode]]:
        return [AEAnimation]


async def comfy_entrypoint() -> AEAnimationExtension:
    return AEAnimationExtension()
