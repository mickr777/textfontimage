import cv2
import numpy as np
from PIL import Image
from invokeai.invocation_api import (
    BaseInvocation,
    InvocationContext,
    invocation,
    InputField,
    ImageField,
    ImageOutput,
)

@invocation(
    "cv_extrude_depth",
    title="Extrude Depth from Mask",
    tags=["cv", "mask", "depth"],
    category="controlnet",
    version="1.4.1",
    use_cache=False,
)
class ExtrudeDepthInvocation(BaseInvocation):
    """Node for creating fake depth by "extruding" a mask using OpenCV."""

    mask: ImageField = InputField(
        default="None", description="The mask from which to extrude"
    )
    direction: float = InputField(
        default=45.0, description="Extrude direction in degrees"
    )
    shift: int = InputField(
        default=40, description="Number of pixels to shift bottom from top"
    )
    close_point: int = InputField(
        default=180, ge=0, le=255, description="Closest extrusion depth"
    )
    far_point: int = InputField(
        default=80, ge=0, le=255, description="Farthest extrusion depth"
    )
    bg_threshold: int = InputField(
        default=10, ge=0, lt=255, description="Background threshold"
    )
    bg_depth: int = InputField(
        default=0, ge=0, lt=255, description="Target background depth"
    )
    steps: int = InputField(
        default=100, description="Number of steps in extrusion gradient"
    )
    invert: bool = InputField(
        default=False, description="Inverts mask image before extruding"
    )

    def extrude(self, cv_mask: np.ndarray) -> np.ndarray:
        direction_rad = self.direction * np.pi / 180
        alpha = np.cos(direction_rad)
        beta = np.sin(direction_rad)
        canvas = np.zeros_like(cv_mask, dtype=np.float32)
        slope = (self.close_point - self.far_point) / 255
        offset = self.far_point

        for frac in np.linspace(0, 1, self.steps):
            shift = (1 - frac) * self.shift
            x_shift = np.round(alpha * shift).astype(int)
            y_shift = np.round(beta * shift).astype(int)
            canv_x = np.max((x_shift, 0))
            canv_y = np.max((y_shift, 0))
            mask_x = np.max((-x_shift, 0))
            mask_y = np.max((-y_shift, 0))
            mask_area = cv_mask[mask_x : -canv_x - 1, mask_y : -canv_y - 1]
            canvas_area = canvas[canv_x : -mask_x - 1, canv_y : -mask_y - 1]
            values = offset + slope * frac * mask_area
            sub_mask = values > canvas_area
            sub_mask &= self.bg_threshold < mask_area
            canvas_area[sub_mask] = values[sub_mask]
        canvas[canvas < self.bg_threshold] = self.bg_depth
        return canvas.astype(np.uint8)

    def invoke(self, context: InvocationContext) -> ImageOutput:
        mask = context.images.get_pil(self.mask.image_name)

        cv_mask = np.array(mask)
        if cv_mask.ndim == 3 and cv_mask.shape[-1] == 4:
            cv_mask = cv_mask[:, :, -1]
        elif cv_mask.ndim == 3:
            cv_mask = cv2.cvtColor(cv_mask, cv2.COLOR_RGB2GRAY)

        if self.invert:
            cv_mask = cv2.bitwise_not(cv_mask)

        cv_extruded = self.extrude(cv_mask)

        pil_extruded = Image.fromarray(cv_extruded)

        mask_dto = context.images.save(image=pil_extruded)
        return ImageOutput.build(mask_dto)
