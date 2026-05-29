# Standard Library Imports
# ------------------------
import ctypes
from dataclasses import dataclass
import gc

# Third Party Imports
# -------------------
import cv2
import numpy as np
import onnxruntime as ort
from OpenGL import GL
from qtpy import QtCore, QtGui, QtWidgets


# Data Structures
# ---------------
@dataclass(frozen=True)
class LamaTileSettings:
    """Store tiling settings for full-res inpainting."""
    tile_size: int = 512
    overlap: int = 32
    mask_threshold: int = 127
    dilate_for_seams: bool = True
    context_kernel_tiles: int = 1
    safety_unmask_border: int = 16
    use_global_pass: bool = True
    global_max_side: int = 1024


# LaMa Tiled Inpaint (NumPy API)
# ------------------------------
def lama_inpaint_fullres_tiled_bgr(
    sess: ort.InferenceSession,
    img_bgr: np.ndarray,
    mask_gray: np.ndarray,
    settings: LamaTileSettings,
    *,
    input_names: tuple[str, str] | None = None,
) -> np.ndarray:
    """Inpaint full-res BGR image using tiled inference.

    Args:
        img_bgr: Input image (H,W,3) uint8 BGR.
        mask_gray: Mask (H,W) uint8. Non-zero = inpaint.
        settings: Tiling + threshold settings.
        sess: Preloaded ONNX Runtime session to reuse across runs.
        input_names: Cached input tensor names for the session.

    Returns:
        Output image (H,W,3) uint8 BGR.
    """
    if img_bgr.ndim != 3 or img_bgr.shape[2] != 3:
        raise ValueError("img_bgr must be (H,W,3) BGR")
    if mask_gray.ndim != 2:
        raise ValueError("mask_gray must be (H,W) grayscale")
    if mask_gray.shape[:2] != img_bgr.shape[:2]:
        raise ValueError("mask must match image resolution")

    model_tile_size = _infer_model_tile_size(sess)
    if model_tile_size is None:
        model_tile_size = settings.tile_size

    # Binarize mask -> {0,255}
    _, mask_bin = cv2.threshold(
        mask_gray,
        settings.mask_threshold,
        255,
        cv2.THRESH_BINARY,
    )

    tile_size = _select_tile_size_for_mask(mask_bin, settings.tile_size)

    tile_select_mask = mask_bin
    if settings.dilate_for_seams and settings.overlap > 0:
        k = _odd_kernel_size(settings.overlap * 2 + 1)
        kernel = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (k, k))
        tile_select_mask = cv2.dilate(mask_bin, kernel, iterations=1)

    if input_names is None:
        image_name, mask_name = _get_input_names(sess)
    else:
        if len(input_names) != 2:
            raise ValueError("input_names must be (image, mask)")
        image_name, mask_name = input_names

    guide_full = None
    if settings.use_global_pass:
        guide_full = _global_guide_bgr(
            sess=sess,
            image_name=image_name,
            mask_name=mask_name,
            img_bgr=img_bgr,
            mask_bin=mask_bin,
            max_side=settings.global_max_side,
            tile_size=model_tile_size,
        )

    return _inpaint_tiled(
        sess=sess,
        image_name=image_name,
        mask_name=mask_name,
        img_bgr=img_bgr,
        mask_bin=mask_bin,
        tile_select_mask=tile_select_mask,
        tile_size=tile_size,
        overlap=settings.overlap,
        context_kernel_tiles=settings.context_kernel_tiles,
        safety_unmask_border=settings.safety_unmask_border,
        guide_full=guide_full,
        model_tile_size=model_tile_size,
    )


def _inpaint_tiled(
    sess: ort.InferenceSession,
    image_name: str,
    mask_name: str,
    img_bgr: np.ndarray,
    mask_bin: np.ndarray,
    tile_select_mask: np.ndarray,
    tile_size: int,
    overlap: int,
    context_kernel_tiles: int = 1,
    safety_unmask_border: int = 0,
    guide_full: np.ndarray | None = None,
    model_tile_size: int | None = None,
) -> np.ndarray:
    """Run tiled inference and stitch seamlessly using feather blending."""
    if overlap < 0 or overlap * 2 >= tile_size:
        raise ValueError("overlap must be >=0 and overlap*2 < tile_size")

    if model_tile_size is None or model_tile_size <= 0:
        model_tile_size = tile_size

    h, w = img_bgr.shape[:2]
    stride = tile_size - overlap * 2
    if stride <= 0:
        raise ValueError("Invalid stride; reduce overlap or increase tile_size")

    pad_top, pad_left, pad_bottom, pad_right = _compute_sliding_padding(h, w, tile_size, stride)

    img_pad = cv2.copyMakeBorder(
        img_bgr, pad_top, pad_bottom, pad_left, pad_right, borderType=cv2.BORDER_REFLECT_101
    )
    mask_pad = cv2.copyMakeBorder(
        mask_bin, pad_top, pad_bottom, pad_left, pad_right, borderType=cv2.BORDER_CONSTANT, value=0
    )
    select_pad = cv2.copyMakeBorder(
        tile_select_mask, pad_top, pad_bottom, pad_left, pad_right, borderType=cv2.BORDER_CONSTANT, value=0
    )

    ph, pw = img_pad.shape[:2]
    guide_pad = None
    if guide_full is not None:
        guide_pad = cv2.copyMakeBorder(
            guide_full, pad_top, pad_bottom, pad_left, pad_right, borderType=cv2.BORDER_REFLECT_101
        )

    tile_boxes = _iter_mask_tile_boxes(
        select_pad, tile_size=tile_size, stride=stride, context_kernel_tiles=context_kernel_tiles
    )
    if not tile_boxes:
        return img_bgr

    acc = np.zeros((ph, pw, 3), dtype=np.float32)
    wsum = np.zeros((ph, pw, 1), dtype=np.float32)
    w_tile = _make_feather_weight(tile_size=tile_size, overlap=overlap)

    ran_any = False

    for (y0, x0, y1, x1) in tile_boxes:
        ran_any = True

        img_tile_bgr = img_pad[y0:y1, x0:x1].copy()
        mask_tile = mask_pad[y0:y1, x0:x1].copy()  # 0/255

        b = int(max(0, safety_unmask_border))
        if b > 0:
            mask_tile[:b, :] = 0
            mask_tile[-b:, :] = 0
            mask_tile[:, :b] = 0
            mask_tile[:, -b:] = 0

        if guide_pad is not None:
            guide_tile = guide_pad[y0:y1, x0:x1]
            masked = mask_tile > 0
            img_tile_bgr[masked] = guide_tile[masked]

        out_tile = _run_lama_tile(
            sess=sess,
            image_name=image_name,
            mask_name=mask_name,
            img_tile_bgr=img_tile_bgr,
            mask_tile=mask_tile,
            tile_size=tile_size,
            model_tile_size=model_tile_size,
        )

        acc[y0:y1, x0:x1] += out_tile * w_tile
        wsum[y0:y1, x0:x1] += w_tile

    if not ran_any:
        return img_bgr

    avg = np.zeros_like(acc)
    np.divide(acc, wsum, out=avg, where=wsum > 1e-8)
    coverage = np.clip(wsum, 0.0, 1.0)
    out_pad = img_pad.astype(np.float32) * (1.0 - coverage) + avg * coverage
    out_pad = np.clip(out_pad, 0.0, 255.0).astype(np.uint8)
    return out_pad[pad_top : pad_top + h, pad_left : pad_left + w]


def _make_image_blob_bgr(tile_bgr: np.ndarray, tile_size: int) -> np.ndarray:
    """Create NCHW float32 image blob in BGR order, scaled to 0..1."""
    return cv2.dnn.blobFromImage(
        tile_bgr,
        scalefactor=1.0 / 255.0,
        size=(tile_size, tile_size),
        mean=(0, 0, 0),
        swapRB=False,
        crop=False,
    ).astype(np.float32)


def _make_mask_blob(mask_tile_0_255: np.ndarray, tile_size: int) -> np.ndarray:
    """Create NCHW float32 mask blob and binarize to {0,1}."""
    mask_blob = cv2.dnn.blobFromImage(
        mask_tile_0_255,
        scalefactor=1.0,
        size=(tile_size, tile_size),
        mean=(0,),
        swapRB=False,
        crop=False,
    ).astype(np.float32)
    return (mask_blob > 0).astype(np.float32)


def _postprocess_to_bgr_float(output_nchw: np.ndarray) -> np.ndarray:
    """Convert model output NCHW -> BGR float32 HWC."""
    out_chw = output_nchw[0]
    out_hwc = np.transpose(out_chw, (1, 2, 0)).astype(np.float32)

    # Heuristic: if looks like 0..1, scale up
    if float(out_hwc.max()) <= 1.5:
        out_hwc *= 255.0

    return out_hwc


def _infer_model_tile_size(sess: ort.InferenceSession) -> int | None:
    """Infer square model input size from ONNX inputs if fixed."""
    for inp in sess.get_inputs():
        shape = inp.shape
        if len(shape) != 4:
            continue
        h = shape[2]
        w = shape[3]
        if isinstance(h, int) and isinstance(w, int) and h > 0 and w > 0 and h == w:
            return int(h)
    return None


def _run_model_tile(
    sess: ort.InferenceSession,
    image_name: str,
    mask_name: str,
    img_tile_bgr: np.ndarray,
    mask_tile: np.ndarray,
    model_tile_size: int,
) -> np.ndarray:
    """Run the model for a single input tile and return float32 BGR."""
    image_blob = _make_image_blob_bgr(img_tile_bgr, model_tile_size)
    mask_blob = _make_mask_blob(mask_tile, model_tile_size)
    out_nchw = sess.run(None, {image_name: image_blob, mask_name: mask_blob})[0]
    return _postprocess_to_bgr_float(out_nchw)


def _split_strided_offsets(img: np.ndarray, n: int) -> list[np.ndarray]:
    """Split into n*n images by picking (oy, ox) inside each n x n block."""
    h, w = img.shape[:2]
    if (h % n) or (w % n):
        raise ValueError(f"Image must be divisible by n. Got {h}x{w}, n={n}")

    tiles = []
    for oy in range(n):
        for ox in range(n):
            tiles.append(img[oy::n, ox::n])
    return tiles


def _merge_strided_offsets(tiles: list[np.ndarray], n: int) -> np.ndarray:
    """Merge n*n strided tiles back to the original image."""
    if len(tiles) != n * n:
        raise ValueError("tiles must have length n*n")

    th, tw = tiles[0].shape[:2]
    has_c = tiles[0].ndim == 3
    c = tiles[0].shape[2] if has_c else None

    h, w = th * n, tw * n
    if has_c:
        out = np.zeros((h, w, c), dtype=tiles[0].dtype)
    else:
        out = np.zeros((h, w), dtype=tiles[0].dtype)

    k = 0
    for oy in range(n):
        for ox in range(n):
            out[oy::n, ox::n] = tiles[k]
            k += 1
    return out


def _run_lama_tile(
    sess: ort.InferenceSession,
    image_name: str,
    mask_name: str,
    img_tile_bgr: np.ndarray,
    mask_tile: np.ndarray,
    tile_size: int,
    model_tile_size: int,
) -> np.ndarray:
    """Run inference for a tile; supports strided offsets for larger tiles."""
    if tile_size == model_tile_size:
        return _run_model_tile(sess, image_name, mask_name, img_tile_bgr, mask_tile, model_tile_size)

    if tile_size > model_tile_size and (tile_size % model_tile_size) == 0:
        n = tile_size // model_tile_size
        img_tiles = _split_strided_offsets(img_tile_bgr, n)
        mask_tiles = _split_strided_offsets(mask_tile, n)
        out_tiles = []
        for img_sub, mask_sub in zip(img_tiles, mask_tiles):
            out_tiles.append(_run_model_tile(sess, image_name, mask_name, img_sub, mask_sub, model_tile_size))
        return _merge_strided_offsets(out_tiles, n)

    out_small = _run_model_tile(sess, image_name, mask_name, img_tile_bgr, mask_tile, model_tile_size)
    return cv2.resize(out_small, (tile_size, tile_size), interpolation=cv2.INTER_LINEAR)


def _global_guide_bgr(
    sess: ort.InferenceSession,
    image_name: str,
    mask_name: str,
    img_bgr: np.ndarray,
    mask_bin: np.ndarray,
    *,
    max_side: int,
    tile_size: int,
) -> np.ndarray:
    """Run a coarse full-image pass to provide a global guide."""
    h, w = img_bgr.shape[:2]
    s = min(1.0, float(max_side) / float(max(h, w)))
    if s >= 1.0:
        small_img = img_bgr
        small_mask = mask_bin
    else:
        small_img = cv2.resize(img_bgr, (int(round(w * s)), int(round(h * s))), interpolation=cv2.INTER_AREA)
        small_mask = cv2.resize(mask_bin, (small_img.shape[1], small_img.shape[0]), interpolation=cv2.INTER_NEAREST)

    ih, iw = small_img.shape[:2]
    pad_b = max(0, tile_size - ih)
    pad_r = max(0, tile_size - iw)
    small_img_pad = cv2.copyMakeBorder(small_img, 0, pad_b, 0, pad_r, cv2.BORDER_REFLECT_101)
    small_mask_pad = cv2.copyMakeBorder(small_mask, 0, pad_b, 0, pad_r, cv2.BORDER_CONSTANT, value=0)

    img_blob = _make_image_blob_bgr(small_img_pad, tile_size)
    mask_blob = _make_mask_blob(small_mask_pad, tile_size)

    out_nchw = sess.run(None, {image_name: img_blob, mask_name: mask_blob})[0]
    out_pad = _postprocess_to_bgr_float(out_nchw).astype(np.uint8)

    out_small = out_pad[:ih, :iw]
    guide_full = cv2.resize(out_small, (w, h), interpolation=cv2.INTER_LINEAR)
    return guide_full


def _create_ort_session(model_path: str, providers: list[str]) -> ort.InferenceSession:
    """Create an ONNX Runtime inference session."""
    so = ort.SessionOptions()
    so.log_severity_level = 3
    return ort.InferenceSession(model_path, sess_options=so, providers=providers)


def _get_input_names(sess: ort.InferenceSession) -> tuple[str, str]:
    """Get input tensor names (assumes 2 inputs)."""
    inputs = sess.get_inputs()
    if len(inputs) < 2:
        raise ValueError(f"Expected 2 inputs (image, mask), got {len(inputs)}")
    return inputs[0].name, inputs[1].name


def _make_feather_weight(tile_size: int, overlap: int) -> np.ndarray:
    """Make feather blending weight window [T,T,1]."""
    if overlap == 0:
        return np.ones((tile_size, tile_size, 1), dtype=np.float32)

    x = np.ones((tile_size,), dtype=np.float32)
    ramp = np.linspace(0.0, np.pi, overlap, dtype=np.float32)
    fade = 0.5 - 0.5 * np.cos(ramp)  # 0..1

    x[:overlap] = fade
    x[-overlap:] = fade[::-1]
    y = x.copy()

    w2d = np.outer(y, x).astype(np.float32)
    return w2d[..., None]


def _iter_mask_tile_boxes(
    select_pad: np.ndarray,
    tile_size: int,
    stride: int,
    *,
    context_kernel_tiles: int = 1,
) -> list[tuple[int, int, int, int]]:
    """Return tile boxes centered on masked region for efficiency."""
    mask = (select_pad > 0).astype(np.uint8)
    num_labels, _labels, stats, centroids = cv2.connectedComponentsWithStats(mask, connectivity=8)
    if num_labels <= 1:
        return []

    ph, pw = select_pad.shape[:2]
    max_x_start = max(0, pw - tile_size)
    max_y_start = max(0, ph - tile_size)

    boxes: set[tuple[int, int, int, int]] = set()

    k = max(1, int(context_kernel_tiles))
    r = (k - 1) // 2 if (k % 2 == 1) else (k // 2)
    for label in range(1, num_labels):
        x, y, w, h, area = stats[label]
        if area <= 0:
            continue

        min_x, max_x = int(x), int(x + w - 1)
        min_y, max_y = int(y), int(y + h - 1)
        cx, cy = centroids[label]

        start_x = int(round(cx - tile_size / 2))
        start_y = int(round(cy - tile_size / 2))
        start_x = int(np.clip(start_x, 0, max_x_start))
        start_y = int(np.clip(start_y, 0, max_y_start))

        starts_x = _axis_starts(start_x, min_x, max_x, stride, max_x_start, tile_size)
        starts_y = _axis_starts(start_y, min_y, max_y, stride, max_y_start, tile_size)

        for sy in starts_y:
            for sx in starts_x:
                for oy in range(-r, r + 1):
                    for ox in range(-r, r + 1):
                        nsy = int(np.clip(sy + oy * stride, 0, max_y_start))
                        nsx = int(np.clip(sx + ox * stride, 0, max_x_start))
                        boxes.add((nsy, nsx, nsy + tile_size, nsx + tile_size))

    return sorted(boxes)


def _axis_starts(
    start0: int,
    min_coord: int,
    max_coord: int,
    stride: int,
    max_start: int,
    tile_size: int,
) -> list[int]:
    """Compute axis starts aligned to stride, centered on start0."""
    starts = [start0]

    start = start0
    while start > min_coord:
        start -= stride
        if start < 0:
            start = 0
            if start not in starts:
                starts.append(start)
            break
        starts.append(start)

    start = start0
    while start + tile_size - 1 < max_coord:
        start += stride
        if start > max_start:
            start = max_start
            if start not in starts:
                starts.append(start)
            break
        starts.append(start)

    return sorted(set(starts))


def _compute_sliding_padding(h: int, w: int, tile_size: int, stride: int) -> tuple[int, int, int, int]:
    """Compute padding so sliding tiles cover full image."""
    pad_top = 0
    pad_left = 0

    def _needed_pad(n: int) -> int:
        if n <= tile_size:
            return tile_size - n
        last_start = ((n - tile_size + stride - 1) // stride) * stride
        covered = last_start + tile_size
        return max(0, covered - n)

    return pad_top, pad_left, _needed_pad(h), _needed_pad(w)


def _select_tile_size_for_mask(
    mask_bin: np.ndarray,
    base_tile_size: int,
    *,
    max_tile_size: int | None = 2048,
    context_pad_ratio: float = 0.25,
) -> int:
    """Pick a larger tile size when the mask consumes most of a tile."""
    if base_tile_size <= 0:
        return base_tile_size

    if mask_bin is None:
        return base_tile_size

    ys, xs = np.where(mask_bin > 0)
    if xs.size == 0 or ys.size == 0:
        return base_tile_size

    max_side = int(max(xs.max() - xs.min() + 1, ys.max() - ys.min() + 1))
    context_pad = max(0, int(round(base_tile_size * float(context_pad_ratio))))
    desired_side = max_side + context_pad

    level = int(np.ceil(desired_side / float(base_tile_size)))
    level = max(1, level)

    if max_tile_size is not None and max_tile_size > 0:
        max_level = max(1, int(max_tile_size // base_tile_size))
        level = min(level, max_level)

    return base_tile_size * level


def _odd_kernel_size(k: int) -> int:
    """Return an odd kernel size >= 1."""
    k = int(k)
    if k <= 1:
        return 1
    return k if (k % 2 == 1) else (k + 1)


# PyQt Mask Paint Viewport
# ------------------------
class MaskPaintViewport(QtWidgets.QOpenGLWidget):
    """A viewport that displays an image and lets user paint a binary mask."""

    image_changed = QtCore.Signal()
    mask_changed = QtCore.Signal()

    def __init__(self, parent: QtWidgets.QWidget | None = None):
        """Initialize the viewport."""
        fmt = QtGui.QSurfaceFormat()
        fmt.setVersion(2, 1)
        fmt.setProfile(QtGui.QSurfaceFormat.CompatibilityProfile)
        fmt.setSwapBehavior(QtGui.QSurfaceFormat.DoubleBuffer)
        super().__init__(parent)
        self.setFormat(fmt)

        self._img_bgr: np.ndarray | None = None
        self._img_rgb: np.ndarray | None = None
        self._mask: np.ndarray | None = None  # uint8 (H,W) 0/255

        self._zoom = 1.0
        self._pan = QtCore.QPointF(0.0, 0.0)
        self._is_panning = False
        self._last_mouse = QtCore.QPoint()

        self._brush_radius = 24
        self._erase_mode = False

        self._undo_masks: list[np.ndarray] = []
        self._max_undo = 30

        self._gl_ready = False
        self._program: int | None = None
        self._pos_loc: int | None = None
        self._tex_loc: int | None = None
        self._u_image_loc: int | None = None
        self._u_mask_loc: int | None = None
        self._u_mask_strength_loc: int | None = None
        self._vbo: int | None = None
        self._image_tex: int | None = None
        self._mask_tex: int | None = None
        self._image_tex_size: tuple[int, int] | None = None
        self._mask_tex_size: tuple[int, int] | None = None
        self._image_dirty = False
        self._mask_dirty = False
        self._mask_strength = 0.55
        self._tile_settings = LamaTileSettings()
        self._tile_overlay: list[tuple[int, int, int, int, bool]] = []
        self._tile_overlay_dirty = True
        self._show_tiles = True
        self._overlay_program: int | None = None
        self._overlay_pos_loc: int | None = None
        self._overlay_color_loc: int | None = None
        self._overlay_vbo: int | None = None

        self.setMouseTracking(True)
        self.setFocusPolicy(QtCore.Qt.StrongFocus)

    # Public Methods
    # --------------
    def set_image_bgr(self, img_bgr: np.ndarray | None):
        """Set the image and reset mask."""
        if img_bgr is None:
            self._img_bgr = None
            self._img_rgb = None
            self._mask = None
            self._image_dirty = True
            self._mask_dirty = True
            self._tile_overlay_dirty = True
            self.update()
            return

        self._img_bgr = img_bgr.copy()
        self._img_rgb = cv2.cvtColor(self._img_bgr, cv2.COLOR_BGR2RGB)
        h, w = self._img_bgr.shape[:2]
        self._mask = np.zeros((h, w), dtype=np.uint8)

        self._zoom = 1.0
        self._pan = QtCore.QPointF(0.0, 0.0)
        self._undo_masks = []
        self._image_dirty = True
        self._mask_dirty = True
        self._tile_overlay_dirty = True

        self.image_changed.emit()
        self.mask_changed.emit()
        self.update()

    def set_display_image_bgr(self, img_bgr: np.ndarray | None):
        """Swap the displayed image without resetting mask/viewport."""
        if img_bgr is None:
            return
        if self._img_bgr is None or self._mask is None:
            self.set_image_bgr(img_bgr)
            return
        if self._img_bgr.shape[:2] != img_bgr.shape[:2]:
            self.set_image_bgr(img_bgr)
            return
        self._img_bgr = img_bgr.copy()
        self._img_rgb = cv2.cvtColor(self._img_bgr, cv2.COLOR_BGR2RGB)
        self._image_dirty = True
        self._tile_overlay_dirty = True
        self.image_changed.emit()
        self.update()

    def get_image_bgr(self) -> np.ndarray | None:
        """Return the current image (BGR)."""
        if self._img_bgr is None:
            return None
        return self._img_bgr.copy()

    def get_mask_gray(self) -> np.ndarray | None:
        """Return the current mask (uint8 0/255)."""
        if self._mask is None:
            return None
        return self._mask.copy()

    def set_brush_radius(self, radius: int):
        """Set brush radius in screen-ish pixels (image space)."""
        self._brush_radius = max(1, int(radius))
        self.update()

    def set_erase_mode(self, enabled: bool):
        """Enable/disable erase mode."""
        self._erase_mode = bool(enabled)
        self.update()

    def get_view_state(self) -> tuple[float, QtCore.QPointF]:
        """Return the current zoom and pan state."""
        return float(self._zoom), QtCore.QPointF(self._pan)

    def set_view_state(self, zoom: float, pan: QtCore.QPointF):
        """Restore zoom and pan state."""
        self._zoom = float(np.clip(zoom, 0.1, 16.0))
        self._pan = QtCore.QPointF(pan)
        self.update()

    def set_show_tiles(self, enabled: bool):
        """Toggle tile overlay visualization."""
        self._show_tiles = bool(enabled)
        self._tile_overlay_dirty = True
        self.update()

    def set_tile_settings(self, settings: "LamaTileSettings"):
        """Update tile overlay settings."""
        self._tile_settings = settings
        self._tile_overlay_dirty = True
        self.update()

    def undo(self):
        """Undo last mask stroke."""
        if self._mask is None:
            return
        if not self._undo_masks:
            return
        self._mask = self._undo_masks.pop()
        self._mask_dirty = True
        self._tile_overlay_dirty = True
        self.mask_changed.emit()
        self.update()

    # Qt Events
    # ---------
    def initializeGL(self):
        """Initialize OpenGL resources."""
        self._gl_ready = True
        GL.glClearColor(0.07, 0.07, 0.07, 1.0)
        GL.glDisable(GL.GL_DEPTH_TEST)
        GL.glPixelStorei(GL.GL_UNPACK_ALIGNMENT, 1)

        self._program = self._create_shader_program()
        self._pos_loc = GL.glGetAttribLocation(self._program, "position")
        self._tex_loc = GL.glGetAttribLocation(self._program, "texCoord")
        self._u_image_loc = GL.glGetUniformLocation(self._program, "uImage")
        self._u_mask_loc = GL.glGetUniformLocation(self._program, "uMask")
        self._u_mask_strength_loc = GL.glGetUniformLocation(self._program, "uMaskStrength")

        self._vbo = GL.glGenBuffers(1)
        GL.glBindBuffer(GL.GL_ARRAY_BUFFER, self._vbo)
        GL.glBufferData(GL.GL_ARRAY_BUFFER, 4 * 4 * 4, None, GL.GL_DYNAMIC_DRAW)

        self._image_tex = GL.glGenTextures(1)
        self._mask_tex = GL.glGenTextures(1)

        for tex in (self._image_tex, self._mask_tex):
            GL.glBindTexture(GL.GL_TEXTURE_2D, tex)
            GL.glTexParameteri(GL.GL_TEXTURE_2D, GL.GL_TEXTURE_WRAP_S, GL.GL_CLAMP_TO_EDGE)
            GL.glTexParameteri(GL.GL_TEXTURE_2D, GL.GL_TEXTURE_WRAP_T, GL.GL_CLAMP_TO_EDGE)
            GL.glTexParameteri(GL.GL_TEXTURE_2D, GL.GL_TEXTURE_MIN_FILTER, GL.GL_NEAREST)
            GL.glTexParameteri(GL.GL_TEXTURE_2D, GL.GL_TEXTURE_MAG_FILTER, GL.GL_NEAREST)

        GL.glBindTexture(GL.GL_TEXTURE_2D, 0)

        self._overlay_program = self._create_overlay_program()
        self._overlay_pos_loc = GL.glGetAttribLocation(self._overlay_program, "position")
        self._overlay_color_loc = GL.glGetUniformLocation(self._overlay_program, "uColor")
        self._overlay_vbo = GL.glGenBuffers(1)

        self._image_dirty = True
        self._mask_dirty = True

    def paintGL(self):
        """Render the image + mask overlay with OpenGL."""
        dpr = self.devicePixelRatioF()
        GL.glViewport(0, 0, max(1, int(self.width() * dpr)), max(1, int(self.height() * dpr)))
        GL.glClear(GL.GL_COLOR_BUFFER_BIT)

        if self._img_rgb is None:
            self._draw_placeholder()
            return

        if self._image_dirty:
            self._upload_image_texture()
        if self._mask_dirty:
            self._upload_mask_texture()

        target = self._compute_target_rect(QtCore.QSize(self._img_rgb.shape[1], self._img_rgb.shape[0]))
        if target.width() <= 0 or target.height() <= 0:
            return

        vertices = self._build_vertices(target)

        GL.glUseProgram(self._program)
        GL.glUniform1i(self._u_image_loc, 0)
        GL.glUniform1i(self._u_mask_loc, 1)
        GL.glUniform1f(self._u_mask_strength_loc, float(self._mask_strength))

        GL.glActiveTexture(GL.GL_TEXTURE0)
        GL.glBindTexture(GL.GL_TEXTURE_2D, self._image_tex)
        GL.glActiveTexture(GL.GL_TEXTURE1)
        GL.glBindTexture(GL.GL_TEXTURE_2D, self._mask_tex)

        GL.glBindBuffer(GL.GL_ARRAY_BUFFER, self._vbo)
        GL.glBufferSubData(GL.GL_ARRAY_BUFFER, 0, vertices.nbytes, vertices)

        stride = 4 * 4
        GL.glEnableVertexAttribArray(self._pos_loc)
        GL.glVertexAttribPointer(self._pos_loc, 2, GL.GL_FLOAT, GL.GL_FALSE, stride, ctypes.c_void_p(0))
        GL.glEnableVertexAttribArray(self._tex_loc)
        GL.glVertexAttribPointer(self._tex_loc, 2, GL.GL_FLOAT, GL.GL_FALSE, stride, ctypes.c_void_p(8))
        GL.glDrawArrays(GL.GL_TRIANGLE_STRIP, 0, 4)
        GL.glDisableVertexAttribArray(self._pos_loc)
        GL.glDisableVertexAttribArray(self._tex_loc)
        GL.glBindBuffer(GL.GL_ARRAY_BUFFER, 0)
        GL.glUseProgram(0)

        self._draw_tile_overlay_gl()
        self._draw_cursor_overlay()

    def resizeGL(self, w: int, h: int):
        """Resize OpenGL viewport."""
        dpr = self.devicePixelRatioF()
        GL.glViewport(0, 0, max(1, int(w * dpr)), max(1, int(h * dpr)))

    def _draw_placeholder(self):
        """Draw placeholder text when no image is loaded."""
        painter = QtGui.QPainter(self)
        painter.setRenderHint(QtGui.QPainter.TextAntialiasing, True)
        painter.setPen(QtGui.QColor(180, 180, 180))
        painter.drawText(self.rect(), QtCore.Qt.AlignCenter, "Load an image to start")
        painter.end()

    def _draw_cursor_overlay(self):
        """Draw the brush cursor on top of the GL output."""
        if not self.underMouse():
            return
        pos = self.mapFromGlobal(QtGui.QCursor.pos())
        img_pt = self._widget_to_image(pos)
        if img_pt is None:
            return
        r = int(max(2, self._brush_radius * self._zoom))
        painter = QtGui.QPainter(self)
        painter.setRenderHint(QtGui.QPainter.Antialiasing, True)
        pen = QtGui.QPen(QtGui.QColor(255, 255, 255, 160))
        pen.setWidth(1)
        painter.setPen(pen)
        painter.setBrush(QtCore.Qt.NoBrush)
        painter.drawEllipse(QtCore.QPoint(pos.x(), pos.y()), r, r)
        painter.end()

    def _draw_tile_overlay_gl(self):
        """Draw tile overlay using OpenGL."""
        if not self._show_tiles:
            return
        self._ensure_tile_overlay()
        if not self._tile_overlay or self._img_bgr is None:
            return

        h, w = self._img_bgr.shape[:2]
        target = self._compute_target_rect(QtCore.QSize(w, h))
        if target.width() <= 0 or target.height() <= 0:
            return

        fill_vertices, line_vertices = self._build_tile_overlay_vertices(target, w, h)
        if fill_vertices.size == 0 and line_vertices.size == 0:
            return

        GL.glEnable(GL.GL_BLEND)
        GL.glBlendFunc(GL.GL_SRC_ALPHA, GL.GL_ONE_MINUS_SRC_ALPHA)
        GL.glUseProgram(self._overlay_program)

        if fill_vertices.size:
            GL.glUniform4f(self._overlay_color_loc, 0.0, 0.78, 0.95, 0.25)
            GL.glBindBuffer(GL.GL_ARRAY_BUFFER, self._overlay_vbo)
            GL.glBufferData(GL.GL_ARRAY_BUFFER, fill_vertices.nbytes, fill_vertices, GL.GL_DYNAMIC_DRAW)
            GL.glEnableVertexAttribArray(self._overlay_pos_loc)
            GL.glVertexAttribPointer(self._overlay_pos_loc, 2, GL.GL_FLOAT, GL.GL_FALSE, 0, ctypes.c_void_p(0))
            GL.glDrawArrays(GL.GL_TRIANGLES, 0, int(fill_vertices.shape[0]))
            GL.glDisableVertexAttribArray(self._overlay_pos_loc)

        if line_vertices.size:
            GL.glLineWidth(1.0)
            GL.glUniform4f(self._overlay_color_loc, 1.0, 1.0, 1.0, 0.35)
            GL.glBindBuffer(GL.GL_ARRAY_BUFFER, self._overlay_vbo)
            GL.glBufferData(GL.GL_ARRAY_BUFFER, line_vertices.nbytes, line_vertices, GL.GL_DYNAMIC_DRAW)
            GL.glEnableVertexAttribArray(self._overlay_pos_loc)
            GL.glVertexAttribPointer(self._overlay_pos_loc, 2, GL.GL_FLOAT, GL.GL_FALSE, 0, ctypes.c_void_p(0))
            GL.glDrawArrays(GL.GL_LINES, 0, int(line_vertices.shape[0]))
            GL.glDisableVertexAttribArray(self._overlay_pos_loc)

        GL.glBindBuffer(GL.GL_ARRAY_BUFFER, 0)
        GL.glUseProgram(0)
        GL.glDisable(GL.GL_BLEND)

    def _create_shader_program(self) -> int:
        """Create the OpenGL shader program for image + mask rendering."""
        vertex_src = """
        #version 120
        attribute vec2 position;
        attribute vec2 texCoord;
        varying vec2 vTexCoord;
        void main() {
            gl_Position = vec4(position, 0.0, 1.0);
            vTexCoord = texCoord;
        }
        """
        fragment_src = """
        #version 120
        uniform sampler2D uImage;
        uniform sampler2D uMask;
        uniform float uMaskStrength;
        varying vec2 vTexCoord;
        void main() {
            vec3 img = texture2D(uImage, vTexCoord).rgb;
            float mask = texture2D(uMask, vTexCoord).r;
            float alpha = clamp(mask * uMaskStrength, 0.0, 1.0);
            vec3 outColor = mix(img, vec3(1.0, 0.0, 0.0), alpha);
            gl_FragColor = vec4(outColor, 1.0);
        }
        """
        vs = self._compile_shader(vertex_src, GL.GL_VERTEX_SHADER)
        fs = self._compile_shader(fragment_src, GL.GL_FRAGMENT_SHADER)
        program = GL.glCreateProgram()
        GL.glAttachShader(program, vs)
        GL.glAttachShader(program, fs)
        GL.glLinkProgram(program)

        linked = GL.glGetProgramiv(program, GL.GL_LINK_STATUS)
        if not linked:
            info = GL.glGetProgramInfoLog(program).decode("utf-8", errors="ignore")
            GL.glDeleteProgram(program)
            raise RuntimeError(f"Shader link failed: {info}")

        GL.glDeleteShader(vs)
        GL.glDeleteShader(fs)
        return program

    def _create_overlay_program(self) -> int:
        """Create the OpenGL shader program for tile overlay rendering."""
        vertex_src = """
        #version 120
        attribute vec2 position;
        void main() {
            gl_Position = vec4(position, 0.0, 1.0);
        }
        """
        fragment_src = """
        #version 120
        uniform vec4 uColor;
        void main() {
            gl_FragColor = uColor;
        }
        """
        vs = self._compile_shader(vertex_src, GL.GL_VERTEX_SHADER)
        fs = self._compile_shader(fragment_src, GL.GL_FRAGMENT_SHADER)
        program = GL.glCreateProgram()
        GL.glAttachShader(program, vs)
        GL.glAttachShader(program, fs)
        GL.glLinkProgram(program)

        linked = GL.glGetProgramiv(program, GL.GL_LINK_STATUS)
        if not linked:
            info = GL.glGetProgramInfoLog(program).decode("utf-8", errors="ignore")
            GL.glDeleteProgram(program)
            raise RuntimeError(f"Shader link failed: {info}")

        GL.glDeleteShader(vs)
        GL.glDeleteShader(fs)
        return program

    def _compile_shader(self, source: str, shader_type: int) -> int:
        """Compile an OpenGL shader."""
        shader = GL.glCreateShader(shader_type)
        GL.glShaderSource(shader, source)
        GL.glCompileShader(shader)
        compiled = GL.glGetShaderiv(shader, GL.GL_COMPILE_STATUS)
        if not compiled:
            info = GL.glGetShaderInfoLog(shader).decode("utf-8", errors="ignore")
            GL.glDeleteShader(shader)
            raise RuntimeError(f"Shader compile failed: {info}")
        return shader

    def _upload_image_texture(self):
        """Upload the current image to the GPU texture."""
        if self._img_rgb is None or self._image_tex is None:
            return
        img = np.ascontiguousarray(self._img_rgb)
        h, w = img.shape[:2]
        GL.glBindTexture(GL.GL_TEXTURE_2D, self._image_tex)
        if self._image_tex_size != (w, h):
            GL.glTexImage2D(GL.GL_TEXTURE_2D, 0, GL.GL_RGB, w, h, 0, GL.GL_RGB, GL.GL_UNSIGNED_BYTE, img)
            self._image_tex_size = (w, h)
        else:
            GL.glTexSubImage2D(GL.GL_TEXTURE_2D, 0, 0, 0, w, h, GL.GL_RGB, GL.GL_UNSIGNED_BYTE, img)
        self._image_dirty = False

    def _upload_mask_texture(self):
        """Upload the current mask to the GPU texture."""
        if self._mask is None or self._mask_tex is None:
            return
        mask = np.ascontiguousarray(self._mask)
        h, w = mask.shape[:2]
        GL.glBindTexture(GL.GL_TEXTURE_2D, self._mask_tex)
        if self._mask_tex_size != (w, h):
            GL.glTexImage2D(GL.GL_TEXTURE_2D, 0, GL.GL_LUMINANCE, w, h, 0, GL.GL_LUMINANCE, GL.GL_UNSIGNED_BYTE, mask)
            self._mask_tex_size = (w, h)
        else:
            GL.glTexSubImage2D(GL.GL_TEXTURE_2D, 0, 0, 0, w, h, GL.GL_LUMINANCE, GL.GL_UNSIGNED_BYTE, mask)
        self._mask_dirty = False

    def _ensure_tile_overlay(self):
        """Rebuild tile overlay data when needed."""
        if not self._show_tiles:
            return
        if not self._tile_overlay_dirty:
            return
        self._tile_overlay = self._build_tile_overlay()
        self._tile_overlay_dirty = False

    def _build_tile_overlay_vertices(
        self,
        target: QtCore.QRect,
        img_w: int,
        img_h: int,
    ) -> tuple[np.ndarray, np.ndarray]:
        """Build OpenGL vertices for tile overlay in NDC."""
        if not self._tile_overlay:
            return np.zeros((0, 2), dtype=np.float32), np.zeros((0, 2), dtype=np.float32)

        sx = target.width() / float(max(1, img_w))
        sy = target.height() / float(max(1, img_h))

        fill_vertices = []
        line_vertices = []

        for x0, y0, x1, y1, is_processing in self._tile_overlay:
            wx0 = target.x() + x0 * sx
            wy0 = target.y() + y0 * sy
            wx1 = target.x() + x1 * sx
            wy1 = target.y() + y1 * sy

            nx0, ny0 = self._widget_to_ndc(wx0, wy0)
            nx1, ny1 = self._widget_to_ndc(wx1, wy1)

            if is_processing:
                fill_vertices.extend(
                    [
                        (nx0, ny0),
                        (nx1, ny0),
                        (nx1, ny1),
                        (nx0, ny0),
                        (nx1, ny1),
                        (nx0, ny1),
                    ]
                )

            line_vertices.extend(
                [
                    (nx0, ny0),
                    (nx1, ny0),
                    (nx1, ny0),
                    (nx1, ny1),
                    (nx1, ny1),
                    (nx0, ny1),
                    (nx0, ny1),
                    (nx0, ny0),
                ]
            )

        fill_arr = np.array(fill_vertices, dtype=np.float32) if fill_vertices else np.zeros((0, 2), dtype=np.float32)
        line_arr = np.array(line_vertices, dtype=np.float32) if line_vertices else np.zeros((0, 2), dtype=np.float32)
        return fill_arr, line_arr

    def _widget_to_ndc(self, x: float, y: float) -> tuple[float, float]:
        """Convert widget coordinates to NDC."""
        dpr = self.devicePixelRatioF()
        vw = max(1.0, self.width() * dpr)
        vh = max(1.0, self.height() * dpr)
        px = x * dpr
        py = y * dpr
        nx = (px / vw) * 2.0 - 1.0
        ny = 1.0 - (py / vh) * 2.0
        return nx, ny

    def _build_tile_overlay(self) -> list[tuple[int, int, int, int, bool]]:
        """Compute tile overlay rectangles in image space."""
        if self._img_bgr is None or self._mask is None:
            return []

        overlap = int(self._tile_settings.overlap)
        h, w = self._mask.shape[:2]
        _, mask_bin = cv2.threshold(
            self._mask,
            self._tile_settings.mask_threshold,
            255,
            cv2.THRESH_BINARY,
        )

        base_tile_size = int(self._tile_settings.tile_size)
        tile_size = _select_tile_size_for_mask(mask_bin, base_tile_size)
        if tile_size <= 0:
            return []

        stride = tile_size - overlap * 2
        if stride <= 0:
            return []

        tile_select_mask = mask_bin
        if self._tile_settings.dilate_for_seams and overlap > 0:
            k = _odd_kernel_size(overlap * 2 + 1)
            kernel = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (k, k))
            tile_select_mask = cv2.dilate(mask_bin, kernel, iterations=1)

        pad_top, pad_left, pad_bottom, pad_right = _compute_sliding_padding(h, w, tile_size, stride)
        select_pad = cv2.copyMakeBorder(
            tile_select_mask, pad_top, pad_bottom, pad_left, pad_right, borderType=cv2.BORDER_CONSTANT, value=0
        )

        tile_boxes = _iter_mask_tile_boxes(
            select_pad,
            tile_size=tile_size,
            stride=stride,
            context_kernel_tiles=self._tile_settings.context_kernel_tiles,
        )
        overlay = []
        for (y0, x0, y1, x1) in tile_boxes:
            is_processing = True

            img_x0 = x0 - pad_left
            img_y0 = y0 - pad_top
            img_x1 = x1 - pad_left
            img_y1 = y1 - pad_top

            ix0 = max(0, img_x0)
            iy0 = max(0, img_y0)
            ix1 = min(w, img_x1)
            iy1 = min(h, img_y1)

            if ix1 <= ix0 or iy1 <= iy0:
                continue

            overlay.append((ix0, iy0, ix1, iy1, is_processing))

        return overlay

    def _build_vertices(self, target: QtCore.QRect) -> "np.ndarray":
        """Build a quad covering the target rect in NDC."""
        dpr = self.devicePixelRatioF()
        vw = max(1.0, self.width() * dpr)
        vh = max(1.0, self.height() * dpr)

        x0 = target.x() * dpr
        y0 = target.y() * dpr
        x1 = x0 + target.width() * dpr
        y1 = y0 + target.height() * dpr

        def _ndc_x(x: float) -> float:
            return (x / vw) * 2.0 - 1.0

        def _ndc_y(y: float) -> float:
            return 1.0 - (y / vh) * 2.0

        return np.array(
            [
                [_ndc_x(x0), _ndc_y(y0), 0.0, 0.0],
                [_ndc_x(x1), _ndc_y(y0), 1.0, 0.0],
                [_ndc_x(x0), _ndc_y(y1), 0.0, 1.0],
                [_ndc_x(x1), _ndc_y(y1), 1.0, 1.0],
            ],
            dtype=np.float32,
        )

    def wheelEvent(self, event: QtGui.QWheelEvent):
        """Zoom under mouse."""
        if self._img_bgr is None:
            return

        angle = event.angleDelta().y()
        if angle == 0:
            return

        factor = 1.15 if angle > 0 else 1.0 / 1.15
        old_zoom = self._zoom
        new_zoom = float(np.clip(old_zoom * factor, 0.1, 16.0))

        mouse_pos = event.pos()
        before = self._widget_to_image(mouse_pos)
        self._zoom = new_zoom
        after = self._widget_to_image(mouse_pos)

        if before is not None and after is not None:
            # adjust pan so the image point stays under cursor
            dx = (after.x() - before.x())
            dy = (after.y() - before.y())
            self._pan += QtCore.QPointF(dx, dy)

        self.update()

    def mousePressEvent(self, event: QtGui.QMouseEvent):
        """Begin paint or pan."""
        if self._img_bgr is None:
            return

        if event.button() == QtCore.Qt.MiddleButton:
            self._is_panning = True
            self._last_mouse = event.pos()
            return

        if event.button() == QtCore.Qt.LeftButton:
            self._push_undo()
            self._apply_brush(event.pos())
            return

    def mouseMoveEvent(self, event: QtGui.QMouseEvent):
        """Continue paint or pan."""
        if self._img_bgr is None:
            return

        if self._is_panning:
            delta = event.pos() - self._last_mouse
            self._last_mouse = event.pos()
            # pan in image-space units
            self._pan -= QtCore.QPointF(delta.x() / self._zoom, delta.y() / self._zoom)
            self.update()
            return

        if event.buttons() & QtCore.Qt.LeftButton:
            self._apply_brush(event.pos())
            return

        self.update()

    def mouseReleaseEvent(self, event: QtGui.QMouseEvent):
        """End paint or pan."""
        if event.button() == QtCore.Qt.MiddleButton:
            self._is_panning = False
            return

    # Private Methods
    # ---------------
    def _push_undo(self):
        """Store current mask for undo."""
        if self._mask is None:
            return
        self._undo_masks.append(self._mask.copy())
        if len(self._undo_masks) > self._max_undo:
            self._undo_masks.pop(0)

    def _apply_brush(self, widget_pos: QtCore.QPoint):
        """Paint on the mask at widget position."""
        if self._mask is None:
            return

        img_pt = self._widget_to_image(widget_pos)
        if img_pt is None:
            return

        x = int(round(img_pt.x()))
        y = int(round(img_pt.y()))
        h, w = self._mask.shape[:2]

        if x < 0 or y < 0 or x >= w or y >= h:
            return

        value = 0 if self._erase_mode else 255
        cv2.circle(self._mask, (x, y), int(self._brush_radius), value, thickness=-1)

        self._mask_dirty = True
        self._tile_overlay_dirty = True
        self.mask_changed.emit()
        self.update()

    def _compute_target_rect(self, pix_size: QtCore.QSize) -> QtCore.QRect:
        """Compute destination rect for drawing pixmap with zoom+pan."""
        ww = max(1, self.width())
        wh = max(1, self.height())

        img_w = pix_size.width()
        img_h = pix_size.height()

        # place image centered, then apply pan (in image space) and zoom
        scaled_w = int(img_w * self._zoom)
        scaled_h = int(img_h * self._zoom)

        cx = ww // 2 - scaled_w // 2
        cy = wh // 2 - scaled_h // 2

        # pan is in image pixels
        cx += int(-self._pan.x() * self._zoom)
        cy += int(-self._pan.y() * self._zoom)

        return QtCore.QRect(cx, cy, scaled_w, scaled_h)

    def _widget_to_image(self, widget_pos: QtCore.QPoint) -> QtCore.QPointF | None:
        """Convert widget coord -> image coord."""
        if self._img_bgr is None:
            return

        h, w = self._img_bgr.shape[:2]
        target = self._compute_target_rect(QtCore.QSize(w, h))

        if target.width() <= 0 or target.height() <= 0:
            return

        # map to normalized within target rect
        x = (widget_pos.x() - target.x()) / float(target.width())
        y = (widget_pos.y() - target.y()) / float(target.height())

        if x < 0.0 or y < 0.0 or x > 1.0 or y > 1.0:
            return

        return QtCore.QPointF(x * w, y * h)


# Worker Thread
# -------------
class LamaInpaintWorker(QtCore.QThread):
    """Run LaMa inference off the UI thread."""

    finished_image = QtCore.Signal(object)  # np.ndarray BGR
    failed = QtCore.Signal(str)

    def __init__(
        self,
        parent: QtCore.QObject | None = None,
        img_bgr: np.ndarray | None = None,
        mask_gray: np.ndarray | None = None,
        settings: LamaTileSettings | None = None,
        session: ort.InferenceSession | None = None,
        input_names: tuple[str, str] | None = None,
    ):
        """Initialize worker."""
        super().__init__(parent)
        self._img_bgr = img_bgr
        self._mask_gray = mask_gray
        self._settings = settings if settings is not None else LamaTileSettings()
        self._session = session
        self._input_names = input_names

    def run(self):
        """Run inference."""
        try:
            if self._img_bgr is None or self._mask_gray is None:
                raise ValueError("Missing image or mask")
            if self._session is None:
                raise ValueError("Missing model session or path")

            out = lama_inpaint_fullres_tiled_bgr(
                img_bgr=self._img_bgr,
                mask_gray=self._mask_gray,
                settings=self._settings,
                sess=self._session,
                input_names=self._input_names,
            )
            self.finished_image.emit(out)
        except Exception as exc:
            self.failed.emit(str(exc))


# Main Widget
# -----------
class LamaMaskInpaintWidget(QtWidgets.QWidget):
    """A PyQt widget to paint a mask and run LaMa inpainting."""

    # Initialization and Setup
    # ------------------------
    def __init__(self, parent: QtWidgets.QWidget = None):
        """Initialize the widget and set up the UI."""
        super().__init__(
            parent,
            windowTitle="LaMa Mask Paint + Inpaint (Full-res tiled)",
        )

        self._model_path = ""
        self._ort_session = None
        self._ort_input_names = None
        self._orig_bgr = None
        self._last_output_bgr = None
        self._worker = None

        self._settings = LamaTileSettings()

        self._init_ui()
        self._init_signal_connections()

    def _init_ui(self):
        """Initialize the UI."""
        # Create Widgets
        # --------------
        # Viewport
        self._viewport = MaskPaintViewport()
        self._viewport.set_tile_settings(self._settings)

        # Controls
        self._load_image_btn = QtWidgets.QPushButton("Load Image")
        self._load_model_btn = QtWidgets.QPushButton("Load Model (.onnx)")
        self._release_model_btn = QtWidgets.QPushButton("Release Model", enabled=False)
        self._run_btn = QtWidgets.QPushButton("Inpaint", enabled=False)
        self._save_btn = QtWidgets.QPushButton("Save Output", enabled=False)
        self._undo_btn = QtWidgets.QPushButton("Undo")

        self._erase_chk = QtWidgets.QCheckBox("Erase")
        self._preview_chk = QtWidgets.QCheckBox("Preview Output", enabled=False)
        self._show_tiles_chk = QtWidgets.QCheckBox("Show Tiles", checked=True)
        self._brush_slider = QtWidgets.QSlider(
            QtCore.Qt.Horizontal,
            minimum=1,
            maximum=200,
            value=24,
        )

        self._tile_spin = QtWidgets.QSpinBox(
            minimum=256,
            maximum=2048,
            singleStep=64,
            value=self._settings.tile_size,
        )

        self._overlap_spin = QtWidgets.QSpinBox(
            minimum=0,
            maximum=512,
            singleStep=8,
            value=self._settings.overlap,
        )

        self._status = QtWidgets.QLabel("Ready")
        self._image_size_label = QtWidgets.QLabel("Image Size: -")

        # Add Widgets to Layouts
        # ----------------------
        form = QtWidgets.QFormLayout()
        form.addRow("Brush Size", self._brush_slider)
        form.addRow("", self._erase_chk)
        form.addRow("", self._preview_chk)
        form.addRow("", self._show_tiles_chk)
        form.addRow("Tile Size", self._tile_spin)
        form.addRow("Overlap", self._overlap_spin)

        btn_row = QtWidgets.QHBoxLayout()
        btn_row.addWidget(self._load_image_btn)
        btn_row.addWidget(self._load_model_btn)
        btn_row.addWidget(self._release_model_btn)
        btn_row.addWidget(self._undo_btn)
        btn_row.addStretch(1)
        btn_row.addWidget(self._run_btn)
        btn_row.addWidget(self._save_btn)

        left = QtWidgets.QVBoxLayout()
        left.addLayout(btn_row)
        left.addWidget(self._viewport, 1)
        left.addWidget(self._status)

        right = QtWidgets.QVBoxLayout()
        right.addLayout(form)
        right.addWidget(self._image_size_label)
        right.addStretch(1)

        root = QtWidgets.QHBoxLayout(self)
        root.addLayout(left, 1)
        root.addLayout(right)

    def _init_signal_connections(self):
        """Initialize signal-slot connections."""
        self._load_image_btn.clicked.connect(self._show_load_image_dialog)
        self._load_model_btn.clicked.connect(self._show_load_model_dialog)
        self._release_model_btn.clicked.connect(self._release_model)
        self._run_btn.clicked.connect(self._on_run_clicked)
        self._save_btn.clicked.connect(self._on_save_clicked)
        self._undo_btn.clicked.connect(self._viewport.undo)

        self._erase_chk.toggled.connect(self._viewport.set_erase_mode)
        self._brush_slider.valueChanged.connect(self._viewport.set_brush_radius)
        self._preview_chk.toggled.connect(self._update_preview_display)
        self._show_tiles_chk.toggled.connect(self._viewport.set_show_tiles)

        self._tile_spin.valueChanged.connect(self._set_tile_settings)
        self._overlap_spin.valueChanged.connect(self._set_tile_settings)

        self._viewport.image_changed.connect(self._update_run_enabled_state)
        self._viewport.image_changed.connect(self._update_image_size_label)
        self._viewport.mask_changed.connect(self._update_run_enabled_state)
        # self._update_image_size_label()

    # Slots
    # -----
    def _show_load_image_dialog(self):
        """Load an image file."""
        path, _ = QtWidgets.QFileDialog.getOpenFileName(
            self,
            "Open Image",
            "",
            "Images (*.png *.jpg *.jpeg *.bmp *.tif *.tiff *.exr);;All Files (*)",
        )
        if not path:
            return

        # Note: OpenCV may not read EXR depending on build; if it fails, show message.
        img_bgr = cv2.imread(path, cv2.IMREAD_COLOR)
        if img_bgr is None:
            QtWidgets.QMessageBox.warning(self, "Load Failed", f"Could not read image:\n{path}")
            return

        self._viewport.set_image_bgr(img_bgr)
        self._orig_bgr = img_bgr.copy()
        self._last_output_bgr = None
        self._set_preview_checked(False)
        self._preview_chk.setEnabled(False)
        self._save_btn.setEnabled(False)
        self._status.setText(f"Loaded image: {path}")

    def _show_load_model_dialog(self):
        """Load an ONNX model file."""
        if self._worker is not None:
            QtWidgets.QMessageBox.information(
                self,
                "Busy",
                "Wait for the current inpaint to finish before loading a model.",
            )
            return

        path, _ = QtWidgets.QFileDialog.getOpenFileName(
            self,
            "Open Model (.onnx)",
            "",
            "ONNX (*.onnx);;All Files (*)",
        )
        if not path:
            return

        try:
            sess = _create_ort_session(path, providers=["CUDAExecutionProvider", "CPUExecutionProvider"])

            input_names = _get_input_names(sess)
        except Exception as exc:
            QtWidgets.QMessageBox.critical(
                self,
                "Load Failed",
                f"Could not load model:\n{path}\n\n{exc}",
            )
            return

        self._model_path = path
        self._ort_session = sess
        self._ort_input_names = input_names
        self._status.setText(f"Loaded model: {path} (cached)")
        self._update_run_enabled_state()

    def _release_model(self):
        """Release the cached ONNX session."""
        if self._worker is not None:
            return
        if self._ort_session is None:
            return
        self._clear_model_session()
        self._status.setText("Model released")
        self._update_run_enabled_state()

    def _set_tile_settings(self):
        """Update tiling settings."""
        tile_size = self._tile_spin.value()
        overlap = self._overlap_spin.value()

        # Clamp overlap to keep stride valid
        max_overlap = (tile_size // 2) - 1
        if overlap > max_overlap:
            overlap = max_overlap
            self._overlap_spin.blockSignals(True)
            self._overlap_spin.setValue(overlap)
            self._overlap_spin.blockSignals(False)

        self._settings = LamaTileSettings(
            tile_size=tile_size,
            overlap=overlap,
            mask_threshold=self._settings.mask_threshold,
            dilate_for_seams=self._settings.dilate_for_seams,
            context_kernel_tiles=self._settings.context_kernel_tiles,
            safety_unmask_border=self._settings.safety_unmask_border,
            use_global_pass=self._settings.use_global_pass,
            global_max_side=self._settings.global_max_side,
        )
        self._viewport.set_tile_settings(self._settings)

    def _set_preview_checked(self, checked: bool):
        """Update preview toggle without firing signals."""
        self._preview_chk.blockSignals(True)
        self._preview_chk.setChecked(checked)
        self._preview_chk.blockSignals(False)

    def _update_preview_display(self):
        """Show either the original or inpainted image."""
        if self._orig_bgr is None or self._last_output_bgr is None:
            return
        if self._preview_chk.isChecked():
            self._viewport.set_display_image_bgr(self._last_output_bgr)
        else:
            self._viewport.set_display_image_bgr(self._orig_bgr)

    def _clear_model_session(self):
        """Drop cached ONNX session and free resources."""
        self._ort_session = None
        self._ort_input_names = None
        self._model_path = ""
        gc.collect()

    def _update_run_enabled_state(self):
        """Enable run button when ready."""
        has_model = self._ort_session is not None
        has_image = self._viewport.get_image_bgr() is not None
        has_output = (self._last_output_bgr is not None) and (self._orig_bgr is not None)
        busy = self._worker is not None
        self._run_btn.setEnabled(has_model and has_image and (not busy))
        self._release_model_btn.setEnabled(has_model and (not busy))
        self._load_model_btn.setEnabled(not busy)
        self._preview_chk.setEnabled(has_output and (not busy))

    def _update_image_size_label(self):
        """Refresh the image size label."""
        img_bgr = self._viewport.get_image_bgr()
        if img_bgr is None:
            self._image_size_label.setText("Image Size: -")
            return
        h, w = img_bgr.shape[:2]
        self._image_size_label.setText(f"Image Size: {w} x {h}")

    def _on_run_clicked(self):
        """Run inpainting in a worker thread."""
        if self._worker is not None:
            return

        img_bgr = self._viewport.get_image_bgr()
        mask_gray = self._viewport.get_mask_gray()

        if img_bgr is None or mask_gray is None:
            return
        if self._ort_session is None:
            return

        self._orig_bgr = img_bgr.copy()
        self._status.setText("Inpainting…")
        self._run_btn.setEnabled(False)
        self._save_btn.setEnabled(False)

        self._worker = LamaInpaintWorker(
            parent=self,
            img_bgr=img_bgr,
            mask_gray=mask_gray,
            settings=self._settings,
            session=self._ort_session,
            input_names=self._ort_input_names,
        )
        self._worker.finished_image.connect(self._on_worker_finished)
        self._worker.failed.connect(self._on_worker_failed)
        self._worker.finished.connect(self._on_worker_done)
        self._update_run_enabled_state()
        self._worker.start()

    def _on_worker_finished(self, out_bgr: object):
        """Handle successful output."""
        zoom, pan = self._viewport.get_view_state()
        self._last_output_bgr = out_bgr
        self._set_preview_checked(True)
        self._preview_chk.setEnabled(True)
        # Show result as new image, reset mask
        self._viewport.set_image_bgr(out_bgr)
        self._viewport.set_view_state(zoom, pan)
        self._save_btn.setEnabled(True)
        self._status.setText("Done")

    def _on_worker_failed(self, message: str):
        """Handle failure."""
        QtWidgets.QMessageBox.critical(self, "Inpaint Failed", message)
        self._status.setText("Failed")

    def _on_worker_done(self):
        """Cleanup worker state."""
        self._worker = None
        self._update_run_enabled_state()

    def _on_save_clicked(self):
        """Save the latest output."""
        if self._last_output_bgr is None:
            return

        path, _ = QtWidgets.QFileDialog.getSaveFileName(
            self,
            "Save Output",
            "",
            "png (*.png);;JPEG (*.jpg *.jpeg);;TIFF (*.tif *.tiff);;All Files (*)",
        )
        if not path:
            return
        path = f'{path}.png' if not path.lower().endswith(('.png', '.jpg', '.jpeg', '.tif', '.tiff')) else path
        ok = cv2.imwrite(path, self._last_output_bgr)
        if not ok:
            QtWidgets.QMessageBox.warning(self, "Save Failed", f"Could not save:\n{path}")
            return

        self._status.setText(f"Saved: {path}")


# Main Function
# -------------
def main():
    """Create the application and show the widget."""
    import sys

    app = QtWidgets.QApplication(sys.argv)
    w = LamaMaskInpaintWidget()
    w.resize(1200, 800)
    w.show()
    sys.exit(app.exec_())


if __name__ == "__main__":
    main()
