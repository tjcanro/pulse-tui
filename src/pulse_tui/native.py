"""Load our optional CPU rasterizer and describe its C function signature."""
from __future__ import annotations

import ctypes
from pathlib import Path

import numpy as np


class NativeRasterizer:
    """Optional compiled hot loops; all audio, camera and mesh controls stay in Python."""
    def __init__(self):
        self.library = ctypes.CDLL(str(Path(__file__).parent / "_native" / "wireframe_native.so"))
        self.library.pulse_renderer_abi.restype = ctypes.c_int
        if self.library.pulse_renderer_abi() != 1:
            raise RuntimeError("Unsupported native renderer ABI")
        # Validate array layout before passing pointers to the C function.
        vector = np.ctypeslib.ndpointer(dtype=np.float64, ndim=1, flags="C_CONTIGUOUS")
        indices = np.ctypeslib.ndpointer(dtype=np.int64, ndim=2, flags="C_CONTIGUOUS")
        self.render = self.library.pulse_rasterize
        self.render.argtypes = [vector, vector, vector, vector, indices, ctypes.c_size_t,
                                indices, ctypes.c_size_t, ctypes.c_int, ctypes.c_int, vector, vector]
        # C fills the caller's depth/dot buffers in place; it returns no object.
        self.render.restype = None
